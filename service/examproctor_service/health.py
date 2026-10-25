"""Liveness and readiness checks against the service's own dependencies."""

import asyncio

import asyncpg
import httpx
from redis import asyncio as aioredis

from .config import Settings


async def check_postgres(settings: Settings) -> None:
    conn = await asyncpg.connect(settings.database_url, timeout=settings.dependency_timeout_s)
    try:
        await conn.fetchval("SELECT 1")
    finally:
        await conn.close()


async def check_redis(settings: Settings) -> None:
    client = aioredis.from_url(settings.redis_url, socket_timeout=settings.dependency_timeout_s)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def check_object_store(settings: Settings) -> None:
    async with httpx.AsyncClient(timeout=settings.dependency_timeout_s) as client:
        url = f"{settings.object_store_url}{settings.object_store_health_path}"
        response = await client.get(url)
        response.raise_for_status()


CHECKS = {
    "postgres": check_postgres,
    "redis": check_redis,
    "object_store": check_object_store,
}


async def run_checks(settings: Settings, checks=CHECKS) -> dict[str, str]:
    async def run(check) -> str:
        try:
            await asyncio.wait_for(check(settings), settings.dependency_timeout_s + 1)
            return "ok"
        except Exception as exc:  # any dependency failure is reported as a status
            return f"error: {type(exc).__name__}"

    names = list(checks)
    results = await asyncio.gather(*(run(checks[name]) for name in names))
    return dict(zip(names, results, strict=True))
