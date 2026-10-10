import json
from unittest.mock import AsyncMock, MagicMock


import uuid

import pytest

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
async def test_create_reservation_exception_returns_error_not_success():
    service, reservation_service = _build_ai_service()
    reservation_service.create_reservation.side_effect = RuntimeError(
        "simulated reservation failure"
    )

    arguments = {
        "customer_name": "Mario Rossi",
        "customer_phone": "3333333333",
        "customer_email": "mario@example.com",
        "party_size": 2,
        "reservation_time": "2026-10-17T19:00:00",
        "special_requests": "",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
        restaurant_id=uuid.uuid4(),
        session_id="lab015-error-test",
    )

    assert result.get("success") is not True
    assert "error" in result
    assert reservation_id is None
    reservation_service.create_reservation.assert_awaited_once()


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

    reply, reservation_id, reservation_status, modification_status = await service._run_completion_loop(
        messages=messages,
        restaurant_id=None,
        session_id="lab-005-test",
    )

    assert reply == "Che orario preferisci?"
    assert reservation_id is None
    assert reservation_status is None
    assert modification_status is None

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

@pytest.mark.asyncio
async def test_completion_loop_propagates_pending_reservation_status():
    service, reservation_service = _build_ai_service()

    reservation_id = uuid.uuid4()

    fake_reservation = MagicMock()
    fake_reservation.id = reservation_id
    fake_reservation.status.value = "pending"
    fake_reservation.customer_name = "Luigi Fossato"
    fake_reservation.customer_email = "luigi@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 10
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-09-25T11:00:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation
    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE
    )

    check_tool_call = MagicMock()
    check_tool_call.id = "call_check_pending"
    check_tool_call.function.name = "check_availability"
    check_tool_call.function.arguments = json.dumps(
        {
            "party_size": 10,
            "reservation_time": "2026-09-25T11:00:00",
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    check_message = MagicMock()
    check_message.content = None
    check_message.tool_calls = [check_tool_call]
    check_response = MagicMock()
    check_response.choices = [MagicMock(message=check_message)]

    create_tool_call = MagicMock()
    create_tool_call.id = "call_create_pending"
    create_tool_call.function.name = "create_reservation"
    create_tool_call.function.arguments = json.dumps(
        {
            "customer_name": "Luigi Fossato",
            "customer_phone": "3333333333",
            "customer_email": "luigi@example.com",
            "party_size": 10,
            "reservation_time": "2026-09-25T11:00:00",
            "special_requests": "",
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    first_message = MagicMock()
    first_message.content = None
    first_message.tool_calls = [create_tool_call]

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=first_message)]

    second_message = MagicMock()
    second_message.content = (
        "La richiesta di prenotazione è stata registrata "
        "ed è in attesa di conferma."
    )
    second_message.tool_calls = None

    second_response = MagicMock()
    second_response.choices = [MagicMock(message=second_message)]

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            check_response,
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
                "Vorrei prenotare per 10 persone "
                "il 25 settembre alle 11:00."
            ),
        },
    ]

    reply, returned_reservation_id, reservation_status, modification_status = (
        await service._run_completion_loop(
            messages=messages,
            restaurant_id=None,
            session_id="lab-006-pending-status",
        )
    )

    assert returned_reservation_id == reservation_id
    assert reservation_status == "pending"
    assert modification_status is None
    assert "attesa di conferma" in reply

    reservation_service.assess_booking_availability.assert_awaited_once()
    reservation_service.create_reservation.assert_awaited_once()

@pytest.mark.asyncio
async def test_guest_local_time_is_not_double_shifted_at_ai_boundary():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    arguments = {
        "reservation_time": "2026-10-07T11:15:00+08:00",
        "reservation_local_datetime": "2026-10-07T19:15:00",
        "party_size": 2,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    await service._execute_tool(
        "check_availability",
        json.dumps(arguments),
        timezone_name="Australia/Perth",
    )

    call = reservation_service.assess_booking_availability.await_args

    requested_time = call.kwargs["reservation_time"]

    assert requested_time.isoformat() == "2026-10-07T19:15:00+08:00"

@pytest.mark.asyncio
async def test_completion_loop_preserves_guest_local_wall_clock_time():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    tool_call = MagicMock()
    tool_call.id = "call_lab009_perth_time"
    tool_call.function.name = "check_availability"
    tool_call.function.arguments = json.dumps(
        {
            # Simulates the bad absolute datetime observed in production.
            "reservation_time": "2026-10-07T11:15:00+08:00",

            # Authoritative guest-selected restaurant-local wall clock.
            "reservation_local_datetime": "2026-10-07T19:15:00",

            "party_size": 2,
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    first_message = MagicMock()
    first_message.content = None
    first_message.tool_calls = [tool_call]

    first_response = MagicMock()
    first_response.choices = [MagicMock(message=first_message)]

    second_message = MagicMock()
    second_message.content = "Le 19:15 sono disponibili."
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
                "Vorrei prenotare un tavolo per 2 persone "
                "il 7 ottobre 2026 alle 19:15."
            ),
        },
    ]

    reply, reservation_id, reservation_status, modification_status = (
        await service._run_completion_loop(
            messages=messages,
            restaurant_id=None,
            session_id="lab-009-perth-time",
            timezone_name="Australia/Perth",
        )
    )

    assert reply == "Le 19:15 sono disponibili."
    assert reservation_id is None
    assert reservation_status is None
    assert modification_status is None

    reservation_service.assess_booking_availability.assert_awaited_once()

    call = reservation_service.assess_booking_availability.await_args
    requested_time = call.kwargs["reservation_time"]

    assert requested_time.isoformat() == "2026-10-07T19:15:00+08:00"

@pytest.mark.asyncio
async def test_create_reservation_preserves_guest_local_wall_clock_time():
    service, reservation_service = _build_ai_service()

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 2
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-10-07T19:15:00+08:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation

    arguments = {
        "customer_name": "Luca Test",
        "customer_phone": "3333333333",
        "customer_email": "luca@example.com",
        "party_size": 2,

        # Simulates the bad absolute datetime observed in production.
        "reservation_time": "2026-10-07T11:15:00+08:00",

        # Authoritative restaurant-local wall clock.
        "reservation_local_datetime": "2026-10-07T19:15:00",

        "special_requests": "",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    await service._execute_tool(
        "create_reservation",
        json.dumps(arguments),
        restaurant_id=None,
        session_id="lab-009-create",
        timezone_name="Australia/Perth",
    )

    reservation_service.create_reservation.assert_awaited_once()

    payload = reservation_service.create_reservation.await_args.args[0]

    assert payload.reservation_time.isoformat() == (
        "2026-10-07T19:15:00+08:00"
    )

@pytest.mark.asyncio
async def test_customer_local_datetime_with_timezone_offset_fails_closed():
    service, reservation_service = _build_ai_service()

    arguments = {
        "reservation_time": "2026-10-07T11:15:00+08:00",
        "reservation_local_datetime": "2026-10-07T19:15:00+08:00",
        "party_size": 2,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    result, reservation_id = await service._execute_tool(
        "check_availability",
        json.dumps(arguments),
        timezone_name="Australia/Perth",
    )

    assert reservation_id is None
    assert "error" in result

    reservation_service.assess_booking_availability.assert_not_awaited()

@pytest.mark.asyncio
async def test_completion_loop_rejects_create_time_different_from_validated_check():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 2
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-10-07T11:15:00+08:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation

    check_tool_call = MagicMock()
    check_tool_call.id = "call_lab009_check"
    check_tool_call.function.name = "check_availability"
    check_tool_call.function.arguments = json.dumps(
        {
            "reservation_time": "2026-10-07T11:15:00+08:00",
            "reservation_local_datetime": "2026-10-07T19:15:00",
            "party_size": 2,
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    check_message = MagicMock()
    check_message.content = None
    check_message.tool_calls = [check_tool_call]

    check_response = MagicMock()
    check_response.choices = [MagicMock(message=check_message)]

    create_tool_call = MagicMock()
    create_tool_call.id = "call_lab009_create"
    create_tool_call.function.name = "create_reservation"
    create_tool_call.function.arguments = json.dumps(
        {
            "customer_name": "Luca Test",
            "customer_phone": "3333333333",
            "customer_email": "luca@example.com",
            "party_size": 2,
            "reservation_time": "2026-10-07T03:15:00+08:00",

            # Simulates semantic drift between CHECK and CREATE.
            "reservation_local_datetime": "2026-10-07T11:15:00",

            "special_requests": "",
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    create_message = MagicMock()
    create_message.content = None
    create_message.tool_calls = [create_tool_call]

    create_response = MagicMock()
    create_response.choices = [MagicMock(message=create_message)]

    final_message = MagicMock()
    final_message.content = "Non posso confermare la prenotazione."
    final_message.tool_calls = None

    final_response = MagicMock()
    final_response.choices = [MagicMock(message=final_message)]

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            check_response,
            create_response,
            final_response,
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
                "Vorrei prenotare un tavolo per 2 persone "
                "il 7 ottobre 2026 alle 19:15."
            ),
        },
    ]

    await service._run_completion_loop(
        messages=messages,
        restaurant_id=None,
        session_id="lab-009-check-create-consistency",
        timezone_name="Australia/Perth",
    )

    reservation_service.assess_booking_availability.assert_awaited_once()

    # A CREATE whose time differs from the slot validated immediately
    # before it must fail closed rather than persist another instant.
    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_completion_loop_allows_create_matching_validated_check():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 2
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-10-07T19:15:00+08:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation

    check_tool_call = MagicMock()
    check_tool_call.id = "call_lab009_check_matching"
    check_tool_call.function.name = "check_availability"
    check_tool_call.function.arguments = json.dumps(
        {
            "reservation_time": "2026-10-07T11:15:00+08:00",
            "reservation_local_datetime": "2026-10-07T19:15:00",
            "party_size": 2,
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    check_message = MagicMock()
    check_message.content = None
    check_message.tool_calls = [check_tool_call]

    check_response = MagicMock()
    check_response.choices = [MagicMock(message=check_message)]

    create_tool_call = MagicMock()
    create_tool_call.id = "call_lab009_create_matching"
    create_tool_call.function.name = "create_reservation"
    create_tool_call.function.arguments = json.dumps(
        {
            "customer_name": "Luca Test",
            "customer_phone": "3333333333",
            "customer_email": "luca@example.com",
            "party_size": 2,
            "reservation_time": "2026-10-07T11:15:00+08:00",
            "reservation_local_datetime": "2026-10-07T19:15:00",
            "special_requests": "",
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    create_message = MagicMock()
    create_message.content = None
    create_message.tool_calls = [create_tool_call]

    create_response = MagicMock()
    create_response.choices = [MagicMock(message=create_message)]

    final_message = MagicMock()
    final_message.content = "Prenotazione confermata."
    final_message.tool_calls = None

    final_response = MagicMock()
    final_response.choices = [MagicMock(message=final_message)]

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            check_response,
            create_response,
            final_response,
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
                "Vorrei prenotare un tavolo per 2 persone "
                "il 7 ottobre 2026 alle 19:15."
            ),
        },
    ]

    await service._run_completion_loop(
        messages=messages,
        restaurant_id=None,
        session_id="lab-009-check-create-matching",
        timezone_name="Australia/Perth",
    )

    reservation_service.assess_booking_availability.assert_awaited_once()
    reservation_service.create_reservation.assert_awaited_once()

    payload = reservation_service.create_reservation.await_args.args[0]

    assert payload.reservation_time.isoformat() == (
        "2026-10-07T19:15:00+08:00"
    )

@pytest.mark.asyncio
async def test_completion_loop_rejects_create_party_size_different_from_validated_check():
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.party_size = 8
    fake_reservation.reservation_time = __import__(
        "datetime"
    ).datetime.fromisoformat("2026-10-07T19:15:00+08:00")
    fake_reservation.special_requests = ""

    reservation_service.create_reservation.return_value = fake_reservation

    # CHECK validates 19:15 local for 2 guests.
    check_tool_call = MagicMock()
    check_tool_call.id = "call_lab009_create_party_check"
    check_tool_call.function.name = "check_availability"
    check_tool_call.function.arguments = json.dumps(
        {
            "reservation_time": "2026-10-07T11:15:00+08:00",
            "reservation_local_datetime": "2026-10-07T19:15:00",
            "party_size": 2,
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    check_message = MagicMock()
    check_message.content = None
    check_message.tool_calls = [check_tool_call]

    check_response = MagicMock()
    check_response.choices = [
        MagicMock(message=check_message)
    ]

    # CREATE keeps the validated time but drifts from 2 to 8 guests.
    create_tool_call = MagicMock()
    create_tool_call.id = "call_lab009_create_party_create"
    create_tool_call.function.name = "create_reservation"
    create_tool_call.function.arguments = json.dumps(
        {
            "customer_name": "Luca Test",
            "customer_phone": "3333333333",
            "customer_email": "luca@example.com",
            "party_size": 8,
            "reservation_time": "2026-10-07T11:15:00+08:00",
            "reservation_local_datetime": "2026-10-07T19:15:00",
            "special_requests": "",
            "customer_provided_date": True,
            "customer_provided_time": True,
            "customer_provided_party_size": True,
        }
    )

    create_message = MagicMock()
    create_message.content = None
    create_message.tool_calls = [create_tool_call]

    create_response = MagicMock()
    create_response.choices = [
        MagicMock(message=create_message)
    ]

    final_message = MagicMock()
    final_message.content = "Non posso confermare la prenotazione."
    final_message.tool_calls = None

    final_response = MagicMock()
    final_response.choices = [
        MagicMock(message=final_message)
    ]

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            check_response,
            create_response,
            final_response,
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
                "Vorrei prenotare un tavolo per 2 persone "
                "il 7 ottobre 2026 alle 19:15."
            ),
        },
    ]

    await service._run_completion_loop(
        messages=messages,
        restaurant_id=None,
        session_id="lab-009-check-create-party-size",
        timezone_name="Australia/Perth",
    )

    reservation_service.assess_booking_availability.assert_awaited_once()

    reservation_service.create_reservation.assert_not_awaited()

@pytest.mark.asyncio
async def test_failed_availability_check_cannot_authorize_booking():
    """A failed availability check must never authorize reservation creation."""
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.side_effect = ValueError(
        "Simulated availability failure"
    )

    def tool_call(call_id, name, arguments):
        call = MagicMock()
        call.id = call_id
        call.function.name = name
        call.function.arguments = json.dumps(arguments)
        return call

    booking_intent = {
        "reservation_time": "2026-11-25T19:00:00",
        "party_size": 14,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    check_call = tool_call(
        "check_failed",
        "check_availability",
        booking_intent,
    )

    create_call = tool_call(
        "create_after_failure",
        "create_reservation",
        {
            **booking_intent,
            "customer_name": "Birthday Guest",
            "customer_phone": "+15551234567",
        },
    )

    def completion(calls=None, content=None):
        message = MagicMock()
        message.tool_calls = calls
        message.content = content
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            completion([check_call]),
            completion([create_call]),
            completion(content="Non posso confermare senza disponibilità."),
        ]
    )

    messages = [
        {"role": "system", "content": "Test system prompt"},
        {"role": "user", "content": "Prenotazione per 14 persone."},
    ]

    await service._run_completion_loop(
        messages=messages,
        restaurant_id=uuid.uuid4(),
        session_id="lab016-failed-check",
    )

    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_party_size_correction_requires_recheck_then_allows_booking():
    """A corrected party size can be booked only after a fresh availability check."""
    from datetime import datetime

    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.party_size = 12
    fake_reservation.reservation_time = datetime.fromisoformat(
        "2026-11-25T19:00:00+08:00"
    )
    fake_reservation.special_requests = ""
    reservation_service.create_reservation.return_value = fake_reservation

    intent = {
        "reservation_time": "2026-11-25T19:00:00+08:00",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    def tool_call(call_id, name, arguments):
        call = MagicMock()
        call.id = call_id
        call.function.name = name
        call.function.arguments = json.dumps(arguments)
        return call

    def completion(calls=None, content=None):
        message = MagicMock()
        message.content = content
        message.tool_calls = calls
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    create_arguments = {
        **intent,
        "party_size": 12,
        "customer_name": "Luca Test",
        "customer_phone": "3333333333",
        "customer_email": "luca@example.com",
    }

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            completion([tool_call("check14", "check_availability", {
                **intent, "party_size": 14,
            })]),
            completion([tool_call("create12_early", "create_reservation",
                                  create_arguments)]),
            completion([tool_call("check12", "check_availability", {
                **intent, "party_size": 12,
            })]),
            completion([tool_call("create12_valid", "create_reservation",
                                  create_arguments)]),
            completion(content="Prenotazione confermata per 12 persone."),
        ]
    )

    messages = [
        {"role": "system", "content": "Test system prompt"},
        {"role": "user", "content": "Prenotazione per 14 persone."},
        {"role": "user", "content": "Correzione: siamo 12 persone."},
    ]

    reply, reservation_id, status, _ = await service._run_completion_loop(
        messages=messages,
        restaurant_id=uuid.uuid4(),
        session_id="lab016-party-correction",
    )

    assert reply == "Prenotazione confermata per 12 persone."
    assert reservation_id == fake_reservation.id
    assert status == "confirmed"

    assert reservation_service.assess_booking_availability.await_count == 2
    checked_sizes = [
        call.kwargs["party_size"]
        for call in reservation_service.assess_booking_availability.await_args_list
    ]
    assert checked_sizes == [14, 12]

    reservation_service.create_reservation.assert_awaited_once()
    payload = reservation_service.create_reservation.await_args.args[0]
    assert payload.party_size == 12

    tool_results = {
        message["tool_call_id"]: json.loads(message["content"])
        for message in messages
        if message.get("role") == "tool"
    }
    assert tool_results["create12_early"]["error"] == (
        "party_size_changed_after_availability_check"
    )


@pytest.mark.asyncio
async def test_handle_message_preserves_party_size_correction_across_turns():
    """A later guest correction must reach the model in the same session."""
    from types import SimpleNamespace

    service, _ = _build_ai_service()
    restaurant_id = uuid.uuid4()
    conversation = SimpleNamespace(id=uuid.uuid4())
    stored_messages = []

    async def add_message(conversation_id, role, content):
        assert conversation_id == conversation.id
        stored_messages.append(SimpleNamespace(role=role, content=content))

    async def get_recent_messages(conversation_id, limit):
        assert conversation_id == conversation.id
        return stored_messages[-limit:]

    service.conversation_repo = SimpleNamespace(
        get_or_create=AsyncMock(return_value=(conversation, False)),
        touch=AsyncMock(),
        add_message=AsyncMock(side_effect=add_message),
        get_recent_messages=AsyncMock(side_effect=get_recent_messages),
    )

    service.restaurant_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=None)
    )

    service._run_completion_loop = AsyncMock(
        side_effect=[
            ("Per quale data e ora?", None, None, None),
            ("Perfetto, aggiorno a 12 persone.", None, None, None),
        ]
    )

    session_id = "lab016-correction-across-turns"

    await service.handle_message(
        session_id=session_id,
        user_message="Vorrei prenotare per 14 persone.",
        restaurant_id=restaurant_id,
    )

    await service.handle_message(
        session_id=session_id,
        user_message="Scusa, ho sbagliato: siamo 12 persone.",
        restaurant_id=restaurant_id,
    )

    assert service._run_completion_loop.await_count == 2

    second_turn_messages = (
        service._run_completion_loop.await_args_list[1].args[0]
    )

    history = [
        (message["role"], message["content"])
        for message in second_turn_messages
        if message["role"] != "system"
    ]

    assert history == [
        ("user", "Vorrei prenotare per 14 persone."),
        ("assistant", "Per quale data e ora?"),
        ("user", "Scusa, ho sbagliato: siamo 12 persone."),
    ]

    calls = service.conversation_repo.get_or_create.await_args_list
    assert len(calls) == 2
    assert all(call.args == (session_id, restaurant_id) for call in calls)


