"""
Restaurant-defined table combinations.

These models describe which physical tables may be joined together.
AIE must use only configured combinations and must never invent arbitrary ones.
"""

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TableCombination(Base):
    """A valid physical combination of two or more restaurant tables."""

    __tablename__ = "table_combinations"

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

    service_area_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "service_areas.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    min_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    max_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    setup_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="table_combinations",
    )

    service_area = relationship(
        "ServiceArea",
        back_populates="table_combinations",
    )

    members = relationship(
        "TableCombinationMember",
        back_populates="combination",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TableCombinationMember.sort_order",
    )

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "name",
            name="uq_table_combinations_restaurant_name",
        ),
    )


class TableCombinationMember(Base):
    """One physical table belonging to one configured combination."""

    __tablename__ = "table_combination_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    combination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "table_combinations.id",
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

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    combination = relationship(
        "TableCombination",
        back_populates="members",
    )

    table = relationship(
        "Table",
        back_populates="combination_memberships",
    )

    __table_args__ = (
        UniqueConstraint(
            "combination_id",
            "table_id",
            name="uq_table_combination_members_combination_table",
        ),
    )