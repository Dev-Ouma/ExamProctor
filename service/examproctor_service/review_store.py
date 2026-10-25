"""Read models for reviewers, reviewer decisions and appeals, and the staff audit log.

`PgReviewStore` reads the tables the worker fills (flags, scores); `MemoryReviewStore` backs unit
tests on top of `MemoryStore`.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import asyncpg

from .store import MemoryStore, Session, migrate

DECISIONS = ("no_issue", "concern", "refer_misconduct")
APPEALS = ("opened", "upheld", "overturned", "withdrawn")


@dataclass
class Review:
    session_id: str
    kind: str  # decision | appeal
    value: str
    notes: str
    reviewer_id: int
    reviewer_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_json(self) -> dict[str, Any]:
        return asdict(self) | {"created_at": self.created_at.isoformat()}


@dataclass
class SessionRow:
    session: Session
    created_at: datetime | None
    score: float | None
    band: str | None
    flag_count: int
    uploads: dict[str, int]
    decision: str | None
    appeal: str | None

    def to_json(self) -> dict[str, Any]:
        s = self.session
        return {
            "session_id": s.id,
            "moodle_user_id": s.moodle_user_id,
            "status": s.status,
            "created_at": iso(self.created_at),
            "started_at": iso(s.started_at),
            "ended_at": iso(s.ended_at),
            "integrity_score": self.score,
            "band": self.band,
            "flag_count": self.flag_count,
            "uploads": self.uploads,
            "decision": self.decision,
            "appeal": self.appeal,
            "purged": s.purged_at is not None,
        }


@dataclass
class LiveRow:
    row: SessionRow
    camera: dict[str, Any] | None  # key, captured_at, faces
    recent_flags: list[dict[str, Any]]


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ReviewStore(Protocol):
    async def list_sessions(self, quiz_id: int, after: str | None, limit: int) -> list[SessionRow]: ...
    async def flags(self, session_id: str) -> list[dict[str, Any]]: ...
    async def score(self, session_id: str) -> dict[str, Any] | None: ...
    async def uploads(self, session_id: str) -> list[dict[str, Any]]: ...
    async def events(self, session_id: str) -> list[dict[str, Any]]: ...
    async def reviews(self, session_id: str) -> list[Review]: ...
    async def add_review(self, review: Review) -> None: ...
    async def audit(self, actor: str, action: str, target: str, ip: str | None, detail: dict[str, Any]) -> None: ...
    async def summary(self, quiz_id: int) -> dict[str, Any]: ...
    async def user_sessions(self, user_id: int, quiz_id: int | None) -> list[Session]: ...
    async def quiz_users(self, quiz_id: int) -> list[int]: ...
    async def user_quizzes(self, user_id: int) -> list[int]: ...
    async def erase_session(self, session_id: str) -> None: ...
    async def live_view(self, quiz_id: int, ended_after: datetime) -> list[LiveRow]: ...


def summarise(rows: list[SessionRow], flag_types: dict[str, int]) -> dict[str, Any]:
    """Quiz-level numbers for the report header. Shared by both stores."""
    bands: dict[str, int] = {}
    decisions: dict[str, int] = {}
    scores = [r.score for r in rows if r.score is not None]
    for r in rows:
        bands[r.band or "pending"] = bands.get(r.band or "pending", 0) + 1
        decisions[r.decision or "undecided"] = decisions.get(r.decision or "undecided", 0) + 1
    return {
        "sessions": len(rows),
        "finished": sum(1 for r in rows if r.session.ended_at),
        "started": sum(1 for r in rows if r.session.started_at),
        "blocked": sum(1 for r in rows if r.session.status == "blocked"),
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "bands": bands,
        "decisions": decisions,
        "flag_types": dict(sorted(flag_types.items(), key=lambda kv: -kv[1])),
    }


class MemoryReviewStore:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.flag_rows: dict[str, list[dict[str, Any]]] = {}
        self.scores: dict[str, dict[str, Any]] = {}
        self.analysis: dict[tuple[str, str], dict[str, Any]] = {}
        self.review_rows: list[Review] = []
        self.audit_rows: list[dict[str, Any]] = []

    def _row(self, s: Session) -> SessionRow:
        score = self.scores.get(s.id)
        latest = {r.kind: r.value for r in self.review_rows if r.session_id == s.id}
        uploads: dict[str, int] = {}
        for (sid, _), u in self.store.uploads.items():
            if sid == s.id and u.status == "verified":
                uploads[u.kind] = uploads.get(u.kind, 0) + 1
        return SessionRow(
            session=s,
            created_at=None,
            score=score["value"] if score else None,
            band=score["band"] if score else None,
            flag_count=len(self.flag_rows.get(s.id, [])),
            uploads=uploads,
            decision=latest.get("decision"),
            appeal=latest.get("appeal"),
        )

    async def list_sessions(self, quiz_id: int, after: str | None, limit: int) -> list[SessionRow]:
        ids = sorted(s.id for s in self.store.sessions.values() if s.quiz_id == quiz_id)
        ids = [i for i in ids if after is None or i > after][:limit]
        return [self._row(self.store.sessions[i]) for i in ids]

    async def flags(self, session_id: str) -> list[dict[str, Any]]:
        return self.flag_rows.get(session_id, [])

    async def score(self, session_id: str) -> dict[str, Any] | None:
        return self.scores.get(session_id)

    async def uploads(self, session_id: str) -> list[dict[str, Any]]:
        rows = [u for (sid, _), u in self.store.uploads.items() if sid == session_id and u.status == "verified"]
        return [
            {
                "key": u.key,
                "kind": u.kind,
                "seq": u.seq,
                "captured_at": u.captured_at.isoformat(),
                "analysis": self.analysis.get((session_id, u.key)),
            }
            for u in sorted(rows, key=lambda u: u.captured_at)
        ]

    async def events(self, session_id: str) -> list[dict[str, Any]]:
        rows = [e for e in self.store.events if e.session_id == session_id]
        return [
            {"type": e.type, "ts": e.client_ts.isoformat(), "data": e.payload}
            for e in sorted(rows, key=lambda e: e.client_ts)
        ]

    async def reviews(self, session_id: str) -> list[Review]:
        return [r for r in self.review_rows if r.session_id == session_id]

    async def add_review(self, review: Review) -> None:
        self.review_rows.append(review)

    async def audit(self, actor: str, action: str, target: str, ip: str | None, detail: dict[str, Any]) -> None:
        self.audit_rows.append({"actor": actor, "action": action, "target": target, "ip": ip, "detail": detail})

    async def summary(self, quiz_id: int) -> dict[str, Any]:
        rows = await self.list_sessions(quiz_id, None, 1_000_000)
        types: dict[str, int] = {}
        for r in rows:
            for f in self.flag_rows.get(r.session.id, []):
                types[f["type"]] = types.get(f["type"], 0) + 1
        return summarise(rows, types)

    async def user_sessions(self, user_id: int, quiz_id: int | None) -> list[Session]:
        return [
            s
            for s in self.store.sessions.values()
            if s.moodle_user_id == user_id and (quiz_id is None or s.quiz_id == quiz_id)
        ]

    async def quiz_users(self, quiz_id: int) -> list[int]:
        return sorted({s.moodle_user_id for s in self.store.sessions.values() if s.quiz_id == quiz_id})

    async def user_quizzes(self, user_id: int) -> list[int]:
        return sorted({s.quiz_id for s in self.store.sessions.values() if s.moodle_user_id == user_id})

    async def erase_session(self, session_id: str) -> None:
        self.store.sessions.pop(session_id, None)
        self.store.uploads = {k: v for k, v in self.store.uploads.items() if k[0] != session_id}
        self.store.events = [e for e in self.store.events if e.session_id != session_id]
        self.flag_rows.pop(session_id, None)
        self.scores.pop(session_id, None)
        self.review_rows = [r for r in self.review_rows if r.session_id != session_id]

    async def live_view(self, quiz_id: int, ended_after: datetime) -> list[LiveRow]:
        out = []
        for r in await self.list_sessions(quiz_id, None, 1_000_000):
            s = r.session
            if s.started_at is None or (s.ended_at and s.ended_at <= ended_after):
                continue
            cameras = [u for u in await self.uploads(s.id) if u["kind"] == "camera"]
            camera = None
            if cameras:
                last = cameras[-1]
                camera = {
                    "key": last["key"],
                    "captured_at": last["captured_at"],
                    "faces": len((last["analysis"] or {}).get("faces") or []),
                }
            flags = [
                {k: f.get(k) for k in ("type", "start", "end", "severity")} for f in self.flag_rows.get(s.id, [])[-3:]
            ]
            out.append(LiveRow(r, camera, flags))
        return out


SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions (id),
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    notes TEXT NOT NULL,
    reviewer_id BIGINT NOT NULL,
    reviewer_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reviews_session ON reviews (session_id, id);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    ip TEXT,
    detail JSONB NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sessions_quiz ON sessions (quiz_id, id);
CREATE INDEX IF NOT EXISTS uploads_latest ON uploads (session_id, kind, captured_at DESC) WHERE status = 'verified';
"""

