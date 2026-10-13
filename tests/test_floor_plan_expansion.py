
import uuid

import pytest

from app.models.floor_feature import FloorFeature
from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_placement import TablePlacement
from app.models.user import User

from app.repositories.floor_feature_repository import FloorFeatureRepository
from app.repositories.floor_plan_repository import FloorPlanRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.service_area_repository import ServiceAreaRepository
from app.repositories.table_placement_repository import TablePlacementRepository

from app.schemas.floor_plan import FloorPlanUpdate
from app.services.floor_plan_service import FloorPlanService


@pytest.mark.asyncio
async def test_expansion_centers_tables_and_features(db_session):
    user = User(
        email=f"floor-expansion-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="LAB-021G Restaurant",
        slug=f"lab021g-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    area = ServiceArea(
        restaurant_id=restaurant.id,
        name="Main Room",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(area)
    await db_session.flush()

    floor_plan = FloorPlan(
        service_area_id=area.id,
        name="Test Layout",
        width=1200,
        height=800,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    table = Table(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        table_code="T1",
        table_number="1",
        seats=4,
        is_active=True,
    )
    db_session.add(table)
    await db_session.flush()

    placement = TablePlacement(
        floor_plan_id=floor_plan.id,
        table_id=table.id,
        x=100,
        y=100,
        width=80,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(placement)

    feature = FloorFeature(
        floor_plan_id=floor_plan.id,
        feature_type="wall",
        x=250,
        y=100,
        width=200,
        height=20,
        rotation=0,
        is_visible=True,
    )
    db_session.add(feature)
    await db_session.flush()

    original_table_x = placement.x
    original_wall_x = feature.x
    original_distance = feature.x - placement.x

    service = FloorPlanService(
        repository=FloorPlanRepository(db_session),
        placement_repository=TablePlacementRepository(db_session),
        service_area_repository=ServiceAreaRepository(db_session),
        restaurant_repository=RestaurantRepository(db_session),
        feature_repository=FloorFeatureRepository(db_session),
    )

    await service.update_floor_plan(
        restaurant_id=restaurant.id,
        area_id=area.id,
        floor_plan_id=floor_plan.id,
        owner_id=user.id,
        payload=FloorPlanUpdate(
            width=2400,
            height=1800,
        ),
    )

    await db_session.refresh(floor_plan)
    await db_session.refresh(placement)
    await db_session.refresh(feature)

    assert floor_plan.width == 2400
    assert floor_plan.height == 1800

    assert placement.x != original_table_x
    assert feature.x != original_wall_x

    # The table and wall must move by exactly the same amount.
    assert (
        feature.x - placement.x
        == original_distance
    )

    # The entire occupied layout must be centered.
    occupied_min_x = min(placement.x, feature.x)
    occupied_max_x = max(
        placement.x + placement.width,
        feature.x + feature.width,
    )

    occupied_min_y = min(placement.y, feature.y)
    occupied_max_y = max(
        placement.y + placement.height,
        feature.y + feature.height,
    )

    assert abs(
        (occupied_min_x + occupied_max_x) / 2
        - floor_plan.width / 2
    ) <= 0.5

    assert abs(
        (occupied_min_y + occupied_max_y) / 2
        - floor_plan.height / 2
    ) <= 0.5


@pytest.mark.asyncio
async def test_rename_does_not_move_layout(db_session):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace

    floor_plan = SimpleNamespace(
        id=uuid.uuid4(),
        service_area_id=uuid.uuid4(),
        name="Original Layout",
        width=1200,
        height=800,
        is_default=False,
        is_active=True,
    )

    restaurant_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    restaurant_repository = AsyncMock()
    restaurant_repository.get_by_id_for_owner.return_value = SimpleNamespace(
        id=restaurant_id,
        owner_id=owner_id,
        subscription_status="trialing",
    )

    area_repository = AsyncMock()
    area_repository.get_by_id.return_value = SimpleNamespace(
        id=floor_plan.service_area_id,
        restaurant_id=restaurant_id,
    )

    plan_repository = AsyncMock()
    plan_repository.get_by_id.return_value = floor_plan

    async def update_plan(*, floor_plan, fields):
        for key, value in fields.items():
            setattr(floor_plan, key, value)
        return floor_plan

    plan_repository.update.side_effect = update_plan
    plan_repository.list_by_service_area.return_value = [floor_plan]

    placement_repository = AsyncMock()
    feature_repository = AsyncMock()

    service = FloorPlanService(
        repository=plan_repository,
        placement_repository=placement_repository,
        service_area_repository=area_repository,
        restaurant_repository=restaurant_repository,
        feature_repository=feature_repository,
    )

    result = await service.update_floor_plan(
        restaurant_id=restaurant_id,
        area_id=floor_plan.service_area_id,
        floor_plan_id=floor_plan.id,
        owner_id=owner_id,
        payload=FloorPlanUpdate(name="Renamed Layout"),
    )

    assert result.name == "Renamed Layout"

    placement_repository.list_by_floor_plan.assert_not_awaited()
    feature_repository.list_by_floor_plan.assert_not_awaited()
    placement_repository.update.assert_not_awaited()
    feature_repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_shrinking_floor_plan_is_rejected():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from fastapi import HTTPException

    restaurant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    area_id = uuid.uuid4()

    floor_plan = SimpleNamespace(
        id=uuid.uuid4(),
        service_area_id=area_id,
        name="Original Layout",
        width=2400,
        height=1800,
        is_default=False,
        is_active=True,
    )

    restaurant_repository = AsyncMock()
    restaurant_repository.get_by_id_for_owner.return_value = (
        SimpleNamespace(
            id=restaurant_id,
            owner_id=owner_id,
            subscription_status="trialing",
        )
    )

    area_repository = AsyncMock()
    area_repository.get_by_id.return_value = SimpleNamespace(
        id=area_id,
        restaurant_id=restaurant_id,
    )

    plan_repository = AsyncMock()
    plan_repository.get_by_id.return_value = floor_plan

    placement_repository = AsyncMock()
    feature_repository = AsyncMock()

    service = FloorPlanService(
        repository=plan_repository,
        placement_repository=placement_repository,
        service_area_repository=area_repository,
        restaurant_repository=restaurant_repository,
        feature_repository=feature_repository,
    )

    with pytest.raises(HTTPException) as exc:
        await service.update_floor_plan(
            restaurant_id=restaurant_id,
            area_id=area_id,
            floor_plan_id=floor_plan.id,
            owner_id=owner_id,
            payload=FloorPlanUpdate(
                width=1200,
                height=800,
            ),
        )

    assert exc.value.status_code == 422
    assert floor_plan.width == 2400
    assert floor_plan.height == 1800

    plan_repository.update.assert_not_awaited()
    placement_repository.update.assert_not_awaited()
    feature_repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_expansion_failure_can_be_rolled_back(db_session):
    from unittest.mock import AsyncMock

    user = User(
        email=f"rollback-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    restaurant = Restaurant(
        owner_id=user.id,
        name="LAB-021G Rollback",
        slug=f"lab021g-rollback-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    area = ServiceArea(
        restaurant_id=restaurant.id,
        name="Main Room",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(area)
    await db_session.flush()

    plan = FloorPlan(
        service_area_id=area.id,
        name="Rollback Layout",
        width=1200,
        height=800,
        is_default=True,
        is_active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    table = Table(
        restaurant_id=restaurant.id,
        service_area_id=area.id,
        table_code="T1",
        table_number="1",
        seats=4,
        is_active=True,
    )
    db_session.add(table)
    await db_session.flush()

    placement = TablePlacement(
        floor_plan_id=plan.id,
        table_id=table.id,
        x=100,
        y=100,
        width=80,
        height=80,
        rotation=0,
        is_visible=True,
    )
    db_session.add(placement)

    feature = FloorFeature(
        floor_plan_id=plan.id,
        feature_type="wall",
        x=250,
        y=100,
        width=200,
        height=20,
        rotation=0,
        is_visible=True,
    )
    db_session.add(feature)
    await db_session.commit()

    original_placement_id = placement.id
    original_feature_id = feature.id
    original_plan_id = plan.id

    feature_repository = FloorFeatureRepository(db_session)
    feature_repository.update = AsyncMock(
        side_effect=RuntimeError("Simulated feature update failure")
    )

    service = FloorPlanService(
        repository=FloorPlanRepository(db_session),
        placement_repository=TablePlacementRepository(db_session),
        service_area_repository=ServiceAreaRepository(db_session),
        restaurant_repository=RestaurantRepository(db_session),
        feature_repository=feature_repository,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated feature update failure",
    ):
        await service.update_floor_plan(
            restaurant_id=restaurant.id,
            area_id=area.id,
            floor_plan_id=plan.id,
            owner_id=user.id,
            payload=FloorPlanUpdate(
                width=2400,
                height=1800,
            ),
        )

    # The request transaction must be rolled back after failure.
    await db_session.rollback()

    await db_session.refresh(plan)
    await db_session.refresh(placement)
    await db_session.refresh(feature)

    assert plan.id == original_plan_id
    assert plan.width == 1200
    assert plan.height == 800

    assert placement.id == original_placement_id
    assert placement.x == 100
    assert placement.y == 100

    assert feature.id == original_feature_id
    assert feature.x == 250
    assert feature.y == 100

