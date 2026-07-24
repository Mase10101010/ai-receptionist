import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FloorPlanCreate(BaseModel):
    name: str = Field(
        default="Default Layout",
        min_length=1,
        max_length=100,
    )
    width: int = Field(default=1200, ge=400, le=5000)
    height: int = Field(default=800, ge=400, le=5000)
    sort_order: int = Field(default=0, ge=0)
    is_default: bool = False


class FloorPlanUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    width: int | None = Field(default=None, ge=400, le=5000)
    height: int | None = Field(default=None, ge=400, le=5000)
    sort_order: int | None = Field(default=None, ge=0)
    is_default: bool | None = None
    is_active: bool | None = None


class FloorPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_area_id: uuid.UUID
    name: str
    width: int
    height: int
    sort_order: int
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime