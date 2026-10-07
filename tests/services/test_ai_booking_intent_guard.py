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