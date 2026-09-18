import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.table_combination_rule import (
    TableCombinationRule,
    TableCombinationRuleMember,
    TableCombinationRuleStatus,
    build_table_combination_member_key,
)



class TableCombinationRuleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(
        self,
        rule_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> TableCombinationRule | None:
        result = await self.db.execute(
            select(TableCombinationRule)
            .where(
                TableCombinationRule.id == rule_id,
                TableCombinationRule.restaurant_id
                == restaurant_id,
            )
            .options(
                selectinload(
                    TableCombinationRule.members
                ).selectinload(
                    TableCombinationRuleMember.table
                )
            )
        )

        return result.scalar_one_or_none()

    async def get_by_member_set(
        self,
        floor_plan_id: uuid.UUID,
        table_ids: list[uuid.UUID],
    ) -> TableCombinationRule | None:
        member_key = build_table_combination_member_key(
            table_ids
        )

        result = await self.db.execute(
            select(TableCombinationRule)
            .where(
                TableCombinationRule.floor_plan_id
                == floor_plan_id,
                TableCombinationRule.member_key
                == member_key,
            )
            .options(
                selectinload(
                    TableCombinationRule.members
                ).selectinload(
                    TableCombinationRuleMember.table
                )
            )
        )

        return result.scalar_one_or_none()

    async def list_by_floor_plan(
        self,
        floor_plan_id: uuid.UUID,
    ) -> list[TableCombinationRule]:
        result = await self.db.execute(
            select(TableCombinationRule)
            .where(
                TableCombinationRule.floor_plan_id
                == floor_plan_id,
            )
            .options(
                selectinload(
                    TableCombinationRule.members
                ).selectinload(
                    TableCombinationRuleMember.table
                )
            )
            .order_by(
                TableCombinationRule.created_at,
                TableCombinationRule.id,
            )
        )

        return list(
            result.scalars().unique().all()
        )

    async def create(
        self,
        *,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        table_ids: list[uuid.UUID],
        status: TableCombinationRuleStatus = (
            TableCombinationRuleStatus.AUTO
        ),
    ) -> TableCombinationRule:
        member_key = build_table_combination_member_key(
            table_ids
        )

        canonical_table_ids = sorted(
            set(table_ids),
            key=str,
        )

        rule = TableCombinationRule(
            restaurant_id=restaurant_id,
            service_area_id=service_area_id,
            floor_plan_id=floor_plan_id,
            member_key=member_key,
            status=status,
            members=[
                TableCombinationRuleMember(
                    table_id=table_id,
                    sort_order=index,
                )
                for index, table_id in enumerate(
                    canonical_table_ids
                )
            ],
        )

        self.db.add(rule)
        await self.db.flush()

        return await self.get_by_id(
            rule_id=rule.id,
            restaurant_id=restaurant_id,
        )

    async def set_status(
        self,
        rule: TableCombinationRule,
        status: TableCombinationRuleStatus,
    ) -> TableCombinationRule:
        rule.status = status

        await self.db.flush()

        return await self.get_by_id(
            rule_id=rule.id,
            restaurant_id=rule.restaurant_id,
        )

    async def delete(
        self,
        rule: TableCombinationRule,
    ) -> None:
        await self.db.delete(rule)
        await self.db.flush()