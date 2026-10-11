"""Pydantic schemas for environmental floor-plan features."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FloorFeatureType = Literal[
    "window",
    "door",
    "wall",
    "bar_counter",
    "sofa",
    "entrance",
    "other",
]


class FloorFeatureCreate(BaseModel):
    feature_type: FloorFeatureType
    label: str | None = Field(default=None, max_length=100)
    x: int = Field(default=0, ge=0)
    y: int = Field(default=0, ge=0)
    width: int = Field(default=80, ge=1, le=5000)
    height: int = Field(default=40, ge=1, le=5000)
    rotation: int = Field(default=0, ge=0, le=359)
    is_visible: bool = True


class FloorFeatureUpdate(BaseModel):
    feature_type: FloorFeatureType | None = None
    label: str | None = Field(default=None, max_length=100)
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1, le=5000)
    height: int | None = Field(default=None, ge=1, le=5000)
    rotation: int | None = Field(default=None, ge=0, le=359)
    is_visible: bool | None = None


    @model_validator(mode="after")
    def reject_null_for_required_fields(self):
        non_nullable = {
            "feature_type",
            "x",
            "y",
            "width",
            "height",
            "rotation",
            "is_visible",
        }
        for field in non_nullable & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class FloorFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    floor_plan_id: uuid.UUID
    feature_type: FloorFeatureType
    label: str | None
    x: int
    y: int
    width: int
    height: int
    rotation: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime
