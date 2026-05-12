import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant


class RestaurantRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, restaurant: Restaurant) -> Restaurant:
        self.db.add(restaurant)
        await self.db.flush()
        await self.db.refresh(restaurant)
        return restaurant

    async def get_by_id(self, restaurant_id: uuid.UUID) -> Restaurant | None:
        result = await self.db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id_for_owner(
            self,
            restaurant_id:uuid.UUID,
            owner_id: uuid.UUID,
    ) -> Restaurant | None:
        result = await self.db.execute(
            select(Restaurant).where(
                Restaurant.id == restaurant_id,
                Restaurant.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Restaurant | None:
        result = await self.db.execute(
            select(Restaurant).where(Restaurant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[Restaurant]:
        result = await self.db.execute(
            select(Restaurant)
            .where(Restaurant.owner_id == owner_id)
            .order_by(Restaurant.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, restaurant: Restaurant, fields: dict) -> Restaurant:
        for key, value in fields.items():
            setattr(restaurant, key, value)

        await self.db.flush()
        await self.db.refresh(restaurant)
        return restaurant
