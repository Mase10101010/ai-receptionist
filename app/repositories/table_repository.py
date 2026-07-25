import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.table import Table
from app.models.table_placement import TablePlacement


class TableRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, table: Table) -> Table:
        self.db.add(table)
        await self.db.flush()
        await self.db.refresh(table)
        return table

    async def get_by_id(
        self,
        table_id: uuid.UUID,
        restaurant_id: uuid.UUID | None = None,
    ) -> Table | None:
        stmt = select(Table).where(Table.id == table_id)

        if restaurant_id is not None:
            stmt = stmt.where(Table.restaurant_id == restaurant_id)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_number(
        self,
        restaurant_id: uuid.UUID,
        table_number: str,
    ) -> Table | None:
        result = await self.db.execute(
            select(Table).where(
                Table.restaurant_id == restaurant_id,
                Table.table_number == table_number,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_restaurant(
        self,
        restaurant_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[Table]:
        stmt = (
            select(Table)
            .where(Table.restaurant_id == restaurant_id)
            .order_by(Table.table_number.asc())
        )

        if not include_inactive:
            stmt = stmt.where(Table.is_active == True)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def list_capacity_candidates(
        self,
        restaurant_id: uuid.UUID,
        party_size: int,
    ) -> list[Table]:
        result = await self.db.execute(
            select(Table)
            .where(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True,
                Table.seats >= party_size,
            )
            .order_by(Table.seats.asc(), Table.table_number.asc())
        )

        return list(result.scalars().all())

    async def update(
        self,
        table: Table,
        fields: dict,
    ) -> Table:
        for key, value in fields.items():
            setattr(table, key, value)

        await self.db.flush()
        await self.db.refresh(table)
        return table

    async def delete(self, table: Table) -> None:
        await self.db.delete(table)
        await self.db.flush()

    async def list_by_floor_plan(
        self,
        restaurant_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[tuple[Table, TablePlacement]]:
        stmt = (
            select(Table, TablePlacement)
            .join(
                TablePlacement,
                TablePlacement.table_id == Table.id,
            )
            .where(
                Table.restaurant_id == restaurant_id,
                TablePlacement.floor_plan_id == floor_plan_id,
                TablePlacement.is_visible == True,
            )
            .order_by(Table.table_number.asc())
        )
        if not include_inactive:
            stmt = stmt.where(Table.is_active == True)

        result = await self.db.execute(stmt)
        return list(result.all())

    async def get_with_placement(
        self,
        table_id: uuid.UUID,
        restaurant_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
    ) -> tuple[Table, TablePlacement] | None:
        result = await self.db.execute(
            select(Table, TablePlacement)
            .join(
                TablePlacement,
                TablePlacement.table_id == Table.id,
            )
            .where(
                Table.id == table_id,
                Table.restaurant_id == restaurant_id,
                TablePlacement.floor_plan_id == floor_plan_id,
            )
        )

        return result.one_or_none()