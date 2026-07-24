import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_area import ServiceArea


class ServiceAreaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        area: ServiceArea,
    ) -> ServiceArea:
        self.db.add(area)
        await self.db.flush()
        await self.db.refresh(area)
        return area

    async def get_by_id(
        self,
        area_id: uuid.UUID,
    ) -> ServiceArea | None:
        result = await self.db.execute(
            select(ServiceArea).where(
                ServiceArea.id == area_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        restaurant_id: uuid.UUID,
        name: str,
    ) -> ServiceArea | None:
        result = await self.db.execute(
            select(ServiceArea).where(
                ServiceArea.restaurant_id == restaurant_id,
                ServiceArea.name == name,
            )
        )

        return result.scalar_one_or_none()

    async def list_by_restaurant(
        self,
        restaurant_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[ServiceArea]:

        stmt = (
            select(ServiceArea)
            .where(ServiceArea.restaurant_id == restaurant_id)
            .order_by(ServiceArea.sort_order)
        )

        if not include_inactive:
            stmt = stmt.where(
                ServiceArea.is_active == True,
            )

        result = await self.db.execute(stmt)

        return list(result.scalars().all())

    async def update(
        self,
        area: ServiceArea,
        fields: dict,
    ) -> ServiceArea:

        for key, value in fields.items():
            setattr(area, key, value)

        await self.db.flush()
        await self.db.refresh(area)

        return area

    async def delete(
        self,
        area: ServiceArea,
    ) -> None:

        await self.db.delete(area)
        await self.db.flush()