from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.intelligence_temporal.marginal_capacity import (
    TemporalMarginalCapacityService,
    TemporalMarginalCapacitySlot,
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
    *,
    baseline: list[bool],
    candidate: list[bool],
) -> list[TemporalMarginalCapacitySlot]:
    assert len(baseline) == len(candidate)

    return [
        TemporalMarginalCapacitySlot(
            slot_time=(
                START
                + timedelta(
                    minutes=index * 15
                )
            ),
            baseline_directly_available=(
                baseline_available
            ),
            candidate_directly_available=(
                candidate_available
            ),
        )
        for (
            index,
            (
                baseline_available,
                candidate_available,
            ),
        ) in enumerate(
            zip(
                baseline,
                candidate,
                strict=True,
            )
        )
    ]


def test_no_change_has_zero_marginal_loss():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    True,
                    True,
                    False,
                    True,
                ],
                candidate=[
                    True,
                    True,
                    False,
                    True,
                ],
            )
        )
    )

    assert result.total_slots == 4

    assert result.lost_available_slots == 0
    assert result.gained_available_slots == 0

    assert result.marginal_loss_ratio == 0.0

    assert result.first_capacity_loss_at is None
    assert result.last_capacity_loss_at is None


def test_available_to_unavailable_is_capacity_loss():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    True,
                    True,
                    True,
                    True,
                ],
                candidate=[
                    True,
                    False,
                    True,
                    False,
                ],
            )
        )
    )

    assert result.baseline_available_slots == 4
    assert result.candidate_available_slots == 2

    assert result.lost_available_slots == 2
    assert result.gained_available_slots == 0

    assert result.marginal_loss_ratio == 0.5


def test_unavailable_to_available_is_capacity_gain_not_loss():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    False,
                    False,
                    True,
                ],
                candidate=[
                    True,
                    False,
                    True,
                ],
            )
        )
    )

    assert result.lost_available_slots == 0
    assert result.gained_available_slots == 1

    assert result.marginal_loss_ratio == 0.0


def test_loss_ratio_uses_baseline_available_slots_only():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    True,
                    True,
                    False,
                    False,
                ],
                candidate=[
                    False,
                    True,
                    False,
                    False,
                ],
            )
        )
    )

    assert result.baseline_available_slots == 2
    assert result.lost_available_slots == 1

    assert result.marginal_loss_ratio == 0.5


def test_zero_baseline_capacity_has_zero_loss_ratio():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    False,
                    False,
                    False,
                ],
                candidate=[
                    False,
                    True,
                    False,
                ],
            )
        )
    )

    assert result.baseline_available_slots == 0
    assert result.lost_available_slots == 0
    assert result.gained_available_slots == 1

    assert result.marginal_loss_ratio == 0.0


def test_first_and_last_capacity_loss_are_chronological():
    slots = _slots(
        baseline=[
            True,
            True,
            True,
            True,
            True,
        ],
        candidate=[
            True,
            False,
            True,
            False,
            True,
        ],
    )

    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=list(
                reversed(slots)
            )
        )
    )

    assert (
        result.first_capacity_loss_at
        == slots[1].slot_time
    )

    assert (
        result.last_capacity_loss_at
        == slots[3].slot_time
    )


def test_unchanged_states_are_counted_separately():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=_slots(
                baseline=[
                    True,
                    False,
                    True,
                    False,
                ],
                candidate=[
                    True,
                    False,
                    False,
                    True,
                ],
            )
        )
    )

    assert result.unchanged_available_slots == 1
    assert result.unchanged_unavailable_slots == 1

    assert result.lost_available_slots == 1
    assert result.gained_available_slots == 1


def test_empty_comparison_is_valid_zero_signal():
    result = (
        TemporalMarginalCapacityService
        .calculate(
            slots=[],
        )
    )

    assert result.total_slots == 0
    assert result.baseline_available_slots == 0
    assert result.candidate_available_slots == 0

    assert result.lost_available_slots == 0
    assert result.gained_available_slots == 0

    assert result.marginal_loss_ratio == 0.0


def test_duplicate_slot_times_fail_closed():
    slot_time = START

    with pytest.raises(
        ValueError,
        match="duplicate slot times",
    ):
        TemporalMarginalCapacityService.calculate(
            slots=[
                TemporalMarginalCapacitySlot(
                    slot_time=slot_time,
                    baseline_directly_available=True,
                    candidate_directly_available=True,
                ),
                TemporalMarginalCapacitySlot(
                    slot_time=slot_time,
                    baseline_directly_available=True,
                    candidate_directly_available=False,
                ),
            ]
        )