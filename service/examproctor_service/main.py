"""FastAPI application entry point."""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api import router as sessions_router
from .config import Settings, get_settings
from .evidence import router as evidence_router
from .health import run_checks
from .live import router as live_router
from .live_store import MemoryActionStore, MemoryBus, PgActionStore, RedisBus
from .objectstore import ObjectStore, S3ObjectStore
from .privacy import router as privacy_router
from .refphotos import router as refphotos_router
from .refstore import MemoryRefStore, PgRefStore
from .retention import loop as retention_loop
from .review import router as review_router
from .review_store import MemoryReviewStore, PgReviewStore
from .store import PgStore, Store
from .webhooks import retry_loop

SettingsDep = Annotated[Settings, Depends(get_settings)]


def create_app(
    store: Store | None = None,
    http: httpx.AsyncClient | None = None,
    objects: ObjectStore | None = None,
) -> FastAPI:
    """Build the app. Tests pass an in-memory store and a mock HTTP client."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned_store = store is None
        app.state.store = store or await PgStore.connect(settings.database_url)
        app.state.http = http or httpx.AsyncClient(timeout=10)
        app.state.objects = objects or S3ObjectStore(settings)
        app.state.refs = PgRefStore(app.state.store.pool) if owned_store else MemoryRefStore()
        if owned_store:
            app.state.reviews = PgReviewStore(app.state.store.pool)
            await app.state.reviews.migrate()
            app.state.actions = PgActionStore(app.state.store.pool)
            await app.state.actions.migrate()
            app.state.bus = RedisBus(settings.redis_url)
        else:
            app.state.reviews = MemoryReviewStore(app.state.store)
            app.state.actions = MemoryActionStore()
            app.state.bus = MemoryBus()
        background = []
        if owned_store:
            await app.state.objects.ensure_bucket()
            background = [
                asyncio.create_task(retry_loop(app.state.store, settings, app.state.http)),
                asyncio.create_task(retention_loop(app.state.store, app.state.objects, settings)),
            ]
        try:
            yield
        finally:
            for task in background:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            if owned_store:
                await app.state.bus.close()
                await app.state.store.close()
            if http is None:
                await app.state.http.aclose()

    app = FastAPI(title="ExamProctor service", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],  # admin PUT/DELETE are server-to-server only
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        # JSON API: never sniffed, framed, cached or given a referrer.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(HTTPException)
    async def error_body(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
        detail = {**detail, "request_id": getattr(request.state, "request_id", None)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @app.get("/v1/health")
    async def health(settings: SettingsDep) -> dict[str, str]:
        """Liveness: the process is up. No dependency calls."""
        return {"status": "ok", "version": __version__, "env": settings.env}

    @app.get("/v1/health/ready")
    async def ready(settings: SettingsDep) -> JSONResponse:
        """Readiness: Postgres, Redis and the object store all answer."""
        checks = await run_checks(settings)
        ok = all(result == "ok" for result in checks.values())
        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "checks": checks},
        )

    app.include_router(sessions_router)
    app.include_router(evidence_router)
    app.include_router(refphotos_router)
    app.include_router(review_router)
    app.include_router(privacy_router)
    app.include_router(live_router)
    return app


app = create_app()