@pytest.mark.asyncio
async def test_two_turn_party_correction_requires_fresh_availability():
    """A prior turn's availability must never authorize a corrected booking."""
    from datetime import datetime
    from types import SimpleNamespace

    service, reservation_service = _build_ai_service()
    restaurant_id = uuid.uuid4()
    conversation = SimpleNamespace(id=uuid.uuid4())
    stored_messages = []

    async def add_message(conversation_id, role, content):
        assert conversation_id == conversation.id
        stored_messages.append(SimpleNamespace(role=role, content=content))

    async def get_recent_messages(conversation_id, limit):
        assert conversation_id == conversation.id
        return stored_messages[-limit:]

    service.conversation_repo = SimpleNamespace(
        get_or_create=AsyncMock(return_value=(conversation, False)),
        touch=AsyncMock(),
        add_message=AsyncMock(side_effect=add_message),
        get_recent_messages=AsyncMock(side_effect=get_recent_messages),
    )
    service.restaurant_repo.get_by_id = AsyncMock(return_value=None)

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    fake_reservation = MagicMock()
    fake_reservation.id = uuid.uuid4()
    fake_reservation.status.value = "confirmed"
    fake_reservation.customer_name = "Luca Test"
    fake_reservation.customer_phone = "3333333333"
    fake_reservation.customer_email = "luca@example.com"
    fake_reservation.party_size = 12
    fake_reservation.reservation_time = datetime.fromisoformat(
        "2026-11-25T19:00:00+08:00"
    )
    fake_reservation.special_requests = ""
    reservation_service.create_reservation.return_value = fake_reservation

    intent = {
        "reservation_time": "2026-11-25T19:00:00+08:00",
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    def tool_call(call_id, name, arguments):
        call = MagicMock()
        call.id = call_id
        call.function.name = name
        call.function.arguments = json.dumps(arguments)
        return call

    def completion(calls=None, content=None):
        message = MagicMock()
        message.content = content
        message.tool_calls = calls
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    create_arguments = {
        **intent,
        "party_size": 12,
        "customer_name": "Luca Test",
        "customer_phone": "3333333333",
        "customer_email": "luca@example.com",
    }

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            completion([tool_call("check14", "check_availability", {
                **intent, "party_size": 14,
            })]),
            completion(content="Disponibilità verificata per 14 persone."),
            completion([tool_call(
                "create12_early", "create_reservation", create_arguments
            )]),
            completion([tool_call("check12", "check_availability", {
                **intent, "party_size": 12,
            })]),
            completion([tool_call(
                "create12_valid", "create_reservation", create_arguments
            )]),
            completion(content="Prenotazione confermata per 12 persone."),
        ]
    )

    session_id = "lab016-two-turn-fresh-check"

    first = await service.handle_message(
        session_id=session_id,
        user_message=(
            "Vorrei prenotare per 14 persone il 25 novembre "
            "2026 alle 19:00."
        ),
        restaurant_id=restaurant_id,
    )
    assert first[2] is None

    second = await service.handle_message(
        session_id=session_id,
        user_message="Scusa, ho sbagliato: siamo 12 persone.",
        restaurant_id=restaurant_id,
    )

    assert second[0] == session_id
    assert second[1] == "Prenotazione confermata per 12 persone."
    assert second[2] == fake_reservation.id
    assert second[3] == "confirmed"

    checked_sizes = [
        call.kwargs["party_size"]
        for call in reservation_service.assess_booking_availability.await_args_list
    ]
    assert checked_sizes == [14, 12]

    reservation_service.create_reservation.assert_awaited_once()
    payload = reservation_service.create_reservation.await_args.args[0]
    assert payload.party_size == 12

    completion_messages = [
        call.kwargs["messages"]
        for call in service.client.chat.completions.create.await_args_list
    ]

    second_turn_start = completion_messages[2]
    assert any(
        message.get("role") == "user"
        and "14 persone" in (message.get("content") or "")
        for message in second_turn_start
    )
    assert any(
        message.get("role") == "user"
        and "12 persone" in (message.get("content") or "")
        for message in second_turn_start
    )

    tool_results = {
        message["tool_call_id"]: json.loads(message["content"])
        for message in completion_messages[-1]
        if message.get("role") == "tool"
    }
    assert tool_results["create12_early"]["error"] == (
        "availability_check_required"
    )
    assert tool_results["create12_valid"]["success"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("create_time", "should_create"),
    [
        ("2026-11-25T20:00:00+08:00", False),
        ("2026-11-25T11:00:00+00:00", True),
    ],
)
async def test_create_reservation_time_must_match_validated_check(
    create_time, should_create
):
    from datetime import datetime

    service, reservation_service = _build_ai_service()
    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    reservation = MagicMock()
    reservation.id = uuid.uuid4()
    reservation.status.value = "confirmed"
    reservation.customer_name = "Luca Test"
    reservation.customer_phone = "3333333333"
    reservation.customer_email = "luca@example.com"
    reservation.party_size = 12
    reservation.reservation_time = datetime.fromisoformat(create_time)
    reservation.special_requests = ""
    reservation_service.create_reservation.return_value = reservation

    intent = {
        "party_size": 12,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    }

    def tool_call(call_id, name, arguments):
        call = MagicMock()
        call.id = call_id
        call.function.name = name
        call.function.arguments = json.dumps(arguments)
        return call

    def completion(calls=None, content=None):
        message = MagicMock()
        message.content = content
        message.tool_calls = calls
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            completion([
                tool_call("check_time", "check_availability", {
                    **intent,
                    "reservation_time": "2026-11-25T19:00:00+08:00",
                })
            ]),
            completion([
                tool_call("create_time", "create_reservation", {
                    **intent,
                    "reservation_time": create_time,
                    "customer_name": "Luca Test",
                    "customer_phone": "3333333333",
                    "customer_email": "luca@example.com",
                })
            ]),
            completion(content="Richiesta elaborata."),
        ]
    )

    messages = [
        {"role": "system", "content": "Test"},
        {
            "role": "user",
            "content": "Prenotazione per 12 persone il 25 novembre alle 19:00.",
        },
    ]

    await service._run_completion_loop(
        messages=messages,
        restaurant_id=uuid.uuid4(),
        session_id="lab016-time-consistency",
        timezone_name="Australia/Perth",
    )

    reservation_service.assess_booking_availability.assert_awaited_once()

    tool_results = {
        message["tool_call_id"]: json.loads(message["content"])
        for message in messages
        if message.get("role") == "tool"
    }

    if should_create:
        reservation_service.create_reservation.assert_awaited_once()
        assert tool_results["create_time"]["success"] is True
    else:
        reservation_service.create_reservation.assert_not_awaited()
        assert tool_results["create_time"]["error"] == (
            "reservation_time_changed_after_availability_check"
        )


