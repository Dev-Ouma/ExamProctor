"""Capture endpoints: presigned uploads, upload confirmation, event batches, heartbeat, finish."""

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .api import SessionDep, SettingsDep, StoreDep, error
from .live_store import paused
from .objectstore import ObjectStore
from .store import Event, Session, Upload

router = APIRouter(prefix="/v1/sessions")

EVENT_TYPES = {
    "focus",
    "blur",
    "visibility_hidden",
    "visibility_visible",
    "fullscreen_exit",
    "copy",
    "cut",
    "paste",
    "contextmenu",
    "online",
    "offline",
    "resize",
    "question_shown",
    "nav_click",
    "input_summary",
    "stream_ended",
    "capture_error",
    "connectivity_gap",
    "shell_loaded",
    "attempt_left",
    "display_info",
    "terminated_by_invigilator",
}
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def get_objects(request: Request) -> ObjectStore:
    return request.app.state.objects


ObjectsDep = Annotated[ObjectStore, Depends(get_objects)]


def require_capturing(session: Session) -> None:
    # A terminated session still accepts what the browser had queued, so the evidence is complete.
    if session.status not in ("ready", "finished", "terminated"):
        raise error(409, "session_not_ready", "pre-checks have not passed")
    if session.purged_at is not None:
        raise error(410, "session_purged", "evidence for this session was deleted")


def object_key(env: str, session: Session, kind: str, seq: int) -> str:
    return f"{env}/{session.quiz_id}/{session.id}/{kind}/{seq:06d}.jpg"


class PresignRequest(BaseModel):
    kind: Literal["camera", "screen", "reference", "room_scan"]
    bytes: int = Field(gt=0)
    sha256: str
    seq: int = Field(ge=0, le=1_000_000)
    captured_at: datetime


@router.post("/{session_id}/uploads/presign")
async def presign(
    body: PresignRequest,
    session: SessionDep,
    store: StoreDep,
    objects: ObjectsDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    require_capturing(session)
    if body.kind in ("camera", "screen") and not session.policy.get(body.kind):
        raise error(403, "kind_not_in_policy", f"{body.kind} capture is not enabled for this quiz")
    if body.bytes > settings.max_image_bytes:
        raise error(413, "too_large", f"images must be at most {settings.max_image_bytes} bytes")
    if not SHA256.match(body.sha256):
        raise error(400, "bad_sha256", "sha256 must be 64 lowercase hex characters")
    key = object_key(settings.env, session, body.kind, body.seq)
    upload = await store.put_upload(
        Upload(
            session_id=session.id,
            kind=body.kind,
            seq=body.seq,
            key=key,
            sha256=body.sha256,
            bytes=body.bytes,
            captured_at=body.captured_at,
        )
    )
    if upload.sha256 != body.sha256:
        raise error(409, "seq_conflict", "this sequence number was used for different content")
    if upload.status == "verified":
        return {"key": key, "already_uploaded": True}
    if session.started_at is None:
        session.started_at = datetime.now(UTC)
        await store.save_session(session)
    url = objects.presign_put(key, "image/jpeg", body.bytes, settings.upload_url_ttl_s)
    return {"key": key, "url": url, "headers": {"Content-Type": "image/jpeg"}}


class CompleteRequest(BaseModel):
    key: str


@router.post("/{session_id}/uploads/complete")
async def complete(body: CompleteRequest, session: SessionDep, store: StoreDep, objects: ObjectsDep) -> dict[str, Any]:
    require_capturing(session)
    upload = await store.get_upload(session.id, body.key)
    if upload is None:
        raise error(404, "unknown_upload", "presign this upload first")
    if upload.status == "verified":
        return {"key": upload.key, "status": "verified"}
    found = await objects.sha256_of(upload.key)
    if found is None:
        raise error(409, "not_uploaded", "object not found in the store; retry the PUT")
    digest, size = found
    upload.status = "verified" if (digest == upload.sha256 and size == upload.bytes) else "corrupt"
    upload.verified_at = datetime.now(UTC)
    await store.save_upload(upload)
    if upload.status == "corrupt":
        raise error(422, "checksum_mismatch", "stored object does not match its sha256; re-upload")
    return {"key": upload.key, "status": "verified"}


class EventIn(BaseModel):
    type: str
    ts: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: list[EventIn] = Field(max_length=500)


@router.post("/{session_id}/events")
async def events(body: EventBatch, session: SessionDep, store: StoreDep) -> dict[str, Any]:
    require_capturing(session)
    accepted = [e for e in body.events if e.type in EVENT_TYPES]
    await store.add_events(
        [Event(session_id=session.id, type=e.type, client_ts=e.ts, payload=e.data) for e in accepted]
    )
    return {"accepted": len(accepted), "rejected": len(body.events) - len(accepted)}


class Heartbeat(BaseModel):
    queued_uploads: int = 0
    camera_live: bool | None = None
    screen_live: bool | None = None
    online_since: datetime | None = None


@router.post("/{session_id}/heartbeat")
async def heartbeat(body: Heartbeat, session: SessionDep, store: StoreDep, request: Request) -> dict[str, Any]:
    """Liveness for the live wall; the reply carries invigilator notices (warn, message, pause...)."""
    require_capturing(session)
    now = datetime.now(UTC)
    session.last_seen_at = now
    session.client_health = body.model_dump(mode="json")
    await store.save_session(session)
    actions = request.app.state.actions
    notices = [a.notice() for a in await actions.take_undelivered(session.id)]
    await request.app.state.bus.publish(session.quiz_id, {"type": "heartbeat", "session_id": session.id})
    return {
        "server_time": now.isoformat(),
        "status": session.status,
        "paused": paused(await actions.for_session(session.id)),
        "notices": notices,
    }


@router.post("/{session_id}/notices/{action_id}/ack")
async def ack_notice(action_id: int, session: SessionDep, request: Request) -> dict[str, Any]:
    if not await request.app.state.actions.ack(session.id, action_id):
        raise error(404, "not_found", "no such notice for this session")
    return {"acked": action_id}


@router.post("/{session_id}/finish")
async def finish(session: SessionDep, store: StoreDep, request: Request) -> dict[str, Any]:
    require_capturing(session)
    if session.ended_at is None:
        session.ended_at = datetime.now(UTC)
        session.status = "finished"
        await store.save_session(session)
        await request.app.state.bus.publish(session.quiz_id, {"type": "finished", "session_id": session.id})
    return {"status": session.status, "uploads": await store.count_uploads(session.id)}
