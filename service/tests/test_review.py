import time
from datetime import UTC, datetime

import jwt
import pytest
from test_evidence import JPEG, presign
from test_sessions import DESKTOP_OK, consent, start


def staff_token(settings, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": settings.moodle_issuer,
        "aud": settings.staff_audience,
        "sub": "900",
        "name": "Synthetic Reviewer",
        "course_id": 2,
        "quiz_id": 3,
        "caps": ["review", "decide", "exportevidence"],
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.moodle_shared_secret, algorithm="HS256")


def staff(settings, **overrides) -> dict[str, str]:
    return {"Authorization": f"Bearer {staff_token(settings, **overrides)}"}


@pytest.fixture
def reviews(client):
    return client.app.state.reviews


@pytest.fixture
def captured(client, settings, objects):
    """A ready session with one verified camera image."""
    session, headers = start(client, settings)
    sid = session["session_id"]
    consent(client, session, headers, settings)
    client.post(f"/v1/sessions/{sid}/precheck", json=DESKTOP_OK, headers=headers)
    body = presign(client, sid, headers).json()
    objects.put(body["key"], JPEG)
    client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": body["key"]}, headers=headers)
    return sid, body["key"]


def test_staff_token_required(client, captured):
    assert client.get("/v1/review/quizzes/3/sessions").status_code == 401
    assert client.get("/v1/review/quizzes/3/sessions", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_session_token_is_not_a_staff_token(client, settings, captured):
    session, headers = start(client, settings)
    assert client.get("/v1/review/quizzes/3/sessions", headers=headers).status_code == 401


def test_overlong_staff_token_refused(client, settings):
    now = int(time.time())
    headers = staff(settings, iat=now, exp=now + 3 * 86400)
    assert client.get("/v1/review/quizzes/3/sessions", headers=headers).status_code == 401


def test_unknown_capability_refused(client, settings):
    assert client.get("/v1/review/quizzes/3/sessions", headers=staff(settings, caps=["root"])).status_code == 401


def test_list_is_scoped_to_the_token_quiz(client, settings, captured):
    sid, _ = captured
    body = client.get("/v1/review/quizzes/3/sessions", headers=staff(settings)).json()
    assert [s["session_id"] for s in body["sessions"]] == [sid]
    assert body["sessions"][0]["uploads"] == {"camera": 1}
    assert client.get("/v1/review/quizzes/4/sessions", headers=staff(settings)).status_code == 403


def test_other_quiz_session_looks_missing(client, settings, captured):
    sid, _ = captured
    response = client.get(f"/v1/review/sessions/{sid}", headers=staff(settings, quiz_id=99))
    assert response.status_code == 404


def test_review_has_timeline_signed_links_and_no_embeddings(client, settings, captured, reviews):
    sid, key = captured
    reviews.analysis[(sid, key)] = {"faces": 1, "embedding": [0.1, 0.2]}
    reviews.flag_rows[sid] = [{"type": "NO_FACE", "severity": 2, "confidence": 0.9, "evidence": [key]}]
    reviews.scores[sid] = {"value": 88.0, "band": "clear", "reasons": [], "version": "v1"}
    body = client.get(f"/v1/review/sessions/{sid}", headers=staff(settings)).json()
    upload = body["uploads"][0]
    assert upload["url"].startswith("memory://evidence/") and "get" in upload["url"]
    assert upload["analysis"] == {"faces": 1}
    assert body["flags"][0]["type"] == "NO_FACE"
    assert body["score"]["band"] == "clear"
    assert reviews.audit_rows[-1]["action"] == "view_evidence"


def test_purged_session_has_no_links(client, settings, captured, store):
    sid, _ = captured
    store.sessions[sid].purged_at = datetime.now(UTC)
    body = client.get(f"/v1/review/sessions/{sid}", headers=staff(settings)).json()
    assert body["session"]["purged"] is True
    assert all(u["url"] is None for u in body["uploads"])


def test_decision_needs_notes_unless_no_issue(client, settings, captured):
    sid, _ = captured
    url = f"/v1/review/sessions/{sid}/decision"
    assert client.post(url, json={"decision": "concern"}, headers=staff(settings)).status_code == 422
    assert client.post(url, json={"decision": "no_issue"}, headers=staff(settings)).status_code == 200


def test_decision_is_recorded_audited_and_sent_to_moodle(client, settings, captured, reviews, store):
    sid, _ = captured
    response = client.post(
        f"/v1/review/sessions/{sid}/decision",
        json={"decision": "concern", "notes": "Second face at 10:02; ask the student."},
        headers=staff(settings),
    )
    assert response.status_code == 200
    assert response.json()["reviewer_name"] == "Synthetic Reviewer"
    listed = client.get("/v1/review/quizzes/3/sessions", headers=staff(settings)).json()["sessions"][0]
    assert listed["decision"] == "concern"
    assert reviews.audit_rows[-1]["action"] == "record_decision"
    assert store.outbox[-1].event == "decision.recorded"
    assert store.outbox[-1].payload["value"] == "concern"


def test_decision_needs_decide_capability(client, settings, captured):
    sid, _ = captured
    response = client.post(
        f"/v1/review/sessions/{sid}/decision", json={"decision": "no_issue"}, headers=staff(settings, caps=["review"])
    )
    assert response.status_code == 403


def test_appeal_flow(client, settings, captured):
    sid, _ = captured
    url = f"/v1/review/sessions/{sid}/appeal"
    assert client.post(url, json={"status": "opened", "notes": ""}, headers=staff(settings)).status_code == 422
    assert (
        client.post(
            url, json={"status": "opened", "notes": "Student says sibling walked in."}, headers=staff(settings)
        ).status_code
        == 200
    )
    assert (
        client.post(
            url, json={"status": "upheld", "notes": "Evidence consistent."}, headers=staff(settings)
        ).status_code
        == 200
    )
    body = client.get(f"/v1/review/sessions/{sid}", headers=staff(settings)).json()
    assert [r["value"] for r in body["reviews"]] == ["opened", "upheld"]
    listed = client.get("/v1/review/quizzes/3/sessions", headers=staff(settings)).json()["sessions"][0]
    assert listed["appeal"] == "upheld"


def test_summary_counts(client, settings, captured, reviews):
    sid, _ = captured
    reviews.flag_rows[sid] = [{"type": "FOCUS_LOSS"}, {"type": "FOCUS_LOSS"}, {"type": "NO_FACE"}]
    reviews.scores[sid] = {"value": 70.0, "band": "review", "reasons": [], "version": "v1"}
    body = client.get("/v1/review/quizzes/3/summary", headers=staff(settings)).json()
    assert body["sessions"] == 1
    assert body["bands"] == {"review": 1}
    assert body["flag_types"] == {"FOCUS_LOSS": 2, "NO_FACE": 1}
    assert body["average_score"] == 70.0


def test_csv_export_needs_capability_and_is_audited(client, settings, captured, reviews):
    sid, _ = captured
    denied = client.get("/v1/review/quizzes/3/export.csv", headers=staff(settings, caps=["review"]))
    assert denied.status_code == 403
    response = client.get("/v1/review/quizzes/3/export.csv", headers=staff(settings))
    assert response.status_code == 200
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("session_id,moodle_user_id")
    assert lines[1].startswith(sid)
    assert reviews.audit_rows[-1]["action"] == "export_csv"
