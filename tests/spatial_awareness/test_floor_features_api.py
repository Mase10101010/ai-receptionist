import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_feature import FloorFeature
from app.models.floor_plan import FloorPlan
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea

pytestmark = pytest.mark.asyncio


async def test_create_and_read_window(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
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

    floor_plan = FloorPlan(
        service_area_id=area.id,
        name=f"Spatial Test {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )

    db_session.add(floor_plan)
    await db_session.flush()

    base = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}/features"
    )

    payload = {
        "feature_type": "window",
        "label": "Window A",
        "x": 100,
        "y": 120,
        "width": 160,
        "height": 20,
        "rotation": 0,
        "is_visible": True,
    }

    created = await client.post(base, json=payload)

    assert created.status_code == 201, created.text

    data = created.json()
    feature_id = data["id"]

    assert data["feature_type"] == "window"
    assert data["label"] == "Window A"
    assert data["x"] == 100

    stored = await db_session.get(
        FloorFeature,
        uuid.UUID(feature_id),
    )

    assert stored is not None
    assert stored.floor_plan_id == floor_plan.id

    fetched = await client.get(f"{base}/{feature_id}")

    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == feature_id

    listed = await client.get(base)

    assert listed.status_code == 200, listed.text
    assert any(
        feature["id"] == feature_id
        for feature in listed.json()
    )

    print("PASS: POST creates window")
    print("PASS: Window persisted in database")
    print("PASS: GET retrieves window")
    print("PASS: GET list includes window")


