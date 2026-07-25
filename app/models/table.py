import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Table(Base):
    __tablename__ = "tables"

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "table_number",
            name="uq_tables_restaurant_table_number",
        ),
        UniqueConstraint(
            "table_code",
            name="uq_tables_table_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
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

    floor_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "floor_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    table_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    table_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    seats: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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

    shape: Mapped[str] = mapped_column(
        String(20),
        default="square",
        nullable=False,
    )

    rotation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="tables",
    )

    service_area = relationship(
        "ServiceArea",
        back_populates="tables",
    )

    placements = relationship(
        "TablePlacement",
        back_populates="table",
        cascade="all, delete-orphan",
    )