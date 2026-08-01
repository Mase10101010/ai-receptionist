from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)

from app.models.reservation import Reservation, ReservationStatus
from app.models.table import Table
from app.models.table_combination import (
    TableCombination as ORMTableCombination,
    TableCombinationMember,
)

from .optimizer import ReservationOptimizer
from .schemas import (
    IntelligenceAssignmentResponse,
    IntelligenceOptimizeRequest,
    IntelligenceOptimizeResponse,
    IntelligenceApplyRequest,
    IntelligenceApplyResponse,
)
from .sqlalchemy_adapter import (
    combinations_to_intelligence,
    reservations_to_intelligence,
    tables_to_intelligence,
)
from .types import OptimizationRequest


BLOCKING_STATUSES = (
    ReservationStatus.PENDING,
    ReservationStatus.CONFIRMED,
    ReservationStatus.SEATED,
)


class IntelligenceOptimizationService:
    def __init__(self, optimizer: ReservationOptimizer | None = None) -> None:
        self.optimizer = optimizer or ReservationOptimizer()

    async def optimize(
        self,
        session: AsyncSession,
        payload: IntelligenceOptimizeRequest,
    ) -> IntelligenceOptimizeResponse:
        tables_result = await session.execute(
            select(Table)
            .where(
                Table.restaurant_id == payload.restaurant_id,
                Table.is_active.is_(True),
            )
            .order_by(Table.table_number)
        )
        tables = list(tables_result.scalars().all())

        combinations_result = await session.execute(
            select(ORMTableCombination)
            .options(
                selectinload(
                    ORMTableCombination.members,
                ).selectinload(
                    TableCombinationMember.table,
                )
            )
            .where(
                ORMTableCombination.restaurant_id
                == payload.restaurant_id,
                ORMTableCombination.is_active.is_(True),
            )
            .order_by(ORMTableCombination.name)
        )

        combinations = list(
            combinations_result.scalars().unique().all()
        )

        range_start = payload.requested_start - timedelta(hours=12)
        range_end = (
            payload.requested_start
            + timedelta(minutes=payload.duration_minutes)
            + timedelta(hours=12)
        )

        reservations_stmt = (
            select(Reservation)
            .options(
                selectinload(
                    Reservation.table_assignments,
                )
            )
            .where(
                Reservation.restaurant_id
                == payload.restaurant_id,
                Reservation.status.in_(
                    BLOCKING_STATUSES,
                ),
                Reservation.reservation_time
                >= range_start,
                Reservation.reservation_time
                < range_end,
            )
        )

        if payload.reservation_id is not None:
            reservations_stmt = reservations_stmt.where(
                Reservation.id
                != payload.reservation_id,
            )

        reservations_result = await session.execute(
            reservations_stmt
        )

        reservations = list(
            reservations_result.scalars().unique().all()
        )

        reservations = list(
            reservations_result.scalars().unique().all()
        )

        result = self.optimizer.optimize(
            request=OptimizationRequest(
                requested_start=payload.requested_start,
                party_size=payload.party_size,
                duration_minutes=payload.duration_minutes,
                buffer_before_minutes=payload.buffer_before_minutes,
                buffer_after_minutes=payload.buffer_after_minutes,
                preferred_area_id=(
                    str(payload.preferred_service_area_id)
                    if payload.preferred_service_area_id
                    else None
                ),
                preferred_floor_id=None,
                allow_combinations=True,
                max_alternatives=payload.max_alternatives,
            ),
            tables=tables_to_intelligence(tables),
            reservations=reservations_to_intelligence(reservations),
            combinations=combinations_to_intelligence(
                combinations,
            ),
        )

        table_number_by_id = {
            str(table.id): table.table_number for table in tables
        }

        def serialize(item):
            candidate = item.candidate
            return IntelligenceAssignmentResponse(
                table_ids=[UUID(table_id) for table_id in candidate.table_ids],
                table_numbers=[
                    table_number_by_id.get(table_id, table_id)
                    for table_id in candidate.table_ids
                ],
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                capacity=candidate.capacity,
                score=item.score,
                seat_waste=item.seat_waste,
                fragmentation_minutes=item.fragmentation_minutes,
                explanation=item.explanation,
            )

        return IntelligenceOptimizeResponse(
            available=result.available,
            recommended=serialize(result.recommended) if result.recommended else None,
            alternatives=[serialize(item) for item in result.alternatives],
            rejected_candidates=result.rejected_candidates,
        )

    async def apply_recommendation(
        self,
        session: AsyncSession,
        payload: IntelligenceApplyRequest,
        allowed_restaurant_ids: list[UUID],
    ) -> IntelligenceApplyResponse:
        if payload.primary_table_id not in payload.table_ids:
            raise ValidationError(
                "Primary table must be included in table_ids."
            )

        unique_table_ids = list(dict.fromkeys(payload.table_ids))

        reservation_result = await session.execute(
            select(Reservation).where(
                Reservation.id == payload.reservation_id,
                Reservation.restaurant_id.in_(allowed_restaurant_ids),
            )
        )

        reservation = reservation_result.scalar_one_or_none()

        if reservation is None:
            raise NotFoundError(
                f"Reservation {payload.reservation_id} not found"
            )

        if reservation.restaurant_id is None:
            raise ValidationError(
                "Reservation is not associated with a restaurant."
            )

        if reservation.status in {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }:
            raise ValidationError(
                "Completed, cancelled, or no-show reservations "
                "cannot be reassigned."
            )

        tables_result = await session.execute(
            select(Table).where(
                Table.id.in_(unique_table_ids),
                Table.restaurant_id == reservation.restaurant_id,
                Table.is_active.is_(True),
            )
        )

        tables = list(tables_result.scalars().all())

        if len(tables) != len(unique_table_ids):
            raise ValidationError(
                "One or more selected tables were not found, are inactive, "
                "or belong to another restaurant."
            )

        service_area_ids = {
            table.service_area_id
            for table in tables
        }

        if len(service_area_ids) != 1:
            raise ValidationError(
                "Combined tables must belong to the same service area."
            )

        selected_capacity = sum(table.seats for table in tables)

        if selected_capacity < reservation.party_size:
            raise ValidationError(
                "Selected tables do not have enough total capacity."
            )

        requested_start = reservation.reservation_time
        requested_end = (
            reservation.reservation_time
            + timedelta(minutes=reservation.duration_minutes)
        )

        nearby_result = await session.execute(
            select(Reservation)
            .options(
                selectinload(Reservation.table_assignments)
            )
            .where(
                Reservation.restaurant_id == reservation.restaurant_id,
                Reservation.id != reservation.id,
                Reservation.status.in_(BLOCKING_STATUSES),
                Reservation.reservation_time
                < requested_end,
                Reservation.reservation_time
                >= requested_start - timedelta(minutes=720),
            )
        )

        nearby_reservations = list(
            nearby_result.scalars().unique().all()
        )

        selected_table_id_set = set(unique_table_ids)

        for existing in nearby_reservations:
            existing_start = existing.reservation_time
            existing_end = (
                existing.reservation_time
                + timedelta(minutes=existing.duration_minutes)
            )

            if not (
                existing_start < requested_end
                and existing_end > requested_start
            ):
                continue

            existing_table_ids = set(
                existing.assigned_table_ids
                or (
                    [existing.table_id]
                    if existing.table_id is not None
                    else []
                )
            )

            if selected_table_id_set.intersection(
                existing_table_ids
            ):
                raise ValidationError(
                    "One or more selected tables are already occupied "
                    "during this reservation."
                )

        await session.execute(
            sa.delete(ReservationTableAssignment).where(
                ReservationTableAssignment.reservation_id
                == reservation.id,
            )
        )

        reservation.table_id = payload.primary_table_id

        for table_id in unique_table_ids:
            session.add(
                ReservationTableAssignment(
                    reservation_id=reservation.id,
                    table_id=table_id,
                    is_primary=(
                        table_id == payload.primary_table_id
                    ),
                )
            )

        await session.flush()
        await session.refresh(reservation)

        table_number_by_id = {
            table.id: table.table_number
            for table in tables
        }

        ordered_table_numbers = [
            table_number_by_id[table_id]
            for table_id in unique_table_ids
        ]

        return IntelligenceApplyResponse(
            reservation_id=reservation.id,
            restaurant_id=reservation.restaurant_id,
            primary_table_id=payload.primary_table_id,
            table_ids=unique_table_ids,
            table_numbers=ordered_table_numbers,
            status=reservation.status.value,
        )