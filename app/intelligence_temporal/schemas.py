from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FutureCapacityRequest(BaseModel):
    restaurant_id: UUID
    start_at: datetime

    party_size: int = Field(
        ge=1,
        le=100,
    )

    duration_minutes: int = Field(
        default=90,
        ge=15,
        le=720,
    )

    horizon_minutes: int = Field(
        default=180,
        ge=0,
        le=1440,
    )

    slot_minutes: int = Field(
        default=30,
        ge=15,
        le=180,
    )


class FutureCapacitySlot(BaseModel):
    start_at: datetime
    end_at: datetime

    directly_available: bool

    table_ids: list[UUID] = Field(
        default_factory=list,
    )
    table_numbers: list[str] = Field(
        default_factory=list,
    )

    assignment_capacity: int | None = None
    seat_waste: int | None = None


class FutureCapacitySummary(BaseModel):
    total_slots: int

    directly_available_slots: int
    unavailable_slots: int

    availability_ratio: float

    first_directly_available_at: datetime | None = None

    longest_directly_available_run: int


class FutureCapacityResponse(BaseModel):
    restaurant_id: UUID
    start_at: datetime

    party_size: int
    duration_minutes: int

    horizon_minutes: int
    slot_minutes: int

    slots: list[FutureCapacitySlot] = Field(
        default_factory=list,
    )

    summary: FutureCapacitySummary

    mode: str = "deterministic"