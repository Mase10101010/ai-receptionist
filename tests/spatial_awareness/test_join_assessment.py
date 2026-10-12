"""Tests for read-only Spatial Join Assessment."""

import uuid

import pytest

from app.models.table_combination_rule import (
    TableCombinationRuleStatus,
)
from app.services.spatial_intelligence.advisory import (
    SpatialAdvisoryStatus,
)
from app.services.spatial_intelligence.analysis import (
    FloorPlanSpatialAnalysis,
)
from app.services.spatial_intelligence.join_assessment import (
    assess_physical_join,
)
from app.services.spatial_intelligence.obstacles import (
    ObstacleDetectionResult,
)


def make_analysis(first, second, obstacles=(), *, include_pair=True):
    return FloorPlanSpatialAnalysis(
        floor_plan_id=uuid.uuid4(),
        table_feature_relationships=(),
        table_pair_obstacles=(
            (
                ObstacleDetectionResult(
                    first_table_id=first,
                    second_table_id=second,
                    obstacle_feature_ids=obstacles,
                ),
            )
            if include_pair
            else ()
        ),
    )


@pytest.mark.parametrize(
    "rule_status",
    list(TableCombinationRuleStatus),
)
@pytest.mark.parametrize(
    ("obstacles_present", "expected_status", "requires_review"),
    [
        (False, SpatialAdvisoryStatus.CLEAR, False),
        (True, SpatialAdvisoryStatus.POTENTIAL_OBSTACLE, True),
    ],
)
def test_assessment_preserves_rule_status(
    rule_status,
    obstacles_present,
    expected_status,
    requires_review,
):
    first, second = uuid.uuid4(), uuid.uuid4()
    rule_id, wall_id = uuid.uuid4(), uuid.uuid4()
    obstacles = (wall_id,) if obstacles_present else ()

    result = assess_physical_join(
        rule_id=rule_id,
        first_table_id=first,
        second_table_id=second,
        rule_status=rule_status,
        analysis=make_analysis(first, second, obstacles),
    )

    assert result.rule_id == rule_id
    assert result.rule_status == rule_status
    assert result.spatial_status == expected_status
    assert result.requires_review is requires_review
    assert result.obstacle_feature_ids == obstacles


def test_unknown_requires_review():
    first, second = uuid.uuid4(), uuid.uuid4()

    result = assess_physical_join(
        rule_id=uuid.uuid4(),
        first_table_id=first,
        second_table_id=second,
        rule_status=TableCombinationRuleStatus.AUTO,
        analysis=make_analysis(
            first, second, include_pair=False
        ),
    )

    assert result.spatial_status == SpatialAdvisoryStatus.UNKNOWN
    assert result.requires_review is True


def test_pair_order_does_not_change_assessment():
    first, second = uuid.uuid4(), uuid.uuid4()
    rule_id, wall_id = uuid.uuid4(), uuid.uuid4()
    analysis = make_analysis(first, second, (wall_id,))

    def assess(a, b):
        return assess_physical_join(
            rule_id=rule_id,
            first_table_id=a,
            second_table_id=b,
            rule_status=TableCombinationRuleStatus.CONFIRMED,
            analysis=analysis,
        )

    assert assess(first, second) == assess(second, first)


def test_same_table_is_rejected():
    table_id = uuid.uuid4()

    with pytest.raises(ValueError, match="distinct"):
        assess_physical_join(
            rule_id=uuid.uuid4(),
            first_table_id=table_id,
            second_table_id=table_id,
            rule_status=TableCombinationRuleStatus.AUTO,
            analysis=make_analysis(uuid.uuid4(), uuid.uuid4()),
        )
