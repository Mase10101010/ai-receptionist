"""Response schemas for read-only floor-plan spatial intelligence."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class TableFeatureRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_id: uuid.UUID
    feature_id: uuid.UUID
    feature_type: str
    separation: float
    overlaps: bool


class TablePairObstacleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    obstacle_feature_ids: tuple[uuid.UUID, ...]
    has_potential_obstacles: bool


class FloorPlanSpatialAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    floor_plan_id: uuid.UUID
    table_feature_relationships: list[
        TableFeatureRelationshipResponse
    ]
    table_pair_obstacles: list[
        TablePairObstacleResponse
    ]
