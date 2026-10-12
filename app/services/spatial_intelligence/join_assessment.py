"""Read-only spatial assessment of physical table joins."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.table_combination_rule import (
    TableCombinationRuleStatus,
)
from app.services.spatial_intelligence.advisory import (
    SpatialAdvisoryStatus,
    evaluate_table_pair_advisory,
)
from app.services.spatial_intelligence.analysis import (
    FloorPlanSpatialAnalysis,
)


@dataclass(frozen=True)
class SpatialJoinAssessment:
    rule_id: uuid.UUID
    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    rule_status: TableCombinationRuleStatus
    spatial_status: SpatialAdvisoryStatus
    obstacle_feature_ids: tuple[uuid.UUID, ...]
    requires_review: bool


def assess_physical_join(
    *,
    rule_id: uuid.UUID,
    first_table_id: uuid.UUID,
    second_table_id: uuid.UUID,
    rule_status: TableCombinationRuleStatus,
    analysis: FloorPlanSpatialAnalysis,
) -> SpatialJoinAssessment:
    """Assess an existing physical join without modifying state."""

    advisory = evaluate_table_pair_advisory(
        analysis=analysis,
        first_table_id=first_table_id,
        second_table_id=second_table_id,
    )

    return SpatialJoinAssessment(
        rule_id=rule_id,
        first_table_id=advisory.first_table_id,
        second_table_id=advisory.second_table_id,
        rule_status=rule_status,
        spatial_status=advisory.status,
        obstacle_feature_ids=advisory.obstacle_feature_ids,
        requires_review=(
            advisory.status != SpatialAdvisoryStatus.CLEAR
        ),
    )
