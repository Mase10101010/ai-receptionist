"""Tests for conservative spatial preference decisions."""

import uuid
from types import SimpleNamespace

from app.services.spatial_intelligence.candidate_assessment import (
    SpatialCandidateAssessment,
)
from app.services.spatial_intelligence.preference_evaluator import (
    SpatialPreference,
)
from app.services.spatial_intelligence.preference_policy import (
    SpatialPreferencePolicy,
)


def make_candidate(table_id, *, score=100.0, lost_slots=0, loss_ratio=0.0):
    return SimpleNamespace(
        evaluation=SimpleNamespace(
            candidate=SimpleNamespace(table_ids=[table_id]),
        ),
        ranking=SimpleNamespace(
            effective_score=score,
            lost_future_available_slots=lost_slots,
            marginal_capacity_loss_ratio=loss_ratio,
        ),
    )


def make_assessment(table_id, distance, *, evaluable=True):
    return SpatialCandidateAssessment(
        resource_id=str(table_id),
        table_ids=(str(table_id),),
        preference=SpatialPreference.NEAR_WINDOW,
        evaluable=evaluable,
        separation=distance,
    )


def test_prefers_closer_table_at_equivalent_temporal_cost():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first),
            make_candidate(second),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 20.0),
        ],
    )

    assert decision.selected_index == 1
    assert decision.applied is True


def test_preserves_better_temporal_score():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first, score=100.0),
            make_candidate(second, score=99.0),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.applied is False


def test_preserves_lower_future_capacity_loss():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first, lost_slots=0),
            make_candidate(second, lost_slots=1),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0


def test_missing_baseline_geometry_preserves_ranking():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first),
            make_candidate(second),
        ],
        assessments=[
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.reason == "baseline_geometry_unavailable"


def test_missing_alternative_geometry_preserves_ranking():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first),
            make_candidate(second),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, None, evaluable=False),
        ],
    )

    assert decision.selected_index == 0


def test_equal_distance_preserves_original_order():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first),
            make_candidate(second),
        ],
        assessments=[
            make_assessment(first, 50.0),
            make_assessment(second, 50.0),
        ],
    )

    assert decision.selected_index == 0


def test_empty_candidates_fail_closed():
    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[],
        assessments=[],
    )

    assert decision.selected_index == 0
    assert decision.applied is False
    assert decision.reason == "no_temporal_candidates"


def test_preserves_lower_marginal_capacity_loss_ratio():
    first, second = uuid.uuid4(), uuid.uuid4()

    decision = SpatialPreferencePolicy.choose(
        ranked_candidates=[
            make_candidate(first, loss_ratio=0.0),
            make_candidate(second, loss_ratio=0.2),
        ],
        assessments=[
            make_assessment(first, 100.0),
            make_assessment(second, 10.0),
        ],
    )

    assert decision.selected_index == 0
    assert decision.applied is False
