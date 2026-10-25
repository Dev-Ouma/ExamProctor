"""Live face check during the pre-check: the student sees at once whether the camera picture is good
enough for the exam (one clear face, enough light, close enough) and can fix it before starting.

Advisory only: the result never blocks the attempt, so a detector mistake cannot lock a student
out. Nothing is stored; the frame is analysed in memory and dropped.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Request

from .api import SessionDep, error
from .refphotos import engine, validate

router = APIRouter(prefix="/v1/sessions")
MAX_FRAME_BYTES = 300_000


@router.post("/{session_id}/facecheck")
async def facecheck(session: SessionDep, request: Request) -> dict[str, Any]:
    if session.consent_version is None:
        raise error(409, "consent_missing", "record consent before the face check")
    if session.ended_at is not None:
        raise error(409, "session_ended", "this session has ended")
    data = await request.body()
    if not data or len(data) > MAX_FRAME_BYTES:
        raise error(413, "too_large", f"send one JPEG frame of at most {MAX_FRAME_BYTES} bytes")
    result = await asyncio.to_thread(engine().analyse, data, False)
    reason = validate(result)
    return {
        "ok": reason is None,
        "reason": reason,
        "faces": len(result.faces),
        "face_px": result.largest_face_px,
        "brightness": round(result.brightness, 1),
    }
