import uuid
from datetime import datetime

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.restaurant import Restaurant
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.restaurant import RestaurantCreate, RestaurantUpdate


class RestaurantService:
    def __init__(self, repository: RestaurantRepository) -> None:
        self.repository = repository

    async def create_restaurant(
        self,
        payload: RestaurantCreate,
        owner_id: uuid.UUID,
    ) -> Restaurant:
        if payload.opening_hour >= payload.closing_hour:
            raise ValidationError("Opening hour must be before closing hour")

        existing = await self.repository.get_by_slug(payload.slug)
        if existing is not None:
            raise ConflictError(f"Restaurant slug '{payload.slug}' already exists")

        now = datetime.utcnow()

        restaurant = Restaurant(
            owner_id=owner_id,
            name=payload.name,
            slug=payload.slug,
            business_type=payload.business_type,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            timezone=payload.timezone,
            opening_hour=payload.opening_hour,
            closing_hour=payload.closing_hour,
            number_of_tables=payload.number_of_tables,
            concierge_tone=payload.concierge_tone,
            subscription_status="trialing",
            created_at=now,
            updated_at=now,
        )

        return await self.repository.create(restaurant)

    async def get_restaurant(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> Restaurant:
        restaurant = await self.repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError(f"Restaurant {restaurant_id} not found")

        return restaurant

    async def list_restaurants(
        self,
        owner_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Restaurant]:
        return await self.repository.list_by_owner(
            owner_id=owner_id,
            skip=skip,
            limit=limit,
        )

    async def update_restaurant(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: RestaurantUpdate,
    ) -> Restaurant:
        restaurant = await self.get_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        updates = payload.model_dump(exclude_unset=True)

        if "email" in updates and updates["email"] is not None:
            updates["email"] = str(updates["email"])

        new_opening = updates.get("opening_hour", restaurant.opening_hour)
        new_closing = updates.get("closing_hour", restaurant.closing_hour)

        if new_opening >= new_closing:
            raise ValidationError("Opening hour must be before closing hour")

        if "slug" in updates and updates["slug"] != restaurant.slug:
            existing = await self.repository.get_by_slug(updates["slug"])
            if existing is not None:
                raise ConflictError(f"Restaurant slug '{updates['slug']}' already exists")

        updates["updated_at"] = datetime.utcnow()

        return await self.repository.update(restaurant, updates)