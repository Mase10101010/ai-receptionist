from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReasonImportance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LearnedSignalStrength(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LearnedSignalDirection(str, Enum):
    NEUTRAL = "neutral"
    PREFERRED = "preferred"
    AVOIDED = "avoided"


class ReasonItem(BaseModel):
    code: str
    title: str
    description: str
    importance: ReasonImportance


class LearnedSignal(BaseModel):
    code: str
    title: str

    strength: LearnedSignalStrength
    direction: LearnedSignalDirection

    strength_value: float

    accepted_value: float | None = None
    dismissed_value: float | None = None

    description: str


class RecommendationReasoning(BaseModel):
    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID | None = None

    base_score: float
    personalized_score: float

    moved_reservations_count: int
    total_seat_waste: int

    reasons: list[ReasonItem] = Field(
        default_factory=list,
    )

    learned_signals: list[LearnedSignal] = Field(
        default_factory=list,
    )

    generated_at: datetime