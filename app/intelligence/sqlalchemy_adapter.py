from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from app.models.reservation import Reservation
from app.models.table import Table
from app.models.table_combination import (
    TableCombination as ORMTableCombination,
)

from .types import (
    ExistingReservation,
    IntelligenceTable,
    TableCombination,
)


def table_to_intelligence(table: Table) -> IntelligenceTable:
    return IntelligenceTable(
        id=str(table.id),
        table_number=table.table_number,
        min_capacity=1,
        max_capacity=table.seats,
        area_id=str(table.service_area_id),
        floor_id=None,
        active=table.is_active,
    )


def reservation_to_intelligence(
    reservation: Reservation,
) -> ExistingReservation | None:
    assigned_table_ids = list(
        getattr(reservation, "assigned_table_ids", []) or [],
    )

    if assigned_table_ids:
        table_ids = tuple(
            str(table_id)
            for table_id in assigned_table_ids
        )
    elif reservation.table_id is not None:
        table_ids = (str(reservation.table_id),)
    else:
        return None

    duration_minutes = max(
        reservation.duration_minutes or 90,
        1,
    )

    status = str(
        getattr(
            reservation.status,
            "value",
            reservation.status,
        )
    ).lower()

    return ExistingReservation(
        id=str(reservation.id),
        start_at=reservation.reservation_time,
        end_at=(
            reservation.reservation_time
            + timedelta(minutes=duration_minutes)
        ),
        party_size=reservation.party_size,
        table_ids=table_ids,
        status=status,
        locked=status == "seated",
    )


def tables_to_intelligence(
    tables: Iterable[Table],
) -> list[IntelligenceTable]:
    return [table_to_intelligence(table) for table in tables]

def combination_to_intelligence(
    combination: ORMTableCombination,
) -> TableCombination:
    ordered_members = sorted(
        combination.members,
        key=lambda member: member.sort_order,
    )

    return TableCombination(
        id=str(combination.id),
        name=combination.name,
        table_ids=tuple(
            str(member.table_id)
            for member in ordered_members
        ),
        min_capacity=combination.min_capacity,
        max_capacity=combination.max_capacity,
        setup_minutes=combination.setup_minutes,
        active=combination.is_active,
    )


def reservations_to_intelligence(
    reservations: Iterable[Reservation],
) -> list[ExistingReservation]:
    converted: list[ExistingReservation] = []
    for reservation in reservations:
        item = reservation_to_intelligence(reservation)
        if item is not None:
            converted.append(item)
    return converted

def combinations_to_intelligence(
    combinations: Iterable[ORMTableCombination],
) -> list[TableCombination]:
    return [
        combination_to_intelligence(combination)
        for combination in combinations
        if combination.is_active
        and len(combination.members) >= 2
    ]
