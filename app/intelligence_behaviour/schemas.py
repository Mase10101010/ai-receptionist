from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class BehaviourConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ManagerTrustLevel(str, Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    DEVELOPING = "developing"
    HIGH = "high"


class PlanPreference(str, Enum):
    UNKNOWN = "unknown"
    SINGLE_MOVE = "single_move"
    MULTI_MOVE = "multi_move"
    LOW_SEAT_WASTE = "low_seat_waste"
    FLEXIBLE = "flexible"


class BehaviourInsight(BaseModel):
    code: str
    title: str
    description: str

    confidence: BehaviourConfidence
    evidence_count: int

    value: float | int | str | None = None


class AISuggestionBehaviourProfile(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    restaurant_id: uuid.UUID

    trust_level: ManagerTrustLevel
    preferred_plan: PlanPreference

    accepted_score_reference: float | None
    average_moves_accepted: float | None
    average_seat_waste_accepted: float | None

    dismissed_score_reference: float | None = None
    average_moves_dismissed: float | None = None
    average_seat_waste_dismissed: float | None = None

    move_preference_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    seat_waste_preference_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    score_preference_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    total_suggestions_observed: int
    total_manager_decisions: int

    acceptance_rate: float

    confidence: BehaviourConfidence

    insights: list[BehaviourInsight]

    generated_at: datetime