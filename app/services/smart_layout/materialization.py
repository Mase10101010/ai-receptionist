from __future__ import annotations

from dataclasses import dataclass

from app.models.table_combination import (
    TableCombination,
)
from app.models.table_combination_rule import (
    TableCombinationRule,
    TableCombinationRuleStatus,
)
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)


@dataclass(frozen=True)
class MaterializationResult:
    created: bool
    preserved: bool
    deleted: bool
    skipped: bool
    combination: TableCombination | None


class SmartLayoutMaterializationService:
    def __init__(
        self,
        combination_repository: TableCombinationRepository,
    ) -> None:
        self.combination_repository = (
            combination_repository
        )

    async def materialize_rule(
        self,
        rule: TableCombinationRule,
    ) -> MaterializationResult:
        existing = (
            await self.combination_repository
            .get_by_smart_layout_rule_id(
                smart_layout_rule_id=rule.id,
                restaurant_id=rule.restaurant_id,
            )
        )

        if (
            rule.status
            == TableCombinationRuleStatus.BLOCKED
        ):
            if existing is not None:
                await self.combination_repository.delete(
                    existing
                )

                return MaterializationResult(
                    created=False,
                    preserved=False,
                    deleted=True,
                    skipped=False,
                    combination=None,
                )

            return MaterializationResult(
                created=False,
                preserved=False,
                deleted=False,
                skipped=True,
                combination=None,
            )

        if existing is not None:
            return MaterializationResult(
                created=False,
                preserved=True,
                deleted=False,
                skipped=False,
                combination=existing,
            )

        members = sorted(
            rule.members,
            key=lambda member: member.sort_order,
        )

        if len(members) < 2:
            raise ValueError(
                "A Smart Layout rule requires at least "
                "two tables before materialization"
            )

        if any(
            member.table is None
            for member in members
        ):
            raise ValueError(
                "Smart Layout rule contains a missing table"
            )

        max_capacity = sum(
            member.table.seats
            for member in members
        )

        combination = TableCombination(
            restaurant_id=rule.restaurant_id,
            service_area_id=rule.service_area_id,
            smart_layout_rule_id=rule.id,
            name=f"Smart Layout {rule.id}",
            min_capacity=1,
            max_capacity=max_capacity,
            setup_minutes=0,
            is_active=True,
        )

        combination = (
            await self.combination_repository.create(
                combination
            )
        )

        combination = (
            await self.combination_repository.replace_members(
                combination=combination,
                table_ids=[
                    member.table_id
                    for member in members
                ],
            )
        )

        return MaterializationResult(
            created=True,
            preserved=False,
            deleted=False,
            skipped=False,
            combination=combination,
        )

    async def dematerialize_rule(
        self,
        rule: TableCombinationRule,
    ) -> bool:
        existing = (
            await self.combination_repository
            .get_by_smart_layout_rule_id(
                smart_layout_rule_id=rule.id,
                restaurant_id=rule.restaurant_id,
            )
        )

        if existing is None:
            return False

        await self.combination_repository.delete(
            existing
        )

        return True