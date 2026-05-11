"""
Centralized logging configuration.

Uses Python's stdlib logging with a structured-ish format suitable for both
local development (human readable) and production (parseable by log aggregators).
"""
import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Configure root logger. Call once at application startup."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    # Clear any existing handlers attached by frameworks (e.g. uvicorn's default)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Tame noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DB_ECHO else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Convenience factory so modules can do `logger = get_logger(__name__)`."""
    return logging.getLogger(name)
