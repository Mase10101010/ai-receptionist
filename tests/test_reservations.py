"""End-to-end tests for the reservations API."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.table import Table

import uuid
import pytest

from app.repositories.reservation_repository import ReservationRepository


def _future_time(hours: int = 24) -> str:
    """Return an ISO datetime safely inside opening hours."""
    target = datetime.now(timezone.utc) + timedelta(hours=hours)
    target = target.replace(hour=19, minute=0, second=0, microsecond=0)
    return target.isoformat()


async def test_health_check(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_create_and_get_reservation(client):
    payload = {
        "customer_name": "Ada Lovelace",
        "customer_phone": "+15551234567",
        "party_size": 4,
        "reservation_time": _future_time(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["customer_name"] == "Ada Lovelace"

    # Fetch it back
    r2 = await client.get(f"/api/v1/reservations/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


async def test_create_reservation_in_past_rejected(client):
    payload = {
        "customer_name": "Past Person",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 422


async def test_oversized_party_rejected(client):
    payload = {
        "customer_name": "Big Group",
        "customer_phone": "+15551234567",
        "party_size": 65,  # exceeds the proposed technical safety limit
        "reservation_time": _future_time(),
    }
    r = await client.post("/api/v1/reservations", json=payload)
    assert r.status_code == 422


async def test_cancel_reservation(client):
    payload = {
        "customer_name": "Bye Bye",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(48),
    }
    created = (await client.post("/api/v1/reservations", json=payload)).json()
    r = await client.delete(f"/api/v1/reservations/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


async def test_list_reservations(client):
    for i in range(3):
        await client.post(
            "/api/v1/reservations",
            json={
                "customer_name": f"Guest {i}",
                "customer_phone": "+15551234567",
                "party_size": 2,
                "reservation_time": _future_time(24 + i),
            },
        )
    r = await client.get("/api/v1/reservations")
    assert r.status_code == 200
    assert len(r.json()) >= 3


async def test_get_unknown_reservation_returns_404(client):
    r = await client.get("/api/v1/reservations/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

async def test_mark_reservation_seated_records_seated_at_once(client):
    payload = {
        "customer_name": "Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(72),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()
    assert created["status"] == "confirmed"

    seated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert seated_response.status_code == 200, seated_response.text

    seated = seated_response.json()
    assert seated["status"] == "seated"
    assert seated["seated_at"] is not None

    first_seated_at = seated["seated_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "seated"
    assert repeated["seated_at"] == first_seated_at

async def test_mark_reservation_completed_records_completed_at_once(client):
    payload = {
        "customer_name": "Completed Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(96),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    seated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "seated"},
    )
    assert seated_response.status_code == 200, seated_response.text

    completed_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "completed"},
    )
    assert completed_response.status_code == 200, completed_response.text

    completed = completed_response.json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    first_completed_at = completed["completed_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "completed"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "completed"
    assert repeated["completed_at"] == first_completed_at

async def test_cancel_reservation_records_cancelled_at_once(client):
    payload = {
        "customer_name": "Cancelled Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(120),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    cancelled_response = await client.delete(
        f"/api/v1/reservations/{created['id']}",
    )
    assert cancelled_response.status_code == 200, cancelled_response.text

    cancelled = cancelled_response.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None

    first_cancelled_at = cancelled["cancelled_at"]

    repeated_response = await client.delete(
        f"/api/v1/reservations/{created['id']}",
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "cancelled"
    assert repeated["cancelled_at"] == first_cancelled_at


async def test_mark_reservation_no_show_records_no_show_at_once(client):
    payload = {
        "customer_name": "No Show Temporal Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": _future_time(144),
    }

    created_response = await client.post(
        "/api/v1/reservations",
        json=payload,
    )
    assert created_response.status_code == 201, created_response.text

    created = created_response.json()

    no_show_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "no_show"},
    )
    assert no_show_response.status_code == 200, no_show_response.text

    no_show = no_show_response.json()
    assert no_show["status"] == "no_show"
    assert no_show["no_show_at"] is not None

    first_no_show_at = no_show["no_show_at"]

    repeated_response = await client.patch(
        f"/api/v1/reservations/{created['id']}",
        json={"status": "no_show"},
    )
    assert repeated_response.status_code == 200, repeated_response.text

    repeated = repeated_response.json()
    assert repeated["status"] == "no_show"
    assert repeated["no_show_at"] == first_no_show_at

@pytest.mark.parametrize(
    "next_turn_offset_minutes",
    [90, 120],
)


async def test_cannot_seat_next_turn_while_same_physical_table_is_still_seated(
    client,
    db_session,
    next_turn_offset_minutes,
):
    table_result = await db_session.execute(
        select(Table).where(Table.table_number == "1")
    )
    table = table_result.scalar_one()

    first_time = datetime.now(timezone.utc) + timedelta(days=10)
    first_time = first_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )
    second_time = first_time + timedelta(
        minutes=next_turn_offset_minutes
    )

    first_payload = {
        "customer_name": "LAB010 First Guest",
        "customer_phone": "+15551234567",
        "party_size": 2,
        "reservation_time": first_time.isoformat(),
        "duration_minutes": 90,
        "table_id": str(table.id),
    }

    second_payload = {
        "customer_name": "LAB010 Next Turn",
        "customer_phone": "+15557654321",
        "party_size": 2,
        "reservation_time": second_time.isoformat(),
        "duration_minutes": 90,
        "table_id": str(table.id),
    }

    first_response = await client.post(
        "/api/v1/reservations",
        json=first_payload,
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/api/v1/reservations",
        json=second_payload,
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    assert first["table_id"] == str(table.id)
    assert second["table_id"] == str(table.id)

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text
    assert seat_first_response.json()["status"] == "seated"

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )

    assert seat_second_response.status_code == 409, seat_second_response.text

    second_after_conflict = await client.get(
        f"/api/v1/reservations/{second['id']}"
    )
    assert second_after_conflict.status_code == 200
    assert second_after_conflict.json()["status"] == "confirmed"

    assert second_after_conflict.json()["seated_at"] is None

async def test_completed_reservation_releases_table_for_next_turn(
    client,
    db_session,
):
    table_result = await db_session.execute(
        select(Table).where(Table.table_number == "1")
    )
    table = table_result.scalar_one()

    first_time = datetime.now(timezone.utc) + timedelta(days=10)
    first_time = first_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )
    second_time = first_time + timedelta(minutes=90)

    first_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Completed Guest",
            "customer_phone": "+15551234567",
            "party_size": 2,
            "reservation_time": first_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Next Guest",
            "customer_phone": "+15557654321",
            "party_size": 2,
            "reservation_time": second_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text

    complete_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "completed"},
    )
    assert complete_first_response.status_code == 200, complete_first_response.text
    assert complete_first_response.json()["status"] == "completed"

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )

    assert seat_second_response.status_code == 200, seat_second_response.text
    assert seat_second_response.json()["status"] == "seated"
    assert seat_second_response.json()["seated_at"] is not None

async def test_no_show_reservation_releases_table_for_next_turn(
    client,
    db_session,
):
    table_result = await db_session.execute(
        select(Table).where(Table.table_number == "1")
    )
    table = table_result.scalar_one()

    first_time = datetime.now(timezone.utc) + timedelta(days=10)
    first_time = first_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )
    second_time = first_time + timedelta(minutes=90)

    first_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 No Show Guest",
            "customer_phone": "+15551234567",
            "party_size": 2,
            "reservation_time": first_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Next Guest",
            "customer_phone": "+15557654321",
            "party_size": 2,
            "reservation_time": second_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text

    no_show_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "no_show"},
    )
    assert no_show_first_response.status_code == 200, no_show_first_response.text
    assert no_show_first_response.json()["status"] == "no_show"

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )

    assert seat_second_response.status_code == 200, seat_second_response.text
    assert seat_second_response.json()["status"] == "seated"
    assert seat_second_response.json()["seated_at"] is not None

async def test_cannot_seat_reservation_when_secondary_physical_table_is_still_occupied(
    client,
    db_session,
):
    tables_result = await db_session.execute(
        select(Table)
        .where(Table.table_number.in_(["1", "2"]))
        .order_by(Table.table_number)
    )
    tables = list(tables_result.scalars().all())

    assert len(tables) == 2

    first_table = tables[0]
    second_table = tables[1]

    first_time = datetime.now(timezone.utc) + timedelta(days=10)
    first_time = first_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )
    second_time = first_time + timedelta(minutes=90)

    first_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Combined Guest",
            "customer_phone": "+15551234567",
            "party_size": 2,
            "reservation_time": first_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(first_table.id),
        },
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Secondary Table Guest",
            "customer_phone": "+15557654321",
            "party_size": 2,
            "reservation_time": second_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(second_table.id),
        },
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    repository = ReservationRepository(db_session)

    first_reservation = await repository.get_by_id(
        uuid.UUID(first["id"]),
    )
    assert first_reservation is not None

    await repository.replace_table_assignments(
        reservation=first_reservation,
        table_ids=[
            first_table.id,
            second_table.id,
        ],
        primary_table_id=first_table.id,
    )

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )

    assert seat_second_response.status_code == 409, seat_second_response.text

    second_after_conflict = await client.get(
        f"/api/v1/reservations/{second['id']}"
    )
    assert second_after_conflict.status_code == 200
    assert second_after_conflict.json()["status"] == "confirmed"
    assert second_after_conflict.json()["seated_at"] is None

async def test_cannot_move_seated_reservation_to_physically_occupied_table(
    client,
    db_session,
):
    tables_result = await db_session.execute(
        select(Table)
        .where(Table.table_number.in_(["1", "2"]))
        .order_by(Table.table_number)
    )
    tables = list(tables_result.scalars().all())

    assert len(tables) == 2

    first_table = tables[0]
    second_table = tables[1]

    reservation_time = datetime.now(timezone.utc) + timedelta(days=10)
    reservation_time = reservation_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )

    first_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Moving Seated Guest",
            "customer_phone": "+15551234567",
            "party_size": 2,
            "reservation_time": reservation_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(first_table.id),
        },
    )
    assert first_response.status_code == 201, first_response.text

    # Use a later planned time so normal temporal planning allows T2.
    second_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Occupying Guest",
            "customer_phone": "+15557654321",
            "party_size": 2,
            "reservation_time": (
                reservation_time + timedelta(minutes=90)
            ).isoformat(),
            "duration_minutes": 90,
            "table_id": str(second_table.id),
        },
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )
    assert seat_second_response.status_code == 200, seat_second_response.text

    move_response = await client.post(
        f"/api/v1/reservations/{first['id']}/move",
        json={"table_id": str(second_table.id)},
    )

    assert move_response.status_code == 409, move_response.text

    first_after_conflict = await client.get(
        f"/api/v1/reservations/{first['id']}"
    )
    assert first_after_conflict.status_code == 200
    assert first_after_conflict.json()["status"] == "seated"
    assert first_after_conflict.json()["table_id"] == str(first_table.id)

async def test_cannot_seat_when_legacy_seated_reservation_occupies_table(
    client,
    db_session,
):
    table_result = await db_session.execute(
        select(Table).where(Table.table_number == "1")
    )
    table = table_result.scalar_one()

    first_time = datetime.now(timezone.utc) + timedelta(days=10)
    first_time = first_time.replace(
        hour=19,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None,
    )

    first_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Legacy Seated Guest",
            "customer_phone": "+15551234567",
            "party_size": 2,
            "reservation_time": first_time.isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert first_response.status_code == 201, first_response.text

    second_response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB010 Next Guest",
            "customer_phone": "+15557654321",
            "party_size": 2,
            "reservation_time": (
                first_time + timedelta(minutes=90)
            ).isoformat(),
            "duration_minutes": 90,
            "table_id": str(table.id),
        },
    )
    assert second_response.status_code == 201, second_response.text

    first = first_response.json()
    second = second_response.json()

    repository = ReservationRepository(db_session)

    first_reservation = await repository.get_by_id(
        uuid.UUID(first["id"]),
    )
    assert first_reservation is not None

    # Simulate a legacy reservation that only has Reservation.table_id
    # and no reservation_table_assignments rows.
    await repository.replace_table_assignments(
        reservation=first_reservation,
        table_ids=[],
        primary_table_id=None,
    )

    first_reservation.table_id = table.id
    await db_session.flush()

    seat_first_response = await client.patch(
        f"/api/v1/reservations/{first['id']}",
        json={"status": "seated"},
    )
    assert seat_first_response.status_code == 200, seat_first_response.text

    seat_second_response = await client.patch(
        f"/api/v1/reservations/{second['id']}",
        json={"status": "seated"},
    )

    assert seat_second_response.status_code == 409, seat_second_response.text

@pytest.mark.asyncio
async def test_large_party_booking_assigns_four_derived_tables(
    client,
    db_session,
):
    """A 14-person HTTP booking uses four connected 4-seat tables."""
    from app.models.floor_plan import FloorPlan
    from app.models.reservation_table_assignment import (
        ReservationTableAssignment,
    )
    from app.repositories.table_combination_repository import (
        TableCombinationRepository,
    )
    from app.services.smart_layout.derivation import (
        derive_table_combinations,
    )
    from app.services.smart_layout.derived_materialization import (
        SmartLayoutDerivedMaterializationService,
    )

    tables = list(
        (
            await db_session.execute(
                select(Table).order_by(Table.table_number)
            )
        ).scalars().all()
    )
    assert len(tables) == 4

    restaurant_id = tables[0].restaurant_id
    area_id = tables[0].service_area_id

    floor_plan = FloorPlan(
        service_area_id=area_id,
        name=f"LAB016 Large Party {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    joins = [
        frozenset((tables[index].id, tables[index + 1].id))
        for index in range(3)
    ]
    derived = derive_table_combinations(joins)

    materializer = SmartLayoutDerivedMaterializationService(
        combination_repository=TableCombinationRepository(db_session),
    )
    await materializer.sync(
        restaurant_id=restaurant_id,
        service_area_id=area_id,
        floor_plan_id=floor_plan.id,
        derived_table_sets=derived,
        tables_by_id={table.id: table for table in tables},
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB016 Birthday Party",
            "customer_phone": "+15551234567",
            "party_size": 14,
            "reservation_time": _future_time(72),
            "duration_minutes": 90,
        },
    )

    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "confirmed"
    assert booking["party_size"] == 14


@pytest.mark.asyncio
async def test_large_party_booking_assigns_four_derived_tables(
    client,
    db_session,
):
    """A 14-person HTTP booking uses four connected 4-seat tables."""
    from app.models.floor_plan import FloorPlan
    from app.models.reservation_table_assignment import (
        ReservationTableAssignment,
    )
    from app.repositories.table_combination_repository import (
        TableCombinationRepository,
    )
    from app.services.smart_layout.derivation import (
        derive_table_combinations,
    )
    from app.services.smart_layout.derived_materialization import (
        SmartLayoutDerivedMaterializationService,
    )

    tables = list(
        (
            await db_session.execute(
                select(Table).order_by(Table.table_number)
            )
        ).scalars().all()
    )
    assert len(tables) == 4

    restaurant_id = tables[0].restaurant_id
    area_id = tables[0].service_area_id

    floor_plan = FloorPlan(
        service_area_id=area_id,
        name=f"LAB016 Large Party {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    joins = [
        frozenset((tables[index].id, tables[index + 1].id))
        for index in range(3)
    ]
    derived = derive_table_combinations(joins)

    materializer = SmartLayoutDerivedMaterializationService(
        combination_repository=TableCombinationRepository(db_session),
    )
    await materializer.sync(
        restaurant_id=restaurant_id,
        service_area_id=area_id,
        floor_plan_id=floor_plan.id,
        derived_table_sets=derived,
        tables_by_id={table.id: table for table in tables},
    )
    await db_session.flush()

    response = await client.post(
        "/api/v1/reservations",
        json={
            "customer_name": "LAB016 Birthday Party",
            "customer_phone": "+15551234567",
            "party_size": 14,
            "reservation_time": _future_time(72),
            "duration_minutes": 90,
        },
    )

    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "confirmed"
    assert booking["party_size"] == 14

    assignments = list(
        (
            await db_session.execute(
                select(ReservationTableAssignment).where(
                    ReservationTableAssignment.reservation_id
                    == uuid.UUID(booking["id"])
                )
            )
        ).scalars().all()
    )

    assert len(assignments) == 4
    assert {assignment.table_id for assignment in assignments} == {
        table.id for table in tables
    }
    assert sum(assignment.is_primary for assignment in assignments) == 1
