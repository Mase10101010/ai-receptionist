from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence_temporal.candidate_cost import (
    TemporalCandidateCost,
)
from app.intelligence_temporal.temporal_ranking import (
    TemporalRankingPolicy,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _cost(
    *,
    base_score: float = 90.0,
    loss_ratio: float = 0.0,
    lost_slots: int = 0,
) -> TemporalCandidateCost:
    return TemporalCandidateCost(
        table_ids=(uuid4(),),
        start_at=NOW,
        end_at=(
            NOW
            + timedelta(minutes=90)
        ),
        base_score=base_score,
        seat_waste=0,
        fragmentation_minutes=0,
        future_baseline_available_slots=10,
        future_candidate_available_slots=(
            10 - lost_slots
        ),
        lost_future_available_slots=lost_slots,
        gained_future_available_slots=0,
        marginal_capacity_loss_ratio=loss_ratio,
        first_future_capacity_loss_at=(
            NOW + timedelta(minutes=30)
            if lost_slots
            else None
        ),
        last_future_capacity_loss_at=(
            NOW + timedelta(minutes=60)
            if lost_slots
            else None
        ),
        has_temporal_cost=(
            lost_slots > 0
        ),
    )


def test_zero_temporal_cost_preserves_base_score():
    result = TemporalRankingPolicy.score(
        cost=_cost(
            base_score=90.0,
            loss_ratio=0.0,
        )
    )

    assert result.temporal_penalty == 0.0
    assert result.effective_score == 90.0


def test_temporal_loss_reduces_effective_score():
    result = TemporalRankingPolicy.score(
        cost=_cost(
            base_score=90.0,
            loss_ratio=0.4,
            lost_slots=4,
        )
    )

    assert result.temporal_penalty == 10.0
    assert result.effective_score == 80.0


def test_full_loss_applies_max_v1_penalty():
    result = TemporalRankingPolicy.score(
        cost=_cost(
            base_score=90.0,
            loss_ratio=1.0,
            lost_slots=10,
        )
    )

    assert result.temporal_penalty == 25.0
    assert result.effective_score == 65.0


def test_preserves_original_base_score():
    result = TemporalRankingPolicy.score(
        cost=_cost(
            base_score=77.5,
            loss_ratio=0.2,
            lost_slots=2,
        )
    )

    assert result.base_score == 77.5


def test_lower_temporal_cost_can_beat_higher_technical_score():
    technically_better = (
        TemporalRankingPolicy.score(
            cost=_cost(
                base_score=92.0,
                loss_ratio=0.4,
                lost_slots=4,
            )
        )
    )

    temporally_better = (
        TemporalRankingPolicy.score(
            cost=_cost(
                base_score=88.0,
                loss_ratio=0.0,
                lost_slots=0,
            )
        )
    )

    assert (
        temporally_better.effective_score
        >
        technically_better.effective_score
    )


def test_large_technical_advantage_can_still_win():
    technically_strong = (
        TemporalRankingPolicy.score(
            cost=_cost(
                base_score=100.0,
                loss_ratio=0.2,
                lost_slots=2,
            )
        )
    )

    technically_weaker = (
        TemporalRankingPolicy.score(
            cost=_cost(
                base_score=80.0,
                loss_ratio=0.0,
                lost_slots=0,
            )
        )
    )

    assert (
        technically_strong.effective_score
        >
        technically_weaker.effective_score
    )


def test_ranking_score_preserves_loss_truth():
    result = TemporalRankingPolicy.score(
        cost=_cost(
            base_score=90.0,
            loss_ratio=0.3,
            lost_slots=3,
        )
    )

    assert (
        result.marginal_capacity_loss_ratio
        == 0.3
    )

    assert (
        result.lost_future_available_slots
        == 3
    )