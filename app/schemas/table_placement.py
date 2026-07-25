import uuid

from pydantic import BaseModel, ConfigDict, Field


class TablePlacementUpdate(BaseModel):
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=40, le=400)
    height: int | None = Field(default=None, ge=40, le=400)
    rotation: int | None = Field(default=None, ge=0, lt=360)


class TablePlacementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    floor_plan_id: uuid.UUID
    table_id: uuid.UUID

    x: int
    y: int
    width: int
    height: int
    rotation: int

    is_visible: bool