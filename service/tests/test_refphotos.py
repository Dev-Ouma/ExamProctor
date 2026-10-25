import hashlib
import secrets
import time

import cv2
import numpy as np
import pytest
from conftest import SECRET

from examproctor_service.webhooks import sign

MODELS_PRESENT = (
    __import__("pathlib")
    .Path(__file__)
    .resolve()
    .parents[1]
    .joinpath("models", "face_recognition_sface_2021dec.onnx")
    .exists()
)
needs_models = pytest.mark.skipif(not MODELS_PRESENT, reason="run `make models`")


def signed_headers(method: str, path: str, body: bytes, secret: str = SECRET, ts: int | None = None) -> dict:
    ts_s = str(int(time.time()) if ts is None else ts)
    nonce = secrets.token_hex(16)
    canonical = f"{method} {path} {hashlib.sha256(body).hexdigest()}"
    return {
        "X-ExamProctor-Timestamp": ts_s,
        "X-ExamProctor-Nonce": nonce,
        "X-ExamProctor-Signature": sign(secret, ts_s, nonce, canonical),
        "Content-Type": "image/jpeg",
    }


def noise_jpeg() -> bytes:
    rng = np.random.default_rng(3)
    return cv2.imencode(".jpg", rng.integers(60, 200, (480, 640, 3), dtype=np.uint8))[1].tobytes()


PATH = "/v1/admin/reference-photos/42"


def test_unsigned_or_badly_signed_requests_are_refused(client):
    body = b"x"
    assert client.put(PATH, content=body).status_code == 401
    wrong = signed_headers("PUT", PATH, body, secret="other-secret-" + "x" * 32)
    assert client.put(PATH, content=body, headers=wrong).status_code == 401
    stale = signed_headers("PUT", PATH, body, ts=int(time.time()) - 3600)
    assert client.put(PATH, content=body, headers=stale).json()["error"]["code"] == "stale"
    other_user = signed_headers("PUT", "/v1/admin/reference-photos/43", body)
    assert client.put(PATH, content=body, headers=other_user).status_code == 401


@needs_models
def test_photo_without_a_face_is_stored_as_invalid_and_not_kept(client, objects):
    body = noise_jpeg()

    response = client.put(PATH, content=body, headers=signed_headers("PUT", PATH, body))

    assert response.json() == {"user_id": 42, "status": "invalid", "reason": "no_face", "face_px": 0}
    assert objects.objects == {}
    status = client.get(PATH, headers=signed_headers("GET", PATH, b"")).json()
    assert (status["status"], status["reason"]) == ("invalid", "no_face")


@needs_models
def test_delete_then_get_is_not_found(client):
    body = noise_jpeg()
    client.put(PATH, content=body, headers=signed_headers("PUT", PATH, body))

    deleted = client.delete(PATH, headers=signed_headers("DELETE", PATH, b""))

    assert deleted.json() == {"user_id": 42, "deleted": True}
    assert client.get(PATH, headers=signed_headers("GET", PATH, b"")).status_code == 404
