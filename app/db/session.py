"""
Async database engine and session factory.

We use SQLAlchemy 2.x's native async support with the asyncpg driver. The engine
is created at import time (lazy connection — no actual DB hit until the first
query) and reused across the whole application via FastAPI's dependency system.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────
# `pool_pre_ping=True` tests connections before use, which prevents stale
# connection errors after database restarts or network blips.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    future=True,
)

# ── Session factory ───────────────────────────────────────────────────────
# expire_on_commit=False keeps ORM objects usable after `commit()` without
# re-querying — important for returning objects from API handlers.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise
        finally:
            await session.close()
