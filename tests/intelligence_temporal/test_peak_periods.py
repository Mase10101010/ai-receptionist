from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.intelligence_temporal.peak_periods import (
    TemporalPeakPeriodService,
    TemporalPeakState,
)
from app.intelligence_temporal.saturation import (
    TemporalSaturationSlot,
)


START = datetime(
    2026,
    9,
    6,
    18,
    0,
    tzinfo=timezone.utc,
)


def _period(
    *,
    start_offset_minutes: int,
    availability: list[bool],
) -> list[TemporalSaturationSlot]:
    return [
        TemporalSaturationSlot(
            slot_time=(
                START
                + timedelta(
                    minutes=(
                        start_offset_minutes
                        + index * 15
                    )
                )
            ),
            directly_available=available,
        )
        for index, available
        in enumerate(availability)
    ]


def test_low_saturation_period_is_off_peak():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                _period(
                    start_offset_minutes=0,
                    availability=[
                        True,
                        True,
                        True,
                        True,
                    ],
                )
            ]
        )
    )

    assert len(result.periods) == 1

    assert (
        result.periods[0].state
        == TemporalPeakState.OFF_PEAK
    )


def test_quarter_unavailable_is_balanced():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                _period(
                    start_offset_minutes=0,
                    availability=[
                        True,
                        True,
                        True,
                        False,
                    ],
                )
            ]
        )
    )

    assert (
        result.periods[0].state
        == TemporalPeakState.BALANCED
    )


def test_sixty_percent_unavailable_is_peak():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                _period(
                    start_offset_minutes=0,
                    availability=[
                        False,
                        False,
                        False,
                        True,
                        True,
                    ],
                )
            ]
        )
    )

    assert (
        result.periods[0].state
        == TemporalPeakState.PEAK
    )


def test_fully_unavailable_period_is_peak():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                _period(
                    start_offset_minutes=0,
                    availability=[
                        False,
                        False,
                        False,
                    ],
                )
            ]
        )
    )

    assert (
        result.periods[0].state
        == TemporalPeakState.PEAK
    )


def test_multiple_periods_are_classified_independently():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                _period(
                    start_offset_minutes=0,
                    availability=[
                        True,
                        True,
                        True,
                        True,
                    ],
                ),
                _period(
                    start_offset_minutes=60,
                    availability=[
                        True,
                        True,
                        False,
                        False,
                    ],
                ),
                _period(
                    start_offset_minutes=120,
                    availability=[
                        False,
                        False,
                        False,
                        True,
                    ],
                ),
            ]
        )
    )

    assert [
        period.state
        for period in result.periods
    ] == [
        TemporalPeakState.OFF_PEAK,
        TemporalPeakState.BALANCED,
        TemporalPeakState.PEAK,
    ]


def test_period_boundaries_are_preserved():
    period = _period(
        start_offset_minutes=30,
        availability=[
            True,
            False,
            True,
        ],
    )

    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                period,
            ]
        )
    )

    assert (
        result.periods[0].start_at
        == period[0].slot_time
    )

    assert (
        result.periods[0].end_at
        == period[-1].slot_time
    )


def test_input_slot_order_is_normalized():
    period = _period(
        start_offset_minutes=0,
        availability=[
            True,
            False,
            False,
            False,
        ],
    )

    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                list(
                    reversed(period)
                )
            ]
        )
    )

    assert (
        result.periods[0].state
        == TemporalPeakState.PEAK
    )


def test_empty_periods_are_ignored():
    result = (
        TemporalPeakPeriodService
        .calculate(
            periods=[
                [],
                _period(
                    start_offset_minutes=0,
                    availability=[
                        True,
                        True,
                    ],
                ),
                [],
            ]
        )
    )

    assert len(result.periods) == 1

    assert (
        result.periods[0].state
        == TemporalPeakState.OFF_PEAK
    )