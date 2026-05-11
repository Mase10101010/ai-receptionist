from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    business_type: Mapped[str] = mapped_column(
        String(100),
        default="restaurant",
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        default="Australia/Perth",
        nullable=False,
    )

    opening_hour: Mapped[int] = mapped_column(
        Integer,
        default=11,
        nullable=False,
    )

    closing_hour: Mapped[int] = mapped_column(
        Integer,
        default=22,
        nullable=False,
    )

    number_of_tables: Mapped[int] = mapped_column(
        Integer,
        default=20,
        nullable=False,
    )

    concierge_tone: Mapped[str] = mapped_column(
        String(100),
        default="Elegant",
        nullable=False,
    )

    subscription_status: Mapped[str] = mapped_column(
        String(50),
        default="trialing",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    reservations = relationship(
        "Reservation",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )