"""Service configuration, read from EXAMPROCTOR_* environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXAMPROCTOR_")

    env: Literal["dev", "staging", "live"] = "dev"
    database_url: str = "postgresql://examproctor:examproctor@localhost:5432/examproctor"
    redis_url: str = "redis://localhost:6379/0"
    object_store_url: str = "http://localhost:8333"
    object_store_health_path: str = "/healthz"
    dependency_timeout_s: float = 2.0

    # Moodle site this service trusts (single site in v1).
    moodle_issuer: str = "http://localhost:8080"
    moodle_shared_secret: str = ""  # same value as local_examproctor "signing key"
    moodle_webhook_url: str = "http://localhost:8080/local/examproctor/webhook.php"
    moodle_webhook_host: str | None = None  # Host header when calling Moodle on an internal name
    launch_audience: str = "examproctor-service"
    launch_max_lifetime_s: int = 120

    # Tokens this service issues to the browser.
    session_signing_key: str = ""
    session_token_ttl_s: int = 6 * 3600

    cors_origins: list[str] = ["http://localhost:8080"]
    consent_text_version: str = "2026-10-en-sw-1"
    webhook_retry_interval_s: float = 5.0

    @model_validator(mode="after")
    def require_strong_keys_outside_dev(self) -> "Settings":
        if self.env != "dev":
            for name in ("moodle_shared_secret", "session_signing_key"):
                if len(getattr(self, name)) < 32:
                    raise ValueError(f"EXAMPROCTOR_{name.upper()} must be at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
