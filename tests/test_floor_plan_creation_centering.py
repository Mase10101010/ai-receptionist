
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

from app.schemas.floor_plan import FloorPlanCreate
from app.services.floor_plan_service import FloorPlanService


@pytest.mark.asyncio
async def test_new_floor_plan_centers_copied_tables_and_features(db_session):
    # Create test owner.
    user = User(
        email=f"floor-create-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(user)
    await db_session.flush()

    # Create restaurant.
    restaurant = Restaurant(
        owner_id=user.id,
        name="LAB-021K Restaurant",
        slug=f"lab021k-{uuid.uuid4()}",
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(restaurant)
    await db_session.flush()

    # Create service area.
    area = ServiceArea(
        restaurant_id=restaurant.id,
        name="Main Room",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(area)
    await db_session.flush()

    # Original floor plan.
    source_plan = FloorPlan(
        service_area_id=area.id,
        name="Original",
        width=1200,
        height=800,
        is_default=True,
        is_active=True,
    )
    db_session.add(source_plan)
    await db_session.flush()

    original_positions = [(100, 100), (300, 100)]

    # Create two tables and their placements.
    for index, (x, y) in enumerate(original_positions, start=1):
        table = Table(
            restaurant_id=restaurant.id,
            service_area_id=area.id,
            table_code=f"T{index}",
            table_number=str(index),
            seats=4,
            is_active=True,
        )
        db_session.add(table)
        await db_session.flush()

        placement = TablePlacement(
            floor_plan_id=source_plan.id,
            table_id=table.id,
            x=x,
            y=y,
            width=80,
            height=80,
            rotation=0,
            is_visible=True,
        )
        db_session.add(placement)

    # Add a structural feature.
    source_wall = FloorFeature(
        floor_plan_id=source_plan.id,
        feature_type="wall",
        label="Main Wall",
        x=500,
        y=100,
        width=200,
        height=20,
        rotation=0,
        is_visible=True,
    )
    db_session.add(source_wall)

    await db_session.flush()

    placement_repository = TablePlacementRepository(db_session)
    feature_repository = FloorFeatureRepository(db_session)

    service = FloorPlanService(
        repository=FloorPlanRepository(db_session),
        placement_repository=placement_repository,
        service_area_repository=ServiceAreaRepository(db_session),
        restaurant_repository=RestaurantRepository(db_session),
        feature_repository=feature_repository,
    )

    # Create a larger floor plan, copying the existing layout.
    new_plan = await service.create_floor_plan(
        restaurant_id=restaurant.id,
        area_id=area.id,
        owner_id=user.id,
        payload=FloorPlanCreate(
            name="Centered Copy",
            width=2000,
            height=1400,
        ),
    )

    # Load copied and original elements.
    copied = await placement_repository.list_by_floor_plan(new_plan.id)
    original = await placement_repository.list_by_floor_plan(source_plan.id)

    copied_features = await feature_repository.list_by_floor_plan(new_plan.id)

    assert len(copied) == 2
    assert len(original) == 2
    assert len(copied_features) == 1

    copied.sort(key=lambda item: item.x)
    original.sort(key=lambda item: item.x)

    copied_wall = copied_features[0]

    # Verify table separation is preserved.
    assert copied[1].x - copied[0].x == 200

    # Verify wall properties are preserved.
    assert copied_wall.feature_type == "wall"
    assert copied_wall.label == "Main Wall"
    assert copied_wall.width == 200
    assert copied_wall.height == 20
    assert copied_wall.rotation == 0
    assert copied_wall.is_visible is True

    # Verify every element received the same translation.
    dx = copied[0].x - original[0].x
    dy = copied[0].y - original[0].y

    for copied_table, original_table in zip(copied, original):
        assert copied_table.x == original_table.x + dx
        assert copied_table.y == original_table.y + dy
        assert copied_table.width == original_table.width
        assert copied_table.height == original_table.height
        assert copied_table.rotation == original_table.rotation
        assert copied_table.table_id == original_table.table_id
        assert copied_table.id != original_table.id

    assert copied_wall.x == source_wall.x + dx
    assert copied_wall.y == source_wall.y + dy
    assert copied_wall.id != source_wall.id

    # Verify the complete layout is centered.
    all_elements = [*copied, copied_wall]

    min_x = min(item.x for item in all_elements)
    max_x = max(item.x + item.width for item in all_elements)
    min_y = min(item.y for item in all_elements)
    max_y = max(item.y + item.height for item in all_elements)

    assert abs(
        (min_x + max_x) / 2 - new_plan.width / 2
    ) <= 0.5

    assert abs(
        (min_y + max_y) / 2 - new_plan.height / 2
    ) <= 0.5

    # Verify original layout was not modified.
    assert [(item.x, item.y) for item in original] == original_positions

    await db_session.refresh(source_wall)

    assert source_wall.x == 500
    assert source_wall.y == 100
    assert source_plan.width == 1200
    assert source_plan.height == 800
