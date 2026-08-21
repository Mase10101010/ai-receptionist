from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RestaurantLearningProfile(Base):
    __tablename__ = "restaurant_learning_profiles"

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            name=(
                "uq_restaurant_learning_profiles_"
                "restaurant_id"
            ),
        ),
        Index(
            "ix_restaurant_learning_profiles_updated_at",
            "updated_at",
        ),
        Index(
            (
                "ix_restaurant_learning_profiles_"
                "last_processed_event_at"
            ),
            "last_processed_event_at",
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

    suggestions_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    suggestions_read: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    suggestions_accepted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    suggestions_dismissed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    suggestions_expired: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    accepted_score_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    dismissed_score_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    accepted_moves_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    accepted_seat_waste_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    dismissed_moves_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    dismissed_seat_waste_average: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    acceptance_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    dismissal_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    read_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    profile_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    last_processed_event_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "intelligence_events.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    last_processed_event_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc,
        ),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc,
        ),
        onupdate=lambda: datetime.now(
            timezone.utc,
        ),
    )