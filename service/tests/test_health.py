from fastapi.testclient import TestClient

from examproctor_service import health
from examproctor_service.config import Settings, get_settings
from examproctor_service.main import app

client = TestClient(app)


def test_liveness_reports_version_and_env():
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "env": "dev"}


async def test_run_checks_reports_each_dependency():
    async def passes(_settings):
        return None

    async def fails(_settings):
        raise ConnectionRefusedError

    result = await health.run_checks(Settings(), {"a": passes, "b": fails})

    assert result == {"a": "ok", "b": "error: ConnectionRefusedError"}


def test_readiness_returns_503_when_a_dependency_is_down(monkeypatch):
    async def fake_checks(_settings):
        return {"postgres": "ok", "redis": "error: TimeoutError", "object_store": "ok"}

    monkeypatch.setattr("examproctor_service.main.run_checks", fake_checks)
    app.dependency_overrides[get_settings] = Settings
    try:
        response = client.get("/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["redis"] == "error: TimeoutError"


def test_staging_refuses_short_keys():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(env="staging", moodle_shared_secret="short", session_signing_key="x" * 32)


def test_security_headers_on_every_response(client):
    for path in ("/v1/health", "/v1/review/quizzes/3/sessions"):
        headers = client.get(path).headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Cache-Control"] == "no-store"
