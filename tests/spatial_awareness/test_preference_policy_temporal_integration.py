"""Compatibility tests using real Temporal Intelligence models."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.intelligence.schemas import IntelligenceAssignmentResponse
from app.intelligence_temporal.candidate_ranking import TemporalRankedCandidate
from app.intelligence_temporal.candidate_temporal_evaluator import TemporalCandidateEvaluation
from app.intelligence_temporal.temporal_ranking import TemporalRankingScore
from app.services.spatial_intelligence.candidate_assessment import SpatialCandidateAssessment
from app.services.spatial_intelligence.preference_evaluator import SpatialPreference
from app.services.spatial_intelligence.preference_policy import SpatialPreferencePolicy


def make_temporal_candidate(table_id, *, score=100.0, lost_slots=0, loss_ratio=0.0):
    start = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)

    assignment = IntelligenceAssignmentResponse(
        table_ids=[table_id],
        table_numbers=["1"],
        start_at=start,
        end_at=start + timedelta(minutes=90),
        capacity=4,
        score=score,
        seat_waste=2,
        fragmentation_minutes=0,
        explanation="Technical candidate",
    )

    # The policy reads only candidate identity and temporal ranking.
    # Construct the real Pydantic evaluation without inventing a
    # counterfactual capacity calculation.
    evaluation = TemporalCandidateEvaluation.model_construct(
        candidate=assignment,
        counterfactual=None,
        occupancy_duration_minutes=90,
    )

    ranking = TemporalRankingScore(
        base_score=score,
        temporal_penalty=0.0,
        effective_score=score,
        marginal_capacity_loss_ratio=loss_ratio,
        lost_future_available_slots=lost_slots,
    )

    return TemporalRankedCandidate(
        evaluation=evaluation,
        ranking=ranking,
    )


def make_assessment(table_id, distance):
    return SpatialCandidateAssessment(
        resource_id=str(table_id),
        table_ids=(str(table_id),),
        preference=SpatialPreference.NEAR_WINDOW,
        evaluable=True,
        separation=distance,
    )


def test_real_temporal_models_select_closer_equivalent_candidate():
    first, second = uuid4(), uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_temporal_candidate(first),
            make_temporal_candidate(second),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 20.0),
        ],
    )

    assert decision.selected_index == 1
    assert decision.applied is True


def test_real_temporal_models_preserve_higher_effective_score():
    first, second = uuid4(), uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_temporal_candidate(first, score=100.0),
            make_temporal_candidate(second, score=95.0),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.applied is False


def test_real_temporal_models_preserve_future_capacity():
    first, second = uuid4(), uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_temporal_candidate(first, lost_slots=0),
            make_temporal_candidate(second, lost_slots=2),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.applied is False


def test_real_temporal_models_preserve_lower_loss_ratio():
    first, second = uuid4(), uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_temporal_candidate(first, loss_ratio=0.0),
            make_temporal_candidate(second, loss_ratio=0.2),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.applied is False
