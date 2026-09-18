from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.intelligence_temporal.saturation import (
    TemporalSaturationService,
    TemporalSaturationSlot,
    TemporalSaturationState,
)


START = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _slots(
    availability: list[bool],
) -> list[TemporalSaturationSlot]:
    return [
        TemporalSaturationSlot(
            slot_time=(
                START
                + timedelta(
                    minutes=index * 15
                )
            ),
            directly_available=available,
        )
        for index, available
        in enumerate(availability)
    ]


def test_empty_profile_is_low_saturation():
    result = TemporalSaturationService.calculate(
        slots=[],
    )

    assert result.total_slots == 0
    assert result.available_slots == 0
    assert result.unavailable_slots == 0
    assert result.unavailable_ratio == 0.0

    assert (
        result.state
        == TemporalSaturationState.LOW
    )


def test_all_available_is_low_saturation():
    result = TemporalSaturationService.calculate(
        slots=_slots(
            [
                True,
                True,
                True,
                True,
            ]
        ),
    )

    assert result.available_slots == 4
    assert result.unavailable_slots == 0

    assert (
        result.state
        == TemporalSaturationState.LOW
    )

    assert result.longest_unavailable_run == 0


def test_quarter_unavailable_is_moderate():
    result = TemporalSaturationService.calculate(
        slots=_slots(
            [
                True,
                True,
                True,
                False,
            ]
        ),
    )

    assert result.unavailable_ratio == 0.25

    assert (
        result.state
        == TemporalSaturationState.MODERATE
    )


def test_sixty_percent_unavailable_is_high():
    result = TemporalSaturationService.calculate(
        slots=_slots(
            [
                False,
                False,
                False,
                True,
                True,
            ]
        ),
    )

    assert result.unavailable_ratio == 0.6

    assert (
        result.state
        == TemporalSaturationState.HIGH
    )


def test_all_unavailable_is_full():
    result = TemporalSaturationService.calculate(
        slots=_slots(
            [
                False,
                False,
                False,
            ]
        ),
    )

    assert result.unavailable_ratio == 1.0

    assert (
        result.state
        == TemporalSaturationState.FULL
    )


def test_tracks_first_available_and_unavailable_slots():
    slots = _slots(
        [
            False,
            False,
            True,
            True,
        ]
    )

    result = TemporalSaturationService.calculate(
        slots=slots,
    )

    assert (
        result.first_unavailable_at
        == slots[0].slot_time
    )

    assert (
        result.first_available_at
        == slots[2].slot_time
    )


def test_longest_unavailable_run_is_calculated():
    result = TemporalSaturationService.calculate(
        slots=_slots(
            [
                False,
                False,
                True,
                False,
                False,
                False,
                True,
                False,
            ]
        ),
    )

    assert result.longest_unavailable_run == 3


def test_input_order_does_not_change_run_semantics():
    slots = _slots(
        [
            False,
            False,
            True,
            False,
        ]
    )

    result = TemporalSaturationService.calculate(
        slots=list(
            reversed(slots)
        ),
    )

    assert result.longest_unavailable_run == 2


def test_duplicate_slot_time_fails_closed():
    slot_time = START

    with pytest.raises(
        ValueError,
        match="duplicate slot times",
    ):
        TemporalSaturationService.calculate(
            slots=[
                TemporalSaturationSlot(
                    slot_time=slot_time,
                    directly_available=True,
                ),
                TemporalSaturationSlot(
                    slot_time=slot_time,
                    directly_available=False,
                ),
            ],
        )