"""
Application configuration.

All settings are loaded from environment variables (or a .env file in development)
using pydantic-settings. This gives us type-safe config with validation at startup —
if a required env var is missing or malformed, the app fails fast rather than
crashing later at runtime.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
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
    # Async URL used by the FastAPI app (asyncpg driver)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/restaurant_ai",
        description="Async PostgreSQL connection string (asyncpg)",
    )
    # Sync URL used by Alembic migrations (psycopg2 driver)
    SYNC_DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/restaurant_ai",
        description="Sync PostgreSQL connection string (psycopg2) for Alembic",
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False  # Set True to log all SQL (dev only)

    # ── OpenAI ────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key (required)")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 800
    OPENAI_TIMEOUT_SECONDS: float = 30.0

    # ── Conversation memory ───────────────────────────────────────────────
    # How many past message pairs to include in the LLM context. Trimming the
    # window keeps token costs predictable while still feeling "stateful".
    CONVERSATION_HISTORY_LIMIT: int = 20

    # ── Restaurant business rules ─────────────────────────────────────────
    RESTAURANT_NAME: str = "La Maison"
    RESTAURANT_TIMEZONE: str = "America/New_York"
    OPENING_HOUR: int = 11   # 11:00 (24h)
    CLOSING_HOUR: int = 22   # 22:00 (24h)
    MAX_PARTY_SIZE: int = 12
    MIN_PARTY_SIZE: int = 1
    RESERVATION_DURATION_MINUTES: int = 90  # Default table booking length
    MAX_DAILY_CAPACITY: int = 80  # Total seats available per service

    # ── Security ──────────────────────────────────────────────────────────
    # Comma-separated list of allowed CORS origins
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:3000"

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    """
    Return the application settings singleton.

    `lru_cache` ensures we only instantiate Settings once per process — this
    avoids re-reading the .env file on every dependency injection call.
    """
    return Settings()  # type: ignore[call-arg]


# Module-level convenience handle. Most code can `from app.core.config import settings`.
settings = get_settings()
