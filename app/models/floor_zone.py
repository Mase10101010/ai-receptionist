import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FloorZone(Base):
    __tablename__ = "floor_zones"

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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(20),
        default="#7fe3e6",
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
        default=320,
        nullable=False,
    )

    height: Mapped[int] = mapped_column(
        Integer,
        default=220,
        nullable=False,
    )

    rotation: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="floor_zones",
    )