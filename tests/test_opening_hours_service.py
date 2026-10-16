
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.opening_hours_service import (
    OpeningHoursError,
    is_booking_time_allowed,
    validate_weekly_schedule,
)


TIMEZONE = "Australia/Perth"

WEEKLY_SCHEDULE = [
    {
        "day": "Mon",
        "is_open": True,
        "sessions": [
            {
                "start": "12:00",
                "end": "15:00",
                "last_booking": "14:30",
            },
            {
                "start": "19:00",
                "end": "23:00",
                "last_booking": "22:30",
            },
        ],
    },
    {
        "day": "Tue",
        "is_open": False,
        "sessions": [],
    },
]


def booking_time(hour: int, minute: int = 0) -> datetime:
    return datetime(
        2026, 10, 19, hour, minute,
        tzinfo=ZoneInfo(TIMEZONE),
    )


def allowed(dt: datetime, **overrides) -> bool:
    params = {
        "reservation_time": dt,
        "timezone_name": TIMEZONE,
        "weekly_schedule": WEEKLY_SCHEDULE,
        "opening_hour": 11,
        "closing_hour": 22,
        "special_closures": None,
    }
    params.update(overrides)
    return is_booking_time_allowed(**params)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (11, 59, False),
        (12, 0, True),
        (14, 29, True),
        (14, 30, True),
        (14, 31, False),
        (15, 0, False),
        (17, 0, False),
        (18, 59, False),
        (19, 0, True),
        (22, 30, True),
        (22, 31, False),
        (23, 0, False),
    ],
)
def test_multiple_sessions(hour, minute, expected):
    assert allowed(booking_time(hour, minute)) is expected


def test_closed_weekday():
    tuesday = datetime(
        2026, 10, 20, 13, 0,
        tzinfo=ZoneInfo(TIMEZONE),
    )
    assert allowed(tuesday) is False


def test_special_closure():
    assert allowed(
        booking_time(13),
        special_closures=[
            {"date": "2026-10-19", "reason": "Private event"}
        ],
    ) is False


def test_legacy_opening_hours():
    assert allowed(
        booking_time(21, 59),
        weekly_schedule=None,
    ) is True

    assert allowed(
        booking_time(22),
        weekly_schedule=None,
    ) is False


def test_legacy_weekly_schedule():
    legacy = [
        {
            "day": "Mon",
            "is_open": True,
            "opening_hour": 10,
            "closing_hour": 18,
        }
    ]
    assert allowed(
        booking_time(17, 45),
        weekly_schedule=legacy,
    ) is True

    assert allowed(
        booking_time(18),
        weekly_schedule=legacy,
    ) is False


def test_valid_schedule():
    validate_weekly_schedule(WEEKLY_SCHEDULE)


def test_overlapping_sessions_rejected():
    invalid = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {
                    "start": "12:00",
                    "end": "15:00",
                    "last_booking": "14:30",
                },
                {
                    "start": "14:00",
                    "end": "23:00",
                    "last_booking": "22:30",
                },
            ],
        }
    ]

    with pytest.raises(OpeningHoursError):
        validate_weekly_schedule(invalid)


def test_last_booking_outside_session_rejected():
    invalid = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {
                    "start": "12:00",
                    "end": "15:00",
                    "last_booking": "15:30",
                }
            ],
        }
    ]

    with pytest.raises(OpeningHoursError):
        validate_weekly_schedule(invalid)


def test_duplicate_weekday_rejected():
    with pytest.raises(OpeningHoursError):
        validate_weekly_schedule([
            {"day": "Mon", "is_open": True},
            {"day": "Mon", "is_open": False},
        ])


def test_naive_datetime_rejected():
    with pytest.raises(OpeningHoursError):
        allowed(datetime(2026, 10, 19, 13, 0))


def test_overnight_session_after_midnight():
    schedule = [
        {
            "day": "Fri",
            "is_open": True,
            "sessions": [
                {
                    "start": "19:00",
                    "end": "02:00",
                    "last_booking": "01:30",
                }
            ],
        },
        {"day": "Sat", "is_open": False, "sessions": []},
    ]

    validate_weekly_schedule(schedule)

    saturday_early = datetime(
        2026, 10, 17, 0, 30,
        tzinfo=ZoneInfo(TIMEZONE),
    )

    assert allowed(
        saturday_early,
        weekly_schedule=schedule,
    ) is True


def test_overnight_session_does_not_allow_late_legacy_fallback():
    schedule = [
        {
            "day": "Fri",
            "is_open": True,
            "sessions": [
                {
                    "start": "19:00",
                    "end": "02:00",
                    "last_booking": "01:30",
                }
            ],
        },
        {"day": "Sat", "is_open": False, "sessions": []},
    ]

    saturday_after_service = datetime(
        2026, 10, 17, 3, 0,
        tzinfo=ZoneInfo(TIMEZONE),
    )

    assert allowed(
        saturday_after_service,
        weekly_schedule=schedule,
    ) is False


def test_overnight_session_respects_previous_day_special_closure():
    schedule = [
        {
            "day": "Fri",
            "is_open": True,
            "sessions": [
                {
                    "start": "19:00",
                    "end": "02:00",
                    "last_booking": "01:30",
                }
            ],
        },
        {"day": "Sat", "is_open": False, "sessions": []},
    ]

    saturday_early = datetime(
        2026, 10, 17, 0, 30,
        tzinfo=ZoneInfo(TIMEZONE),
    )

    assert allowed(
        saturday_early,
        weekly_schedule=schedule,
        special_closures=[
            {
                "date": "2026-10-16",
                "reason": "Private event",
            }
        ],
    ) is False


def test_overlapping_sessions_across_midnight_rejected():
    schedule = [
        {
            "day": "Fri",
            "is_open": True,
            "sessions": [
                {"start": "19:00", "end": "02:00"}
            ],
        },
        {
            "day": "Sat",
            "is_open": True,
            "sessions": [
                {"start": "01:00", "end": "04:00"}
            ],
        },
    ]

    with pytest.raises(OpeningHoursError):
        validate_weekly_schedule(schedule)


def test_overlapping_sessions_across_week_boundary_rejected():
    schedule = [
        {
            "day": "Sun",
            "is_open": True,
            "sessions": [
                {"start": "20:00", "end": "03:00"}
            ],
        },
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {"start": "02:00", "end": "06:00"}
            ],
        },
    ]

    with pytest.raises(OpeningHoursError):
        validate_weekly_schedule(schedule)
