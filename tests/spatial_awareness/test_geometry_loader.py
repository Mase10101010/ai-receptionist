"""Integration tests for restaurant-scoped spatial geometry loading."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_feature import FloorFeature
from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.geometry_loader import (
    SpatialGeometryLoader,
)

pytestmark = pytest.mark.asyncio


async def make_scenario(db_session, *, area_active=True, plan_active=True):
    restaurant = (await db_session.execute(
        select(Restaurant)
    )).scalars().one()

    area = (await db_session.execute(
        select(ServiceArea).where(
            ServiceArea.restaurant_id == restaurant.id
        )
    )).scalars().one()

    area.is_active = area_active

    table = (await db_session.execute(
        select(Table).where(
            Table.restaurant_id == restaurant.id
        ).order_by(Table.table_number)
    )).scalars().first()

    plan = FloorPlan(
        service_area_id=area.id,
        name=f"Spatial Loader {uuid.uuid4()}",
        is_active=plan_active,
    )
    db_session.add(plan)
    await db_session.flush()

    placement = TablePlacement(
        floor_plan_id=plan.id,
        table_id=table.id,
        x=0,
        y=0,
        width=80,
        height=80,
        rotation=0,
        is_visible=True,
    )
    window = FloorFeature(
        floor_plan_id=plan.id,
        feature_type="window",
        x=100,
        y=0,
        width=40,
        height=40,
        rotation=0,
        is_visible=True,
    )

    db_session.add_all([placement, window])
    await db_session.flush()

    return restaurant, area, plan, table, placement, window


async def test_loads_visible_geometry(client, db_session: AsyncSession):
    restaurant, _, _, table, placement, window = (
        await make_scenario(db_session)
    )

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert [p.table_id for p in result.placements] == [table.id]
    assert [f.id for f in result.features] == [window.id]


async def test_inactive_area_excluded(client, db_session: AsyncSession):
    restaurant, *_ = await make_scenario(
        db_session, area_active=False
    )

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert result.placements == ()
    assert result.features == ()


async def test_inactive_floor_plan_excluded(client, db_session: AsyncSession):
    restaurant, *_ = await make_scenario(
        db_session, plan_active=False
    )

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert result.placements == ()
    assert result.features == ()


async def test_hidden_geometry_excluded(client, db_session: AsyncSession):
    restaurant, _, _, _, placement, window = (
        await make_scenario(db_session)
    )

    placement.is_visible = False
    window.is_visible = False
    await db_session.flush()

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert result.placements == ()
    assert result.features == ()


async def test_inactive_table_excluded(client, db_session: AsyncSession):
    restaurant, _, _, table, _, window = (
        await make_scenario(db_session)
    )

    table.is_active = False
    await db_session.flush()

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert result.placements == ()
    assert [f.id for f in result.features] == [window.id]


async def test_other_restaurant_cannot_read_geometry(
    client, db_session: AsyncSession
):
    restaurant, *_ = await make_scenario(db_session)

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=uuid.uuid4(),
    )

    assert result.placements == ()
    assert result.features == ()


async def test_mismatched_table_area_excluded(
    client, db_session: AsyncSession
):
    restaurant, area, _, table, _, window = (
        await make_scenario(db_session)
    )

    other_area = ServiceArea(
        restaurant_id=restaurant.id,
        name=f"Other Area {uuid.uuid4()}",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(other_area)
    await db_session.flush()

    table.service_area_id = other_area.id
    await db_session.flush()

    result = await SpatialGeometryLoader.load(
        session=db_session,
        restaurant_id=restaurant.id,
    )

    assert result.placements == ()
    assert [f.id for f in result.features] == [window.id]
