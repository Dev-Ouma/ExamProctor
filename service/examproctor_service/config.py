"""Service configuration, read from EXAMPROCTOR_* environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXAMPROCTOR_")

    env: Literal["dev", "staging", "live"] = "dev"
    database_url: str = "postgresql://examproctor:examproctor@localhost:5432/examproctor"
    redis_url: str = "redis://localhost:6379/0"
    object_store_url: str = "http://localhost:8333"
    object_store_health_path: str = "/healthz"
    dependency_timeout_s: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
