from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReasonImportance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReasonItem(BaseModel):
    code: str
    title: str
    description: str
    importance: ReasonImportance


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

    generated_at: datetime