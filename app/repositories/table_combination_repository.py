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

    async def get_by_id_for_update(
        self,
        combination_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> TableCombination | None:
        """Lock the authoritative combination before modifying it."""
        result = await self.db.execute(
            select(TableCombination)
            .where(
                TableCombination.id == combination_id,
                TableCombination.restaurant_id == restaurant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        combination = result.scalar_one_or_none()

        if combination is None:
            return None

        await self.db.refresh(
            combination,
            attribute_names=["members"],
        )

        return combination

    async def get_by_smart_layout_rule_id(
        self,
        smart_layout_rule_id: uuid.UUID,
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
                TableCombination.smart_layout_rule_id
                == smart_layout_rule_id,
                TableCombination.restaurant_id
                == restaurant_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_smart_layout_key(
        self,
        smart_layout_key: str,
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
                TableCombination.smart_layout_key
                == smart_layout_key,
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
        locked_combination = await self.get_by_id_for_update(
            combination_id=combination.id,
            restaurant_id=combination.restaurant_id,
        )

        if locked_combination is None:
            raise ValueError("Table combination no longer exists.")

        combination = locked_combination

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
        # Serialize membership changes with Gap Recovery Apply.
        # Reload authoritative members after acquiring the row lock.
        locked_combination = await self.get_by_id_for_update(
            combination_id=combination.id,
            restaurant_id=combination.restaurant_id,
        )

        if locked_combination is None:
            raise ValueError(
                "Table combination no longer exists."
            )

        combination = locked_combination
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
        locked_combination = await self.get_by_id_for_update(
            combination_id=combination.id,
            restaurant_id=combination.restaurant_id,
        )

        if locked_combination is None:
            raise ValueError("Table combination no longer exists.")

        combination = locked_combination

        await self.db.delete(combination)
        await self.db.flush()