"""
Reservation repository.
"""
import uuid
from datetime import datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)

from app.models.reservation import Reservation, ReservationStatus


RESERVATION_LOAD_OPTIONS = (
    selectinload(
        Reservation.table,
    ),
    selectinload(
        Reservation.table_assignments,
    ).selectinload(
        ReservationTableAssignment.table,
    ),
)


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
        stmt = (
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .where(
                Reservation.id == reservation_id,
            )
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
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .where(
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
        stmt = (
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .order_by(
                Reservation.reservation_time.desc(),
            )
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
        restaurant_id: uuid.UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Reservation]:
        if not restaurant_ids:
            return []

        stmt = (
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .where(
                Reservation.restaurant_id.in_(
                    restaurant_ids,
                ),
            )
        )

        if restaurant_id is not None:
            stmt = stmt.where(
                Reservation.restaurant_id == restaurant_id,
            )

        if status is not None:
            stmt = stmt.where(
                Reservation.status == status,
            )

        if start is not None:
            stmt = stmt.where(
                Reservation.reservation_time >= start,
            )

        if end is not None:
            stmt = stmt.where(
                Reservation.reservation_time < end,
            )

        stmt = (
            stmt
            .order_by(
                Reservation.reservation_time.asc(),
            )
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)

        return list(
            result.scalars().unique().all()
        )

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
        stmt = (
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .where(
                and_(
                    Reservation.reservation_time >= start,
                    Reservation.reservation_time < end,
                    Reservation.status.notin_(
                        exclude_statuses,
                    ),
                )
            )
        )

        if restaurant_id is not None:
            stmt = stmt.where(
                Reservation.restaurant_id == restaurant_id,
            )

        result = await self.db.execute(stmt)

        return list(
            result.scalars().unique().all()
        )

    async def find_upcoming_by_customer(
        self,
        customer_name: str | None = None,
        customer_phone: str | None = None,
        restaurant_id: uuid.UUID | None = None,
        limit: int = 5,
    ) -> list[Reservation]:
        stmt = (
            select(Reservation)
            .options(
                *RESERVATION_LOAD_OPTIONS,
            )
            .where(
                Reservation.reservation_time >= datetime.utcnow(),
                Reservation.status.notin_(
                    (
                        ReservationStatus.CANCELLED,
                        ReservationStatus.NO_SHOW,
                        ReservationStatus.COMPLETED,
                    )
                ),
            )
        )

        if restaurant_id is not None:
            stmt = stmt.where(
                Reservation.restaurant_id == restaurant_id,
            )

        if customer_phone:
            stmt = stmt.where(
                Reservation.customer_phone == customer_phone,
            )

        if customer_name:
            stmt = stmt.where(
                func.lower(
                    Reservation.customer_name,
                ).like(
                    f"%{customer_name.lower()}%"
                )
            )

        stmt = (
            stmt
            .order_by(
                Reservation.reservation_time.asc(),
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)

        return list(
            result.scalars().unique().all()
        )

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

    async def replace_table_assignments(
        self,
        reservation: Reservation,
        table_ids: list[uuid.UUID],
        primary_table_id: uuid.UUID | None = None,
    ) -> Reservation:
        """
        Replace every physical table assignment for a reservation.

        Reservation.table_id remains the backward-compatible primary table.
        """

        unique_table_ids = list(dict.fromkeys(table_ids))

        if primary_table_id is not None:
            if primary_table_id not in unique_table_ids:
                unique_table_ids.insert(0, primary_table_id)
        elif unique_table_ids:
            primary_table_id = unique_table_ids[0]

        await self.db.execute(
            delete(ReservationTableAssignment).where(
                ReservationTableAssignment.reservation_id
                == reservation.id,
            ),
        )

        reservation.table_id = primary_table_id

        for table_id in unique_table_ids:
            self.db.add(
                ReservationTableAssignment(
                    reservation_id=reservation.id,
                    table_id=table_id,
                    is_primary=table_id == primary_table_id,
                ),
            )

        await self.db.flush()
        await self.db.refresh(reservation)

        return reservation

    async def delete(self, reservation: Reservation) -> None:
        await self.db.delete(reservation)
        await self.db.flush()