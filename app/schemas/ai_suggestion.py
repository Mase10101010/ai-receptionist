from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_suggestion import (
    AISuggestionStatus,
    AISuggestionType,
)


class AISuggestionReservationPayload(BaseModel):
    id: uuid.UUID
    customer_name: str
    party_size: int
    reservation_time: datetime
    duration_minutes: int


class AISuggestionPayload(BaseModel):
    reservation: AISuggestionReservationPayload
    plan: dict[str, Any]
    engine_version: str
    mode: str


class AISuggestionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    restaurant_id: uuid.UUID
    reservation_id: uuid.UUID | None

    suggestion_type: AISuggestionType
    status: AISuggestionStatus

    title: str
    description: str
    score: float | None

    payload: dict[str, Any]

    is_read: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AISuggestionListResponse(BaseModel):
    suggestions: list[AISuggestionResponse] = Field(
        default_factory=list,
    )
    total: int


class AISuggestionActionResponse(BaseModel):
    id: uuid.UUID
    status: AISuggestionStatus
    is_read: bool
    updated_at: datetime


class AISuggestionAnalyzeResponse(BaseModel):
    created: bool
    suggestion: AISuggestionResponse | None = None