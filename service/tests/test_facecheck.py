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
