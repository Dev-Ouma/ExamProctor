"""Signed service -> Moodle webhooks, delivered through the outbox with retries."""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import Settings
from .store import OutboxItem, Store, backoff

log = logging.getLogger(__name__)


def sign(secret: str, timestamp: str, nonce: str, body: str) -> str:
    message = f"{timestamp}.{nonce}.{body}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def build_request(settings: Settings, event: str, payload: dict[str, Any]) -> tuple[str, dict]:
    body = json.dumps({"event": event, "data": payload}, separators=(",", ":"), sort_keys=True)
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    headers = {
        "Content-Type": "application/json",
        "X-ExamProctor-Timestamp": timestamp,
        "X-ExamProctor-Nonce": nonce,
        "X-ExamProctor-Signature": sign(settings.moodle_shared_secret, timestamp, nonce, body),
    }
    if settings.moodle_webhook_host:
        headers["Host"] = settings.moodle_webhook_host
    return body, headers


async def deliver(item: OutboxItem, store: Store, settings: Settings, client: httpx.AsyncClient):
    """Try one outbox item once. Returns True when Moodle accepted it."""
    body, headers = build_request(settings, item.event, item.payload)
    try:
        response = await client.post(settings.moodle_webhook_url, content=body, headers=headers)
        ok = response.status_code == 200
        if not ok:
            log.warning("webhook %s rejected: %s", item.id, response.status_code)
    except httpx.HTTPError as exc:
        log.warning("webhook %s failed: %s", item.id, type(exc).__name__)
        ok = False
    now = datetime.now(UTC)
    if ok:
        await store.mark_delivered(item, now)
    else:
        await store.mark_failed(item, now + backoff(item.attempts + 1))
    return ok


async def retry_loop(store: Store, settings: Settings, client: httpx.AsyncClient) -> None:
    while True:
        for item in await store.due_outbox(datetime.now(UTC)):
            if await deliver(item, store, settings, client) and item.event == "session.ready":
                session = await store.get_session(item.payload["session_id"])
                if session is not None:
                    session.ready_delivered = True
                    await store.save_session(session)
        await asyncio.sleep(settings.webhook_retry_interval_s)
