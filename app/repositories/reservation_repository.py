"""
Reservation repository.
"""
import uuid
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation, ReservationStatus


class ReservationRepository:
    """Async data access for reservations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, reservation: Reservation) -> Reservation:
        self.db.add(reservation)
        await self.db.flush()
        await self.db.refresh(reservation)
        return reservation

    async def get_by_id(
        self,
        reservation_id: uuid.UUID,
        restaurant_id: uuid.UUID | None = None,
    ) -> Reservation | None:
        stmt = select(Reservation).where(
            Reservation.id == reservation_id,
        )

        if restaurant_id is not None:
            stmt = stmt.where(
                Reservation.restaurant_id == restaurant_id,
            )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_restaurants(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> Reservation | None:
        if not restaurant_ids:
            return None

        result = await self.db.execute(
            select(Reservation).where(
                Reservation.id == reservation_id,
                Reservation.restaurant_id.in_(restaurant_ids),
            )
        )

        return result.scalar_one_or_none()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
        restaurant_id: uuid.UUID | None = None,
    ) -> list[Reservation]:
        stmt = select(Reservation).order_by(
            Reservation.reservation_time.desc(),
        )

        if status is not None:
            stmt = stmt.where(Reservation.status == status)

        if restaurant_id is not None:
            stmt = stmt.where(Reservation.restaurant_id == restaurant_id)

        stmt = stmt.offset(skip).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_restaurant_ids(
        self,
        restaurant_ids: list[uuid.UUID],
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        if not restaurant_ids:
            return []

        stmt = (
            select(Reservation)
            .where(Reservation.restaurant_id.in_(restaurant_ids))
            .order_by(Reservation.reservation_time.desc())
            .offset(skip)
            .limit(limit)
        )

        if status is not None:
            stmt = stmt.where(Reservation.status == status)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_in_window(
        self,
        start: datetime,
        end: datetime,
        restaurant_id: uuid.UUID | None = None,
        exclude_statuses: tuple[ReservationStatus, ...] = (
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        ),
    ) -> list[Reservation]:
        stmt = select(Reservation).where(
            and_(
                Reservation.reservation_time >= start,
                Reservation.reservation_time < end,
                Reservation.status.notin_(exclude_statuses),
            )
        )

        if restaurant_id is not None:
            stmt = stmt.where(Reservation.restaurant_id == restaurant_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_upcoming_by_customer(
            self,
            customer_name: str | None = None,
            customer_phone: str | None = None,
            restaurant_id: uuid.UUID | None = None,
            limit: int = 5,
    ) -> list[Reservation]:
        stmt = select(Reservation).where(
            Reservation.reservation_time >= datetime.utcnow(),
            Reservation.status.notin_(
                (
                    ReservationStatus.CANCELLED,
                    ReservationStatus.NO_SHOW,
                    ReservationStatus.COMPLETED,
                )
            ),
        )

        if restaurant_id is not None:
            stmt = stmt.where(Reservation.restaurant_id == restaurant_id)

        if customer_phone:
            stmt = stmt.where(Reservation.customer_phone == customer_phone)
        
        if customer_name:
            stmt = stmt.where(
                func.lower(Reservation.customer_name).like(
                    f"%{customer_name.lower()}%"
                )
            )
        
        stmt = stmt.order_by(Reservation.reservation_time.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        reservation: Reservation,
        fields: dict,
    ) -> Reservation:
        for key, value in fields.items():
            setattr(reservation, key, value)

        await self.db.flush()
        await self.db.refresh(reservation)
        return reservation

    async def delete(self, reservation: Reservation) -> None:
        await self.db.delete(reservation)
        await self.db.flush()