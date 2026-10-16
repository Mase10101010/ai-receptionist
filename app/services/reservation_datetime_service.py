"""Timezone-safe normalization of reservation datetimes."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ReservationDateTimeError(ValueError):
    """Invalid or ambiguous reservation datetime."""


def normalize_reservation_datetime(
    value: datetime,
    timezone_name: str,
) -> datetime:
    """Return an aware UTC datetime for a reservation."""

    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(timezone.utc)

    try:
        restaurant_timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ReservationDateTimeError(
            f"Invalid restaurant timezone: {timezone_name}"
        ) from exc

    candidates = []

    for fold in (0, 1):
        local = value.replace(
            tzinfo=restaurant_timezone,
            fold=fold,
        )
        utc_value = local.astimezone(timezone.utc)
        round_trip = utc_value.astimezone(restaurant_timezone)

        if round_trip.replace(tzinfo=None) == value:
            if utc_value not in candidates:
                candidates.append(utc_value)

    if not candidates:
        raise ReservationDateTimeError(
            "This local reservation time does not exist "
            "because of a daylight-saving transition."
        )

    if len(candidates) > 1:
        raise ReservationDateTimeError(
            "This local reservation time is ambiguous "
            "because of a daylight-saving transition. "
            "Provide an explicit UTC offset."
        )

    return candidates[0]



def normalize_persisted_datetime(value: datetime) -> datetime:
    """Normalize a persisted UTC instant to an aware UTC datetime.

    PostgreSQL may return naive datetimes for UTC values stored in
    timestamp-without-time-zone columns.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)
