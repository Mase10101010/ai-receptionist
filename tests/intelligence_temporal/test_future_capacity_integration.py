from datetime import datetime
from uuid import uuid4

import pytest

from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
)
from app.intelligence_temporal.service import (
    TemporalCapacityService,
)
from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User


@pytest.mark.asyncio
async def test_future_capacity_uses_real_optimizer_and_blocking_reservation(
    db_session,
):
    """
    Integration proof for T1 Future Capacity V1.

    One real table is occupied by a confirmed reservation from
    18:00 until 19:30.

    The Temporal service must therefore report:

    18:00 -> unavailable
    18:30 -> unavailable
    19:00 -> unavailable
    19:30 -> available
    20:00 -> available

    No optimizer mock is used.
    """

    user_id = uuid4()
    restaurant_id = uuid4()
    service_area_id = uuid4()
    table_id = uuid4()
    reservation_id = uuid4()

    user = User(
        id=user_id,
        email=f"temporal-{user_id}@example.com",
        hashed_password="test-password",
        is_active=True,
    )

    restaurant = Restaurant(
        id=restaurant_id,
        owner_id=user_id,
        name="Temporal Test Restaurant",
        slug=f"temporal-{restaurant_id}",
        opening_hour=0,
        closing_hour=23,
        subscription_status="trialing",
    )

    service_area = ServiceArea(
        id=service_area_id,
        restaurant_id=restaurant_id,
        name="Main Dining",
        area_type="indoor",
        is_active=True,
    )

    table = Table(
        id=table_id,
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        table_code=f"TEMPORAL-{table_id}",
        table_number="12",
        seats=4,
        is_active=True,
    )

    reservation_start = datetime(
        2026,
        9,
        10,
        18,
        0,
    )

    reservation = Reservation(
        id=reservation_id,
        restaurant_id=restaurant_id,
        table_id=table_id,
        customer_name="Temporal Test Guest",
        customer_phone="+390000000000",
        party_size=4,
        reservation_time=reservation_start,
        duration_minutes=90,
        status=ReservationStatus.CONFIRMED,
    )

    assignment = ReservationTableAssignment(
        reservation_id=reservation_id,
        table_id=table_id,
        is_primary=True,
    )

    db_session.add_all(
        [
            user,
            restaurant,
            service_area,
            table,
            reservation,
            assignment,
        ]
    )

    await db_session.flush()

    service = TemporalCapacityService()

    result = await service.profile(
        session=db_session,
        request=FutureCapacityRequest(
            restaurant_id=restaurant_id,
            start_at=reservation_start,
            party_size=4,
            duration_minutes=90,
            horizon_minutes=120,
            slot_minutes=30,
        ),
    )

    assert len(result.slots) == 5

    expected_starts = [
        datetime(2026, 9, 10, 18, 0),
        datetime(2026, 9, 10, 18, 30),
        datetime(2026, 9, 10, 19, 0),
        datetime(2026, 9, 10, 19, 30),
        datetime(2026, 9, 10, 20, 0),
    ]

    assert [
        slot.start_at
        for slot in result.slots
    ] == expected_starts

    assert [
        slot.directly_available
        for slot in result.slots
    ] == [
        False,
        False,
        False,
        True,
        True,
    ]

    assert result.slots[0].table_ids == []
    assert result.slots[1].table_ids == []
    assert result.slots[2].table_ids == []

    assert result.slots[3].table_ids == [
        table_id,
    ]
    assert result.slots[3].table_numbers == [
        "12",
    ]
    assert result.slots[3].assignment_capacity == 4
    assert result.slots[3].seat_waste == 0

    assert result.slots[4].table_ids == [
        table_id,
    ]

    assert result.summary.total_slots == 5
    assert (
        result.summary.directly_available_slots
        == 2
    )
    assert result.summary.unavailable_slots == 3
    assert result.summary.availability_ratio == 0.4

    assert (
        result.summary.first_directly_available_at
        == datetime(
            2026,
            9,
            10,
            19,
            30,
        )
    )

    assert (
        result.summary.longest_directly_available_run
        == 2
    )