LIST_SQL = """
SELECT s.*, sc.value AS score_value, sc.band AS score_band,
       (SELECT count(*) FROM flags f WHERE f.session_id = s.id) AS flag_count,
       (SELECT jsonb_object_agg(kind, n) FROM (
            SELECT kind, count(*) AS n FROM uploads u
             WHERE u.session_id = s.id AND u.status = 'verified' GROUP BY kind) k) AS upload_counts,
       (SELECT value FROM reviews r WHERE r.session_id = s.id AND r.kind = 'decision'
         ORDER BY id DESC LIMIT 1) AS decision,
       (SELECT value FROM reviews r WHERE r.session_id = s.id AND r.kind = 'appeal'
         ORDER BY id DESC LIMIT 1) AS appeal
  FROM sessions s LEFT JOIN scores sc ON sc.session_id = s.id
 WHERE s.quiz_id = $1 AND ($2::uuid IS NULL OR s.id > $2::uuid)
 ORDER BY s.id
 LIMIT $3
"""


LIVE_SQL = """
SELECT s.*, sc.value AS score_value, sc.band AS score_band,
       (SELECT count(*) FROM flags f WHERE f.session_id = s.id) AS flag_count,
       (SELECT jsonb_object_agg(kind, n) FROM (
            SELECT kind, count(*) AS n FROM uploads u
             WHERE u.session_id = s.id AND u.status = 'verified' GROUP BY kind) k) AS upload_counts,
       (SELECT value FROM reviews r WHERE r.session_id = s.id AND r.kind = 'decision'
         ORDER BY id DESC LIMIT 1) AS decision,
       (SELECT value FROM reviews r WHERE r.session_id = s.id AND r.kind = 'appeal'
         ORDER BY id DESC LIMIT 1) AS appeal,
       cam.key AS cam_key, cam.captured_at AS cam_at,
       COALESCE(jsonb_array_length(cam.analysis -> 'faces'), 0) AS cam_faces,
       (SELECT jsonb_agg(x ORDER BY x ->> 'start') FROM (
            SELECT jsonb_build_object('type', f.type, 'start', f.start_ts, 'end', f.end_ts,
                                      'severity', f.severity) AS x
              FROM flags f WHERE f.session_id = s.id ORDER BY f.start_ts DESC, f.idx DESC LIMIT 3) t) AS recent
  FROM sessions s
  LEFT JOIN scores sc ON sc.session_id = s.id
  LEFT JOIN LATERAL (
       SELECT key, captured_at, analysis FROM uploads u
        WHERE u.session_id = s.id AND u.kind = 'camera' AND u.status = 'verified'
        ORDER BY captured_at DESC LIMIT 1) cam ON true
 WHERE s.quiz_id = $1 AND s.started_at IS NOT NULL AND (s.ended_at IS NULL OR s.ended_at > $2)
"""


