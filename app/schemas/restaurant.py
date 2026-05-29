import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    business_type: str = Field(default="restaurant", max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    preferred_language: str = Field(default="en", max_length=10)
    timezone: str = Field(default="Australia/Perth", max_length=100)
    opening_hour: int = Field(default=11, ge=0, le=23)
    closing_hour: int = Field(default=22, ge=0, le=23)
    number_of_tables: int = Field(default=20, ge=1)
    table_setup: list[dict[str, Any]] | None = None
    weekly_schedule: list[dict[str, Any]] | None = None
    special_closures: list[dict[str, Any]] | None = None
    concierge_tone: str = Field(default="Elegant", max_length=100)


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    business_type: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    preferred_language: str | None + Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=100)
    opening_hour: int | None = Field(default=None, ge=0, le=23)
    closing_hour: int | None = Field(default=None, ge=0, le=23)
    number_of_tables: int | None = Field(default=None, ge=1)
    table_setup: list[dict[str, Any]] | None = None
    weekly_schedule: list[dict[str, Any]] | None = None
    special_closures: list[dict[str, Any]] | None = None
    concierge_tone: str | None = Field(default=None, max_length=100)
    subscription_status: str | None = Field(default=None, max_length=50)


class RestaurantResponse(RestaurantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_status: str
    created_at: datetime
    updated_at: datetime
    
    owner_id: uuid.UUID
