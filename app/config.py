"""
config.py — Central settings module.

All config comes from environment variables (loaded from .env in dev).
Using pydantic-settings means:
  1. Every variable is type-checked automatically
  2. You get a clear error if a required var is missing
  3. No scattered os.getenv() calls across the codebase

lru_cache() means Settings() is only instantiated once — it's a singleton.
Import `settings` anywhere and you get the same object.
"""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Don't error on unknown env vars
    )

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "PRScope"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "prscope"
    POSTGRES_PASSWORD: str = "prscope_dev"
    POSTGRES_DB: str = "prscope"

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL URL built from individual parts."""
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # NOTE: We don't define a separate sync DATABASE_URL_SYNC.
    # Alembic migrations also run async (via async_engine_from_config in
    # alembic/env.py) — using the SAME asyncpg URL as the app itself.
    # One driver, one URL, one less thing that can drift out of sync.

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── GitHub ────────────────────────────────────────────────────────────────
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/github/callback"

    # ── Encryption ────────────────────────────────────────────────────────────
    # For encrypting GitHub access tokens in the database.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # ── LLM ───────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Single import target — use this everywhere:
#   from app.config import settings
settings = get_settings()
