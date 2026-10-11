"""Read-only geometric relationships between tables and floor features."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.smart_layout.geometry import (
    PlacementGeometry,
    minimum_polygon_separation,
    placement_corners,
    polygons_overlap,
)


@dataclass(frozen=True)
class TableFeatureRelationship:
    table_id: uuid.UUID
    feature_id: uuid.UUID
    feature_type: str
    separation: float
    overlaps: bool


def evaluate_table_feature_relationship(
    placement: TablePlacement,
    feature: FloorFeature,
) -> TableFeatureRelationship:
    """Measure two visible objects on the same floor plan.

    Separation is expressed in floor-plan coordinate units, not metres.
    This function never modifies the supplied objects.
    """
    if placement.floor_plan_id != feature.floor_plan_id:
        raise ValueError(
            "Table placement and feature must belong to the same floor plan"
        )

    if not placement.is_visible or not feature.is_visible:
        raise ValueError(
            "Cannot evaluate invisible floor-plan objects"
        )

    table_geometry = PlacementGeometry(
        x=placement.x,
        y=placement.y,
        width=placement.width,
        height=placement.height,
        rotation=placement.rotation,
    )

    feature_geometry = PlacementGeometry(
        x=feature.x,
        y=feature.y,
        width=feature.width,
        height=feature.height,
        rotation=feature.rotation,
    )

    table_polygon = placement_corners(table_geometry)
    feature_polygon = placement_corners(feature_geometry)

    return TableFeatureRelationship(
        table_id=placement.table_id,
        feature_id=feature.id,
        feature_type=feature.feature_type,
        separation=minimum_polygon_separation(
            table_polygon,
            feature_polygon,
        ),
        overlaps=polygons_overlap(
            table_polygon,
            feature_polygon,
        ),
    )
