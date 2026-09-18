"""
Shared pytest fixtures.

We use an in-memory SQLite DB for tests (via aiosqlite) so the suite is fast
and hermetic. The few PG-specific bits (UUID column type) work on SQLite via
SQLAlchemy's compatibility layer.
"""
import asyncio
import os
from collections.abc import AsyncGenerator

# Set required env vars BEFORE importing app code
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///:memory:")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import *  # noqa: F401, F403 — register models on metadata

from types import SimpleNamespace
from uuid import uuid4

from app.api.dependencies import get_current_user

from app.api.v1.endpoints.reservations import (
    get_current_user_restaurant_ids,
)

from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory DB for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX async test client with a real restaurant workspace."""

    async def _override_get_db():
        yield db_session

    test_user = User(
        email=f"test-{uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )

    db_session.add(test_user)
    await db_session.flush()

    test_restaurant = Restaurant(
        owner_id=test_user.id,
        name="Alias Test Restaurant",
        slug=f"alias-test-{uuid4()}",
        opening_hour=0,
        closing_hour=23,
        number_of_tables=4,
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )

    db_session.add(test_restaurant)
    await db_session.flush()

    service_area = ServiceArea(
        restaurant_id=test_restaurant.id,
        name="Main Dining Room",
        area_type="indoor",
        is_active=True,
    )

    db_session.add(service_area)
    await db_session.flush()

    test_tables = [
        Table(
            restaurant_id=test_restaurant.id,
            service_area_id=service_area.id,
            table_code=f"T{i}",
            table_number=str(i),
            seats=4,
            is_active=True,
        )
        for i in range(1, 5)
    ]

    db_session.add_all(test_tables)
    await db_session.flush()

    async def _override_get_current_user():
        return test_user

    async def _override_get_current_user_restaurant_ids():
        return [test_restaurant.id]

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = (
        _override_get_current_user
    )
    app.dependency_overrides[
        get_current_user_restaurant_ids
    ] = _override_get_current_user_restaurant_ids

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()