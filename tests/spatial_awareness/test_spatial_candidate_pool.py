"""Integration tests for spatial candidate pool expansion."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.intelligence.optimizer import ReservationOptimizer
from app.intelligence.schemas import IntelligenceOptimizeRequest
from app.intelligence.sqlalchemy_service import IntelligenceOptimizationService
from app.models.restaurant import Restaurant

pytestmark = pytest.mark.asyncio


class RecordingOptimizer(ReservationOptimizer):
    def __init__(self):
        self.received_limits = []

    def optimize(self, request, tables, reservations, combinations=None):
        self.received_limits.append(request.max_alternatives)
        return super().optimize(
            request=request,
            tables=tables,
            reservations=reservations,
            combinations=combinations,
        )


@pytest.mark.parametrize(
    ("spatial_preference", "expected_limit"),
    [
        (None, 3),
        ("near_window", 10),
    ],
)
async def test_spatial_preference_expands_candidate_pool(
    client,
    db_session,
    spatial_preference,
    expected_limit,
):
    restaurant = (
        await db_session.execute(select(Restaurant))
    ).scalars().one()

    optimizer = RecordingOptimizer()
    service = IntelligenceOptimizationService(
        optimizer=optimizer,
    )

    payload = IntelligenceOptimizeRequest(
        restaurant_id=restaurant.id,
        requested_start=datetime(
            2026, 10, 20, 12, tzinfo=timezone.utc
        ),
        party_size=2,
        duration_minutes=90,
        max_alternatives=3,
        spatial_preference=spatial_preference,
    )

    response = await service.optimize(
        session=db_session,
        payload=payload,
    )

    assert optimizer.received_limits == [expected_limit]
    assert response.available is True
    assert response.recommended is not None


async def test_fourth_table_can_win_with_window_preference(client, db_session):
    """A spatial preference can recover a candidate excluded from the normal top 3."""
    from uuid import uuid4

    from app.models.service_area import ServiceArea
    from app.models.table import Table
    from app.models.floor_plan import FloorPlan
    from app.models.table_placement import TablePlacement
    from app.models.floor_feature import FloorFeature

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

    service = IntelligenceOptimizationService()

    common = dict(
        restaurant_id=restaurant.id,
        requested_start=datetime(
            2026, 10, 20, 12, tzinfo=timezone.utc
        ),
        party_size=2,
        duration_minutes=90,
        max_alternatives=3,
    )

    normal = await service.optimize(
        session=db_session,
        payload=IntelligenceOptimizeRequest(**common),
    )

    assert normal.available is True
    assert normal.recommended is not None

    normal_ids = {
        table_id
        for candidate in [normal.recommended, *normal.alternatives]
        for table_id in candidate.table_ids
    }

    excluded_ids = {table.id for table in tables} - normal_ids
    assert len(excluded_ids) == 1
    excluded_id = excluded_ids.pop()

    plan = FloorPlan(
        service_area_id=area.id,
        name=f"Window Preference {uuid4()}",
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    for index, table in enumerate(tables):
        db_session.add(
            TablePlacement(
                floor_plan_id=plan.id,
                table_id=table.id,
                x=0 if table.id == excluded_id else 300 + index * 200,
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

    spatial = await service.optimize(
        session=db_session,
        payload=IntelligenceOptimizeRequest(
            **common,
            spatial_preference="near_window",
        ),
    )

    assert spatial.available is True
    assert spatial.recommended is not None

    # The internal pool may expand, but the public response must
    # respect the originally requested candidate limit.
    assert len(normal.alternatives) <= 2
    assert len(spatial.alternatives) <= 2

    print("Normal recommendation:", normal.recommended.table_ids)
    print("Previously excluded table:", excluded_id)
    print("Spatial recommendation:", spatial.recommended.table_ids)

    assert spatial.recommended.table_ids == [excluded_id]
