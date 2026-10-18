"""Tests for read-only spatial candidate assessment."""

import uuid
from datetime import datetime, timezone

import pytest

from app.intelligence.types import AssignmentKind, CandidateAssignment
from app.services.spatial_intelligence.candidate_assessment import (
    SpatialCandidateAssessmentService,
)
from app.services.spatial_intelligence.preference_evaluator import (
    SpatialPreference,
    SpatialPreferenceEvaluation,
)


def make_candidate(table_ids):
    return CandidateAssignment(
        kind=(
            AssignmentKind.SINGLE_TABLE
            if len(table_ids) == 1
            else AssignmentKind.TABLE_COMBINATION
        ),
        resource_id="resource-1",
        table_ids=tuple(str(value) for value in table_ids),
        start_at=datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
        end_at=datetime(2026, 10, 20, 14, tzinfo=timezone.utc),
        capacity=4 * len(table_ids),
        minimum_capacity=1,
        area_id=None,
        floor_id=None,
    )


def make_evaluation(table_id, separation, *, evaluable=True):
    return SpatialPreferenceEvaluation(
        table_id=table_id,
        preference=SpatialPreference.NEAR_WINDOW,
        evaluable=evaluable,
        nearest_feature_id=uuid.uuid4() if evaluable else None,
        separation=separation,
    )


def assess(candidates, evaluations):
    return SpatialCandidateAssessmentService.assess(
        candidates=candidates,
        evaluations=evaluations,
        preference=SpatialPreference.NEAR_WINDOW,
    )


def test_single_table_distance():
    table_id = uuid.uuid4()
    candidate = make_candidate([table_id])

    result = assess(
        [candidate],
        [make_evaluation(table_id, 20.0)],
    )[0]

    assert result.evaluable is True
    assert result.separation == pytest.approx(20.0)
    assert result.table_ids == candidate.table_ids


def test_combination_uses_farthest_table():
    first = uuid.uuid4()
    second = uuid.uuid4()

    result = assess(
        [make_candidate([first, second])],
        [
            make_evaluation(first, 20.0),
            make_evaluation(second, 100.0),
        ],
    )[0]

    assert result.evaluable is True
    assert result.separation == pytest.approx(100.0)


def test_missing_geometry_is_not_evaluable():
    table_id = uuid.uuid4()

    result = assess([make_candidate([table_id])], [])[0]

    assert result.evaluable is False
    assert result.separation is None


def test_combination_requires_all_tables_evaluable():
    first = uuid.uuid4()
    second = uuid.uuid4()

    result = assess(
        [make_candidate([first, second])],
        [make_evaluation(first, 20.0)],
    )[0]

    assert result.evaluable is False
    assert result.separation is None


def test_non_evaluable_table_is_rejected():
    table_id = uuid.uuid4()

    result = assess(
        [make_candidate([table_id])],
        [make_evaluation(table_id, None, evaluable=False)],
    )[0]

    assert result.evaluable is False
    assert result.separation is None


def test_empty_candidate_is_not_evaluable():
    result = assess([make_candidate([])], [])[0]

    assert result.evaluable is False
    assert result.separation is None


def test_candidates_are_not_modified():
    table_id = uuid.uuid4()
    candidate = make_candidate([table_id])
    original = candidate

    results = assess(
        [candidate],
        [make_evaluation(table_id, 15.0)],
    )

    assert candidate == original
    assert results[0].resource_id == candidate.resource_id
    assert results[0].separation == pytest.approx(15.0)
