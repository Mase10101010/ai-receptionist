from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)
from app.intelligence_temporal.candidate_cost import (
    TemporalCandidateCost,
)
from app.intelligence_temporal.candidate_counterfactual import (
    TemporalCandidateCounterfactual,
)
from app.intelligence_temporal.candidate_ranking import (
    TemporalCandidateRankingService,
)
from app.intelligence_temporal.candidate_temporal_evaluator import (
    TemporalCandidateEvaluation,
)


NOW = datetime(
    2026,
    9,
    6,
    19,
    0,
    tzinfo=timezone.utc,
)


def _evaluation(
    *,
    base_score: float,
    loss_ratio: float = 0.0,
    lost_slots: int = 0,
    seat_waste: int = 0,
    fragmentation_minutes: int = 0,
    table_count: int = 1,
) -> TemporalCandidateEvaluation:
    table_ids = [
        uuid4()
        for _ in range(table_count)
    ]

    candidate = IntelligenceAssignmentResponse(
        table_ids=table_ids,
        table_numbers=[
            str(index + 1)
            for index in range(table_count)
        ],
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        capacity=4 * table_count,
        score=base_score,
        seat_waste=seat_waste,
        fragmentation_minutes=(
            fragmentation_minutes
        ),
        explanation="Candidate.",
    )

    cost = TemporalCandidateCost(
        table_ids=tuple(table_ids),
        start_at=candidate.start_at,
        end_at=candidate.end_at,
        base_score=base_score,
        seat_waste=seat_waste,
        fragmentation_minutes=(
            fragmentation_minutes
        ),
        future_baseline_available_slots=10,
        future_candidate_available_slots=(
            10 - lost_slots
        ),
        lost_future_available_slots=(
            lost_slots
        ),
        gained_future_available_slots=0,
        marginal_capacity_loss_ratio=(
            loss_ratio
        ),
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

    counterfactual = (
        TemporalCandidateCounterfactual(
            cost=cost,
            evaluated_slots=10,
            baseline_available_slots=10,
            candidate_available_slots=(
                10 - lost_slots
            ),
        )
    )

    return TemporalCandidateEvaluation(
        candidate=candidate,
        counterfactual=counterfactual,
        occupancy_duration_minutes=90,
    )


def test_higher_effective_score_ranks_first():
    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                _evaluation(
                    base_score=80.0,
                ),
                _evaluation(
                    base_score=90.0,
                ),
            ],
        )
    )

    assert (
        result.ranked[0]
        .ranking.effective_score
        == 90.0
    )


def test_temporal_cost_can_change_order():
    technically_best = _evaluation(
        base_score=92.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    temporally_best = _evaluation(
        base_score=88.0,
        loss_ratio=0.0,
        lost_slots=0,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                technically_best,
                temporally_best,
            ],
        )
    )

    assert (
        result.ranked[0]
        .evaluation.candidate.score
        == 88.0
    )


def test_large_technical_advantage_still_wins():
    strong = _evaluation(
        base_score=100.0,
        loss_ratio=0.2,
        lost_slots=2,
    )

    weak = _evaluation(
        base_score=80.0,
        loss_ratio=0.0,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                weak,
                strong,
            ],
        )
    )

    assert (
        result.ranked[0]
        .evaluation.candidate.score
        == 100.0
    )


def test_loss_ratio_breaks_equal_effective_score():
    lower_loss = _evaluation(
        base_score=90.0,
        loss_ratio=0.2,
        lost_slots=2,
    )

    higher_loss = _evaluation(
        base_score=95.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                higher_loss,
                lower_loss,
            ],
        )
    )

    assert (
        result.ranked[0]
        .ranking.marginal_capacity_loss_ratio
        == 0.2
    )


def test_seat_waste_breaks_remaining_tie():
    better = _evaluation(
        base_score=90.0,
        seat_waste=0,
    )

    worse = _evaluation(
        base_score=90.0,
        seat_waste=2,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                worse,
                better,
            ],
        )
    )

    assert (
        result.ranked[0]
        .evaluation.candidate.seat_waste
        == 0
    )


def test_fragmentation_breaks_remaining_tie():
    better = _evaluation(
        base_score=90.0,
        fragmentation_minutes=0,
    )

    worse = _evaluation(
        base_score=90.0,
        fragmentation_minutes=30,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                worse,
                better,
            ],
        )
    )

    assert (
        result.ranked[0]
        .evaluation.candidate
        .fragmentation_minutes
        == 0
    )


def test_fewer_tables_break_remaining_tie():
    single = _evaluation(
        base_score=90.0,
        table_count=1,
    )

    combination = _evaluation(
        base_score=90.0,
        table_count=2,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[
                combination,
                single,
            ],
        )
    )

    assert len(
        result.ranked[0]
        .evaluation.candidate.table_ids
    ) == 1


def test_empty_input_returns_empty_result():
    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[],
        )
    )

    assert result.ranked == []


def test_original_candidate_scores_are_unchanged():
    evaluation = _evaluation(
        base_score=92.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    result = (
        TemporalCandidateRankingService.rank(
            evaluations=[evaluation],
        )
    )

    assert (
        result.ranked[0]
        .evaluation.candidate.score
        == 92.0
    )

    assert (
        result.ranked[0]
        .ranking.effective_score
        == 82.0
    )