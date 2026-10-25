"""Live invigilation (spec 5.4 Live wall, M6): active sessions for one quiz, a WebSocket that says
when to refresh, and invigilator actions with a required reason.

Every action is stored, audited and shown to the student; terminate also closes the Moodle attempt
through a signed webhook. AI flags only inform the invigilator; a person takes every action.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, model_validator

from .api import SettingsDep, StoreDep, error
from .config import get_settings
from .live_store import Action, ActionStore, Bus, paused
from .review import ObjectsDep, ReviewsDep, SessionDep, StaffDep, client_ip, in_scope
from .tokens import TokenError, decode_staff_token

router = APIRouter(prefix="/v1/live")
RECENTLY_ENDED = timedelta(minutes=10)
STALE_AFTER_S = 30
PING_S = 20


def get_actions(request: Request) -> ActionStore:
    return request.app.state.actions


def get_bus(request: Request) -> Bus:
    return request.app.state.bus


ActionsDep = Annotated[ActionStore, Depends(get_actions)]
BusDep = Annotated[Bus, Depends(get_bus)]


@router.get("/quizzes/{quiz_id}/sessions")
async def live_sessions(
    quiz_id: int,
    staff: StaffDep,
    reviews: ReviewsDep,
    actions: ActionsDep,
    objects: ObjectsDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    staff.require("invigilate")
    in_scope(staff, quiz_id)
    now = datetime.now(UTC)
    # One query for the sessions and one for their actions, however many students are sitting.
    rows = await reviews.live_view(quiz_id, now - RECENTLY_ENDED)
    history = await actions.for_sessions([r.row.session.id for r in rows])
    out = []
    for live in rows:
        s = live.row.session
        acts = history.get(s.id, [])
        camera = live.camera
        out.append(
            live.row.to_json()
            | {
                "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
                "online": bool(s.last_seen_at and (now - s.last_seen_at).total_seconds() < STALE_AFTER_S),
                "client_health": s.client_health,
                "paused": paused(acts),
                "terminated": s.status == "terminated",
                "latest_camera": (
                    {
                        "url": objects.presign_get(camera["key"], settings.evidence_view_ttl_s),
                        "captured_at": camera["captured_at"],
                        "faces": camera["faces"],
                    }
                    if camera and not s.purged_at
                    else None
                ),
                "recent_flags": live.recent_flags,
                "actions": [a.to_json() for a in acts[-5:]],
            }
        )
    order = {"high": 0, "review": 1, "clear": 2, None: 3}
    out.sort(
        key=lambda r: (not r["online"] and not r["ended_at"], order.get(r["band"], 3), r["integrity_score"] or 101)
    )
    return {"sessions": out, "server_time": now.isoformat(), "stale_after_s": STALE_AFTER_S}


class ActionRequest(BaseModel):
    type: Literal["warn", "message", "pause", "resume", "terminate"]
    reason: str = Field(min_length=3, max_length=1000)
    message: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def message_for_messages(self) -> "ActionRequest":
        if self.type == "message" and not self.message.strip():
            raise ValueError("a message needs text for the student")
        return self


@router.post("/sessions/{session_id}/actions")
async def act(
    body: ActionRequest,
    session: SessionDep,
    staff: StaffDep,
    actions: ActionsDep,
    reviews: ReviewsDep,
    store: StoreDep,
    bus: BusDep,
    request: Request,
) -> dict[str, Any]:
    staff.require("invigilate")
    if session.ended_at is not None:
        raise error(409, "session_ended", "this session has already ended")
    history = await actions.for_session(session.id)
    if body.type == "resume" and not paused(history):
        raise error(409, "not_paused", "the session is not paused")
    if body.type == "pause" and paused(history):
        raise error(409, "already_paused", "the session is already paused")
    action = await actions.add(
        Action(
            session_id=session.id,
            type=body.type,
            reason=body.reason.strip(),
            message=body.message.strip(),
            actor_id=staff.user_id,
            actor_name=staff.name,
        )
    )
    await reviews.audit(staff.actor, f"live_{body.type}", session.id, client_ip(request), {"reason": action.reason})
    if body.type == "terminate":
        session.status = "terminated"
        session.ended_at = datetime.now(UTC)
        await store.save_session(session)
        await store.enqueue(
            "session.terminated",
            {
                "session_id": session.id,
                "moodle_user_id": session.moodle_user_id,
                "quiz_id": session.quiz_id,
                "reason": action.reason,
                "actor_id": staff.user_id,
            },
        )
    await bus.publish(session.quiz_id, {"type": "action", "session_id": session.id, "action": body.type})
    return action.to_json()


@router.websocket("/quizzes/{quiz_id}/stream")
async def stream(websocket: WebSocket, quiz_id: int) -> None:
    """Tells the live wall when to refresh. Browsers cannot set headers on a WebSocket, so the
    staff token comes as the first message, never in the URL (URLs end up in logs)."""
    await websocket.accept()
    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        claims = decode_staff_token(token, get_settings())
    except (TimeoutError, TokenError, WebSocketDisconnect):
        with contextlib.suppress(Exception):
            await websocket.close(code=4401)
        return
    if "invigilate" not in claims["caps"] or int(claims["quiz_id"]) != quiz_id:
        await websocket.close(code=4403)
        return
    expires = claims["exp"]
    bus: Bus = websocket.app.state.bus
    events = bus.subscribe(quiz_id).__aiter__()
    await websocket.send_json({"type": "hello"})
    try:
        while datetime.now(UTC).timestamp() < expires:
            try:
                event = await asyncio.wait_for(events.__anext__(), timeout=PING_S)
            except TimeoutError:
                event = {"type": "ping"}
            await websocket.send_json(event)
        await websocket.close(code=4401)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            await events.aclose()
