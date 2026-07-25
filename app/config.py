"""Central settings — all config from environment variables via pydantic-settings."""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "PRScope"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "prscope"
    POSTGRES_PASSWORD: str = "prscope_dev"
    POSTGRES_DB: str = "prscope"

    @computed_field  # type: ignore[misc]
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # GitHub
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/github/callback"
    ENABLE_GITHUB_POSTING: bool = False

    # Encryption (Fernet key for GitHub tokens in DB)
    ENCRYPTION_KEY: str = ""

    # LLM
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
