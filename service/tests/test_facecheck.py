import cv2
import numpy as np
from test_faces import needs_models
from test_sessions import consent, start


def post(client, sid, headers, data: bytes):
    return client.post(f"/v1/sessions/{sid}/facecheck", content=data, headers={**headers, "Content-Type": "image/jpeg"})


def test_needs_consent_and_a_frame(client, settings):
    session, headers = start(client, settings)
    sid = session["session_id"]
    assert post(client, sid, headers, b"x").status_code == 409
    consent(client, session, headers, settings)
    assert post(client, sid, headers, b"").status_code == 413
    assert post(client, sid, headers, b"x" * 300_001).status_code == 413


def test_needs_the_session_token(client, settings):
    session, _ = start(client, settings)
    assert client.post(f"/v1/sessions/{session['session_id']}/facecheck", content=b"x").status_code == 401


@needs_models
def test_dark_frame_is_reported_with_a_reason(client, settings):
    session, headers = start(client, settings)
    consent(client, session, headers, settings)
    dark = cv2.imencode(".jpg", np.zeros((480, 640, 3), np.uint8))[1].tobytes()
    body = post(client, session["session_id"], headers, dark).json()
    assert body["ok"] is False and body["reason"] == "too_dark" and body["faces"] == 0


class ScriptedEngine:
    """Returns the queued frame results in order, whatever bytes arrive."""

    def __init__(self, frames):
        self.frames = list(frames)

    def analyse(self, jpeg, embed=True):
        return self.frames.pop(0)


def identity_session(client, settings, monkeypatch, frames, reference=None):
    from test_facegate import ME

    scripted = ScriptedEngine(frames)
    monkeypatch.setattr("examproctor_service.facecheck.engine", lambda: scripted)
    if reference is not False:
        client.app.state.refs.rows[42] = {"status": "valid", "embedding": reference or ME}
    session, headers = start(client, settings, policy={"camera": True, "screen": False, "identity": True})
    consent(client, session, headers, settings)
    return session["session_id"], headers


def passing_frames(challenge):
    from test_facegate import frame, turned

    return [frame(), frame(), frame(), turned(challenge), frame()]


def precheck(client, sid, headers):
    return client.post(f"/v1/sessions/{sid}/precheck", json={"camera": "ok"}, headers=headers).json()


def test_identity_quiz_blocks_until_the_face_gate_passes(client, settings, monkeypatch, store):
    from test_facegate import frame

    sid, headers = identity_session(client, settings, monkeypatch, [frame(faces=0)])
    assert precheck(client, sid, headers)["reasons"] == ["face_check_not_passed"]
    assert post(client, sid, headers, b"jpeg").json()["reason"] == "no_face"  # picks the random challenge

    challenge = store.sessions[sid].face_check["challenge"]
    scripted = ScriptedEngine(passing_frames(challenge))
    monkeypatch.setattr("examproctor_service.facecheck.engine", lambda: scripted)
    bodies = [post(client, sid, headers, b"jpeg").json() for _ in range(5)]

    assert [b["next"] for b in bodies] == ["hold_still", "hold_still", f"turn_{challenge}", "look_back", "done"]
    assert bodies[-1]["ok"] is True and bodies[-1]["gated"] is True and bodies[-1]["reference"] == "institutional"
    assert precheck(client, sid, headers)["status"] == "ready"


def test_wrong_person_is_told_and_stays_blocked(client, settings, monkeypatch):
    from test_facegate import SOMEONE_ELSE, frame

    sid, headers = identity_session(client, settings, monkeypatch, [frame(embedding=SOMEONE_ELSE)])
    body = post(client, sid, headers, b"jpeg").json()

    assert body["ok"] is False and body["reason"] == "not_same_person"
    assert precheck(client, sid, headers)["status"] == "blocked"


def test_invigilator_override_unlocks_and_is_shown_on_the_wall(client, settings, monkeypatch):
    from test_facegate import SOMEONE_ELSE, frame
    from test_live import INVIGILATOR, act
    from test_review import staff

    sid, headers = identity_session(client, settings, monkeypatch, [frame(embedding=SOMEONE_ELSE)])
    post(client, sid, headers, b"jpeg")
    assert precheck(client, sid, headers)["status"] == "blocked"

    def wall_row():
        wall = client.get("/v1/live/quizzes/3/sessions", headers=staff(settings, caps=INVIGILATOR)).json()
        return next(s for s in wall["sessions"] if s["session_id"] == sid)

    assert wall_row()["face_check"] == {"passed": False, "override": False, "stage": "frontal", "similarity": 0.0}
    assert act(client, settings, sid, type="face_override", reason="ab").status_code == 422
    assert act(client, settings, sid, type="face_override", reason="ID card shown on camera").status_code == 200

    assert wall_row()["face_check"]["override"] is True
    assert precheck(client, sid, headers)["status"] == "ready"


def test_override_needs_an_identity_quiz(client, settings):
    from test_live import act

    session, _ = start(client, settings)
    assert act(client, settings, session["session_id"], type="face_override", reason="ID card").status_code == 409


def test_without_identity_policy_the_check_stays_advisory(client, settings, monkeypatch):
    from test_facegate import frame

    monkeypatch.setattr("examproctor_service.facecheck.engine", lambda: ScriptedEngine([frame()]))
    session, headers = start(client, settings, policy={"camera": True, "screen": False})
    consent(client, session, headers, settings)
    body = post(client, session["session_id"], headers, b"jpeg").json()

    assert body["ok"] is True and body["gated"] is False
    assert precheck(client, session["session_id"], headers)["status"] == "ready"
