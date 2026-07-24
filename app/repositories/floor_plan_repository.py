import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_plan import FloorPlan


class FloorPlanRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        floor_plan: FloorPlan,
    ) -> FloorPlan:

        self.db.add(floor_plan)

        await self.db.flush()
        await self.db.refresh(floor_plan)

        return floor_plan

    async def get_by_id(
        self,
        floor_plan_id: uuid.UUID,
    ) -> FloorPlan | None:
        result = await self.db.execute(
            select(FloorPlan)
            .options(
                selectinload(FloorPlan.service_area),
            )
            .where(
                FloorPlan.id == floor_plan_id,
            )
        )

        return result.scalar_one_or_none()

        result = await self.db.execute(
            select(FloorPlan).where(
                FloorPlan.id == floor_plan_id,
            )
        )

        return result.scalar_one_or_none()

    async def list_by_service_area(
        self,
        service_area_id: uuid.UUID,
    ) -> list[FloorPlan]:

        result = await self.db.execute(
            select(FloorPlan)
            .where(
                FloorPlan.service_area_id == service_area_id,
                FloorPlan.is_active == True,
            )
            .order_by(
                FloorPlan.sort_order,
            )
        )

        return list(result.scalars().all())

    async def update(
        self,
        floor_plan: FloorPlan,
        fields: dict,
    ) -> FloorPlan:

        for key, value in fields.items():
            setattr(floor_plan, key, value)

        await self.db.flush()
        await self.db.refresh(floor_plan)

        return floor_plan

    async def delete(
        self,
        floor_plan: FloorPlan,
    ) -> None:

        await self.db.delete(floor_plan)

        await self.db.flush()