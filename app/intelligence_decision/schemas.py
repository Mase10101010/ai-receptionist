from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.intelligence_prediction.schemas import (
    PredictionConfidence,
)


class RecommendationDecisionLevel(str, Enum):
    REVIEW_RECOMMENDED = "review_recommended"
    RECOMMENDED = "recommended"
    STRONG_RECOMMENDATION = "strong_recommendation"


class RecommendationDecisionReason(BaseModel):
    code: str
    description: str


class RecommendationDecision(BaseModel):
    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID | None = None

    level: RecommendationDecisionLevel
    confidence: PredictionConfidence

    summary: str

    reasons: list[
        RecommendationDecisionReason
    ] = Field(
        default_factory=list,
    )

    generated_at: datetime