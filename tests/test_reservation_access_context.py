"""Tests for reservation-scoped authorization context."""

import uuid
from dataclasses import FrozenInstanceError

import pytest

from app.services.reservation_access_context import ReservationAccessContext


def test_context_allows_only_exact_restaurant_and_reservation():
    restaurant_id = uuid.uuid4()
    reservation_id = uuid.uuid4()

    context = ReservationAccessContext(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
    )

    assert context.allows(restaurant_id, reservation_id)
    assert not context.allows(uuid.uuid4(), reservation_id)
    assert not context.allows(restaurant_id, uuid.uuid4())
    assert not context.allows(None, reservation_id)


def test_context_is_immutable():
    context = ReservationAccessContext(
        restaurant_id=uuid.uuid4(),
        reservation_id=uuid.uuid4(),
    )

    with pytest.raises(FrozenInstanceError):
        context.reservation_id = uuid.uuid4()
