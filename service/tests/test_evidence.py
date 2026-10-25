import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from test_sessions import DESKTOP_OK, consent, start

from examproctor_service import retention

JPEG = b"\xff\xd8\xff" + b"synthetic frame" * 100


@pytest.fixture
def ready_session(client, settings):
    session, headers = start(client, settings)
    consent(client, session, headers, settings)
    response = client.post(f"/v1/sessions/{session['session_id']}/precheck", json=DESKTOP_OK, headers=headers)
    assert response.json()["status"] == "ready"
    return session["session_id"], headers


def presign(client, sid, headers, data=JPEG, seq=0, kind="camera"):
    return client.post(
        f"/v1/sessions/{sid}/uploads/presign",
        json={
            "kind": kind,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "seq": seq,
            "captured_at": datetime.now(UTC).isoformat(),
        },
        headers=headers,
    )


def test_upload_round_trip_is_verified_by_sha256(client, ready_session, objects):
    sid, headers = ready_session
    body = presign(client, sid, headers).json()
    assert body["key"].endswith(f"/{sid}/camera/000000.jpg")
    objects.put(body["key"], JPEG)

    done = client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": body["key"]}, headers=headers)

    assert done.json() == {"key": body["key"], "status": "verified"}


def test_tampered_object_is_rejected(client, ready_session, objects):
    sid, headers = ready_session
    key = presign(client, sid, headers).json()["key"]
    objects.put(key, JPEG + b"x")

    done = client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": key}, headers=headers)

    assert done.status_code == 422
    assert done.json()["error"]["code"] == "checksum_mismatch"


def test_duplicate_presign_is_idempotent_and_conflicting_content_refused(client, ready_session, objects):
    sid, headers = ready_session
    key = presign(client, sid, headers).json()["key"]
    objects.put(key, JPEG)
    client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": key}, headers=headers)

    again = presign(client, sid, headers).json()
    other = presign(client, sid, headers, data=JPEG + b"other")

    assert again == {"key": key, "already_uploaded": True}
    assert other.status_code == 409


def test_uploads_need_ready_session_policy_and_size_limit(client, settings):
    session, headers = start(client, settings, policy={"camera": True, "screen": False, "strict": False})
    sid = session["session_id"]
    assert presign(client, sid, headers).status_code == 409  # not ready yet

    consent(client, session, headers, settings)
    client.post(f"/v1/sessions/{sid}/precheck", json={"camera": "ok"}, headers=headers)
    assert presign(client, sid, headers, kind="screen").status_code == 403
    assert presign(client, sid, headers, data=b"x" * (settings.max_image_bytes + 1)).status_code == 413


def test_events_are_filtered_to_known_types(client, ready_session, store):
    sid, headers = ready_session
    now = datetime.now(UTC).isoformat()

    response = client.post(
        f"/v1/sessions/{sid}/events",
        json={"events": [{"type": "blur", "ts": now}, {"type": "keystroke_text", "ts": now}]},
        headers=headers,
    )

    assert response.json() == {"accepted": 1, "rejected": 1}
    assert [e.type for e in store.events] == ["blur"]


def test_heartbeat_and_finish(client, ready_session, objects):
    sid, headers = ready_session
    key = presign(client, sid, headers).json()["key"]
    objects.put(key, JPEG)
    client.post(f"/v1/sessions/{sid}/uploads/complete", json={"key": key}, headers=headers)

    beat = client.post(f"/v1/sessions/{sid}/heartbeat", json={"queued_uploads": 2}, headers=headers)
    finished = client.post(f"/v1/sessions/{sid}/finish", headers=headers)

    assert beat.json()["status"] == "ready"
    assert finished.json() == {"status": "finished", "uploads": {"camera": 1}}


def test_retention_deletes_expired_evidence_but_respects_legal_hold(client, ready_session, store, objects, settings):
    sid, headers = ready_session
    key = presign(client, sid, headers).json()["key"]
    objects.put(key, JPEG)
    client.post(f"/v1/sessions/{sid}/finish", headers=headers)
    held, held_headers = start(client, settings)
    store.sessions[held["session_id"]].ended_at = datetime.now(UTC) - timedelta(days=400)
    store.sessions[held["session_id"]].legal_hold = True
    objects.put(f"dev/3/{held['session_id']}/camera/000000.jpg", JPEG)

    later = datetime.now(UTC) + timedelta(days=settings.retention_days + 1)
    purged = asyncio.run(retention.run_once(store, objects, settings, later))

    assert purged == 1
    assert key not in objects.objects
    assert f"dev/3/{held['session_id']}/camera/000000.jpg" in objects.objects
    assert store.sessions[sid].purged_at == later
    assert presign(client, sid, headers, seq=5).status_code == 410
