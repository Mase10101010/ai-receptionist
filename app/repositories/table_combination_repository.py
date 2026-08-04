import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.table_combination import (
    TableCombination,
    TableCombinationMember,
)


class TableCombinationRepository:
    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def create(
        self,
        combination: TableCombination,
    ) -> TableCombination:
        self.db.add(combination)
        await self.db.flush()
        await self.db.refresh(combination)

        return combination

    async def get_by_id(
        self,
        combination_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> TableCombination | None:
        result = await self.db.execute(
            select(TableCombination)
            .options(
                selectinload(
                    TableCombination.members,
                ).selectinload(
                    TableCombinationMember.table,
                )
            )
            .where(
                TableCombination.id == combination_id,
                TableCombination.restaurant_id
                == restaurant_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        restaurant_id: uuid.UUID,
        name: str,
    ) -> TableCombination | None:
        result = await self.db.execute(
            select(TableCombination)
            .where(
                TableCombination.restaurant_id
                == restaurant_id,
                TableCombination.name == name,
            )
        )

        return result.scalar_one_or_none()

    async def list_by_restaurant(
        self,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> list[TableCombination]:
        stmt = (
            select(TableCombination)
            .options(
                selectinload(
                    TableCombination.members,
                ).selectinload(
                    TableCombinationMember.table,
                )
            )
            .where(
                TableCombination.restaurant_id
                == restaurant_id,
            )
            .order_by(
                TableCombination.name.asc(),
            )
        )

        if service_area_id is not None:
            stmt = stmt.where(
                TableCombination.service_area_id
                == service_area_id,
            )

        if not include_inactive:
            stmt = stmt.where(
                TableCombination.is_active.is_(True),
            )

        result = await self.db.execute(stmt)

        return list(
            result.scalars().unique().all()
        )

    async def update(
        self,
        combination: TableCombination,
        fields: dict,
    ) -> TableCombination:
        for key, value in fields.items():
            setattr(combination, key, value)

        await self.db.flush()
        await self.db.refresh(combination)

        return combination

    async def replace_members(
        self,
        combination: TableCombination,
        table_ids: list[uuid.UUID],
    ) -> TableCombination:
        combination.members.clear()

        for index, table_id in enumerate(
            table_ids,
        ):
            combination.members.append(
                TableCombinationMember(
                    table_id=table_id,
                    sort_order=index,
                )
            )

        await self.db.flush()

        return await self.get_by_id(
            combination_id=combination.id,
            restaurant_id=combination.restaurant_id,
        )

    async def delete(
        self,
        combination: TableCombination,
    ) -> None:
        await self.db.delete(combination)
        await self.db.flush()