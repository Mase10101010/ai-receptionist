from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class OpeningHoursError(ValueError):
    """Invalid opening-hours configuration."""


_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DAY_MINUTES = 1440
_DEFAULT_LAST_BOOKING_OFFSET = 30


def _minutes(value: str) -> int:
    if not isinstance(value, str):
        raise OpeningHoursError("Time must use HH:MM format.")

    match = _TIME_PATTERN.fullmatch(value)
    if match is None:
        raise OpeningHoursError(
            f"Invalid time '{value}'. Expected HH:MM."
        )

    return int(match.group(1)) * 60 + int(match.group(2))


def _session_bounds(
    session: dict[str, Any],
) -> tuple[int, int, int]:
    """Return start, end and last booking as minutes from day start."""
    start = _minutes(session.get("start"))
    end = _minutes(session.get("end"))

    if end <= start:
        end += _DAY_MINUTES

    if end - start >= _DAY_MINUTES:
        raise OpeningHoursError(
            "A session must be shorter than 24 hours."
        )

    last_value = session.get("last_booking")

    if last_value is None:
        last_booking = end - _DEFAULT_LAST_BOOKING_OFFSET
    else:
        last_booking = _minutes(last_value)

        if last_booking < start:
            last_booking += _DAY_MINUTES

    if not start <= last_booking < end:
        raise OpeningHoursError(
            "Last booking must be inside the session."
        )

    return start, end, last_booking


def validate_weekly_schedule(
    weekly_schedule: list[dict[str, Any]] | None,
) -> None:
    """Validate weekly sessions, including overnight overlaps."""
    if weekly_schedule is None:
        return

    if not isinstance(weekly_schedule, list):
        raise OpeningHoursError("Weekly schedule must be a list.")

    seen_days: set[str] = set()
    intervals: list[tuple[int, int]] = []

    for day in weekly_schedule:
        if not isinstance(day, dict):
            raise OpeningHoursError("Each day must be an object.")

        name = day.get("day")

        if name not in _DAYS:
            raise OpeningHoursError(f"Invalid weekday: {name}")

        if name in seen_days:
            raise OpeningHoursError(f"Duplicate weekday: {name}")

        seen_days.add(name)

        is_open = day.get("is_open", True)

        if not isinstance(is_open, bool):
            raise OpeningHoursError("is_open must be boolean.")

        sessions = day.get("sessions")

        if sessions is None:
            continue

        if not isinstance(sessions, list):
            raise OpeningHoursError("Sessions must be a list.")

        if not is_open and sessions:
            raise OpeningHoursError(
                f"{name} is closed but contains sessions."
            )

        day_offset = _DAYS.index(name) * _DAY_MINUTES

        for session in sessions:
            if not isinstance(session, dict):
                raise OpeningHoursError(
                    "Each session must be an object."
                )

            start, end, _ = _session_bounds(session)

            intervals.append((
                day_offset + start,
                day_offset + end,
            ))

    intervals.sort()

    for previous, current in zip(intervals, intervals[1:]):
        if current[0] < previous[1]:
            raise OpeningHoursError(
                "Overlapping opening sessions."
            )

    # Check overlap between Sunday night and Monday morning.
    if len(intervals) > 1:
        first_start = intervals[0][0] + 7 * _DAY_MINUTES
        last_end = intervals[-1][1]

        if first_start < last_end:
            raise OpeningHoursError(
                "Overlapping sessions across week boundary."
            )


def is_booking_time_allowed(
    *,
    reservation_time: datetime,
    timezone_name: str,
    weekly_schedule: list[dict[str, Any]] | None,
    opening_hour: int,
    closing_hour: int,
    special_closures: list[dict[str, Any]] | None = None,
) -> bool:
    """Check arrival eligibility without restricting meal duration."""
    if reservation_time.tzinfo is None:
        raise OpeningHoursError(
            "Reservation time must include timezone information."
        )

    try:
        local_time = reservation_time.astimezone(
            ZoneInfo(timezone_name)
        )
    except ZoneInfoNotFoundError as exc:
        raise OpeningHoursError(
            f"Unknown restaurant timezone: {timezone_name}"
        ) from exc

    local_date = local_time.date().isoformat()

    for closure in special_closures or []:
        if closure.get("date") == local_date:
            return False

    arrival = local_time.hour * 60 + local_time.minute
    weekday = local_time.weekday()

    schedules = {
        day["day"]: day
        for day in weekly_schedule or []
    }

    # Current day's sessions and previous day's overnight sessions.
    for day_shift in (0, -1):
        day_index = (weekday + day_shift) % 7
        day_name = _DAYS[day_index]
        schedule = schedules.get(day_name)

        if schedule is None:
            continue

        if not schedule.get("is_open", True):
            continue

        sessions = schedule.get("sessions")

        if sessions is None:
            continue

        relative_arrival = (
            arrival if day_shift == 0
            else arrival + _DAY_MINUTES
        )

        for session in sessions:
            start, end, last_booking = _session_bounds(session)

            if (
                start <= relative_arrival <= last_booking
                and relative_arrival < end
            ):
                service_date = (
                    local_time.date()
                    if day_shift == 0
                    else local_time.date() - timedelta(days=1)
                )

                if any(
                    closure.get("date") == service_date.isoformat()
                    for closure in special_closures or []
                ):
                    return False

                return True

        if day_shift == 0:
            # Explicit sessions override legacy hours for this day.
            continue

    # If the current day has explicit sessions, no legacy fallback.
    current = schedules.get(_DAYS[weekday])

    if current is not None and current.get("sessions") is not None:
        return False

    if current is not None and not current.get("is_open", True):
        return False

    if current is not None:
        opening_hour = current.get(
            "opening_hour", opening_hour
        )
        closing_hour = current.get(
            "closing_hour", closing_hour
        )

    return opening_hour <= local_time.hour < closing_hour
