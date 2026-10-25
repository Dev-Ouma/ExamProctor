"""Live invigilation state: invigilator actions (warn, message, pause, resume, terminate) and the
event bus that tells live walls something changed.

Actions are stored first, then delivered to the student on the next heartbeat (weak networks make
polling more reliable than a socket on the student side). Live walls listen on the bus.
"""

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import asyncpg
from redis import asyncio as aioredis

from .store import migrate

ACTION_TYPES = ("warn", "message", "pause", "resume", "terminate")


@dataclass
class Action:
    session_id: str
    type: str
    reason: str
    message: str
    actor_id: int
    actor_name: str
    id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    delivered_at: datetime | None = None
    acked_at: datetime | None = None

    def to_json(self) -> dict[str, Any]:
        out = asdict(self)
        for k in ("created_at", "delivered_at", "acked_at"):
            out[k] = out[k].isoformat() if out[k] else None
        return out

    def notice(self) -> dict[str, Any]:
        """What the student sees: the action and the invigilator's words, not their identity."""
        return {
            "id": self.id,
            "type": self.type,
            "message": self.message or self.reason,
            "created_at": self.created_at.isoformat(),
        }


def paused(actions: list[Action]) -> bool:
    state = False
    for a in actions:
        if a.type == "pause":
            state = True
        elif a.type in ("resume", "terminate"):
            state = False
    return state


class ActionStore(Protocol):
    async def add(self, action: Action) -> Action: ...
    async def for_session(self, session_id: str) -> list[Action]: ...
    async def for_sessions(self, session_ids: list[str]) -> dict[str, list[Action]]: ...
    async def take_undelivered(self, session_id: str) -> list[Action]: ...
    async def ack(self, session_id: str, action_id: int) -> bool: ...


class MemoryActionStore:
    def __init__(self) -> None:
        self.rows: list[Action] = []

    async def add(self, action: Action) -> Action:
        action.id = len(self.rows) + 1
        self.rows.append(action)
        return action

    async def for_session(self, session_id: str) -> list[Action]:
        return [a for a in self.rows if a.session_id == session_id]

    async def for_sessions(self, session_ids: list[str]) -> dict[str, list[Action]]:
        wanted = set(session_ids)
        out: dict[str, list[Action]] = defaultdict(list)
        for a in self.rows:
            if a.session_id in wanted:
                out[a.session_id].append(a)
        return out

    async def take_undelivered(self, session_id: str) -> list[Action]:
        now = datetime.now(UTC)
        out = [a for a in self.rows if a.session_id == session_id and a.delivered_at is None]
        for a in out:
            a.delivered_at = now
        return out

    async def ack(self, session_id: str, action_id: int) -> bool:
        for a in self.rows:
            if a.session_id == session_id and a.id == action_id:
                a.acked_at = a.acked_at or datetime.now(UTC)
                return True
        return False


SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions (id),
    type TEXT NOT NULL,
    reason TEXT NOT NULL,
    message TEXT NOT NULL,
    actor_id BIGINT NOT NULL,
    actor_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ,
    acked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS actions_session ON actions (session_id, id);
"""


def _action(r: asyncpg.Record) -> Action:
    return Action(
        id=r["id"],
        session_id=str(r["session_id"]),
        type=r["type"],
        reason=r["reason"],
        message=r["message"],
        actor_id=r["actor_id"],
        actor_name=r["actor_name"],
        created_at=r["created_at"],
        delivered_at=r["delivered_at"],
        acked_at=r["acked_at"],
    )


class PgActionStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def migrate(self) -> None:
        await migrate(self.pool, SCHEMA)

    async def add(self, a: Action) -> Action:
        row = await self.pool.fetchrow(
            "INSERT INTO actions (session_id, type, reason, message, actor_id, actor_name, created_at)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            uuid.UUID(a.session_id),
            a.type,
            a.reason,
            a.message,
            a.actor_id,
            a.actor_name,
            a.created_at,
        )
        a.id = row["id"]
        return a

    async def for_session(self, session_id: str) -> list[Action]:
        rows = await self.pool.fetch("SELECT * FROM actions WHERE session_id = $1 ORDER BY id", uuid.UUID(session_id))
        return [_action(r) for r in rows]

    async def for_sessions(self, session_ids: list[str]) -> dict[str, list[Action]]:
        rows = await self.pool.fetch(
            "SELECT * FROM actions WHERE session_id = ANY($1::uuid[]) ORDER BY id",
            [uuid.UUID(s) for s in session_ids],
        )
        out: dict[str, list[Action]] = defaultdict(list)
        for r in rows:
            out[str(r["session_id"])].append(_action(r))
        return out

    async def take_undelivered(self, session_id: str) -> list[Action]:
        rows = await self.pool.fetch(
            "UPDATE actions SET delivered_at = now() WHERE session_id = $1 AND delivered_at IS NULL RETURNING *",
            uuid.UUID(session_id),
        )
        return sorted((_action(r) for r in rows), key=lambda a: a.id)

    async def ack(self, session_id: str, action_id: int) -> bool:
        result = await self.pool.execute(
            "UPDATE actions SET acked_at = COALESCE(acked_at, now()) WHERE session_id = $1 AND id = $2",
            uuid.UUID(session_id),
            action_id,
        )
        return result.endswith(" 1")


def channel(quiz_id: int) -> str:
    return f"examproctor:live:{quiz_id}"


class Bus(Protocol):
    async def publish(self, quiz_id: int, event: dict[str, Any]) -> None: ...
    def subscribe(self, quiz_id: int) -> AsyncIterator[dict[str, Any]]: ...


class MemoryBus:
    def __init__(self) -> None:
        self.queues: dict[int, list[asyncio.Queue]] = defaultdict(list)
        self.published: list[tuple[int, dict[str, Any]]] = []

    async def publish(self, quiz_id: int, event: dict[str, Any]) -> None:
        self.published.append((quiz_id, event))
        for q in self.queues[quiz_id]:
            q.put_nowait(event)

    async def subscribe(self, quiz_id: int) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue()
        self.queues[quiz_id].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self.queues[quiz_id].remove(q)


class RedisBus:
    """Redis pub/sub, so every service replica and the worker reach every live wall."""

    def __init__(self, url: str) -> None:
        self.redis = aioredis.from_url(url)

    async def publish(self, quiz_id: int, event: dict[str, Any]) -> None:
        try:
            await self.redis.publish(channel(quiz_id), json.dumps(event))
        except Exception:  # noqa: BLE001 - live updates are best effort; the wall also polls
            return

    async def subscribe(self, quiz_id: int) -> AsyncIterator[dict[str, Any]]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel(quiz_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel(quiz_id))
            await pubsub.aclose()

    async def close(self) -> None:
        await self.redis.aclose()
