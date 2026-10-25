"""Reference photo records (embedding + validation status)."""

import json
from datetime import UTC, datetime
from typing import Any, Protocol

import asyncpg


class RefStore(Protocol):
    async def upsert(
        self, user_id: int, key: str, status: str, reason: str | None, face_px: int, embedding: list[float] | None
    ) -> None: ...
    async def get(self, user_id: int) -> dict[str, Any] | None: ...
    async def delete(self, user_id: int) -> bool: ...


class MemoryRefStore:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}

    async def upsert(self, user_id, key, status, reason, face_px, embedding) -> None:
        self.rows[user_id] = {
            "user_id": user_id,
            "key": key,
            "status": status,
            "reason": reason,
            "face_px": face_px,
            "embedding": embedding,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    async def get(self, user_id: int) -> dict[str, Any] | None:
        return self.rows.get(user_id)

    async def delete(self, user_id: int) -> bool:
        return self.rows.pop(user_id, None) is not None


class PgRefStore:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def upsert(self, user_id, key, status, reason, face_px, embedding) -> None:
        await self.pool.execute(
            "INSERT INTO reference_photos (moodle_user_id, key, status, reason, face_px, embedding, updated_at)"
            " VALUES ($1, $2, $3, $4, $5, $6, now()) ON CONFLICT (moodle_user_id) DO UPDATE SET key = $2,"
            " status = $3, reason = $4, face_px = $5, embedding = $6, updated_at = now()",
            user_id,
            key,
            status,
            reason,
            face_px,
            json.dumps(embedding) if embedding else None,
        )

    async def get(self, user_id: int) -> dict[str, Any] | None:
        row = await self.pool.fetchrow("SELECT * FROM reference_photos WHERE moodle_user_id = $1", user_id)
        if row is None:
            return None
        return {
            "user_id": row["moodle_user_id"],
            "key": row["key"],
            "status": row["status"],
            "reason": row["reason"],
            "face_px": row["face_px"],
            "embedding": json.loads(row["embedding"]) if row["embedding"] else None,
            "updated_at": row["updated_at"].isoformat(),
        }

    async def delete(self, user_id: int) -> bool:
        return (await self.pool.execute("DELETE FROM reference_photos WHERE moodle_user_id = $1", user_id)).endswith(
            " 1"
        )
