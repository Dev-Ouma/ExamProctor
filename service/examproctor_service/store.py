"""Persistence for sessions, consents, pre-checks, one-time launch ids and the webhook outbox.

`MemoryStore` backs unit tests; `PgStore` is used at runtime. Both implement `Store`.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import asyncpg


@dataclass
class Session:
    id: str
    moodle_user_id: int
    course_id: int
    cmid: int
    quiz_id: int
    policy: dict[str, Any]
    status: str = "created"  # created -> consented -> ready | blocked
    consent_version: str | None = None
    precheck: dict[str, Any] | None = None
    ready_delivered: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None
    last_seen_at: datetime | None = None
    client_health: dict[str, Any] | None = None
    legal_hold: bool = False
    purged_at: datetime | None = None


UPLOAD_KINDS = ("camera", "screen", "reference", "room_scan")


@dataclass
class Upload:
    session_id: str
    kind: str
    seq: int
    key: str
    sha256: str
    bytes: int
    captured_at: datetime
    status: str = "pending"  # pending -> verified | corrupt
    verified_at: datetime | None = None


@dataclass
class Event:
    session_id: str
    type: str
    client_ts: datetime
    payload: dict[str, Any]
    server_ts: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class OutboxItem:
    id: int
    event: str
    payload: dict[str, Any]
    attempts: int = 0
    next_try_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    delivered_at: datetime | None = None


class Store(Protocol):
    async def use_jti(self, jti: str, expires_at: datetime) -> bool: ...
    async def create_session(self, claims: dict[str, Any]) -> Session: ...
    async def get_session(self, session_id: str) -> Session | None: ...
    async def save_session(self, session: Session) -> None: ...
    async def enqueue(self, event: str, payload: dict[str, Any]) -> OutboxItem: ...
    async def due_outbox(self, now: datetime, limit: int = 50) -> list[OutboxItem]: ...
    async def mark_delivered(self, item: OutboxItem, now: datetime) -> None: ...
    async def mark_failed(self, item: OutboxItem, next_try_at: datetime) -> None: ...
    async def put_upload(self, upload: Upload) -> Upload: ...
    async def get_upload(self, session_id: str, key: str) -> Upload | None: ...
    async def save_upload(self, upload: Upload) -> None: ...
    async def count_uploads(self, session_id: str) -> dict[str, int]: ...
    async def add_events(self, events: list[Event]) -> int: ...
    async def sessions_to_purge(self, ended_before: datetime) -> list[Session]: ...


def _session_from_claims(claims: dict[str, Any]) -> Session:
    return Session(
        id=str(uuid.uuid4()),
        moodle_user_id=int(claims["sub"]),
        course_id=int(claims["course_id"]),
        cmid=int(claims["cmid"]),
        quiz_id=int(claims["quiz_id"]),
        policy=dict(claims["policy"]),
    )


def backoff(attempts: int) -> timedelta:
    """Retry delay after `attempts` failures: 5 s doubling, capped at 10 min."""
    return timedelta(seconds=min(5 * 2 ** max(attempts - 1, 0), 600))


class MemoryStore:
    def __init__(self) -> None:
        self.jtis: dict[str, datetime] = {}
        self.sessions: dict[str, Session] = {}
        self.outbox: list[OutboxItem] = []
        self.uploads: dict[tuple[str, str], Upload] = {}
        self.events: list[Event] = []

    async def use_jti(self, jti: str, expires_at: datetime) -> bool:
        if jti in self.jtis:
            return False
        self.jtis[jti] = expires_at
        return True

    async def create_session(self, claims: dict[str, Any]) -> Session:
        session = _session_from_claims(claims)
        self.sessions[session.id] = session
        return session

    async def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    async def save_session(self, session: Session) -> None:
        self.sessions[session.id] = session

    async def enqueue(self, event: str, payload: dict[str, Any]) -> OutboxItem:
        item = OutboxItem(id=len(self.outbox) + 1, event=event, payload=payload)
        self.outbox.append(item)
        return item

    async def due_outbox(self, now: datetime, limit: int = 50) -> list[OutboxItem]:
        due = [i for i in self.outbox if i.delivered_at is None and i.next_try_at <= now]
        return due[:limit]

    async def mark_delivered(self, item: OutboxItem, now: datetime) -> None:
        item.delivered_at = now

    async def mark_failed(self, item: OutboxItem, next_try_at: datetime) -> None:
        item.attempts += 1
        item.next_try_at = next_try_at

    async def put_upload(self, upload: Upload) -> Upload:
        return self.uploads.setdefault((upload.session_id, upload.key), upload)

    async def get_upload(self, session_id: str, key: str) -> Upload | None:
        return self.uploads.get((session_id, key))

    async def save_upload(self, upload: Upload) -> None:
        self.uploads[(upload.session_id, upload.key)] = upload

    async def count_uploads(self, session_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for (sid, _), u in self.uploads.items():
            if sid == session_id and u.status == "verified":
                counts[u.kind] = counts.get(u.kind, 0) + 1
        return counts

    async def add_events(self, events: list[Event]) -> int:
        self.events.extend(events)
        return len(events)

    async def sessions_to_purge(self, ended_before: datetime) -> list[Session]:
        return [
            s
            for s in self.sessions.values()
            if s.ended_at and s.ended_at < ended_before and not s.legal_hold and not s.purged_at
        ]


SCHEMA = """
CREATE TABLE IF NOT EXISTS launch_jti (
    jti TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    moodle_user_id BIGINT NOT NULL,
    course_id BIGINT NOT NULL,
    cmid BIGINT NOT NULL,
    quiz_id BIGINT NOT NULL,
    policy JSONB NOT NULL,
    status TEXT NOT NULL,
    consent_version TEXT,
    consented_at TIMESTAMPTZ,
    precheck JSONB,
    ready_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS client_health JSONB;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS purged_at TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS uploads (
    session_id UUID NOT NULL REFERENCES sessions (id),
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    seq INT NOT NULL,
    sha256 TEXT NOT NULL,
    bytes INT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    verified_at TIMESTAMPTZ,
    PRIMARY KEY (session_id, key)
);
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions (id),
    type TEXT NOT NULL,
    payload JSONB NOT NULL,
    client_ts TIMESTAMPTZ NOT NULL,
    server_ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_session ON events (session_id, client_ts);
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS analysis JSONB;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS reference_embedding JSONB;
CREATE INDEX IF NOT EXISTS uploads_unanalysed ON uploads (captured_at)
    WHERE status = 'verified' AND analysis IS NULL;
CREATE TABLE IF NOT EXISTS reference_photos (
    moodle_user_id BIGINT PRIMARY KEY,
    key TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    face_px INT,
    embedding JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS flags (
    session_id UUID NOT NULL REFERENCES sessions (id),
    idx INT NOT NULL,
    type TEXT NOT NULL,
    severity INT NOT NULL,
    confidence REAL NOT NULL,
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ NOT NULL,
    evidence JSONB NOT NULL,
    context JSONB NOT NULL,
    question TEXT,
    PRIMARY KEY (session_id, idx)
);
CREATE TABLE IF NOT EXISTS scores (
    session_id UUID PRIMARY KEY REFERENCES sessions (id),
    value REAL NOT NULL,
    band TEXT NOT NULL,
    reasons JSONB NOT NULL,
    version TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS webhook_outbox (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    payload JSONB NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    next_try_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS webhook_outbox_due
    ON webhook_outbox (next_try_at) WHERE delivered_at IS NULL;
"""


class PgStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, dsn: str) -> "PgStore":
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA)
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    async def use_jti(self, jti: str, expires_at: datetime) -> bool:
        result = await self.pool.execute(
            "INSERT INTO launch_jti (jti, expires_at) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            jti,
            expires_at,
        )
        return result.endswith(" 1")

    async def create_session(self, claims: dict[str, Any]) -> Session:
        s = _session_from_claims(claims)
        await self.pool.execute(
            "INSERT INTO sessions (id, moodle_user_id, course_id, cmid, quiz_id, policy, status)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7)",
            uuid.UUID(s.id),
            s.moodle_user_id,
            s.course_id,
            s.cmid,
            s.quiz_id,
            json.dumps(s.policy),
            s.status,
        )
        return s

    async def get_session(self, session_id: str) -> Session | None:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            return None
        row = await self.pool.fetchrow("SELECT * FROM sessions WHERE id = $1", sid)
        if row is None:
            return None
        return Session(
            id=str(row["id"]),
            moodle_user_id=row["moodle_user_id"],
            course_id=row["course_id"],
            cmid=row["cmid"],
            quiz_id=row["quiz_id"],
            policy=json.loads(row["policy"]),
            status=row["status"],
            consent_version=row["consent_version"],
            precheck=json.loads(row["precheck"]) if row["precheck"] else None,
            ready_delivered=row["ready_delivered"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            last_seen_at=row["last_seen_at"],
            client_health=json.loads(row["client_health"]) if row["client_health"] else None,
            legal_hold=row["legal_hold"],
            purged_at=row["purged_at"],
        )

    async def save_session(self, s: Session) -> None:
        await self.pool.execute(
            "UPDATE sessions SET status = $2, consent_version = $3,"
            " consented_at = CASE WHEN $3::text IS NOT NULL THEN COALESCE(consented_at, now()) END,"
            " precheck = $4, ready_delivered = $5, started_at = $6, ended_at = $7,"
            " last_seen_at = $8, client_health = $9, legal_hold = $10, purged_at = $11,"
            " updated_at = now() WHERE id = $1",
            uuid.UUID(s.id),
            s.status,
            s.consent_version,
            json.dumps(s.precheck) if s.precheck is not None else None,
            s.ready_delivered,
            s.started_at,
            s.ended_at,
            s.last_seen_at,
            json.dumps(s.client_health) if s.client_health is not None else None,
            s.legal_hold,
            s.purged_at,
        )

    async def enqueue(self, event: str, payload: dict[str, Any]) -> OutboxItem:
        row = await self.pool.fetchrow(
            "INSERT INTO webhook_outbox (event, payload) VALUES ($1, $2) RETURNING id, attempts, next_try_at",
            event,
            json.dumps(payload),
        )
        return OutboxItem(id=row["id"], event=event, payload=payload, next_try_at=row["next_try_at"])

    async def due_outbox(self, now: datetime, limit: int = 50) -> list[OutboxItem]:
        rows = await self.pool.fetch(
            "SELECT * FROM webhook_outbox WHERE delivered_at IS NULL AND next_try_at <= $1 ORDER BY id LIMIT $2",
            now,
            limit,
        )
        return [
            OutboxItem(
                id=r["id"],
                event=r["event"],
                payload=json.loads(r["payload"]),
                attempts=r["attempts"],
                next_try_at=r["next_try_at"],
            )
            for r in rows
        ]

    async def mark_delivered(self, item: OutboxItem, now: datetime) -> None:
        item.delivered_at = now
        await self.pool.execute("UPDATE webhook_outbox SET delivered_at = $2 WHERE id = $1", item.id, now)

    async def mark_failed(self, item: OutboxItem, next_try_at: datetime) -> None:
        item.attempts += 1
        item.next_try_at = next_try_at
        await self.pool.execute(
            "UPDATE webhook_outbox SET attempts = attempts + 1, next_try_at = $2 WHERE id = $1",
            item.id,
            next_try_at,
        )

    async def put_upload(self, u: Upload) -> Upload:
        await self.pool.execute(
            "INSERT INTO uploads (session_id, key, kind, seq, sha256, bytes, captured_at, status)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT DO NOTHING",
            uuid.UUID(u.session_id),
            u.key,
            u.kind,
            u.seq,
            u.sha256,
            u.bytes,
            u.captured_at,
            u.status,
        )
        existing = await self.get_upload(u.session_id, u.key)
        assert existing is not None
        return existing

    async def get_upload(self, session_id: str, key: str) -> Upload | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM uploads WHERE session_id = $1 AND key = $2", uuid.UUID(session_id), key
        )
        if row is None:
            return None
        return Upload(
            session_id=str(row["session_id"]),
            kind=row["kind"],
            seq=row["seq"],
            key=row["key"],
            sha256=row["sha256"],
            bytes=row["bytes"],
            captured_at=row["captured_at"],
            status=row["status"],
            verified_at=row["verified_at"],
        )

    async def save_upload(self, u: Upload) -> None:
        await self.pool.execute(
            "UPDATE uploads SET status = $3, verified_at = $4 WHERE session_id = $1 AND key = $2",
            uuid.UUID(u.session_id),
            u.key,
            u.status,
            u.verified_at,
        )

    async def count_uploads(self, session_id: str) -> dict[str, int]:
        rows = await self.pool.fetch(
            "SELECT kind, count(*) AS n FROM uploads WHERE session_id = $1 AND status = 'verified' GROUP BY kind",
            uuid.UUID(session_id),
        )
        return {r["kind"]: r["n"] for r in rows}

    async def add_events(self, events: list[Event]) -> int:
        await self.pool.executemany(
            "INSERT INTO events (session_id, type, payload, client_ts, server_ts) VALUES ($1, $2, $3, $4, $5)",
            [(uuid.UUID(e.session_id), e.type, json.dumps(e.payload), e.client_ts, e.server_ts) for e in events],
        )
        return len(events)

    async def sessions_to_purge(self, ended_before: datetime) -> list[Session]:
        rows = await self.pool.fetch(
            "SELECT id FROM sessions WHERE ended_at < $1 AND NOT legal_hold AND purged_at IS NULL",
            ended_before,
        )
        sessions = [await self.get_session(str(r["id"])) for r in rows]
        return [s for s in sessions if s is not None]
