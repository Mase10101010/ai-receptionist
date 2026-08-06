from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AutomationLevel(str, Enum):
    ADVISORY_ONLY = "advisory_only"
    ASSISTED = "assisted"
    ELIGIBLE_FOR_AUTOMATION = (
        "eligible_for_automation"
    )


class RecommendationPolicy(BaseModel):
    restaurant_id: uuid.UUID

    move_penalty_weight: float
    seat_waste_penalty_weight: float
    score_weight: float

    single_move_bonus: float
    low_seat_waste_bonus: float

    minimum_recommended_score: float | None
    maximum_preferred_moves: int | None
    maximum_preferred_seat_waste: int | None

    automation_level: AutomationLevel

    rationale: list[str]

    generated_at: datetime