@pytest.mark.asyncio
async def test_lab016_unverified_large_party_refusal_is_not_returned():
    """A model-only refusal must not bypass availability verification."""
    service, reservation_service = _build_ai_service()

    def completion(content=None, calls=None):
        message = MagicMock()
        message.content = content
        message.tool_calls = calls
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    invented_refusal = (
        "Mi dispiace, 14 persone superano il limite "
        "per le prenotazioni online. Contatta il ristorante."
    )

    service.client.chat.completions.create = AsyncMock(
        return_value=completion(content=invented_refusal)
    )

    messages = [
        {"role": "system", "content": "Restaurant booking assistant."},
        {
            "role": "user",
            "content": (
                "Vorrei prenotare per 14 persone "
                "il 17 ottobre 2026 alle 19:30."
            ),
        },
    ]

    reply, reservation_id, status, modification_status = (
        await service._run_completion_loop(
            messages,
            restaurant_id=uuid.uuid4(),
            timezone_name="Australia/Perth",
        )
    )

    assert invented_refusal != reply
    assert "14 persone superano il limite" not in reply
    assert reservation_id is None
    assert status is None
    assert modification_status is None
    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab016_recovers_from_unverified_refusal_with_availability_check():
    """A false refusal is recovered through a real availability tool call."""
    service, reservation_service = _build_ai_service()

    reservation_service.assess_booking_availability.return_value = (
        BookingAvailabilityOutcome.DIRECT_AVAILABLE
    )

    def completion(content=None, calls=None):
        message = MagicMock()
        message.content = content
        message.tool_calls = calls
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    tool_call = MagicMock()
    tool_call.id = "lab016-check14"
    tool_call.function.name = "check_availability"
    tool_call.function.arguments = json.dumps({
        "reservation_time": "2026-10-17T19:30:00+08:00",
        "reservation_local_datetime": "2026-10-17T19:30:00",
        "party_size": 14,
        "customer_provided_date": True,
        "customer_provided_time": True,
        "customer_provided_party_size": True,
    })

    service.client.chat.completions.create = AsyncMock(
        side_effect=[
            completion(
                content="14 persone superano il limite online."
            ),
            completion(calls=[tool_call]),
            completion(
                content=(
                    "Abbiamo disponibilità per 14 persone "
                    "il 17 ottobre alle 19:30. "
                    "Posso raccogliere i dati per la prenotazione."
                )
            ),
        ]
    )

    messages = [
        {"role": "system", "content": "Restaurant booking assistant."},
        {
            "role": "user",
            "content": (
                "Vorrei prenotare per 14 persone "
                "il 17 ottobre 2026 alle 19:30."
            ),
        },
    ]

    reply, reservation_id, status, modification_status = (
        await service._run_completion_loop(
            messages,
            restaurant_id=uuid.uuid4(),
            timezone_name="Australia/Perth",
        )
    )

    assert "Abbiamo disponibilità per 14 persone" in reply
    assert reservation_id is None
    assert status is None
    assert modification_status is None

    reservation_service.assess_booking_availability.assert_awaited_once()
    assert (
        reservation_service.assess_booking_availability.await_args.kwargs[
            "party_size"
        ]
        == 14
    )
    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab016_english_unverified_party_limit_refusal_is_blocked():
    """An invented English party-size restriction must not reach the guest."""
    service, reservation_service = _build_ai_service()

    invented_refusal = (
        "Sorry, groups of 14 exceed our online booking limit. "
        "Please call the restaurant."
    )

    message = MagicMock()
    message.content = invented_refusal
    message.tool_calls = None

    response = MagicMock()
    response.choices = [MagicMock(message=message)]

    service.client.chat.completions.create = AsyncMock(
        return_value=response
    )

    messages = [
        {"role": "system", "content": "Restaurant booking assistant."},
        {
            "role": "user",
            "content": (
                "I'd like to book for 14 people "
                "on October 17, 2026 at 7:30 PM."
            ),
        },
    ]

    reply, reservation_id, status, modification_status = (
        await service._run_completion_loop(
            messages,
            restaurant_id=uuid.uuid4(),
            timezone_name="Australia/Perth",
        )
    )

    assert invented_refusal != reply
    assert reservation_id is None
    assert status is None
    assert modification_status is None
    reservation_service.create_reservation.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab016_structured_classifier_requires_availability_check():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.ai_service import _classify_unverified_booking_intent

    client = MagicMock()
    response = MagicMock()
    response.choices[0].message.content = json.dumps({
        "new_booking": True,
        "has_date": True,
        "has_time": True,
        "has_party_size": True,
        "requires_availability_check": True,
    })
    client.chat.completions.create = AsyncMock(return_value=response)

    result = await _classify_unverified_booking_intent(
        client,
        [{
            "role": "user",
            "content": (
                "I'd like a table for 14 people on "
                "17 October 2026 at 7:30 pm."
            ),
        }],
        "Sorry, your group exceeds our booking limit.",
    )

    assert result is True
    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_lab016_greeting_does_not_trigger_classifier():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.ai_service import AIService

    service = object.__new__(AIService)
    service.client = MagicMock()

    response = MagicMock()
    response.choices[0].message.content = "Ciao! Come posso aiutarti?"
    response.choices[0].message.tool_calls = None

    service.client.chat.completions.create = AsyncMock(
        return_value=response
    )

    reply, reservation_id, reservation_status, modification_status = (
        await service._run_completion_loop(
            messages=[
                {"role": "user", "content": "Ciao!"}
            ]
        )
    )

    assert reply == "Ciao! Come posso aiutarti?"
    assert reservation_id is None
    assert reservation_status is None
    assert modification_status is None
    service.client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_lab016_incomplete_booking_asks_for_missing_details():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.ai_service import AIService

    service = object.__new__(AIService)
    service.client = MagicMock()

    response = MagicMock()
    response.choices[0].message.content = (
        "Certamente! Per quale giorno e a che ora "
        "vorresti prenotare per 8 persone?"
    )
    response.choices[0].message.tool_calls = None

    service.client.chat.completions.create = AsyncMock(
        return_value=response
    )

    reply, reservation_id, reservation_status, modification_status = (
        await service._run_completion_loop(
            messages=[
                {
                    "role": "user",
                    "content": "Vorrei prenotare per 8 persone",
                }
            ]
        )
    )

    assert "quale giorno" in reply
    assert "a che ora" in reply
    assert reservation_id is None
    assert reservation_status is None
    assert modification_status is None
    service.client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_lab016_unverified_capacity_claim_without_keywords_is_blocked():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.ai_service import AIService

    service = object.__new__(AIService)
    service.client = MagicMock()

    response = MagicMock()
    response.choices[0].message.content = (
        "Mi dispiace, il ristorante accetta gruppi "
        "di massimo 6 persone."
    )
    response.choices[0].message.tool_calls = None

    service.client.chat.completions.create = AsyncMock(
        return_value=response
    )

    reply, *_ = await service._run_completion_loop(
        messages=[{
            "role": "user",
            "content": (
                "Vorrei un tavolo per 12 persone "
                "il 17 ottobre 2026 alle 19:30."
            ),
        }]
    )

    assert "massimo 6 persone" not in reply
