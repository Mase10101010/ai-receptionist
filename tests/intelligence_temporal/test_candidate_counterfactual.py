from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import UUID, uuid4

import pytest

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)
from app.intelligence_temporal.candidate_counterfactual import (
    TemporalCandidateCounterfactualService,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()


def _candidate() -> IntelligenceAssignmentResponse:
    return IntelligenceAssignmentResponse(
        table_ids=[uuid4()],
        table_numbers=["12"],
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        capacity=4,
        score=82.5,
        seat_waste=2,
        fragmentation_minutes=10,
        explanation="Technical candidate.",
    )


def _profile(
    availability: list[bool],
    *,
    restaurant_id: UUID = RESTAURANT_ID,
    start_at: datetime = NOW,
    horizon_minutes: int | None = None,
    slot_minutes: int = 30,
    party_size: int = 2,
    duration_minutes: int = 90,
) -> FutureCapacityResponse:
    slots: list[FutureCapacitySlot] = []

    for index, available in enumerate(
        availability
    ):
        slot_start = (
            start_at
            + timedelta(
                minutes=index * slot_minutes
            )
        )

        slots.append(
            FutureCapacitySlot(
                start_at=slot_start,
                end_at=(
                    slot_start
                    + timedelta(
                        minutes=duration_minutes
                    )
                ),
                directly_available=available,
                assignment_capacity=(
                    4
                    if available
                    else None
                ),
            )
        )

    available_count = sum(
        1
        for available in availability
        if available
    )

    if horizon_minutes is None:
        horizon_minutes = (
            (len(availability) - 1)
            * slot_minutes
            if availability
            else 0
        )

    first_available = next(
        (
            slot.start_at
            for slot in slots
            if slot.directly_available
        ),
        None,
    )

    longest_run = 0
    current_run = 0

    for available in availability:
        if available:
            current_run += 1
            longest_run = max(
                longest_run,
                current_run,
            )
        else:
            current_run = 0

    return FutureCapacityResponse(
        restaurant_id=restaurant_id,
        start_at=start_at,
        party_size=party_size,
        duration_minutes=duration_minutes,
        horizon_minutes=horizon_minutes,
        slot_minutes=slot_minutes,
        slots=slots,
        summary=FutureCapacitySummary(
            total_slots=len(slots),
            directly_available_slots=(
                available_count
            ),
            unavailable_slots=(
                len(slots)
                - available_count
            ),
            availability_ratio=(
                available_count / len(slots)
                if slots
                else 0.0
            ),
            first_directly_available_at=(
                first_available
            ),
            longest_directly_available_run=(
                longest_run
            ),
        ),
    )


def test_evaluates_future_capacity_loss():
    result = (
        TemporalCandidateCounterfactualService
        .evaluate(
            candidate=_candidate(),
            baseline=_profile(
                [
                    True,
                    True,
                    True,
                    True,
                ]
            ),
            candidate_profile=_profile(
                [
                    True,
                    False,
                    False,
                    True,
                ]
            ),
        )
    )

    assert result.evaluated_slots == 4
    assert result.baseline_available_slots == 4
    assert result.candidate_available_slots == 2

    assert (
        result.cost.lost_future_available_slots
        == 2
    )

    assert (
        result.cost.marginal_capacity_loss_ratio
        == 0.5
    )

    assert result.cost.has_temporal_cost is True


def test_no_loss_preserves_zero_temporal_cost():
    result = (
        TemporalCandidateCounterfactualService
        .evaluate(
            candidate=_candidate(),
            baseline=_profile(
                [
                    True,
                    False,
                    True,
                ]
            ),
            candidate_profile=_profile(
                [
                    True,
                    False,
                    True,
                ]
            ),
        )
    )

    assert (
        result.cost.lost_future_available_slots
        == 0
    )

    assert (
        result.cost.marginal_capacity_loss_ratio
        == 0.0
    )

    assert result.cost.has_temporal_cost is False


def test_capacity_gain_is_preserved():
    result = (
        TemporalCandidateCounterfactualService
        .evaluate(
            candidate=_candidate(),
            baseline=_profile(
                [
                    False,
                    False,
                    True,
                ]
            ),
            candidate_profile=_profile(
                [
                    True,
                    False,
                    True,
                ]
            ),
        )
    )

    assert (
        result.cost.gained_future_available_slots
        == 1
    )

    assert (
        result.cost.lost_future_available_slots
        == 0
    )


def test_candidate_identity_is_preserved():
    candidate = _candidate()

    result = (
        TemporalCandidateCounterfactualService
        .evaluate(
            candidate=candidate,
            baseline=_profile(
                [True, True]
            ),
            candidate_profile=_profile(
                [True, False]
            ),
        )
    )

    assert result.cost.table_ids == tuple(
        candidate.table_ids
    )

    assert result.cost.base_score == candidate.score


def test_different_restaurant_fails_closed():
    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=_candidate(),
                baseline=_profile(
                    [True, True]
                ),
                candidate_profile=_profile(
                    [True, True],
                    restaurant_id=uuid4(),
                ),
            )
        )


def test_different_start_fails_closed():
    with pytest.raises(
        ValueError,
        match="same start_at",
    ):
        (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=_candidate(),
                baseline=_profile(
                    [True, True]
                ),
                candidate_profile=_profile(
                    [True, True],
                    start_at=(
                        NOW
                        + timedelta(minutes=30)
                    ),
                ),
            )
        )


def test_different_slot_size_fails_closed():
    with pytest.raises(
        ValueError,
        match="same slot_minutes",
    ):
        (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=_candidate(),
                baseline=_profile(
                    [True, True, True],
                    slot_minutes=30,
                    horizon_minutes=60,
                ),
                candidate_profile=_profile(
                    [True, True],
                    slot_minutes=60,
                    horizon_minutes=60,
                ),
            )
        )


def test_different_slot_times_fail_closed():
    baseline = _profile(
        [
            True,
            True,
            True,
        ]
    )

    candidate_profile = _profile(
        [
            True,
            True,
            True,
        ]
    )

    candidate_profile.slots[1].start_at = (
        candidate_profile.slots[1].start_at
        + timedelta(minutes=5)
    )

    with pytest.raises(
        ValueError,
        match="same slot times",
    ):
        (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=_candidate(),
                baseline=baseline,
                candidate_profile=(
                    candidate_profile
                ),
            )
        )


def test_duplicate_slot_times_fail_closed():
    baseline = _profile(
        [
            True,
            True,
            True,
        ]
    )

    baseline.slots[1].start_at = (
        baseline.slots[0].start_at
    )

    with pytest.raises(
        ValueError,
        match="duplicate slot times",
    ):
        (
            TemporalCandidateCounterfactualService
            .evaluate(
                candidate=_candidate(),
                baseline=baseline,
                candidate_profile=_profile(
                    [
                        True,
                        True,
                        True,
                    ]
                ),
            )
        )