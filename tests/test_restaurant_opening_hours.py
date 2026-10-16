import pytest
from sqlalchemy import select

from app.models.restaurant import Restaurant


@pytest.mark.asyncio
async def test_restaurant_rejects_overlapping_sessions(client, db_session):
    result = await db_session.execute(select(Restaurant))
    restaurant = result.scalar_one()

    invalid_schedule = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {
                    "start": "12:00",
                    "end": "15:00",
                    "last_booking": "14:30",
                },
                {
                    "start": "14:00",
                    "end": "18:00",
                    "last_booking": "17:30",
                },
            ],
        }
    ]

    response = await client.patch(
        f"/api/v1/restaurants/{restaurant.id}",
        json={"weekly_schedule": invalid_schedule},
    )

    assert response.status_code == 422, response.text

    await db_session.refresh(restaurant)

    assert restaurant.weekly_schedule is None


@pytest.mark.asyncio
async def test_restaurant_saves_lunch_and_dinner_sessions(
    client, db_session
):
    result = await db_session.execute(select(Restaurant))
    restaurant = result.scalar_one()

    valid_schedule = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {
                    "start": "12:00",
                    "end": "15:00",
                    "last_booking": "14:30",
                },
                {
                    "start": "19:00",
                    "end": "23:00",
                    "last_booking": "22:30",
                },
            ],
        }
    ]

    response = await client.patch(
        f"/api/v1/restaurants/{restaurant.id}",
        json={"weekly_schedule": valid_schedule},
    )

    assert response.status_code == 200, response.text
    assert response.json()["weekly_schedule"] == valid_schedule

    await db_session.refresh(restaurant)
    assert restaurant.weekly_schedule == valid_schedule


@pytest.mark.asyncio
async def test_restaurant_preserves_legacy_weekly_schedule(
    client, db_session
):
    result = await db_session.execute(select(Restaurant))
    restaurant = result.scalar_one()

    legacy_schedule = [
        {
            "day": "Mon",
            "is_open": True,
            "opening_hour": 11,
            "closing_hour": 22,
        },
        {
            "day": "Tue",
            "is_open": False,
        },
    ]

    response = await client.patch(
        f"/api/v1/restaurants/{restaurant.id}",
        json={"weekly_schedule": legacy_schedule},
    )

    assert response.status_code == 200, response.text
    assert response.json()["weekly_schedule"] == legacy_schedule

    await db_session.refresh(restaurant)
    assert restaurant.weekly_schedule == legacy_schedule


@pytest.mark.asyncio
async def test_create_restaurant_with_multiple_sessions(
    client, db_session
):
    from uuid import uuid4

    schedule = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {"start": "12:00", "end": "15:00"},
                {"start": "19:00", "end": "23:00"},
            ],
        }
    ]

    slug = f"alias-multisession-{uuid4().hex}"

    response = await client.post(
        "/api/v1/restaurants",
        json={
            "name": "Alias Multi-Session Test",
            "slug": slug,
            "timezone": "Australia/Perth",
            "weekly_schedule": schedule,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["weekly_schedule"] == schedule

    from uuid import UUID
    restaurant_id = UUID(response.json()["id"])

    result = await db_session.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id
        )
    )

    restaurant = result.scalar_one()
    assert restaurant.weekly_schedule == schedule


@pytest.mark.asyncio
async def test_create_restaurant_rejects_overlapping_sessions(
    client, db_session
):
    from uuid import uuid4

    slug = f"alias-invalid-hours-{uuid4().hex}"

    invalid_schedule = [
        {
            "day": "Mon",
            "is_open": True,
            "sessions": [
                {"start": "12:00", "end": "15:00"},
                {"start": "14:00", "end": "18:00"},
            ],
        }
    ]

    response = await client.post(
        "/api/v1/restaurants",
        json={
            "name": "Invalid Opening Hours Test",
            "slug": slug,
            "weekly_schedule": invalid_schedule,
        },
    )

    assert response.status_code == 422, response.text

    result = await db_session.execute(
        select(Restaurant).where(Restaurant.slug == slug)
    )

    assert result.scalar_one_or_none() is None
