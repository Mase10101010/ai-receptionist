"""
Association model between reservations and tables.

This model allows one reservation to occupy multiple tables while preserving
Reservation.table_id as the backward-compatible primary table reference.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReservationTableAssignment(Base):
    """Assignment of one table to one reservation."""

    __tablename__ = "reservation_table_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    reservation = relationship(
        "Reservation",
        back_populates="table_assignments",
    )

    table = relationship(
        "Table",
        back_populates="reservation_assignments",
    )

    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            "table_id",
            name="uq_reservation_table_assignment",
        ),
    )