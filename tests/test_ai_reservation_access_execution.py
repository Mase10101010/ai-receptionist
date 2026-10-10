"""Verify reservation authorization at the AI tool execution boundary."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_service import AIService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
        "get_reservation",
        "update_reservation",
        "cancel_reservation",
        "check_availability",
        "suggest_alternative_slots",
    ],
)
async def test_sensitive_tool_denied_before_service_call(tool_name):
    reservation_service = MagicMock()
    reservation_service.get_reservation = AsyncMock()
    reservation_service.update_reservation = AsyncMock()
    reservation_service.cancel_reservation = AsyncMock()
    reservation_service.assess_modification_availability = AsyncMock()
    reservation_service.suggest_alternative_slots = AsyncMock()

    ai_service = object.__new__(AIService)
    ai_service.reservation_service = reservation_service

    result, _ = await ai_service._execute_tool(
        tool_name,
        json.dumps({"reservation_id": str(uuid.uuid4())}),
        restaurant_id=uuid.uuid4(),
    )

    assert result == {"error": "reservation_access_denied"}

    reservation_service.get_reservation.assert_not_awaited()
    reservation_service.update_reservation.assert_not_awaited()
    reservation_service.cancel_reservation.assert_not_awaited()
    reservation_service.assess_modification_availability.assert_not_awaited()
    reservation_service.suggest_alternative_slots.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_update_reaches_reservation_service():
    from types import SimpleNamespace

    from app.services.reservation_access_context import ReservationAccessContext

    restaurant_id = uuid.uuid4()
    reservation_id = uuid.uuid4()
    other_reservation_id = uuid.uuid4()

    reservation_service = MagicMock()
    reservation_service.update_reservation = AsyncMock(
        return_value=SimpleNamespace(
            id=reservation_id,
            status=SimpleNamespace(value="confirmed"),
            reservation_time=None,
            party_size=2,
        )
    )

    ai_service = object.__new__(AIService)
    ai_service.reservation_service = reservation_service

    context = ReservationAccessContext(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    await ai_service._execute_tool(
        "update_reservation",
        json.dumps({
            "reservation_id": str(reservation_id),
            "special_requests": "LAB015 authorized test",
        }),
        restaurant_id=restaurant_id,
        access_context=context,
    )

    reservation_service.update_reservation.assert_awaited_once()

    reservation_service.update_reservation.reset_mock()

    result, _ = await ai_service._execute_tool(
        "update_reservation",
        json.dumps({
            "reservation_id": str(other_reservation_id),
            "special_requests": "LAB015 unauthorized test",
        }),
        restaurant_id=restaurant_id,
        access_context=context,
    )

    assert result == {"error": "reservation_access_denied"}
    reservation_service.update_reservation.assert_not_awaited()

@pytest.mark.asyncio
async def test_authorized_context_supplies_reservation_id_when_missing():
    from types import SimpleNamespace

    from app.services.reservation_access_context import ReservationAccessContext

    restaurant_id = uuid.uuid4()
    reservation_id = uuid.uuid4()

    reservation_service = MagicMock()
    reservation_service.get_reservation = AsyncMock(
        return_value=SimpleNamespace(
            id=reservation_id,
            customer_name="Authorized Guest",
            customer_email="guest@example.com",
            customer_phone="0400000000",
            party_size=2,
            reservation_time=__import__("datetime").datetime(
                2026, 10, 14, 11, 30,
                tzinfo=__import__("datetime").timezone.utc,
            ),
            special_requests="",
            status=SimpleNamespace(value="confirmed"),
        )
    )

    restaurant_repo = MagicMock()
    restaurant_repo.get_by_id = AsyncMock(return_value=None)

    ai_service = object.__new__(AIService)
    ai_service.reservation_service = reservation_service
    ai_service.restaurant_repo = restaurant_repo

    context = ReservationAccessContext(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    result, _ = await ai_service._execute_tool(
        "get_reservation",
        json.dumps({}),
        restaurant_id=restaurant_id,
        access_context=context,
    )

    reservation_service.get_reservation.assert_awaited_once_with(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
    )
    assert result["success"] is True
    assert result["reservation_id"] == str(reservation_id)
