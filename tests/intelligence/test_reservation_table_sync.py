import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)
from app.models.table import Table
from app.repositories.reservation_repository import (
    ReservationRepository,
)


async def test_replace_table_assignments_keeps_primary_table_in_sync(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()
    service_area_id = uuid.uuid4()

    first_table = Table(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        table_code="SYNC_T1",
        table_number="1",
        seats=4,
        shape="square",
        is_active=True,
    )

    second_table = Table(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        table_code="SYNC_T2",
        table_number="2",
        seats=4,
        shape="square",
        is_active=True,
    )

    db_session.add_all([first_table, second_table])
    await db_session.flush()

    reservation = Reservation(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        table_id=first_table.id,
        customer_name="Table Sync Guest",
        customer_phone="+61000000000",
        customer_email=None,
        party_size=6,
        reservation_time=(
            datetime.now(timezone.utc) + timedelta(days=2)
        ),
        duration_minutes=90,
        status=ReservationStatus.CONFIRMED,
        special_requests=None,
        session_id=None,
    )

    repository = ReservationRepository(db_session)
    reservation = await repository.create(reservation)

    # First assignment: one primary table.
    reservation = await repository.replace_table_assignments(
        reservation=reservation,
        table_ids=[first_table.id],
        primary_table_id=first_table.id,
    )

    assert reservation.table_id == first_table.id

    first_result = await db_session.execute(
        select(ReservationTableAssignment).where(
            ReservationTableAssignment.reservation_id
            == reservation.id,
        )
    )

    first_assignments = list(first_result.scalars().all())

    assert len(first_assignments) == 1
    assert first_assignments[0].table_id == first_table.id
    assert first_assignments[0].is_primary is True

    # Move to another table: old assignment must disappear.
    reservation = await repository.replace_table_assignments(
        reservation=reservation,
        table_ids=[second_table.id],
        primary_table_id=second_table.id,
    )

    assert reservation.table_id == second_table.id

    moved_result = await db_session.execute(
        select(ReservationTableAssignment).where(
            ReservationTableAssignment.reservation_id
            == reservation.id,
        )
    )

    moved_assignments = list(moved_result.scalars().all())

    assert len(moved_assignments) == 1
    assert moved_assignments[0].table_id == second_table.id
    assert moved_assignments[0].is_primary is True
    assert all(
        assignment.table_id != first_table.id
        for assignment in moved_assignments
    )


async def test_replace_table_assignments_supports_multiple_tables(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()
    service_area_id = uuid.uuid4()

    tables = [
        Table(
            id=uuid.uuid4(),
            restaurant_id=restaurant_id,
            service_area_id=service_area_id,
            table_code=f"MULTI_T{index}",
            table_number=str(index),
            seats=4,
            shape="square",
            is_active=True,
        )
        for index in (1, 2)
    ]

    db_session.add_all(tables)
    await db_session.flush()

    reservation = Reservation(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        table_id=tables[0].id,
        customer_name="Combined Tables Guest",
        customer_phone="+61000000001",
        customer_email=None,
        party_size=6,
        reservation_time=(
            datetime.now(timezone.utc) + timedelta(days=3)
        ),
        duration_minutes=90,
        status=ReservationStatus.CONFIRMED,
        special_requests=None,
        session_id=None,
    )

    repository = ReservationRepository(db_session)
    reservation = await repository.create(reservation)

    reservation = await repository.replace_table_assignments(
        reservation=reservation,
        table_ids=[
            tables[0].id,
            tables[1].id,
            tables[0].id,  # duplicate intentionally
        ],
        primary_table_id=tables[0].id,
    )

    assert reservation.table_id == tables[0].id

    result = await db_session.execute(
        select(ReservationTableAssignment)
        .where(
            ReservationTableAssignment.reservation_id
            == reservation.id,
        )
        .order_by(
            ReservationTableAssignment.is_primary.desc(),
        )
    )

    assignments = list(result.scalars().all())

    assert len(assignments) == 2
    assert assignments[0].table_id == tables[0].id
    assert assignments[0].is_primary is True

    secondary_assignments = [
        assignment
        for assignment in assignments
        if not assignment.is_primary
    ]

    assert len(secondary_assignments) == 1
    assert secondary_assignments[0].table_id == tables[1].id