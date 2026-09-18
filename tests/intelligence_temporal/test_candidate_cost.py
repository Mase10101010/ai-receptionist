from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import pytest

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)
from app.intelligence_temporal.candidate_cost import (
    TemporalCandidateCostService,
)
from app.intelligence_temporal.marginal_capacity import (
    TemporalMarginalCapacityLoss,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _candidate(
    *,
    score: float = 80.0,
    seat_waste: int = 2,
    fragmentation_minutes: int = 15,
) -> IntelligenceAssignmentResponse:
    table_id = uuid4()

    return IntelligenceAssignmentResponse(
        table_ids=[table_id],
        table_numbers=["12"],
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        capacity=4,
        score=score,
        seat_waste=seat_waste,
        fragmentation_minutes=(
            fragmentation_minutes
        ),
        explanation="Technical candidate.",
    )


def _loss(
    *,
    baseline: int = 10,
    candidate: int = 8,
    lost: int = 2,
    gained: int = 0,
    ratio: float = 0.2,
) -> TemporalMarginalCapacityLoss:
    return TemporalMarginalCapacityLoss(
        total_slots=10,
        baseline_available_slots=baseline,
        candidate_available_slots=candidate,
        lost_available_slots=lost,
        gained_available_slots=gained,
        unchanged_available_slots=8,
        unchanged_unavailable_slots=0,
        marginal_loss_ratio=ratio,
        first_capacity_loss_at=(
            NOW + timedelta(minutes=60)
            if lost
            else None
        ),
        last_capacity_loss_at=(
            NOW + timedelta(minutes=90)
            if lost
            else None
        ),
    )


def test_preserves_candidate_identity():
    candidate = _candidate()

    result = (
        TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=_loss(),
        )
    )

    assert result.table_ids == tuple(
        candidate.table_ids
    )

    assert result.start_at == candidate.start_at
    assert result.end_at == candidate.end_at


def test_preserves_existing_technical_score():
    candidate = _candidate(score=73.25)

    result = (
        TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=_loss(),
        )
    )

    assert result.base_score == 73.25


def test_preserves_existing_efficiency_signals():
    candidate = _candidate(
        seat_waste=3,
        fragmentation_minutes=25,
    )

    result = (
        TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=_loss(),
        )
    )

    assert result.seat_waste == 3
    assert result.fragmentation_minutes == 25


def test_maps_marginal_future_capacity_truth():
    result = (
        TemporalCandidateCostService.calculate(
            candidate=_candidate(),
            marginal_capacity=_loss(
                baseline=12,
                candidate=9,
                lost=3,
                ratio=0.25,
            ),
        )
    )

    assert (
        result.future_baseline_available_slots
        == 12
    )

    assert (
        result.future_candidate_available_slots
        == 9
    )

    assert (
        result.lost_future_available_slots
        == 3
    )

    assert (
        result.marginal_capacity_loss_ratio
        == 0.25
    )


def test_temporal_cost_true_when_future_capacity_is_lost():
    result = (
        TemporalCandidateCostService.calculate(
            candidate=_candidate(),
            marginal_capacity=_loss(
                lost=1,
                ratio=0.1,
            ),
        )
    )

    assert result.has_temporal_cost is True


def test_no_temporal_cost_when_no_capacity_is_lost():
    result = (
        TemporalCandidateCostService.calculate(
            candidate=_candidate(),
            marginal_capacity=_loss(
                baseline=10,
                candidate=10,
                lost=0,
                ratio=0.0,
            ),
        )
    )

    assert result.has_temporal_cost is False

    assert (
        result.first_future_capacity_loss_at
        is None
    )

    assert (
        result.last_future_capacity_loss_at
        is None
    )


def test_gained_capacity_does_not_become_loss():
    result = (
        TemporalCandidateCostService.calculate(
            candidate=_candidate(),
            marginal_capacity=_loss(
                baseline=8,
                candidate=10,
                lost=0,
                gained=2,
                ratio=0.0,
            ),
        )
    )

    assert (
        result.gained_future_available_slots
        == 2
    )

    assert result.has_temporal_cost is False


def test_duplicate_candidate_tables_fail_closed():
    candidate = _candidate()

    candidate.table_ids = [
        candidate.table_ids[0],
        candidate.table_ids[0],
    ]

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=_loss(),
        )


def test_invalid_candidate_interval_fails_closed():
    candidate = _candidate()

    candidate.end_at = candidate.start_at

    with pytest.raises(
        ValueError,
        match="end_at must be after",
    ):
        TemporalCandidateCostService.calculate(
            candidate=candidate,
            marginal_capacity=_loss(),
        )