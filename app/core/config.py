"""
Application configuration.

All settings are loaded from environment variables (or a .env file in development)
using pydantic-settings. This gives us type-safe config with validation at startup —
if a required env var is missing or malformed, the app fails fast rather than
crashing later at runtime.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application metadata ──────────────────────────────────────────────
    APP_NAME: str = "AI Restaurant Receptionist"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────────
    # Render gives us a normal postgresql:// URL. The app needs asyncpg.
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/restaurant_ai",
        description="Async PostgreSQL connection string for FastAPI",
    )

    # Optional. If missing, we derive it automatically from DATABASE_URL.
    SYNC_DATABASE_URL: str | None = Field(
        default=None,
        description="Sync PostgreSQL connection string for Alembic",
    )

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # ── OpenAI ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key (required)")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 800
    OPENAI_TIMEOUT_SECONDS: float = 30.0

    # ── Conversation memory ───────────────────────────────────────────────
    CONVERSATION_HISTORY_LIMIT: int = 20

    # ── Restaurant business rules ─────────────────────────────────────────
    RESTAURANT_NAME: str = "La Maison"
    RESTAURANT_TIMEZONE: str = "America/New_York"
    OPENING_HOUR: int = 11
    CLOSING_HOUR: int = 22
    MAX_PARTY_SIZE: int = 12
    MIN_PARTY_SIZE: int = 1
    RESERVATION_DURATION_MINUTES: int = 90
    MAX_DAILY_CAPACITY: int = 80

    # ── Security ──────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [] 
    
    @field_validator("CORS_ORIGINS", mode = "before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return[i.strip() for i in v.split(",")]
        return v
    def _normalize_database_url(cls, v: str) -> str:
        """
        FastAPI uses async SQLAlchemy, so force asyncpg for app runtime.

        Render often provides:
            postgresql://user:pass@host/db

        We convert it to:
            postgresql+asyncpg://user:pass@host/db
        """
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @property
    def sync_database_url(self) -> str:
        """
        Alembic uses sync SQLAlchemy, so force psycopg2 for migrations.
        """
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL

        url = self.DATABASE_URL

        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg2://", 1)

        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)

        return url

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()