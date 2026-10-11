import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.ai_service import AIService
from app.services.reservation_access_context import ReservationAccessContext


@pytest.fixture
def setup_notes():
    reservation_id = uuid4()
    restaurant_id = uuid4()

    reservation_service = SimpleNamespace(
        get_reservation=AsyncMock(
            return_value=SimpleNamespace(
                special_requests="Allergia alle arachidi."
            )
        ),
        update_reservation=AsyncMock(
            return_value=SimpleNamespace(
                id=reservation_id,
                reservation_time=datetime(
                    2026, 10, 17, 19, 30, tzinfo=timezone.utc
                ),
                party_size=2,
                status=SimpleNamespace(value="confirmed"),
            )
        ),
    )

    service = AIService(
        conversation_repo=SimpleNamespace(),
        reservation_service=reservation_service,
        restaurant_repo=SimpleNamespace(),
    )

    return service, reservation_service, reservation_id, restaurant_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation,incoming,expected",
    [
        (
            "append",
            "Tavolo vicino alla finestra.",
            "Allergia alle arachidi.\nTavolo vicino alla finestra.",
        ),
        (
            "append",
            "Allergia alle arachidi.",
            "Allergia alle arachidi.",
        ),
        (
            "replace",
            "Nessuna allergia.",
            "Nessuna allergia.",
        ),
        (
            "clear",
            None,
            "",
        ),
    ],
)
async def test_notes_operations(
    setup_notes, operation, incoming, expected
):
    service, repository, reservation_id, restaurant_id = setup_notes

    arguments = {
        "reservation_id": str(reservation_id),
        "notes_operation": operation,
    }

    if incoming is not None:
        arguments["special_requests"] = incoming

    result, _ = await service._execute_tool(
        name="update_reservation",
        raw_arguments=json.dumps(arguments),
        restaurant_id=restaurant_id,
        access_context=ReservationAccessContext(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
        ),
    )

    assert result["success"] is True

    repository.get_reservation.assert_awaited_once_with(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
    )

    payload = repository.update_reservation.await_args.kwargs["payload"]
    assert payload.special_requests == expected


@pytest.mark.asyncio
async def test_time_only_modification_does_not_touch_notes(setup_notes):
    service, repository, reservation_id, restaurant_id = setup_notes

    result, _ = await service._execute_tool(
        name="update_reservation",
        raw_arguments=json.dumps({
            "reservation_id": str(reservation_id),
            "reservation_time": "2026-10-18T19:30:00+00:00",
        }),
        restaurant_id=restaurant_id,
        access_context=ReservationAccessContext(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
        ),
    )

    assert result["success"] is True
    repository.get_reservation.assert_not_awaited()

    payload = repository.update_reservation.await_args.kwargs["payload"]
    assert "special_requests" not in payload.model_fields_set


@pytest.mark.asyncio
async def test_unauthorized_notes_modification_is_blocked(setup_notes):
    service, repository, reservation_id, restaurant_id = setup_notes

    result, _ = await service._execute_tool(
        name="update_reservation",
        raw_arguments=json.dumps({
            "reservation_id": str(uuid4()),
            "special_requests": "Elimina allergia.",
            "notes_operation": "replace",
        }),
        restaurant_id=restaurant_id,
        access_context=ReservationAccessContext(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
        ),
    )

    assert result.get("success") is not True
    repository.get_reservation.assert_not_awaited()
    repository.update_reservation.assert_not_awaited()
