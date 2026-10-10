"""Tests for identifying reservation-sensitive AI tool calls."""

import pytest

from app.services.ai_service import _requires_reservation_access


@pytest.mark.parametrize(
    "tool_name",
    [
        "get_reservation",
        "update_reservation",
        "cancel_reservation",
    ],
)
def test_existing_reservation_operations_require_access(tool_name):
    assert _requires_reservation_access(tool_name, {})


@pytest.mark.parametrize(
    "tool_name",
    [
        "check_availability",
        "suggest_alternative_slots",
    ],
)
def test_existing_booking_checks_require_access(tool_name):
    assert _requires_reservation_access(
        tool_name,
        {"reservation_id": "existing-booking-id"},
    )


@pytest.mark.parametrize(
    "tool_name",
    [
        "check_availability",
        "suggest_alternative_slots",
    ],
)
def test_new_booking_checks_do_not_require_access(tool_name):
    assert not _requires_reservation_access(tool_name, {})


def test_new_reservation_does_not_require_existing_booking_access():
    assert not _requires_reservation_access(
        "create_reservation",
        {},
    )


def test_unknown_tool_does_not_claim_reservation_access():
    assert not _requires_reservation_access(
        "unknown_tool",
        {"reservation_id": "existing-booking-id"},
    )


from uuid import uuid4

from app.services.ai_service import _reservation_tool_is_authorized
from app.services.reservation_access_context import ReservationAccessContext


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
def test_sensitive_tools_reject_missing_authorization(tool_name):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    assert not _reservation_tool_is_authorized(
        tool_name,
        {"reservation_id": str(reservation_id)},
        restaurant_id,
        None,
    )


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
def test_sensitive_tools_accept_only_matching_scope(tool_name):
    restaurant_id = uuid4()
    reservation_id = uuid4()

    context = ReservationAccessContext(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    assert _reservation_tool_is_authorized(
        tool_name,
        {"reservation_id": str(reservation_id)},
        restaurant_id,
        context,
    )

    assert not _reservation_tool_is_authorized(
        tool_name,
        {"reservation_id": str(uuid4())},
        restaurant_id,
        context,
    )

    assert not _reservation_tool_is_authorized(
        tool_name,
        {"reservation_id": str(reservation_id)},
        uuid4(),
        context,
    )

    assert not _reservation_tool_is_authorized(
        tool_name,
        {"reservation_id": "not-a-uuid"},
        restaurant_id,
        context,
    )


def test_sensitive_tool_rejects_missing_reservation_id():
    context = ReservationAccessContext(
        restaurant_id=uuid4(),
        reservation_id=uuid4(),
    )

    assert not _reservation_tool_is_authorized(
        "get_reservation",
        {},
        context.restaurant_id,
        context,
    )


def test_new_booking_remains_public():
    assert _reservation_tool_is_authorized(
        "create_reservation",
        {},
        None,
        None,
    )

    assert _reservation_tool_is_authorized(
        "check_availability",
        {"party_size": 2},
        None,
        None,
    )
