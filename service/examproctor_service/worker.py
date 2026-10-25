"""Analysis worker: analyses verified images, then recomputes flags and the score per session.

Run: python -m examproctor_service.worker. Scale by running more replicas: claims use
FOR UPDATE SKIP LOCKED, so workers never take the same image.
"""

import asyncio
import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

import asyncpg

from .analysis.faces import FaceEngine
from .analysis.rules import Frame, PageEvent, all_flags
from .analysis.score import compute
from .config import Settings, get_settings
from .live_store import RedisBus
from .objectstore import ObjectStore, S3ObjectStore
from .store import PgStore

log = logging.getLogger("examproctor.worker")
MODELS = Path(__file__).resolve().parents[1] / "models"
BATCH = 20
STALE_CLAIM = timedelta(minutes=5)


async def claim(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        UPDATE uploads SET claimed_at = now()
         WHERE (session_id, key) IN (
               SELECT session_id, key FROM uploads
                WHERE status = 'verified' AND analysis IS NULL
                  AND kind IN ('camera', 'screen', 'reference')
                  AND (claimed_at IS NULL OR claimed_at < now() - $1::interval)
                ORDER BY captured_at
                LIMIT $2
                  FOR UPDATE SKIP LOCKED)
        RETURNING session_id, key, kind
        """,
        STALE_CLAIM,
        BATCH,
    )


async def analyse_batch(pool: asyncpg.Pool, objects: ObjectStore, engine: FaceEngine) -> set[uuid.UUID]:
    touched: set[uuid.UUID] = set()
    for row in await claim(pool):
        data = await objects.get_bytes(row["key"])
        if data is None:
            result = {"missing": True}
        else:
            frame = await asyncio.to_thread(engine.analyse, data, row["kind"] != "screen")
            result = frame.to_json() | ({"embedding": frame.embedding} if frame.embedding else {})
            if row["kind"] == "reference" and frame.embedding:
                await pool.execute(
                    "UPDATE sessions SET reference_embedding = $2 WHERE id = $1",
                    row["session_id"],
                    json.dumps(frame.embedding),
                )
        await pool.execute(
            "UPDATE uploads SET analysis = $3 WHERE session_id = $1 AND key = $2",
            row["session_id"],
            row["key"],
            json.dumps(result),
        )
        touched.add(row["session_id"])
    return touched


async def rescore(pool: asyncpg.Pool, store: PgStore, session_id: uuid.UUID) -> None:
    session = await pool.fetchrow(
        "SELECT s.reference_embedding, s.precheck, r.embedding AS institutional"
        " FROM sessions s LEFT JOIN reference_photos r ON r.moodle_user_id = s.moodle_user_id AND r.status = 'valid'"
        " WHERE s.id = $1",
        session_id,
    )
    # Institutional (admission) photo first; the live reference from the pre-check otherwise.
    reference = json.loads(session["institutional"] or session["reference_embedding"] or "null")
    frames = [
        Frame(r["key"], r["kind"], r["captured_at"], json.loads(r["analysis"]))
        for r in await pool.fetch(
            "SELECT key, kind, captured_at, analysis FROM uploads"
            " WHERE session_id = $1 AND analysis IS NOT NULL AND kind IN ('camera', 'screen')",
            session_id,
        )
    ]
    events = [
        PageEvent(r["type"], r["client_ts"], json.loads(r["payload"]))
        for r in await pool.fetch("SELECT type, client_ts, payload FROM events WHERE session_id = $1", session_id)
    ]
    device = {k: v for k, v in json.loads(session["precheck"] or "{}").items() if v not in ("ok", True, None)}
    flags = all_flags(frames, events, reference, device)
    score = compute(flags)
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM flags WHERE session_id = $1", session_id)
        await conn.executemany(
            "INSERT INTO flags (session_id, idx, type, severity, confidence, start_ts, end_ts, evidence, context,"
            " question) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            [
                (
                    session_id,
                    i,
                    f.type,
                    f.severity,
                    f.confidence,
                    f.start,
                    f.end,
                    json.dumps(f.evidence),
                    json.dumps(f.context),
                    f.question,
                )
                for i, f in enumerate(flags)
            ],
        )
        previous = await conn.fetchrow("SELECT value, band FROM scores WHERE session_id = $1", session_id)
        await conn.execute(
            "INSERT INTO scores (session_id, value, band, reasons, version, computed_at)"
            " VALUES ($1, $2, $3, $4, $5, now()) ON CONFLICT (session_id) DO UPDATE"
            " SET value = $2, band = $3, reasons = $4, version = $5, computed_at = now()",
            session_id,
            score.value,
            score.band,
            json.dumps(score.reasons),
            score.version,
        )
    if previous is None or previous["value"] != score.value or previous["band"] != score.band:
        await store.enqueue(
            "score.updated",
            {
                "session_id": str(session_id),
                "integrity_score": score.value,
                "band": score.band,
                "flag_count": len(flags),
                "questions": question_counts(flags),
                "version": score.version,
            },
        )


def question_counts(flags: list) -> dict[str, int]:
    """Flags per question element id (for example question-12-3), for badges on Moodle's review page."""
    counts: dict[str, int] = {}
    for f in flags:
        if f.question:
            counts[f.question] = counts.get(f.question, 0) + 1
    return counts


async def run(settings: Settings) -> None:
    store = await PgStore.connect(settings.database_url)
    objects = S3ObjectStore(settings)
    engine = FaceEngine(MODELS)
    bus = RedisBus(settings.redis_url)
    log.info("worker ready")
    try:
        while True:
            touched = await analyse_batch(store.pool, objects, engine)
            for session_id in touched:
                await rescore(store.pool, store, session_id)
                quiz_id = await store.pool.fetchval("SELECT quiz_id FROM sessions WHERE id = $1", session_id)
                await bus.publish(quiz_id, {"type": "scored", "session_id": str(session_id)})
            if not touched:
                await asyncio.sleep(1)
    finally:
        await bus.close()
        await store.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run(get_settings()))
