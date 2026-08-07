from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.intelligence_reasoning.schemas import (
    RecommendationReasoning,
)


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

class IntelligenceReoptimizeRequest(BaseModel):
    restaurant_id: UUID
    requested_start: datetime
    party_size: int = Field(
        ge=1,
        le=100,
    )
    duration_minutes: int = Field(
        default=90,
        ge=15,
        le=720,
    )
    reservation_id: UUID | None = None
    buffer_before_minutes: int = Field(
        default=0,
        ge=0,
        le=180,
    )
    buffer_after_minutes: int = Field(
        default=0,
        ge=0,
        le=180,
    )
    preferred_service_area_id: UUID | None = None
    max_reservations_to_move: int = Field(
        default=1,
        ge=1,
        le=1,
    )
    max_plans: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class IntelligenceReservationMoveResponse(BaseModel):
    reservation_id: UUID

    from_table_ids: list[UUID]
    from_table_numbers: list[str]

    to_table_ids: list[UUID]
    to_table_numbers: list[str]

    party_size: int
    start_at: datetime
    end_at: datetime

    destination_capacity: int
    seat_waste: int
    explanation: str


class IntelligenceReoptimizationPlanResponse(BaseModel):
    new_reservation_assignment: IntelligenceAssignmentResponse

    moves: list[
        IntelligenceReservationMoveResponse
    ] = Field(default_factory=list)

    score: float
    base_score: float
    personalized_score: float
    personalization_applied: bool = False

    personalization_reasons: list[str] = Field(
        default_factory=list,
    )

    reasoning: (
        RecommendationReasoning
        | None
    ) = None

    total_seat_waste: int
    moved_reservations_count: int
    explanation: str

    reasoning: (
        RecommendationReasoning
        | None
    ) = None

class IntelligenceReoptimizeResponse(BaseModel):
    available: bool

    recommended: (
        IntelligenceReoptimizationPlanResponse
        | None
    ) = None

    alternatives: list[
        IntelligenceReoptimizationPlanResponse
    ] = Field(default_factory=list)

    evaluated_plans: int
    rejected_plans: int

    engine_version: str = "aie-reoptimizer-v1"
    mode: str = "read_only"

class IntelligenceReoptimizationMoveApply(BaseModel):
    reservation_id: UUID
    to_table_ids: list[UUID] = Field(
        min_length=1,
        max_length=20,
    )
    primary_table_id: UUID


class IntelligenceApplyReoptimizationRequest(BaseModel):
    new_reservation_id: UUID

    new_reservation_table_ids: list[UUID] = Field(
        min_length=1,
        max_length=20,
    )

    new_reservation_primary_table_id: UUID

    moves: list[
        IntelligenceReoptimizationMoveApply
    ] = Field(
        default_factory=list,
        max_length=5,
    )


class IntelligenceAppliedMoveResponse(BaseModel):
    reservation_id: UUID
    primary_table_id: UUID
    table_ids: list[UUID]
    table_numbers: list[str]


class IntelligenceApplyReoptimizationResponse(BaseModel):
    new_reservation_id: UUID

    new_reservation_primary_table_id: UUID
    new_reservation_table_ids: list[UUID]
    new_reservation_table_numbers: list[str]

    applied_moves: list[
        IntelligenceAppliedMoveResponse
    ] = Field(default_factory=list)

    mode: str = "assisted_reoptimization"
    applied: bool = True