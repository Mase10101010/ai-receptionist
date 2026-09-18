from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.restaurant import RestaurantUpdate
from app.services.restaurant_service import RestaurantService


class FakeRestaurantRepository:
    def __init__(self):
        self.updated_restaurant = None
        self.updated_values = None

    async def get_by_id_for_owner(
        self,
        *,
        restaurant_id,
        owner_id,
    ):
        return SimpleNamespace(
            id=restaurant_id,
            owner_id=owner_id,
            slug="test-restaurant",
            opening_hour="10:00",
            closing_hour="23:00",
            autopilot_enabled=False,
        )

    async def get_by_slug(self, slug):
        return None

    async def update(
        self,
        restaurant,
        updates,
    ):
        self.updated_restaurant = restaurant
        self.updated_values = updates

        for key, value in updates.items():
            setattr(restaurant, key, value)

        return restaurant


class FakeUserRepository:
    pass


class FakeEmailService:
    pass


@pytest.mark.asyncio
async def test_restaurant_update_propagates_autopilot_enabled():
    restaurant_id = uuid4()
    owner_id = uuid4()

    repository = FakeRestaurantRepository()

    service = RestaurantService(
        repository=repository,
        email_service=FakeEmailService(),
        user_repository=FakeUserRepository(),
    )

    result = await service.update_restaurant(
        restaurant_id=restaurant_id,
        owner_id=owner_id,
        payload=RestaurantUpdate(
            autopilot_enabled=True,
        ),
    )

    assert result.autopilot_enabled is True
    assert repository.updated_values["autopilot_enabled"] is True


@pytest.mark.asyncio
async def test_restaurant_update_does_not_change_autopilot_when_unset():
    restaurant_id = uuid4()
    owner_id = uuid4()

    repository = FakeRestaurantRepository()

    restaurant = await repository.get_by_id_for_owner(
        restaurant_id=restaurant_id,
        owner_id=owner_id,
    )
    restaurant.autopilot_enabled = True

    async def get_existing_restaurant(**kwargs):
        return restaurant

    repository.get_by_id_for_owner = get_existing_restaurant

    service = RestaurantService(
        repository=repository,
        email_service=FakeEmailService(),
        user_repository=FakeUserRepository(),
    )

    result = await service.update_restaurant(
        restaurant_id=restaurant_id,
        owner_id=owner_id,
        payload=RestaurantUpdate(),
    )

    assert result.autopilot_enabled is True
    assert "autopilot_enabled" not in repository.updated_values


@pytest.mark.asyncio
async def test_restaurant_update_can_disable_autopilot():
    restaurant_id = uuid4()
    owner_id = uuid4()

    repository = FakeRestaurantRepository()

    restaurant = await repository.get_by_id_for_owner(
        restaurant_id=restaurant_id,
        owner_id=owner_id,
    )
    restaurant.autopilot_enabled = True

    async def get_existing_restaurant(**kwargs):
        return restaurant

    repository.get_by_id_for_owner = get_existing_restaurant

    service = RestaurantService(
        repository=repository,
        email_service=FakeEmailService(),
        user_repository=FakeUserRepository(),
    )

    result = await service.update_restaurant(
        restaurant_id=restaurant_id,
        owner_id=owner_id,
        payload=RestaurantUpdate(
            autopilot_enabled=False,
        ),
    )

    assert result.autopilot_enabled is False
    assert repository.updated_values["autopilot_enabled"] is False