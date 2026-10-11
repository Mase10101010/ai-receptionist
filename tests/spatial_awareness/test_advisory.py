"""Unit tests for read-only Spatial Advisory."""

import uuid

import pytest

from app.services.spatial_intelligence.advisory import (
    SpatialAdvisoryStatus,
    evaluate_table_pair_advisory,
)
from app.services.spatial_intelligence.analysis import (
    FloorPlanSpatialAnalysis,
)
from app.services.spatial_intelligence.obstacles import (
    ObstacleDetectionResult,
)


def make_analysis(first, second, obstacles=()):
    return FloorPlanSpatialAnalysis(
        floor_plan_id=uuid.uuid4(),
        table_feature_relationships=(),
        table_pair_obstacles=(
            ObstacleDetectionResult(
                first_table_id=first,
                second_table_id=second,
                obstacle_feature_ids=obstacles,
            ),
        ),
    )


def test_potential_obstacle():
    first, second, wall = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    analysis = make_analysis(first, second, (wall,))

    result = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=first,
        second_table_id=second,
    )

    assert result.status == SpatialAdvisoryStatus.POTENTIAL_OBSTACLE
    assert result.obstacle_feature_ids == (wall,)


def test_clear_when_detector_finds_no_obstacles():
    first, second = uuid.uuid4(), uuid.uuid4()
    analysis = make_analysis(first, second)

    result = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=first,
        second_table_id=second,
    )

    assert result.status == SpatialAdvisoryStatus.CLEAR
    assert result.obstacle_feature_ids == ()


def test_unknown_when_pair_has_no_analysis():
    first, second = uuid.uuid4(), uuid.uuid4()
    analysis = FloorPlanSpatialAnalysis(
        floor_plan_id=uuid.uuid4(),
        table_feature_relationships=(),
        table_pair_obstacles=(),
    )

    result = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=first,
        second_table_id=second,
    )

    assert result.status == SpatialAdvisoryStatus.UNKNOWN


def test_pair_order_does_not_change_advisory():
    first, second, wall = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    analysis = make_analysis(first, second, (wall,))

    forward = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=first,
        second_table_id=second,
    )
    reverse = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=second,
        second_table_id=first,
    )

    assert forward == reverse


def test_same_table_is_rejected():
    table_id = uuid.uuid4()
    analysis = make_analysis(uuid.uuid4(), uuid.uuid4())

    with pytest.raises(ValueError, match="distinct"):
        evaluate_table_pair_advisory(
            analysis=analysis,
            first_table_id=table_id,
            second_table_id=table_id,
        )
