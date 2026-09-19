from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping

from app.models.table import Table
from app.models.table_combination import TableCombination
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)


TableSet = frozenset[uuid.UUID]


class SmartLayoutDerivedMaterializationService:
    def __init__(
        self,
        combination_repository: TableCombinationRepository,
    ):
        self.combination_repository = combination_repository

    async def sync(
        self,
        *,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        derived_table_sets: Iterable[TableSet],
        tables_by_id: Mapping[uuid.UUID, Table],
    ) -> None:
        normalized_sets = {
            frozenset(table_ids)
            for table_ids in derived_table_sets
            if len(table_ids) >= 2
        }

        desired_by_key = {
            self._build_key(
                floor_plan_id=floor_plan_id,
                table_ids=table_ids,
            ): table_ids
            for table_ids in normalized_sets
        }

        existing_combinations = (
            await self.combination_repository.list_by_restaurant(
                restaurant_id=restaurant_id,
                service_area_id=service_area_id,
                include_inactive=True,
            )
        )

        floor_plan_prefix = f"{floor_plan_id}:"

        existing_derived_by_key = {
            combination.smart_layout_key: combination
            for combination in existing_combinations
            if (
                combination.smart_layout_key is not None
                and combination.smart_layout_key.startswith(
                    floor_plan_prefix
                )
            )
        }

        for smart_layout_key, table_ids in sorted(
            desired_by_key.items(),
            key=lambda item: item[0],
        ):
            existing = existing_derived_by_key.get(
                smart_layout_key
            )

            if existing is not None:
                continue

            ordered_table_ids = sorted(
                table_ids,
                key=str,
            )

            tables = [
                tables_by_id.get(table_id)
                for table_id in ordered_table_ids
            ]

            if any(table is None for table in tables):
                continue

            combination = TableCombination(
                restaurant_id=restaurant_id,
                service_area_id=service_area_id,
                smart_layout_key=smart_layout_key,
                name=(
                    "Smart Layout Derived "
                    f"{smart_layout_key}"
                ),
                min_capacity=1,
                max_capacity=sum(
                    table.seats
                    for table in tables
                    if table is not None
                ),
                setup_minutes=0,
                is_active=True,
            )

            combination = (
                await self.combination_repository.create(
                    combination
                )
            )

            await self.combination_repository.replace_members(
                combination=combination,
                table_ids=ordered_table_ids,
            )

        desired_keys = set(desired_by_key)

        for smart_layout_key, combination in (
            existing_derived_by_key.items()
        ):
            if smart_layout_key in desired_keys:
                continue

            await self.combination_repository.delete(
                combination
            )

    @staticmethod
    def _build_key(
        *,
        floor_plan_id: uuid.UUID,
        table_ids: Iterable[uuid.UUID],
    ) -> str:
        member_key = "|".join(
            sorted(
                str(table_id)
                for table_id in table_ids
            )
        )

        return f"{floor_plan_id}:{member_key}"