def _session(row: asyncpg.Record) -> Session:
    return Session(
        id=str(row["id"]),
        moodle_user_id=row["moodle_user_id"],
        course_id=row["course_id"],
        cmid=row["cmid"],
        quiz_id=row["quiz_id"],
        policy=json.loads(row["policy"]),
        status=row["status"],
        consent_version=row["consent_version"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        last_seen_at=row["last_seen_at"],
        client_health=json.loads(row["client_health"]) if row["client_health"] else None,
        legal_hold=row["legal_hold"],
        purged_at=row["purged_at"],
    )


class PgReviewStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def migrate(self) -> None:
        await migrate(self.pool, SCHEMA)

    async def list_sessions(self, quiz_id: int, after: str | None, limit: int) -> list[SessionRow]:
        rows = await self.pool.fetch(LIST_SQL, quiz_id, uuid.UUID(after) if after else None, limit)
        return [
            SessionRow(
                session=_session(r),
                created_at=r["created_at"],
                score=r["score_value"],
                band=r["score_band"],
                flag_count=r["flag_count"],
                uploads=json.loads(r["upload_counts"]) if r["upload_counts"] else {},
                decision=r["decision"],
                appeal=r["appeal"],
            )
            for r in rows
        ]

    async def flags(self, session_id: str) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT * FROM flags WHERE session_id = $1 ORDER BY start_ts, idx", uuid.UUID(session_id)
        )
        return [
            {
                "index": r["idx"],
                "type": r["type"],
                "severity": r["severity"],
                "confidence": round(r["confidence"], 3),
                "start": r["start_ts"].isoformat(),
                "end": r["end_ts"].isoformat(),
                "evidence": json.loads(r["evidence"]),
                "context": json.loads(r["context"]),
                "question": r["question"],
            }
            for r in rows
        ]

    async def score(self, session_id: str) -> dict[str, Any] | None:
        r = await self.pool.fetchrow("SELECT * FROM scores WHERE session_id = $1", uuid.UUID(session_id))
        if r is None:
            return None
        return {
            "value": r["value"],
            "band": r["band"],
            "reasons": json.loads(r["reasons"]),
            "version": r["version"],
            "computed_at": r["computed_at"].isoformat(),
        }

    async def uploads(self, session_id: str) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT key, kind, seq, captured_at, analysis FROM uploads"
            " WHERE session_id = $1 AND status = 'verified' ORDER BY captured_at, key",
            uuid.UUID(session_id),
        )
        return [
            {
                "key": r["key"],
                "kind": r["kind"],
                "seq": r["seq"],
                "captured_at": r["captured_at"].isoformat(),
                "analysis": json.loads(r["analysis"]) if r["analysis"] else None,
            }
            for r in rows
        ]

    async def events(self, session_id: str) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "SELECT type, client_ts, payload FROM events WHERE session_id = $1 ORDER BY client_ts, id",
            uuid.UUID(session_id),
        )
        return [{"type": r["type"], "ts": r["client_ts"].isoformat(), "data": json.loads(r["payload"])} for r in rows]

    async def reviews(self, session_id: str) -> list[Review]:
        rows = await self.pool.fetch("SELECT * FROM reviews WHERE session_id = $1 ORDER BY id", uuid.UUID(session_id))
        return [
            Review(
                session_id=str(r["session_id"]),
                kind=r["kind"],
                value=r["value"],
                notes=r["notes"],
                reviewer_id=r["reviewer_id"],
                reviewer_name=r["reviewer_name"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def add_review(self, review: Review) -> None:
        await self.pool.execute(
            "INSERT INTO reviews (session_id, kind, value, notes, reviewer_id, reviewer_name, created_at)"
            " VALUES ($1, $2, $3, $4, $5, $6, $7)",
            uuid.UUID(review.session_id),
            review.kind,
            review.value,
            review.notes,
            review.reviewer_id,
            review.reviewer_name,
            review.created_at,
        )

    async def audit(self, actor: str, action: str, target: str, ip: str | None, detail: dict[str, Any]) -> None:
        await self.pool.execute(
            "INSERT INTO audit_log (actor, action, target, ip, detail) VALUES ($1, $2, $3, $4, $5)",
            actor,
            action,
            target,
            ip,
            json.dumps(detail),
        )

    async def summary(self, quiz_id: int) -> dict[str, Any]:
        rows = await self.list_sessions(quiz_id, None, 100_000)
        types = await self.pool.fetch(
            "SELECT f.type, count(*) AS n FROM flags f JOIN sessions s ON s.id = f.session_id"
            " WHERE s.quiz_id = $1 GROUP BY f.type",
            quiz_id,
        )
        return summarise(rows, {r["type"]: r["n"] for r in types})

    async def user_sessions(self, user_id: int, quiz_id: int | None) -> list[Session]:
        rows = await self.pool.fetch(
            "SELECT * FROM sessions WHERE moodle_user_id = $1 AND ($2::bigint IS NULL OR quiz_id = $2)"
            " ORDER BY created_at",
            user_id,
            quiz_id,
        )
        return [_session(r) for r in rows]

    async def quiz_users(self, quiz_id: int) -> list[int]:
        rows = await self.pool.fetch("SELECT DISTINCT moodle_user_id FROM sessions WHERE quiz_id = $1", quiz_id)
        return sorted(r["moodle_user_id"] for r in rows)

    async def user_quizzes(self, user_id: int) -> list[int]:
        rows = await self.pool.fetch("SELECT DISTINCT quiz_id FROM sessions WHERE moodle_user_id = $1", user_id)
        return sorted(r["quiz_id"] for r in rows)

    async def erase_session(self, session_id: str) -> None:
        sid = uuid.UUID(session_id)
        async with self.pool.acquire() as conn, conn.transaction():
            for table in ("reviews", "scores", "flags", "events", "uploads"):
                await conn.execute(f"DELETE FROM {table} WHERE session_id = $1", sid)  # noqa: S608 - fixed names
            await conn.execute("DELETE FROM sessions WHERE id = $1", sid)

    async def live_view(self, quiz_id: int, ended_after: datetime) -> list[LiveRow]:
        rows = await self.pool.fetch(LIVE_SQL, quiz_id, ended_after)
        out = []
        for r in rows:
            row = SessionRow(
                session=_session(r),
                created_at=r["created_at"],
                score=r["score_value"],
                band=r["score_band"],
                flag_count=r["flag_count"],
                uploads=json.loads(r["upload_counts"]) if r["upload_counts"] else {},
                decision=r["decision"],
                appeal=r["appeal"],
            )
            camera = (
                {"key": r["cam_key"], "captured_at": r["cam_at"].isoformat(), "faces": r["cam_faces"]}
                if r["cam_key"]
                else None
            )
            out.append(LiveRow(row, camera, json.loads(r["recent"]) if r["recent"] else []))
        return out
