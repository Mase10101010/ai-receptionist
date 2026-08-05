from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


json_payload_type = JSON().with_variant(
    JSONB(),
    "postgresql",
)


class AISuggestionType(str, Enum):
    REOPTIMIZATION = "reoptimization"
    CAPACITY = "capacity"
    TABLE_RELEASE = "table_release"


class AISuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

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

    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "reservations.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    suggestion_type: Mapped[AISuggestionType] = mapped_column(
        SqlEnum(
            AISuggestionType,
            name="ai_suggestion_type",
            values_callable=lambda enum: [
                item.value
                for item in enum
            ],
        ),
        nullable=False,
        default=AISuggestionType.REOPTIMIZATION,
    )

    status: Mapped[AISuggestionStatus] = mapped_column(
        SqlEnum(
            AISuggestionStatus,
            name="ai_suggestion_status",
            values_callable=lambda enum: [
                item.value
                for item in enum
            ],
        ),
        nullable=False,
        default=AISuggestionStatus.PENDING,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        json_payload_type,
        nullable=False,
        default=dict,
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )