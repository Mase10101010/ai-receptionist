"""Spatial preference integration with real reservation persistence."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.intelligence.schemas import IntelligenceOptimizeRequest
from app.intelligence.sqlalchemy_service import IntelligenceOptimizationService
from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventType,
)
from app.models.floor_feature import FloorFeature
from app.models.floor_plan import FloorPlan
from app.models.reservation import ReservationStatus
from app.models.reservation_table_assignment import ReservationTableAssignment
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_placement import TablePlacement
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.reservation import ReservationCreate
from app.services.reservation_access_service import ReservationAccessService
from app.services.reservation_service import ReservationService

pytestmark = pytest.mark.asyncio


async def test_window_preference_is_persisted_as_selected_table(
    client,
    db_session,
):
    restaurant = (
        await db_session.execute(select(Restaurant))
    ).scalars().one()

    area = (
        await db_session.execute(
            select(ServiceArea).where(
                ServiceArea.restaurant_id == restaurant.id
            )
        )
    ).scalars().one()

    tables = list((
        await db_session.execute(
            select(Table)
            .where(Table.restaurant_id == restaurant.id)
            .order_by(Table.table_number)
        )
    ).scalars().all())

    assert len(tables) == 4

    intelligence = IntelligenceOptimizationService()
    requested_start = datetime(
        2026, 10, 20, 12, tzinfo=timezone.utc
    )

    normal = await intelligence.optimize(
        session=db_session,
        payload=IntelligenceOptimizeRequest(
            restaurant_id=restaurant.id,
            requested_start=requested_start,
            party_size=2,
            duration_minutes=90,
            max_alternatives=3,
        ),
    )

    assert normal.available
    assert normal.recommended is not None

    normal_ids = {
        table_id
        for candidate in [normal.recommended, *normal.alternatives]
        for table_id in candidate.table_ids
    }

    excluded_ids = {table.id for table in tables} - normal_ids
    assert len(excluded_ids) == 1
    expected_table_id = excluded_ids.pop()

    plan = FloorPlan(
        service_area_id=area.id,
        name=f"Booking Window Test {uuid4()}",
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    for index, table in enumerate(tables):
        db_session.add(
            TablePlacement(
                floor_plan_id=plan.id,
                table_id=table.id,
                x=0 if table.id == expected_table_id else 300 + index * 200,
                y=0,
                width=80,
                height=80,
                rotation=0,
                is_visible=True,
            )
        )

    db_session.add(
        FloorFeature(
            floor_plan_id=plan.id,
            feature_type="window",
            x=100,
            y=0,
            width=40,
            height=40,
            rotation=0,
            is_visible=True,
        )
    )
    await db_session.flush()

    repository = ReservationRepository(db_session)

    service = ReservationService(
        repository=repository,
        restaurant_repository=RestaurantRepository(db_session),
        table_repository=TableRepository(db_session),
        email_service=AsyncMock(),
        intelligence_service=intelligence,
    )

    service._validate_reservation_time = AsyncMock()
    service._try_record_temporal_prediction = AsyncMock()

    payload = ReservationCreate(
        restaurant_id=restaurant.id,
        customer_name="Window Preference Guest",
        customer_phone="+15551234567",
        customer_email=None,
        party_size=2,
        reservation_time=requested_start,
        duration_minutes=90,
        spatial_preference="near_window",
    )

    with patch.object(
        ReservationAccessService,
        "issue",
        new=AsyncMock(return_value="test-token"),
    ):
        created = await service.create_reservation(payload)

    assert created.status == ReservationStatus.CONFIRMED
    assert created.table_id == expected_table_id

    reservation_id = created.id
    restaurant_id = restaurant.id

    await db_session.flush()
    db_session.expire_all()

    persisted = await repository.get_by_id(
        reservation_id,
        restaurant_id=restaurant_id,
    )

    assert persisted is not None
    assert persisted.status == ReservationStatus.CONFIRMED
    assert persisted.table_id == expected_table_id

    assignments = (
        await db_session.execute(
            select(ReservationTableAssignment).where(
                ReservationTableAssignment.reservation_id == reservation_id
            )
        )
    ).scalars().all()

    assert len(assignments) == 1
    assert assignments[0].table_id == expected_table_id
    assert assignments[0].is_primary is True


    events = (
        await db_session.execute(
            select(IntelligenceEvent).where(
                IntelligenceEvent.restaurant_id == restaurant_id,
                IntelligenceEvent.entity_id == reservation_id,
                IntelligenceEvent.event_type
                == IntelligenceEventType.RESERVATION_CREATED,
            )
        )
    ).scalars().all()

    assert len(events) == 1
    assert events[0].payload["spatial_preference"] == "near_window"
    assert events[0].payload["table_id"] == str(expected_table_id)
