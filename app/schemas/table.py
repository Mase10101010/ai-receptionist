import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TableShape = Literal["square", "round", "rectangle"]


class TableCreate(BaseModel):
    table_number: str = Field(..., min_length=1, max_length=50)
    seats: int = Field(..., ge=1)

    x: int = Field(default=0, ge=0)
    y: int = Field(default=0, ge=0)
    width: int = Field(default=80, ge=40, le=400)
    height: int = Field(default=80, ge=40, le=400)
    shape: TableShape = "square"
    rotation: int = Field(default=0, ge=0, lt=360)


class TableUpdate(BaseModel):
    table_number: str | None = Field(default=None, min_length=1, max_length=50)
    seats: int | None = Field(default=None, ge=1)
    is_active: bool | None = None

    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=40, le=400)
    height: int | None = Field(default=None, ge=40, le=400)
    shape: TableShape | None = None
    rotation: int | None = Field(default=None, ge=0, lt=360)


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    table_code: str
    table_number: str
    seats: int

    x: int
    y: int
    width: int
    height: int
    shape: TableShape
    rotation: int

    is_active: bool
    created_at: datetime
    updated_at: datetime