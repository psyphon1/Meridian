from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"

    github_app_id: int
    github_private_key: SecretStr
    github_webhook_secret: SecretStr

    database_url: str
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
