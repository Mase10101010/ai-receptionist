"""
SQLAlchemy declarative base.

All ORM models inherit from `Base`. Alembic uses `Base.metadata` for autogeneration.
"""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base with timestamp mixins."""

    # Every row gets created_at / updated_at managed by the database itself
    # (server_default), so timestamps are accurate even when records are
    # inserted outside the ORM (e.g. via raw SQL or future bulk loads).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
