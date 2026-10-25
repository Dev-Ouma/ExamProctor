"""Institutional reference photos, pushed by Moodle (local_examproctor) with a signed request.

OUK collects student photos with consent at admission; Moodle holds the copy of record and pushes
each one here, where it is validated and turned into a face embedding for identity matching.
"""

import hashlib
import hmac
import time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request

from .analysis.faces import MIN_FACE_PIXELS, FaceEngine, FrameResult
from .api import SettingsDep, error
from .config import Settings
from .webhooks import sign

router = APIRouter(prefix="/v1/admin/reference-photos")
MAX_PHOTO_BYTES = 2_000_000
MODELS = Path(__file__).resolve().parents[1] / "models"


@lru_cache
def engine() -> FaceEngine:
    return FaceEngine(MODELS)


def validate(result: FrameResult) -> str | None:
    """Reason the photo cannot anchor identity, or None when it can."""
    if result.decode_error:
        return "unreadable"
    if result.brightness < 40:
        return "too_dark"
    if not result.faces:
        return "no_face"
    if len(result.faces) > 1:
        return "multiple_faces"
    if result.largest_face_px < MIN_FACE_PIXELS:
        return "face_too_small"
    if result.sharpness < 15:
        return "blurry"
    return None


async def signed_by_moodle(
    request: Request,
    settings: SettingsDep,
    x_examproctor_timestamp: Annotated[str, Header()] = "",
    x_examproctor_nonce: Annotated[str, Header()] = "",
    x_examproctor_signature: Annotated[str, Header()] = "",
) -> bytes:
    """HMAC over "<ts>.<nonce>.<METHOD> <path> <sha256(body)>" with the Moodle shared secret.

    Replays inside the 5-minute window are harmless: every call is idempotent for one user's photo."""
    body = await request.body()
    if not x_examproctor_timestamp.isdigit() or abs(time.time() - int(x_examproctor_timestamp)) > 300:
        raise error(401, "stale", "timestamp outside the accepted window")
    # The query string is signed too, so a captured request cannot be replayed with wider scope.
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    canonical = f"{request.method} {target} {hashlib.sha256(body).hexdigest()}"
    expected = sign(settings.moodle_shared_secret, x_examproctor_timestamp, x_examproctor_nonce, canonical)
    if not settings.moodle_shared_secret or not hmac.compare_digest(expected, x_examproctor_signature.lower()):
        raise error(401, "bad_signature", "request not signed by Moodle")
    return body


BodyDep = Annotated[bytes, Depends(signed_by_moodle)]


def photo_key(settings: Settings, user_id: int) -> str:
    return f"{settings.env}/reference/{user_id}.jpg"


@router.put("/{user_id}")
async def put_photo(user_id: int, body: BodyDep, request: Request, settings: SettingsDep) -> dict[str, Any]:
    if not body or len(body) > MAX_PHOTO_BYTES:
        raise error(413, "too_large", f"photo must be 1 byte to {MAX_PHOTO_BYTES} bytes")
    result = engine().analyse(body)
    reason = validate(result)
    status = "invalid" if reason else "valid"
    key = photo_key(settings, user_id)
    if status == "valid":
        await request.app.state.objects.put_bytes(key, body, "image/jpeg")
    await request.app.state.refs.upsert(user_id, key, status, reason, result.largest_face_px, result.embedding)
    return {"user_id": user_id, "status": status, "reason": reason, "face_px": result.largest_face_px}


@router.get("/{user_id}")
async def get_photo(user_id: int, _: BodyDep, request: Request) -> dict[str, Any]:
    row = await request.app.state.refs.get(user_id)
    if row is None:
        raise error(404, "not_found", "no reference photo for this user")
    return {k: row[k] for k in ("user_id", "status", "reason", "face_px", "updated_at")}


@router.delete("/{user_id}")
async def delete_photo(user_id: int, _: BodyDep, request: Request, settings: SettingsDep) -> dict[str, Any]:
    await request.app.state.objects.delete_prefix(photo_key(settings, user_id))
    deleted = await request.app.state.refs.delete(user_id)
    return {"user_id": user_id, "deleted": deleted}
