from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.intelligence_temporal.ranking_decision_trace import (
    TemporalRankingDecisionTraceService,
)


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)


def _evaluation(
    *,
    table_id,
    base_score: float,
    loss_ratio: float = 0.0,
    lost_slots: int = 0,
) -> TemporalCandidateEvaluation:
    candidate = IntelligenceAssignmentResponse(
        table_ids=[table_id],
        table_numbers=["1"],
        start_at=NOW,
        end_at=NOW + timedelta(minutes=90),
        capacity=4,
        score=base_score,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Candidate.",
    )

    cost = TemporalCandidateCost(
        table_ids=(table_id,),
        start_at=candidate.start_at,
        end_at=candidate.end_at,
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
        has_temporal_cost=lost_slots > 0,
    )

    counterfactual = TemporalCandidateCounterfactual(
        cost=cost,
        evaluated_slots=10,
        baseline_available_slots=10,
        candidate_available_slots=(
            10 - lost_slots
        ),
    )

    return TemporalCandidateEvaluation(
        candidate=candidate,
        counterfactual=counterfactual,
        occupancy_duration_minutes=90,
    )


def test_trace_reports_unchanged_recommendation():
    table_id = uuid4()

    evaluation = _evaluation(
        table_id=table_id,
        base_score=90.0,
    )

    ranking = TemporalCandidateRankingService.rank(
        evaluations=[evaluation],
    )

    winner = ranking.ranked[0]

    trace = TemporalRankingDecisionTraceService.build(
        technical_winner=winner,
        temporal_winner=winner,
    )

    assert trace.recommendation_changed is False

    assert trace.technical_winner.table_ids == (
        str(table_id),
    )
    assert trace.temporal_winner.table_ids == (
        str(table_id),
    )

    assert trace.technical_winner.technical_score == 90.0
    assert trace.temporal_winner.technical_score == 90.0


def test_trace_reports_temporal_recommendation_change():
    technical_table = uuid4()
    temporal_table = uuid4()

    technically_best = _evaluation(
        table_id=technical_table,
        base_score=92.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    temporally_best = _evaluation(
        table_id=temporal_table,
        base_score=88.0,
        loss_ratio=0.0,
        lost_slots=0,
    )

    ranking = TemporalCandidateRankingService.rank(
        evaluations=[
            technically_best,
            temporally_best,
        ],
    )

    technical_ranked = next(
        candidate
        for candidate in ranking.ranked
        if candidate.evaluation.candidate.table_ids
        == [technical_table]
    )

    temporal_ranked = ranking.ranked[0]

    trace = TemporalRankingDecisionTraceService.build(
        technical_winner=technical_ranked,
        temporal_winner=temporal_ranked,
    )

    assert trace.recommendation_changed is True

    assert trace.technical_winner.table_ids == (
        str(technical_table),
    )
    assert trace.temporal_winner.table_ids == (
        str(temporal_table),
    )

    assert trace.technical_winner.technical_score == 92.0
    assert trace.temporal_winner.technical_score == 88.0

    assert (
        trace.technical_winner.marginal_capacity_loss_ratio
        == 0.4
    )
    assert (
        trace.temporal_winner.marginal_capacity_loss_ratio
        == 0.0
    )

    assert (
        trace.technical_winner.lost_future_available_slots
        == 4
    )
    assert (
        trace.temporal_winner.lost_future_available_slots
        == 0
    )


def test_trace_uses_existing_ranking_scores_without_recalculation():
    technical_table = uuid4()
    temporal_table = uuid4()

    technically_best = _evaluation(
        table_id=technical_table,
        base_score=92.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    temporally_best = _evaluation(
        table_id=temporal_table,
        base_score=88.0,
        loss_ratio=0.0,
        lost_slots=0,
    )

    ranking = TemporalCandidateRankingService.rank(
        evaluations=[
            technically_best,
            temporally_best,
        ],
    )

    technical_ranked = next(
        candidate
        for candidate in ranking.ranked
        if candidate.evaluation.candidate.table_ids
        == [technical_table]
    )

    temporal_ranked = ranking.ranked[0]

    trace = TemporalRankingDecisionTraceService.build(
        technical_winner=technical_ranked,
        temporal_winner=temporal_ranked,
    )

    assert (
        trace.technical_winner.effective_score
        == technical_ranked.ranking.effective_score
    )
    assert (
        trace.temporal_winner.effective_score
        == temporal_ranked.ranking.effective_score
    )


def test_trace_does_not_mutate_ranked_candidates():
    table_id = uuid4()

    evaluation = _evaluation(
        table_id=table_id,
        base_score=92.0,
        loss_ratio=0.4,
        lost_slots=4,
    )

    ranking = TemporalCandidateRankingService.rank(
        evaluations=[evaluation],
    )

    candidate = ranking.ranked[0]

    original_score = candidate.evaluation.candidate.score
    original_effective_score = (
        candidate.ranking.effective_score
    )
    original_table_ids = list(
        candidate.evaluation.candidate.table_ids
    )

    TemporalRankingDecisionTraceService.build(
        technical_winner=candidate,
        temporal_winner=candidate,
    )

    assert candidate.evaluation.candidate.score == original_score
    assert (
        candidate.ranking.effective_score
        == original_effective_score
    )
    assert (
        candidate.evaluation.candidate.table_ids
        == original_table_ids
    )