async def test_update_and_delete_window(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
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

    floor_plan = FloorPlan(
        service_area_id=area.id,
        name=f"Spatial CRUD {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    base = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}/features"
    )

    created = await client.post(
        base,
        json={
            "feature_type": "window",
            "label": "Original Window",
            "x": 100,
            "y": 100,
            "width": 160,
            "height": 20,
        },
    )
    assert created.status_code == 201, created.text

    feature_id = created.json()["id"]
    url = f"{base}/{feature_id}"

    updated = await client.patch(
        url,
        json={
            "label": "Updated Window",
            "x": 250,
            "rotation": 90,
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["label"] == "Updated Window"
    assert updated.json()["x"] == 250
    assert updated.json()["rotation"] == 90

    stored = await db_session.get(
        FloorFeature,
        uuid.UUID(feature_id),
    )
    assert stored is not None
    assert stored.label == "Updated Window"
    assert stored.x == 250

    deleted = await client.delete(url)
    assert deleted.status_code == 204, deleted.text

    missing = await client.get(url)
    assert missing.status_code == 404, missing.text

    db_session.expire_all()

    stored_after_delete = await db_session.get(
        FloorFeature,
        uuid.UUID(feature_id),
    )
    assert stored_after_delete is None

    print("PASS: PATCH updates feature")
    print("PASS: Updated geometry persisted")
    print("PASS: DELETE removes feature")
    print("PASS: Deleted feature returns 404")
    print("PASS: Database record removed")


async def test_cross_tenant_access_is_denied(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    from app.models.user import User

    foreign_owner = User(
        email=f"foreign-{uuid.uuid4()}@example.com",
        hashed_password="not-used-in-tests",
        is_active=True,
        is_email_verified=True,
        subscription_status="trialing",
    )
    db_session.add(foreign_owner)
    await db_session.flush()

    foreign_restaurant = Restaurant(
        owner_id=foreign_owner.id,
        name="Foreign Restaurant",
        slug=f"foreign-{uuid.uuid4()}",
        opening_hour=0,
        closing_hour=23,
        number_of_tables=4,
        subscription_status="trialing",
        onboarding_completed=True,
        autopilot_enabled=False,
    )
    db_session.add(foreign_restaurant)
    await db_session.flush()

    foreign_area = ServiceArea(
        restaurant_id=foreign_restaurant.id,
        name="Foreign Dining Room",
        area_type="indoor",
        is_active=True,
    )
    db_session.add(foreign_area)
    await db_session.flush()

    foreign_plan = FloorPlan(
        service_area_id=foreign_area.id,
        name="Foreign Floor Plan",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(foreign_plan)
    await db_session.flush()

    foreign_feature = FloorFeature(
        floor_plan_id=foreign_plan.id,
        feature_type="window",
        label="Private Window",
        x=100,
        y=100,
        width=160,
        height=20,
        rotation=0,
        is_visible=True,
    )
    db_session.add(foreign_feature)
    await db_session.flush()

    base = (
        f"/api/v1/restaurants/{foreign_restaurant.id}"
        f"/service-areas/{foreign_area.id}"
        f"/floor-plans/{foreign_plan.id}/features"
    )
    url = f"{base}/{foreign_feature.id}"

    attempts = [
        ("GET list", await client.get(base)),
        ("GET single", await client.get(url)),
        (
            "POST",
            await client.post(
                base,
                json={"feature_type": "door"},
            ),
        ),
        (
            "PATCH",
            await client.patch(
                url,
                json={"label": "Unauthorized Change"},
            ),
        ),
        ("DELETE", await client.delete(url)),
    ]

    for name, response in attempts:
        assert response.status_code == 404, (
            f"{name}: expected 404, got "
            f"{response.status_code}: {response.text}"
        )
        print(f"PASS: Foreign {name} rejected (404)")

    foreign_feature_id = foreign_feature.id
    db_session.expire_all()

    preserved = await db_session.get(
        FloorFeature,
        foreign_feature_id,
    )

    assert preserved is not None
    assert preserved.label == "Private Window"

    print("PASS: Foreign feature remains unchanged")
    print("LAB-018A.16.1: MULTI-TENANT SECURITY PASS")


@pytest.mark.parametrize(
    "invalid_geometry",
    [
        {"x": -1},
        {"y": -1},
        {"width": 0},
        {"height": 0},
        {"rotation": 360},
        {"x": 1150},
        {"y": 781},
        {"x": 0, "y": 0, "rotation": 45},
        {"x": 1100, "y": 700, "rotation": 45},
    ],
)
async def test_invalid_feature_geometry_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    invalid_geometry: dict,
) -> None:
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

    floor_plan = FloorPlan(
        service_area_id=area.id,
        name=f"Geometry Validation {uuid.uuid4()}",
        width=1200,
        height=800,
        sort_order=0,
        is_default=True,
        is_active=True,
    )
    db_session.add(floor_plan)
    await db_session.flush()

    base = (
        f"/api/v1/restaurants/{restaurant.id}"
        f"/service-areas/{area.id}"
        f"/floor-plans/{floor_plan.id}/features"
    )

    valid_geometry = {
        "feature_type": "window",
        "label": "Geometry Test",
        "x": 100,
        "y": 100,
        "width": 160,
        "height": 20,
        "rotation": 0,
    }

    invalid_payload = {
        **valid_geometry,
        **invalid_geometry,
    }

    rejected_create = await client.post(
        base,
        json=invalid_payload,
    )

    assert rejected_create.status_code == 422, (
        f"Invalid POST {invalid_geometry}: "
        f"{rejected_create.status_code} "
        f"{rejected_create.text}"
    )

    created = await client.post(
        base,
        json=valid_geometry,
    )
    assert created.status_code == 201, created.text

    feature_id = uuid.UUID(created.json()["id"])
    url = f"{base}/{feature_id}"

    rejected_update = await client.patch(
        url,
        json=invalid_geometry,
    )

    assert rejected_update.status_code == 422, (
        f"Invalid PATCH {invalid_geometry}: "
        f"{rejected_update.status_code} "
        f"{rejected_update.text}"
    )

    db_session.expire_all()

    preserved = await db_session.get(
        FloorFeature,
        feature_id,
    )

    assert preserved is not None
    assert preserved.x == valid_geometry["x"]
    assert preserved.y == valid_geometry["y"]
    assert preserved.width == valid_geometry["width"]
    assert preserved.height == valid_geometry["height"]
    assert preserved.rotation == valid_geometry["rotation"]

    print(
        f"PASS: Invalid geometry {invalid_geometry} "
        "rejected on POST/PATCH; original preserved"
    )
