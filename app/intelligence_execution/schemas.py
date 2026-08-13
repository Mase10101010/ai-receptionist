from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionEligibility(str, Enum):
    BLOCKED = "blocked"
    MANAGER_CONFIRMATION_REQUIRED = (
        "manager_confirmation_required"
    )
    ELIGIBLE_FOR_AUTOMATIC_EXECUTION = (
        "eligible_for_automatic_execution"
    )


class ExecutionEligibilityReason(BaseModel):
    code: str
    description: str


class ExecutionEligibilityResult(BaseModel):
    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID | None = None

    eligibility: ExecutionEligibility

    reasons: list[
        ExecutionEligibilityReason
    ] = Field(
        default_factory=list,
    )

    generated_at: datetime