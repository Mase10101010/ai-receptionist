"""
Reservation ORM model.

Reservations are the primary domain entity. They can be created either through
the AI chat (via tool calls) or directly through the REST API.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReservationStatus(str, Enum):
    """Lifecycle states of a reservation."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Reservation(Base):
    """A table booking."""
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # SaaS ownership: every reservation belongs to one restaurant.
    # Nullable for now so existing demo flows and old data do not break.
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Customer info — minimal PII, only what's needed to honor the reservation.
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255))

    # Booking details
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=90,
    )

    status: Mapped[ReservationStatus] = mapped_column(
        SQLEnum(
            ReservationStatus,
            name="reservation_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ReservationStatus.PENDING,
        index=True,
    )

    special_requests: Mapped[str | None] = mapped_column(Text)

    # Optional link back to the chat session that created the reservation.
    # Useful for analytics and for letting the AI reference past bookings.
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)

    restaurant = relationship(
        "Restaurant",
        back_populates="reservations",
    )

    __table_args__ = (
        Index("ix_reservations_time_status", "reservation_time", "status"),
        Index("ix_reservations_restaurant_time", "restaurant_id", "reservation_time"),
    )