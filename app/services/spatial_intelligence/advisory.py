"""Read-only advisory classification for table-pair obstacles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from app.services.spatial_intelligence.analysis import (
    FloorPlanSpatialAnalysis,
)


class SpatialAdvisoryStatus(str, Enum):
    CLEAR = "clear"
    POTENTIAL_OBSTACLE = "potential_obstacle"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TablePairSpatialAdvisory:
    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    status: SpatialAdvisoryStatus
    obstacle_feature_ids: tuple[uuid.UUID, ...]


def evaluate_table_pair_advisory(
    *,
    analysis: FloorPlanSpatialAnalysis,
    first_table_id: uuid.UUID,
    second_table_id: uuid.UUID,
) -> TablePairSpatialAdvisory:
    """Classify a pair without changing any restaurant state.

    CLEAR means no obstacle was detected by the current
    limited detector, not that a physical join is guaranteed.
    """
    if first_table_id == second_table_id:
        raise ValueError("Two distinct tables are required")

    first_id, second_id = sorted(
        (first_table_id, second_table_id)
    )

    for result in analysis.table_pair_obstacles:
        if {
            result.first_table_id,
            result.second_table_id,
        } != {first_id, second_id}:
            continue

        return TablePairSpatialAdvisory(
            first_table_id=first_id,
            second_table_id=second_id,
            status=(
                SpatialAdvisoryStatus.POTENTIAL_OBSTACLE
                if result.has_potential_obstacles
                else SpatialAdvisoryStatus.CLEAR
            ),
            obstacle_feature_ids=result.obstacle_feature_ids,
        )

    return TablePairSpatialAdvisory(
        first_table_id=first_id,
        second_table_id=second_id,
        status=SpatialAdvisoryStatus.UNKNOWN,
        obstacle_feature_ids=(),
    )
