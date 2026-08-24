from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RestaurantLearningProfileResponse(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    restaurant_id: uuid.UUID

    suggestions_created: int
    suggestions_read: int
    suggestions_accepted: int
    suggestions_dismissed: int
    suggestions_expired: int

    accepted_score_average: float | None
    dismissed_score_average: float | None
    accepted_moves_average: float | None
    accepted_seat_waste_average: float | None
    accepted_move_complexity_average: (
        float | None
    )

    dismissed_move_complexity_average: (
        float | None
    )

    acceptance_rate: float
    dismissal_rate: float
    read_rate: float
    confidence_score: float

    profile_version: int

    last_processed_event_id: (
        uuid.UUID | None
    )
    last_processed_event_at: (
        datetime | None
    )

    created_at: datetime
    updated_at: datetime


class LearningProfileUpdateResult(BaseModel):
    restaurant_id: uuid.UUID
    processed_events: int
    profile_created: bool
    profile: RestaurantLearningProfileResponse