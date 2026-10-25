"""Evidence retention: delete media for sessions past the retention period unless on legal hold."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from .config import Settings
from .objectstore import ObjectStore
from .store import Store

log = logging.getLogger(__name__)


async def run_once(store: Store, objects: ObjectStore, settings: Settings, now: datetime) -> int:
    """Purge eligible sessions. Returns the number of sessions purged.

    v1 counts the period from the session's end. Counting from "results finalised" needs the
    Moodle results event (M5) and replaces `ended_at` then.
    """
    cutoff = now - timedelta(days=settings.retention_days)
    purged = 0
    for session in await store.sessions_to_purge(cutoff):
        prefix = f"{settings.env}/{session.quiz_id}/{session.id}/"
        deleted = await objects.delete_prefix(prefix)
        session.purged_at = now
        await store.save_session(session)
        log.info("retention purged session %s (%d objects)", session.id, deleted)
        purged += 1
    return purged


async def loop(store: Store, objects: ObjectStore, settings: Settings) -> None:
    while True:
        try:
            await run_once(store, objects, settings, datetime.now(UTC))
        except Exception:
            log.exception("retention run failed")
        await asyncio.sleep(settings.retention_interval_s)
