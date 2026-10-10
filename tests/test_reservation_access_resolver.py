"""Tests for server-side customer access token resolution."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.reservation_access_service import ReservationAccessService


@pytest.fixture
def resolver_setup():
    db = MagicMock()
    db.execute = AsyncMock()

    service = ReservationAccessService(db)

    restaurant_id = uuid.uuid4()
    reservation_id = uuid.uuid4()

    return service, db, restaurant_id, reservation_id


@pytest.mark.asyncio
async def test_valid_token_resolves_to_correct_reservation(resolver_setup):
    service, db, restaurant_id, reservation_id = resolver_setup

    result = MagicMock()
    result.one_or_none.return_value = SimpleNamespace(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )
    db.execute.return_value = result

    context = await service.resolve("valid-token", restaurant_id)

    assert context is not None
    assert context.restaurant_id == restaurant_id
    assert context.reservation_id == reservation_id
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["", "x" * 513, None])
async def test_invalid_token_rejected_without_database_query(
    resolver_setup,
    token,
):
    service, db, restaurant_id, _ = resolver_setup

    context = await service.resolve(token, restaurant_id)

    assert context is None
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_or_expired_token_returns_no_context(resolver_setup):
    service, db, restaurant_id, _ = resolver_setup

    result = MagicMock()
    result.one_or_none.return_value = None
    db.execute.return_value = result

    context = await service.resolve("invalid-token", restaurant_id)

    assert context is None


@pytest.mark.asyncio
async def test_resolver_query_enforces_security_constraints(resolver_setup):
    service, db, restaurant_id, _ = resolver_setup

    result = MagicMock()
    result.one_or_none.return_value = None
    db.execute.return_value = result

    await service.resolve("customer-token", restaurant_id)

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(compiled).lower()

    assert "token_hash" in sql
    assert "restaurant_id" in sql
    assert "revoked_at is null" in sql
    assert "expires_at >" in sql

    parameters = compiled.params
    assert service._hash_token("customer-token") in parameters.values()
    assert restaurant_id in parameters.values()
    assert "customer-token" not in parameters.values()
