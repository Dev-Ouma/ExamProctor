import json
import time
import uuid

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from examproctor_service.config import Settings, get_settings
from examproctor_service.main import create_app
from examproctor_service.objectstore import MemoryObjectStore
from examproctor_service.store import MemoryStore
from examproctor_service.webhooks import sign

SECRET = "moodle-shared-secret-for-tests-0123456789abcdef"


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("EXAMPROCTOR_MOODLE_SHARED_SECRET", SECRET)
    monkeypatch.setenv("EXAMPROCTOR_SESSION_SIGNING_KEY", "session-key-for-tests-0123456789")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


class FakeMoodle:
    """Records webhooks and checks their signatures like local_examproctor does."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.received: list[dict] = []
        self.status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        expected = sign(
            self.settings.moodle_shared_secret,
            request.headers["X-ExamProctor-Timestamp"],
            request.headers["X-ExamProctor-Nonce"],
            body,
        )
        assert request.headers["X-ExamProctor-Signature"] == expected
        if self.status == 200:
            self.received.append(json.loads(body))
        return httpx.Response(self.status, json={"ok": self.status == 200})


@pytest.fixture
def moodle(settings):
    return FakeMoodle(settings)


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def objects():
    return MemoryObjectStore()


@pytest.fixture
def client(settings, store, moodle, objects):
    http = httpx.AsyncClient(transport=httpx.MockTransport(moodle.handler))
    with TestClient(create_app(store=store, http=http, objects=objects)) as test_client:
        yield test_client


def launch_token(settings: Settings, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": settings.moodle_issuer,
        "aud": settings.launch_audience,
        "sub": "42",
        "course_id": 2,
        "cmid": 7,
        "quiz_id": 3,
        "attempt_id": None,
        "policy": {"camera": True, "screen": True, "strict": True},
        "iat": now,
        "exp": now + 120,
        "jti": uuid.uuid4().hex,
    }
    claims.update(overrides)
    return jwt.encode(claims, settings.moodle_shared_secret, algorithm="HS256")
