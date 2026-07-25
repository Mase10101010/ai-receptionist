import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.table_placement import TablePlacement


class TablePlacementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        placement: TablePlacement,
    ) -> TablePlacement:
        self.db.add(placement)
        await self.db.flush()
        await self.db.refresh(placement)
        return placement

    async def get(
        self,
        floor_plan_id: uuid.UUID,
        table_id: uuid.UUID,
    ) -> TablePlacement | None:
        result = await self.db.execute(
            select(TablePlacement).where(
                TablePlacement.floor_plan_id == floor_plan_id,
                TablePlacement.table_id == table_id,
            )
        )

        return result.scalar_one_or_none()

    async def update(
        self,
        placement: TablePlacement,
        fields: dict,
    ) -> TablePlacement:
        for key, value in fields.items():
            setattr(placement, key, value)

        await self.db.flush()
        await self.db.refresh(placement)

        return placement

    async def count_by_floor_plan(
            self,
            floor_plan_id: uuid.UUID,
    ) -> int:
        result = await self.db.execute(
            select(TablePlacement).where(
                TablePlacement.floor_plan_id
                == floor_plan_id,
            )
        )

        return len(result.scalars().all())

    async def copy_floor_plan(
        self,
        source_floor_plan_id: uuid.UUID,
        target_floor_plan_id: uuid.UUID,
    ) -> list[TablePlacement]:
        result = await self.db.execute(
            select(TablePlacement).where(
                TablePlacement.floor_plan_id
                == source_floor_plan_id,
            )
        )

        source_placements = list(
            result.scalars().all(),
        )

        copied_placements: list[TablePlacement] = []

        for source in source_placements:
            copied = TablePlacement(
                floor_plan_id=target_floor_plan_id,
                table_id=source.table_id,
                x=source.x,
                y=source.y,
                width=source.width,
                height=source.height,
                rotation=source.rotation,
                is_visible=source.is_visible,
            )

            self.db.add(copied)
            copied_placements.append(copied)

        await self.db.flush()

        for placement in copied_placements:
            await self.db.refresh(placement)

        return copied_placements

    async def delete(
        self,
        placement: TablePlacement,
    ) -> None:
        await self.db.delete(placement)
        await self.db.flush()

    async def update_for_floor_plan(
        self,
        floor_plan_id: uuid.UUID,
        table_id: uuid.UUID,
        fields: dict,
    ) -> TablePlacement:

        placement = await self.get(
            floor_plan_id=floor_plan_id,
            table_id=table_id,
        )

        if placement is None:
            raise ValueError("Placement not found")

        for key, value in fields.items():
            setattr(placement, key, value)

        await self.db.flush()
        await self.db.refresh(placement)

        return placement