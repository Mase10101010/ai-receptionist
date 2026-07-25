from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TablePlacement(Base):
    __tablename__ = "table_placements"

    __table_args__ = (
        UniqueConstraint(
            "floor_plan_id",
            "table_id",
            name="uq_table_placements_floor_plan_table",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    floor_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "floor_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "tables.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    x: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    y: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    width: Mapped[int] = mapped_column(
        Integer,
        default=80,
        nullable=False,
    )

    height: Mapped[int] = mapped_column(
        Integer,
        default=80,
        nullable=False,
    )

    rotation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_visible: Mapped[bool] = mapped_column(
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

    floor_plan = relationship(
        "FloorPlan",
        back_populates="table_placements",
    )

    table = relationship(
        "Table",
        back_populates="placements",
    )