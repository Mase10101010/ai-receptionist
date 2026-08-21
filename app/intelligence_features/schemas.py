from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AISuggestionFeatures(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    restaurant_id: uuid.UUID

    suggestions_created: int = 0
    suggestions_read: int = 0
    suggestions_accepted: int = 0
    suggestions_dismissed: int = 0
    suggestions_expired: int = 0

    acceptance_rate: float = 0.0
    dismissal_rate: float = 0.0
    read_rate: float = 0.0

    average_created_score: float | None = None
    average_accepted_score: float | None = None
    average_dismissed_score: float | None = None
    average_expired_score: float | None = None

    average_moves_accepted: float | None = None
    average_seat_waste_accepted: float | None = None

    average_moves_dismissed: float | None = None
    average_seat_waste_dismissed: float | None = None

    generated_at: datetime