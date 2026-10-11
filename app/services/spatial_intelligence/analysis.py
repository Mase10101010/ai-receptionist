"""Read-only spatial analysis of a restaurant floor plan."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.obstacles import (
    ObstacleDetectionResult,
    detect_obstacles_between_tables,
)
from app.services.spatial_intelligence.relationships import (
    TableFeatureRelationship,
    evaluate_table_feature_relationship,
)


@dataclass(frozen=True)
class FloorPlanSpatialAnalysis:
    floor_plan_id: uuid.UUID
    table_feature_relationships: tuple[
        TableFeatureRelationship, ...
    ]
    table_pair_obstacles: tuple[
        ObstacleDetectionResult, ...
    ]


def analyze_floor_plan_spatially(
    *,
    floor_plan_id: uuid.UUID,
    placements: Iterable[TablePlacement],
    features: Iterable[FloorFeature],
) -> FloorPlanSpatialAnalysis:
    """Analyze geometry without modifying floor-plan state."""

    placements = list(placements)
    features = list(features)

    if any(
        placement.floor_plan_id != floor_plan_id
        for placement in placements
    ):
        raise ValueError("Table placement belongs to another floor plan")

    if any(
        feature.floor_plan_id != floor_plan_id
        for feature in features
    ):
        raise ValueError("Feature belongs to another floor plan")

    visible_tables = sorted(
        (
            placement
            for placement in placements
            if placement.is_visible
        ),
        key=lambda placement: str(placement.table_id),
    )

    visible_features = sorted(
        (
            feature
            for feature in features
            if feature.is_visible
        ),
        key=lambda feature: str(feature.id),
    )

    relationships = tuple(
        evaluate_table_feature_relationship(
            placement,
            feature,
        )
        for placement in visible_tables
        for feature in visible_features
    )

    obstacles = tuple(
        detect_obstacles_between_tables(
            first,
            second,
            visible_features,
        )
        for first, second in combinations(visible_tables, 2)
    )

    return FloorPlanSpatialAnalysis(
        floor_plan_id=floor_plan_id,
        table_feature_relationships=relationships,
        table_pair_obstacles=obstacles,
    )
