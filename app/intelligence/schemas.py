from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IntelligenceOptimizeRequest(BaseModel):
    restaurant_id: UUID
    requested_start: datetime
    party_size: int = Field(ge=1, le=100)
    duration_minutes: int = Field(default=90, ge=15, le=720)
    buffer_before_minutes: int = Field(default=0, ge=0, le=180)
    buffer_after_minutes: int = Field(default=0, ge=0, le=180)
    preferred_service_area_id: UUID | None = None
    reservation_id: UUID | None = None
    max_alternatives: int = Field(default=5, ge=1, le=20)


class IntelligenceAssignmentResponse(BaseModel):
    table_ids: list[UUID]
    table_numbers: list[str]
    start_at: datetime
    end_at: datetime
    capacity: int
    score: float
    seat_waste: int
    fragmentation_minutes: int
    explanation: str


class IntelligenceOptimizeResponse(BaseModel):
    available: bool
    recommended: IntelligenceAssignmentResponse | None = None
    alternatives: list[IntelligenceAssignmentResponse] = Field(default_factory=list)
    rejected_candidates: int
    engine_version: str = "aie-v1"
    mode: str = "read_only"

class IntelligenceApplyRequest(BaseModel):
    reservation_id: UUID
    table_ids: list[UUID] = Field(
        min_length=1,
        max_length=20,
    )
    primary_table_id: UUID


class IntelligenceApplyResponse(BaseModel):
    reservation_id: UUID
    restaurant_id: UUID
    primary_table_id: UUID
    table_ids: list[UUID]
    table_numbers: list[str]
    status: str
    mode: str = "assisted"
    applied: bool = True