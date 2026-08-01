from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ServiceArea(Base):
    __tablename__ = "service_areas"

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "name",
            name="uq_service_areas_restaurant_name",
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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    area_type: Mapped[str] = mapped_column(
        String(50),
        default="indoor",
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(20),
        default="#7FE3E6",
        nullable=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    restaurant = relationship(
        "Restaurant",
        back_populates="service_areas",
    )

    floor_plans = relationship(
        "FloorPlan",
        back_populates="service_area",
        cascade="all, delete-orphan",
        order_by="FloorPlan.sort_order",
    )

    tables = relationship(
        "Table",
        back_populates="service_area",
    )

    table_combinations = relationship(
        "TableCombination",
        back_populates="service_area",
        cascade="all, delete-orphan",
    )