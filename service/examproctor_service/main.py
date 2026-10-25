"""FastAPI application entry point."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings, get_settings
from .health import run_checks

SettingsDep = Annotated[Settings, Depends(get_settings)]

app = FastAPI(title="ExamProctor service", version=__version__)


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
