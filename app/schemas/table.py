import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TableCreate(BaseModel):
    table_number: str = Field(..., min_length=1, max_length=50)
    seats: int = Field(..., ge=1)


class TableUpdate(BaseModel):
    table_number: str | None = Field(default=None, min_length=1, max_length=50)
    seats: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    restaurant_id: uuid.UUID
    table_code: str
    table_number: str
    seats: int
    is_active: bool
    created_at: datetime
    updated_at: datetime