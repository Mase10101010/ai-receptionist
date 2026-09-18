from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

from app.intelligence_temporal.reoptimization_capacity_evidence import (
    TemporalReoptimizationCapacityEvidenceService,
)
from app.intelligence_temporal.reoptimization_capacity_runner import (
    TemporalReoptimizationCapacityRun,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()


def _profile(
    availability: list[bool],
    *,
    restaurant_id=RESTAURANT_ID,
    start_at=NOW,
):
    slots = [
        FutureCapacitySlot(
            start_at=(
                start_at
                + timedelta(minutes=index * 30)
            ),
            end_at=(
                start_at
                + timedelta(minutes=(index + 1) * 30)
            ),
            directly_available=value,
        )
        for index, value in enumerate(
            availability
        )
    ]

    available_count = sum(
        1
        for value in availability
        if value
    )

    return FutureCapacityResponse(
        restaurant_id=restaurant_id,
        start_at=start_at,
        party_size=4,
        duration_minutes=30,
        horizon_minutes=(
            max(
                0,
                (len(availability) - 1) * 30,
            )
        ),
        slot_minutes=30,
        slots=slots,
        summary=FutureCapacitySummary(
            total_slots=len(slots),
            directly_available_slots=(
                available_count
            ),
            unavailable_slots=(
                len(slots) - available_count
            ),
            availability_ratio=(
                available_count / len(slots)
                if slots
                else 0.0
            ),
            first_directly_available_at=next(
                (
                    slot.start_at
                    for slot in slots
                    if slot.directly_available
                ),
                None,
            ),
            longest_directly_available_run=0,
        ),
    )


def _run(
    baseline,
    candidate,
):
    return TemporalReoptimizationCapacityRun(
        baseline=baseline,
        candidate=candidate,
        new_reservation_id="new",
        moved_reservation_ids=(),
    )


def test_no_capacity_change_has_zero_loss():
    result = (
        TemporalReoptimizationCapacityEvidenceService
        .evaluate(
            run=_run(
                _profile(
                    [True, False, True]
                ),
                _profile(
                    [True, False, True]
                ),
            ),
        )
    )

    assert result.evaluated_slots == 3
    assert result.lost_future_available_slots == 0
    assert result.gained_future_available_slots == 0
    assert result.marginal_capacity_loss_ratio == 0.0


def test_future_capacity_loss_is_detected():
    result = (
        TemporalReoptimizationCapacityEvidenceService
        .evaluate(
            run=_run(
                _profile(
                    [True, True, True, True]
                ),
                _profile(
                    [True, False, False, True]
                ),
            ),
        )
    )

    assert result.baseline_available_slots == 4
    assert result.candidate_available_slots == 2
    assert result.lost_future_available_slots == 2

    assert (
        result.marginal_capacity_loss_ratio
        == 0.5
    )


def test_capacity_gain_is_preserved():
    result = (
        TemporalReoptimizationCapacityEvidenceService
        .evaluate(
            run=_run(
                _profile(
                    [False, False, True]
                ),
                _profile(
                    [True, False, True]
                ),
            ),
        )
    )

    assert result.lost_future_available_slots == 0
    assert result.gained_future_available_slots == 1
    assert result.marginal_capacity_loss_ratio == 0.0


def test_loss_and_gain_are_counted_independently():
    result = (
        TemporalReoptimizationCapacityEvidenceService
        .evaluate(
            run=_run(
                _profile(
                    [True, False, True]
                ),
                _profile(
                    [False, True, True]
                ),
            ),
        )
    )

    assert result.lost_future_available_slots == 1
    assert result.gained_future_available_slots == 1

    assert (
        result.marginal_capacity_loss_ratio
        == 0.5
    )


def test_restaurant_mismatch_fails():
    with pytest.raises(
        ValueError,
        match="restaurant",
    ):
        (
            TemporalReoptimizationCapacityEvidenceService
            .evaluate(
                run=_run(
                    _profile([True]),
                    _profile(
                        [True],
                        restaurant_id=uuid4(),
                    ),
                ),
            )
        )


def test_start_time_mismatch_fails():
    with pytest.raises(
        ValueError,
        match="start",
    ):
        (
            TemporalReoptimizationCapacityEvidenceService
            .evaluate(
                run=_run(
                    _profile([True]),
                    _profile(
                        [True],
                        start_at=(
                            NOW
                            + timedelta(minutes=30)
                        ),
                    ),
                ),
            )
        )


def test_slot_alignment_mismatch_fails():
    baseline = _profile(
        [True, True],
    )

    candidate = _profile(
        [True, True],
    )

    candidate.slots[1].start_at = (
        candidate.slots[1].start_at
        + timedelta(minutes=15)
    )

    with pytest.raises(
        ValueError,
        match="aligned",
    ):
        (
            TemporalReoptimizationCapacityEvidenceService
            .evaluate(
                run=_run(
                    baseline,
                    candidate,
                ),
            )
        )


def test_evidence_is_plan_level_not_execution_authority():
    result = (
        TemporalReoptimizationCapacityEvidenceService
        .evaluate(
            run=_run(
                _profile([True]),
                _profile([True]),
            ),
        )
    )

    assert not hasattr(
        result,
        "allowed",
    )

    assert not hasattr(
        result,
        "execution_eligibility",
    )