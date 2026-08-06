from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


event_payload_type = JSON().with_variant(
    JSONB(),
    "postgresql",
)


class IntelligenceEventType(str, Enum):
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_UPDATED = "reservation_updated"
    RESERVATION_CANCELLED = "reservation_cancelled"
    RESERVATION_MOVED = "reservation_moved"

    AI_SUGGESTION_CREATED = "ai_suggestion_created"
    AI_SUGGESTION_READ = "ai_suggestion_read"
    AI_SUGGESTION_ACCEPTED = "ai_suggestion_accepted"
    AI_SUGGESTION_DISMISSED = "ai_suggestion_dismissed"
    AI_SUGGESTION_EXPIRED = "ai_suggestion_expired"

    SEATING_PLAN_APPLIED = "seating_plan_applied"
    TABLE_ASSIGNMENT_CREATED = "table_assignment_created"

    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_COMPLETED = "conversation_completed"

    GUEST_NO_SHOW = "guest_no_show"
    GUEST_COMPLETED_VISIT = "guest_completed_visit"

    MANUAL_OVERRIDE = "manual_override"


class IntelligenceEventSource(str, Enum):
    SYSTEM = "system"
    MANAGER = "manager"
    GUEST = "guest"
    AI = "ai"
    INTEGRATION = "integration"


class IntelligenceEvent(Base):
    __tablename__ = "intelligence_events"

    __table_args__ = (
        Index(
            "ix_intelligence_events_restaurant_created",
            "restaurant_id",
            "created_at",
        ),
        Index(
            "ix_intelligence_events_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_intelligence_events_event_type_created",
            "event_type",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "restaurants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    event_type: Mapped[IntelligenceEventType] = mapped_column(
        SqlEnum(
            IntelligenceEventType,
            name="intelligence_event_type",
            values_callable=lambda enum: [
                item.value
                for item in enum
            ],
        ),
        nullable=False,
        index=True,
    )

    source: Mapped[IntelligenceEventSource] = mapped_column(
        SqlEnum(
            IntelligenceEventSource,
            name="intelligence_event_source",
            values_callable=lambda enum: [
                item.value
                for item in enum
            ],
        ),
        nullable=False,
        default=IntelligenceEventSource.SYSTEM,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )

    causation_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "intelligence_events.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    event_version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        event_payload_type,
        nullable=False,
        default=dict,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        event_payload_type,
        nullable=False,
        default=dict,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )