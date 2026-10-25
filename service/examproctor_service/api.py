"""Student/SDK session endpoints (spec section 7, M2 subset)."""

from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from .config import Settings, get_settings
from .precheck import PrecheckResults, evaluate
from .store import Session, Store
from .tokens import TokenError, decode_launch_token, decode_session_token, mint_session_token
from .webhooks import deliver

router = APIRouter(prefix="/v1/sessions")


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[Store, Depends(get_store)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def current_session(
    session_id: str,
    store: StoreDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Session:
    if not authorization or not authorization.startswith("Bearer "):
        raise error(401, "unauthorized", "session token required")
    try:
        claims = decode_session_token(authorization.removeprefix("Bearer "), settings)
    except TokenError as exc:
        raise error(401, "unauthorized", "invalid session token") from exc
    if claims["sid"] != session_id:
        raise error(403, "forbidden", "token does not match session")
    session = await store.get_session(session_id)
    if session is None:
        raise error(404, "not_found", "session not found")
    return session


SessionDep = Annotated[Session, Depends(current_session)]


class ExchangeRequest(BaseModel):
    launch_token: str


@router.post("/exchange")
async def exchange(body: ExchangeRequest, store: StoreDep, settings: SettingsDep) -> dict:
    try:
        claims = decode_launch_token(body.launch_token, settings)
    except TokenError as exc:
        raise error(401, "invalid_launch_token", str(exc)) from exc
    if not await store.use_jti(claims["jti"], datetime.fromtimestamp(claims["exp"], UTC)):
        raise error(409, "launch_token_used", "launch token already used")
    session = await store.create_session(claims)
    return {
        "session_id": session.id,
        "session_token": mint_session_token(session.id, session.moodle_user_id, settings),
        "policy": session.policy,
        "consent_text_version": settings.consent_text_version,
    }


class ConsentRequest(BaseModel):
    text_version: str
    accepted: bool


@router.post("/{session_id}/consent")
async def consent(
    body: ConsentRequest, session: SessionDep, store: StoreDep, settings: SettingsDep
):
    if not body.accepted:
        raise error(400, "consent_required", "consent must be accepted to continue")
    if body.text_version != settings.consent_text_version:
        raise error(409, "consent_version_mismatch", "consent text has changed; reload")
    session.consent_version = body.text_version
    if session.status == "created":
        session.status = "consented"
    await store.save_session(session)
    return {"status": session.status}


@router.post("/{session_id}/precheck")
async def precheck(
    body: PrecheckResults,
    session: SessionDep,
    store: StoreDep,
    settings: SettingsDep,
    http: HttpDep,
) -> dict[str, Any]:
    if session.consent_version is None:
        raise error(409, "consent_missing", "record consent before pre-checks")
    if session.status == "ready":
        return status_body(session)
    reasons = evaluate(session.policy, body)
    session.precheck = body.model_dump()
    session.status = "blocked" if reasons else "ready"
    await store.save_session(session)
    if not reasons:
        item = await store.enqueue(
            "session.ready",
            {
                "session_id": session.id,
                "moodle_user_id": session.moodle_user_id,
                "quiz_id": session.quiz_id,
                "cmid": session.cmid,
                "policy": session.policy,
                "context": {k: v for k, v in session.precheck.items() if v != "ok"},
            },
        )
        if await deliver(item, store, settings, http):
            session.ready_delivered = True
            await store.save_session(session)
    return status_body(session, reasons)


@router.get("/{session_id}")
async def get_status(session: SessionDep) -> dict[str, Any]:
    return status_body(session)


def status_body(session: Session, reasons: list[str] | None = None) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "status": session.status,
        "ready_delivered": session.ready_delivered,
        "reasons": reasons or [],
    }
