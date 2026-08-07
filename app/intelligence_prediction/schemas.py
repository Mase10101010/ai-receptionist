from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PredictionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanAcceptancePrediction(BaseModel):
    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID | None = None

    acceptance_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence: PredictionConfidence

    explanation: list[str] = Field(
        default_factory=list,
    )

    generated_at: datetime