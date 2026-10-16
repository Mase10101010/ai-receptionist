"""Regression tests for timezone-safe reservation datetimes."""

from datetime import datetime, timezone

import pytest

from app.services.reservation_datetime_service import (
    ReservationDateTimeError,
    normalize_reservation_datetime,
)


@pytest.mark.parametrize(
    "name,value,restaurant_timezone,expected",
    [
        (
            "Perth",
            datetime(2026, 10, 26, 20),
            "Australia/Perth",
            datetime(2026, 10, 26, 12, tzinfo=timezone.utc),
        ),
        (
            "Milano summer",
            datetime(2026, 7, 15, 20),
            "Europe/Rome",
            datetime(2026, 7, 15, 18, tzinfo=timezone.utc),
        ),
        (
            "Milano winter",
            datetime(2026, 12, 15, 20),
            "Europe/Rome",
            datetime(2026, 12, 15, 19, tzinfo=timezone.utc),
        ),
        (
            "Dubai",
            datetime(2026, 10, 26, 20),
            "Asia/Dubai",
            datetime(2026, 10, 26, 16, tzinfo=timezone.utc),
        ),
    ],
)
def test_naive_datetime_uses_restaurant_timezone(
    name, value, restaurant_timezone, expected
):
    result = normalize_reservation_datetime(value, restaurant_timezone)

    assert result == expected, name
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "value,restaurant_timezone,error_message",
    [
        (
            datetime(2026, 3, 29, 2, 30),
            "Europe/Rome",
            "does not exist",
        ),
        (
            datetime(2026, 10, 25, 2, 30),
            "Europe/Rome",
            "ambiguous",
        ),
        (
            datetime(2026, 10, 26, 20),
            "Invalid/Timezone",
            "Invalid restaurant timezone",
        ),
    ],
)
def test_invalid_local_datetime_is_rejected(
    value, restaurant_timezone, error_message
):
    with pytest.raises(ReservationDateTimeError, match=error_message):
        normalize_reservation_datetime(value, restaurant_timezone)


def test_explicit_offset_preserves_instant():
    value = datetime.fromisoformat("2026-10-26T20:00:00+08:00")

    result = normalize_reservation_datetime(
        value,
        "Australia/Perth",
    )

    assert result == datetime(
        2026, 10, 26, 12, tzinfo=timezone.utc
    )
    assert result.utcoffset().total_seconds() == 0
