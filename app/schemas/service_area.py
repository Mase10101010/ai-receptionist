import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ServiceAreaType = Literal[
    "indoor",
    "outdoor",
    "terrace",
    "garden",
    "bar",
    "private",
    "rooftop",
    "other",
]


class ServiceAreaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    area_type: ServiceAreaType = "indoor"
    color: str = Field(
        default="#7FE3E6",
        min_length=4,
        max_length=20,
    )
    sort_order: int = Field(default=0, ge=0)


class ServiceAreaUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    area_type: ServiceAreaType | None = None
    color: str | None = Field(
        default=None,
        min_length=4,
        max_length=20,
    )
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ServiceAreaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    area_type: ServiceAreaType
    color: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime