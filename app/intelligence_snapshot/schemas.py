from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
)
from app.intelligence_policy.schemas import (
    RecommendationPolicy,
)

from app.intelligence_calibration.schemas import (
    CalibrationMetrics,
)


class IntelligenceLearningSnapshot(BaseModel):
    suggestions_observed: int
    suggestions_read: int

    suggestions_accepted: int
    suggestions_dismissed: int
    suggestions_expired: int

    manager_decisions: int

    acceptance_rate: float
    dismissal_rate: float
    read_rate: float

    confidence_score: float

    profile_version: int
    last_processed_event_at: datetime | None


class IntelligenceSnapshotResponse(BaseModel):
    restaurant_id: uuid.UUID

    learning: IntelligenceLearningSnapshot

    behaviour: AISuggestionBehaviourProfile

    policy: RecommendationPolicy | None

    calibration: CalibrationMetrics

    generated_at: datetime