from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.ai_service import AIService


def _build_ai_service():
    reservation_service = SimpleNamespace(
        check_availability=AsyncMock(),
        assess_booking_availability=AsyncMock(),
        suggest_alternative_slots=AsyncMock(),
        update_reservation=AsyncMock(),
        create_reservation=AsyncMock(),
    )

    service = AIService(
        conversation_repo=SimpleNamespace(),
        reservation_service=reservation_service,
        restaurant_repo=SimpleNamespace(),
    )

    return service, reservation_service


@pytest.mark.asyncio
async def test_modification_check_availability_passes_reservation_id():
    service, reservation_service = _build_ai_service()

    reservation_id = uuid4()
    restaurant_id = uuid4()

    reservation_service.check_availability.return_value = True

    requested_time = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    result, returned_reservation_id = await service._execute_tool(
        name="check_availability",
        raw_arguments=(
            "{"
            f'"reservation_time": "{requested_time.isoformat()}",'
            '"party_size": 6,'
            f'"reservation_id": "{reservation_id}",'
            '"customer_provided_date": true,'
            '"customer_provided_time": true,'
            '"customer_provided_party_size": true'
            "}"
        ),
        restaurant_id=restaurant_id,
    )

    assert result["available"] is True
    assert result["booking_outcome"] == "direct_available"
    assert returned_reservation_id is None

    reservation_service.check_availability.assert_awaited_once_with(
        reservation_time=requested_time,
        party_size=6,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    reservation_service.assess_booking_availability.assert_not_awaited()


@pytest.mark.asyncio
async def test_modification_alternatives_pass_reservation_id():
    service, reservation_service = _build_ai_service()

    reservation_id = uuid4()
    restaurant_id = uuid4()

    requested_time = datetime(
        2026,
        9,
        26,
        12,
        0,
        tzinfo=timezone.utc,
    )

    alternative_time = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    reservation_service.suggest_alternative_slots.return_value = [
        alternative_time,
    ]

    result, returned_reservation_id = await service._execute_tool(
        name="suggest_alternative_slots",
        raw_arguments=(
            "{"
            f'"reservation_time": "{requested_time.isoformat()}",'
            '"party_size": 6,'
            f'"reservation_id": "{reservation_id}"'
            "}"
        ),
        restaurant_id=restaurant_id,
    )

    assert result == {
        "suggestions": [
            alternative_time.isoformat(),
        ]
    }

    assert returned_reservation_id is None

    reservation_service.suggest_alternative_slots.assert_awaited_once_with(
        reservation_time=requested_time,
        party_size=6,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )


@pytest.mark.asyncio
async def test_accepted_modification_alternative_updates_same_reservation():
    service, reservation_service = _build_ai_service()

    reservation_id = uuid4()
    restaurant_id = uuid4()

    accepted_time = datetime(
        2026,
        9,
        26,
        13,
        0,
        tzinfo=timezone.utc,
    )

    updated_reservation = SimpleNamespace(
        id=reservation_id,
        reservation_time=accepted_time,
        party_size=6,
        status=SimpleNamespace(
            value="confirmed",
        ),
    )

    reservation_service.update_reservation.return_value = (
        updated_reservation
    )

    result, returned_reservation_id = await service._execute_tool(
        name="update_reservation",
        raw_arguments=(
            "{"
            f'"reservation_id": "{reservation_id}",'
            f'"reservation_time": "{accepted_time.isoformat()}",'
            '"party_size": 6'
            "}"
        ),
        restaurant_id=restaurant_id,
    )

    assert result["success"] is True
    assert result["reservation_id"] == str(reservation_id)
    assert result["updated_time"] == accepted_time.isoformat()
    assert result["party_size"] == 6
    assert result["status"] == "confirmed"

    assert returned_reservation_id == reservation_id

    reservation_service.update_reservation.assert_awaited_once()

    call = reservation_service.update_reservation.await_args

    assert call.kwargs["reservation_id"] == reservation_id
    assert call.kwargs["payload"].reservation_time == accepted_time
    assert call.kwargs["payload"].party_size == 6

    reservation_service.create_reservation.assert_not_awaited()