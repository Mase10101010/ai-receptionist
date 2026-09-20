import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_service import (
    AIService,
    _missing_required_booking_intent,
)

from app.services.ai_service import (
    AIService,
    BookingAvailabilityOutcome,
    _missing_required_booking_intent,
)


def _build_ai_service():
    conversation_repo = MagicMock()
    reservation_service = MagicMock()
    restaurant_repo = MagicMock()

    reservation_service.assess_booking_availability = AsyncMock()
    reservation_service.create_reservation = AsyncMock()

    service = AIService(
        conversation_repo=conversation_repo,
        reservation_service=reservation_service,
        restaurant_repo=restaurant_repo,
    )

    return service, reservation_service


def test_missing_time_is_detected():
    arguments = {
        "customer_provided_date": True,
        "customer_provided_time": False,
        "customer_provided_party_size": True,
    }

    assert _missing_required_booking_intent(arguments) == ["time"]


def test_missing_date_is_detected():
    arguments = {
        "customer_provided_date": False,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    assert _missing_required_booking_intent(arguments) == ["date"]


def test_missing_party_size_is_detected():
    arguments = {
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": False,
    }

    assert _missing_required_booking_intent(arguments) == ["party_size"]


def test_missing_provenance_flags_fail_closed():
    assert _missing_required_booking_intent({}) == [
        "date",
        "time",
        "party_size",
    ]


def test_complete_booking_intent_is_allowed():
    arguments = {
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    assert _missing_required_booking_intent(arguments) == []


@pytest.mark.asyncio
async def test_invented_time_cannot_reach_availability_service():
    service, reservation_service = _build_ai_service()

    arguments = {
        "reservation_time": "2026-09-25T11:00:00",
        "party_size": 6,
        "customer_provided_date": True,
        "customer_provided_time": False,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "check_availability",
        json.dumps(arguments),
    )

    assert reservation_id is None
    assert result["error"] == "missing_customer_booking_intent"
    assert result["missing_fields"] == ["time"]

    reservation_service.assess_booking_availability.assert_not_awaited()


@pytest.mark.asyncio
async def test_invented_time_cannot_reach_create_reservation():
    service, reservation_service = _build_ai_service()

    arguments = {
        "customer_name": "Mario Rossi",
        "customer_phone": "3333333333",
        "customer_email": "mario@example.com",
        "party_size": 6,
        "reservation_time": "2026-09-25T11:00:00",
        "special_requests": "",
        "customer_provided_date": True,
        "customer_provided_time": False,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
    )

    assert reservation_id is None
    assert result["error"] == "missing_customer_booking_intent"
    assert result["missing_fields"] == ["time"]

    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_date_and_time_cannot_reach_create_reservation():
    service, reservation_service = _build_ai_service()

    arguments = {
        "customer_name": "Mario Rossi",
        "customer_phone": "3333333333",
        "customer_email": "mario@example.com",
        "party_size": 6,
        "reservation_time": "2026-09-25T11:00:00",
        "special_requests": "",
        "customer_provided_date": False,
        "customer_provided_time": False,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
    )

    assert reservation_id is None
    assert result["error"] == "missing_customer_booking_intent"
    assert result["missing_fields"] == ["date", "time"]

    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_party_size_cannot_reach_create_reservation():
    service, reservation_service = _build_ai_service()

    arguments = {
        "customer_name": "Mario Rossi",
        "customer_phone": "3333333333",
        "customer_email": "mario@example.com",
        "party_size": 6,
        "reservation_time": "2026-09-25T19:00:00",
        "special_requests": "",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": False,
    }

    result, reservation_id = await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
    )

    assert reservation_id is None
    assert result["error"] == "missing_customer_booking_intent"
    assert result["missing_fields"] == ["party_size"]

    reservation_service.create_reservation.assert_not_awaited()

@pytest.mark.asyncio
async def test_complete_intent_reaches_availability_service():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    arguments = {
        "reservation_time": "2026-09-25T19:00:00",
        "party_size": 6,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "check_availability",
        json.dumps(arguments),
    )

    assert reservation_id is None
    assert result["booking_outcome"] == "direct_available"

    reservation_service.assess_booking_availability.assert_awaited_once()

@pytest.mark.asyncio
async def test_complete_intent_reaches_create_reservation():
    service, reservation_service = _build_ai_service()

    fake_reservation = MagicMock()
    fake_reservation.id = __import__("uuid").uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Mario Rossi"
    fake_reservation.customer_email = "mario@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 6
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-09-25T19:00:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation

    arguments = {
        "customer_name": "Mario Rossi",
        "customer_phone": "3333333333",
        "customer_email": "mario@example.com",
        "party_size": 6,
        "reservation_time": "2026-09-25T19:00:00",
        "special_requests": "",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
    )

    assert result["success"] is True
    assert result["status"] == "confirmed"
    assert result["reservation_time"] == "2026-09-25T19:00:00"
    assert reservation_id == fake_reservation.id

    reservation_service.create_reservation.assert_awaited_once()

    payload = reservation_service.create_reservation.await_args.args[0]

    assert payload.party_size == 6
    assert payload.reservation_time.isoformat() == "2026-09-25T19:00:00"

@pytest.mark.asyncio
async def test_completion_loop_recovers_from_invented_time_and_asks_guest():
    service, reservation_service = _build_ai_service()

    first_tool_call = MagicMock()
    first_tool_call.id = "call_missing_time"
    first_tool_call.function.name = "check_availability"
    first_tool_call.function.arguments = json.dumps(
        {
            "reservation_time": "2026-09-25T11:00:00",
            "party_size": 6,
            "customer_provided_date": True,
            "customer_provided_time": False,
            "customer_provided_party_size": True,
        }
    )

    first_message = MagicMock()
    first_message.content = None
    first_message.tool_calls = [first_tool_call]

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=first_message)]

    second_message = MagicMock()
    second_message.content = "Che orario preferisci?"
    second_message.tool_calls = None

    second_response = MagicMock()
    second_response.choices = [MagicMock(message=second_message)]

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            first_response,
            second_response,
        ]
    )

    messages = [
        {
            "role": "system",
            "content": "Test system prompt",
        },
        {
            "role": "user",
            "content": (
                "Ciao, vorrei prenotare un tavolo per "
                "6 persone il 25 settembre."
            ),
        },
    ]

    reply, reservation_id = await service._run_completion_loop(
        messages=messages,
        restaurant_id=None,
        session_id="lab-005-test",
    )

    assert reply == "Che orario preferisci?"
    assert reservation_id is None

    reservation_service.assess_booking_availability.assert_not_awaited()
    reservation_service.create_reservation.assert_not_awaited()

    assert service.client.chat.completions.create.await_count == 2

    tool_messages = [
        message
        for message in messages
        if message.get("role") == "tool"
    ]

    assert len(tool_messages) == 1

    tool_result = json.loads(tool_messages[0]["content"])

    assert tool_result["error"] == "missing_customer_booking_intent"
    assert tool_result["missing_fields"] == ["time"]