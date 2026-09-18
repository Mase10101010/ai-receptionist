from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.intelligence_temporal.observations import (
    TemporalObservationService,
)
from app.models.reservation import ReservationStatus


def _reservation(
    *,
    status=ReservationStatus.COMPLETED,
    seated_at=None,
    completed_at=None,
    restaurant_id=None,
    duration_minutes=90,
):
    start = datetime(
        2026,
        9,
        10,
        18,
        0,
    )

    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=(
            restaurant_id
            if restaurant_id is not None
            else uuid4()
        ),
        table_id=uuid4(),
        party_size=4,
        reservation_time=start,
        duration_minutes=duration_minutes,
        status=status,
        seated_at=seated_at,
        completed_at=completed_at,
    )


def test_completed_reservation_becomes_temporal_observation():
    seated_at = datetime(
        2026,
        9,
        10,
        18,
        7,
    )

    completed_at = seated_at + timedelta(
        minutes=74,
    )

    reservation = _reservation(
        seated_at=seated_at,
        completed_at=completed_at,
        duration_minutes=90,
    )

    result = TemporalObservationService.from_reservation(
        reservation,
    )

    assert result is not None

    assert (
        result.reservation_id
        == reservation.id
    )
    assert (
        result.restaurant_id
        == reservation.restaurant_id
    )
    assert result.table_id == reservation.table_id

    assert result.party_size == 4

    assert result.seated_at == seated_at
    assert result.completed_at == completed_at

    assert result.planned_duration_minutes == 90
    assert result.actual_dining_minutes == 74

    assert result.duration_delta_minutes == -16


def test_longer_than_planned_turn_records_positive_delta():
    seated_at = datetime(
        2026,
        9,
        10,
        19,
        0,
    )

    reservation = _reservation(
        seated_at=seated_at,
        completed_at=(
            seated_at + timedelta(minutes=112)
        ),
        duration_minutes=90,
    )

    result = TemporalObservationService.from_reservation(
        reservation,
    )

    assert result is not None
    assert result.actual_dining_minutes == 112
    assert result.duration_delta_minutes == 22


def test_non_completed_reservation_is_not_observed():
    seated_at = datetime(
        2026,
        9,
        10,
        18,
        0,
    )

    reservation = _reservation(
        status=ReservationStatus.SEATED,
        seated_at=seated_at,
        completed_at=None,
    )

    result = TemporalObservationService.from_reservation(
        reservation,
    )

    assert result is None


def test_missing_seated_at_is_not_observed():
    reservation = _reservation(
        seated_at=None,
        completed_at=datetime(
            2026,
            9,
            10,
            19,
            30,
        ),
    )

    assert (
        TemporalObservationService.from_reservation(
            reservation,
        )
        is None
    )


def test_missing_completed_at_is_not_observed():
    reservation = _reservation(
        seated_at=datetime(
            2026,
            9,
            10,
            18,
            0,
        ),
        completed_at=None,
    )

    assert (
        TemporalObservationService.from_reservation(
            reservation,
        )
        is None
    )


def test_invalid_non_positive_turn_is_not_observed():
    seated_at = datetime(
        2026,
        9,
        10,
        18,
        0,
    )

    reservation = _reservation(
        seated_at=seated_at,
        completed_at=seated_at,
    )

    assert (
        TemporalObservationService.from_reservation(
            reservation,
        )
        is None
    )