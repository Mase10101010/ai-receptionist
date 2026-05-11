"""
Reservation ORM model.

Reservations are the primary domain entity. They can be created either through
the AI chat (via tool calls) or directly through the REST API.
"""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReservationStatus(str, Enum):
    """Lifecycle states of a reservation."""
    PENDING = "pending"          # Just created, awaiting confirmation
    CONFIRMED = "confirmed"      # Customer/staff confirmed
    SEATED = "seated"            # Party has arrived and been seated
    COMPLETED = "completed"      # Meal finished
    CANCELLED = "cancelled"      # Cancelled by customer or staff
    NO_SHOW = "no_show"          # Customer didn't arrive


class Reservation(Base):
    """A table booking."""
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Customer info — minimal PII, only what's needed to honor the reservation.
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255))

    # Booking details
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

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

    # Composite index optimizes the most common query: "all reservations
    # in a given time window with a given status".
    __table_args__ = (
        Index("ix_reservations_time_status", "reservation_time", "status"),
    )
