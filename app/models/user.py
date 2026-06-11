import uuid

from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime


from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    subscription_status: Mapped[str] = mapped_column(
        String(50),
        default="inactive",
        nullable=False,
    )

    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    trial_start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    trial_end_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    subscription_start_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    subscription_end_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    has_used_trial: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    restaurants = relationship(
        "Restaurant",
        back_populates="owner",
        cascade="all, delete-orphan",
    )