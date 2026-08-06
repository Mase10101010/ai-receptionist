from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)


class IntelligenceEventCreate(BaseModel):
    restaurant_id: uuid.UUID

    event_type: IntelligenceEventType
    source: IntelligenceEventSource

    entity_type: str = Field(
        min_length=1,
        max_length=100,
    )

    entity_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None

    correlation_id: uuid.UUID | None = None
    causation_event_id: uuid.UUID | None = None

    event_version: int = Field(
        default=1,
        ge=1,
    )

    payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )

    occurred_at: datetime | None = None


class IntelligenceEventResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: uuid.UUID
    restaurant_id: uuid.UUID

    event_type: IntelligenceEventType
    source: IntelligenceEventSource

    entity_type: str
    entity_id: uuid.UUID | None

    actor_user_id: uuid.UUID | None

    correlation_id: uuid.UUID
    causation_event_id: uuid.UUID | None

    event_version: int

    payload: dict[str, Any]
    metadata_json: dict[str, Any]

    occurred_at: datetime
    created_at: datetime