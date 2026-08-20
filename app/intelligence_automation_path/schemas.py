from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.intelligence_policy.schemas import (
    AutomationLevel,
)


class AutomationPathItem(BaseModel):
    code: str
    description: str
    satisfied: bool


class AutomationPath(BaseModel):
    restaurant_id: uuid.UUID

    current_level: AutomationLevel
    next_level: AutomationLevel | None

    requirements: list[
        AutomationPathItem
    ] = Field(
        default_factory=list,
    )

    generated_at: datetime