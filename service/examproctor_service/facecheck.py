"""Live face check during the pre-check: the student sees at once whether the camera picture is good
enough for the exam (one clear face, enough light, close enough) and can fix it before starting.

When the quiz policy turns on the identity check, the check is a gate (see facegate): the face
must match the institutional photo and pass a head-turn liveness challenge before the pre-check
lets the attempt start. An invigilator can override a gate the student cannot pass, with a reason.
Without the identity policy the check stays advisory. Frames are analysed in memory and dropped.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, Request

from . import facegate
from .api import SessionDep, StoreDep, error
from .refphotos import engine, validate

router = APIRouter(prefix="/v1/sessions")
MAX_FRAME_BYTES = 300_000


def face_check_passed(session) -> bool:
    # Same rule as the pre-check decision in api.precheck.
    check = session.face_check or {}
    return check.get("stage") == "passed" or bool(check.get("override"))


@router.post("/{session_id}/facecheck")
async def facecheck(session: SessionDep, store: StoreDep, request: Request) -> dict[str, Any]:
    if session.consent_version is None:
        raise error(409, "consent_missing", "record consent before the face check")
    if session.ended_at is not None:
        raise error(409, "session_ended", "this session has ended")
    data = await request.body()
    if not data or len(data) > MAX_FRAME_BYTES:
        raise error(413, "too_large", f"send one JPEG frame of at most {MAX_FRAME_BYTES} bytes")
    gated = bool(session.policy.get("identity"))
    reference = None
    if gated:
        row = await request.app.state.refs.get(session.moodle_user_id)
        if row and row["status"] == "valid":
            reference = row["embedding"]
    result = await asyncio.to_thread(engine().analyse, data, reference is not None)
    if not gated:
        reason = validate(result)
        passed = reason is None
    elif face_check_passed(session):
        reason, passed = None, True
    else:
        session.face_check, reason = facegate.step(session.face_check, result, reference)
        await store.save_session(session)
        passed = face_check_passed(session)
    return {
        "ok": passed,
        "gated": gated,
        "reason": reason,
        "next": "done" if passed else facegate.instruction(session.face_check) if gated else "hold_still",
        "reference": "institutional" if reference is not None else "none",
        "faces": len(result.faces),
        "face_px": result.largest_face_px,
        "brightness": round(result.brightness, 1),
    }
