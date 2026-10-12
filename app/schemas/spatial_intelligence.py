"""Response schemas for read-only floor-plan spatial intelligence."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


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


class TablePairSpatialAdvisoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    status: str
    obstacle_feature_ids: tuple[uuid.UUID, ...]

class SpatialJoinAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: uuid.UUID
    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    rule_status: str
    spatial_status: str
    obstacle_feature_ids: tuple[uuid.UUID, ...]
    requires_review: bool


class FloorPlanSpatialAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    floor_plan_id: uuid.UUID
    table_feature_relationships: list[
        TableFeatureRelationshipResponse
    ]
    table_pair_obstacles: list[
        TablePairObstacleResponse
    ]
    table_pair_advisories: list[
        TablePairSpatialAdvisoryResponse
    ] = Field(default_factory=list)
    join_assessments: list[
        SpatialJoinAssessmentResponse
    ] = Field(default_factory=list)
