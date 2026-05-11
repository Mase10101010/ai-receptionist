"""
Reservation repository.

The repository pattern isolates SQL/ORM concerns from business logic. The
service layer talks to the repository in domain terms ("get by id", "list
between dates") and never touches SQLAlchemy directly. This makes testing
easier (you can mock the repo) and keeps the database swappable.
"""
import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation, ReservationStatus


class ReservationRepository:
    """Async data access for reservations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Create ────────────────────────────────────────────────────────────
    async def create(self, reservation: Reservation) -> Reservation:
        """Persist a new reservation and return it with DB-generated fields."""
        self.db.add(reservation)
        await self.db.flush()        # Push to DB to populate id/timestamps
        await self.db.refresh(reservation)
        return reservation

    # ── Read ──────────────────────────────────────────────────────────────
    async def get_by_id(self, reservation_id: uuid.UUID) -> Reservation | None:
        """Look up a single reservation by primary key."""
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        """List reservations with optional status filter and pagination."""
        stmt = select(Reservation).order_by(Reservation.reservation_time.desc())
        if status is not None:
            stmt = stmt.where(Reservation.status == status)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_in_window(
        self,
        start: datetime,
        end: datetime,
        exclude_statuses: tuple[ReservationStatus, ...] = (
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        ),
    ) -> list[Reservation]:
        """
        Find reservations that fall within [start, end).

        Used by the service layer for capacity checks: before confirming a
        new booking, count concurrent reservations.
        """
        stmt = select(Reservation).where(
            and_(
                Reservation.reservation_time >= start,
                Reservation.reservation_time < end,
                Reservation.status.notin_(exclude_statuses),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Update ────────────────────────────────────────────────────────────
    async def update(
        self, reservation: Reservation, fields: dict
    ) -> Reservation:
        """Apply a partial update from a dict of field→value."""
        for key, value in fields.items():
            setattr(reservation, key, value)
        await self.db.flush()
        await self.db.refresh(reservation)
        return reservation

    # ── Delete ────────────────────────────────────────────────────────────
    async def delete(self, reservation: Reservation) -> None:
        """Hard-delete a reservation. Prefer status=cancelled in most cases."""
        await self.db.delete(reservation)
        await self.db.flush()
