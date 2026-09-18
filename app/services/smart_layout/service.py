from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.table_combination_rule import (
    TableCombinationRuleStatus,
)
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.services.smart_layout.adjacency import (
    LayoutPlacement,
    build_adjacency_graph,
)
from app.services.smart_layout.discovery import (
    discover_connected_table_sets,
)
from app.services.smart_layout.geometry import (
    PlacementGeometry,
)
from app.services.smart_layout.materialization import (
    SmartLayoutMaterializationService,
)


@dataclass(frozen=True)
class SmartLayoutAnalysisResult:
    discovered_count: int
    created_auto_count: int
    preserved_auto_count: int
    preserved_confirmed_count: int
    preserved_blocked_count: int
    deleted_obsolete_auto_count: int


class SmartLayoutService:
    def __init__(
        self,
        placement_repository: TablePlacementRepository,
        rule_repository: TableCombinationRuleRepository,
        floor_plan_repository: FloorPlanRepository,
        service_area_repository: ServiceAreaRepository,
        materialization_service: (
            SmartLayoutMaterializationService
        ),
    ) -> None:
        self.placement_repository = (
            placement_repository
        )
        self.rule_repository = rule_repository
        self.floor_plan_repository = (
            floor_plan_repository
        )
        self.service_area_repository = (
            service_area_repository
        )
        self.materialization_service = (
            materialization_service
        )

    async def analyze_floor_plan(
        self,
        *,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
    ) -> SmartLayoutAnalysisResult:
        # Fail closed before reading or reconciling
        # any Floor Plan data.
        area = (
            await self.service_area_repository.get_by_id(
                service_area_id
            )
        )

        if (
            area is None
            or area.restaurant_id != restaurant_id
        ):
            raise ValueError(
                "Service area does not belong to restaurant"
            )

        floor_plan = (
            await self.floor_plan_repository.get_by_id(
                floor_plan_id
            )
        )

        if (
            floor_plan is None
            or floor_plan.service_area_id
            != service_area_id
        ):
            raise ValueError(
                "Floor plan does not belong to service area"
            )

        placements = (
            await self.placement_repository
            .list_by_floor_plan(
                floor_plan_id
            )
        )

        layout_placements = [
            LayoutPlacement(
                table_id=placement.table_id,
                geometry=PlacementGeometry(
                    x=placement.x,
                    y=placement.y,
                    width=placement.width,
                    height=placement.height,
                    rotation=placement.rotation,
                ),
                is_visible=placement.is_visible,
            )
            for placement in placements
        ]

        graph = build_adjacency_graph(
            layout_placements
        )

        discovered_sets = (
            discover_connected_table_sets(
                graph
            )
        )

        discovered_keys = {
            frozenset(table_ids)
            for table_ids in discovered_sets
        }

        existing_rules = (
            await self.rule_repository
            .list_by_floor_plan(
                floor_plan_id
            )
        )

        existing_by_members = {
            frozenset(
                member.table_id
                for member in rule.members
            ): rule
            for rule in existing_rules
        }

        created_auto_count = 0
        preserved_auto_count = 0
        preserved_confirmed_count = 0
        preserved_blocked_count = 0
        deleted_obsolete_auto_count = 0

        # Reconcile all currently discovered physical
        # combinations.
        for table_set in discovered_keys:
            existing = existing_by_members.get(
                table_set
            )

            if existing is None:
                created_rule = (
                    await self.rule_repository.create(
                        restaurant_id=restaurant_id,
                        service_area_id=service_area_id,
                        floor_plan_id=floor_plan_id,
                        table_ids=list(table_set),
                        status=(
                            TableCombinationRuleStatus.AUTO
                        ),
                    )
                )

                await (
                    self.materialization_service
                    .materialize_rule(
                        created_rule
                    )
                )

                created_auto_count += 1
                continue

            if (
                existing.status
                == TableCombinationRuleStatus.AUTO
            ):
                preserved_auto_count += 1

            elif (
                existing.status
                == TableCombinationRuleStatus.CONFIRMED
            ):
                preserved_confirmed_count += 1

            elif (
                existing.status
                == TableCombinationRuleStatus.BLOCKED
            ):
                preserved_blocked_count += 1

            # Synchronize executable truth with the
            # persistent physical rule.
            #
            # AUTO / CONFIRMED:
            # create or preserve TableCombination.
            #
            # BLOCKED:
            # delete existing Smart Layout
            # TableCombination, if any.
            await (
                self.materialization_service
                .materialize_rule(
                    existing
                )
            )

        # Reconcile persistent rules that are no longer
        # proposed by current geometry.
        for table_set, rule in (
            existing_by_members.items()
        ):
            if table_set in discovered_keys:
                continue

            if (
                rule.status
                == TableCombinationRuleStatus.AUTO
            ):
                # Important ordering:
                #
                # 1. remove executable Smart Layout
                #    combination
                # 2. remove AUTO rule
                #
                # This prevents ON DELETE SET NULL from
                # leaving an orphaned combination that
                # would look manual.
                await (
                    self.materialization_service
                    .dematerialize_rule(
                        rule
                    )
                )

                await self.rule_repository.delete(
                    rule
                )

                deleted_obsolete_auto_count += 1

            elif (
                rule.status
                == TableCombinationRuleStatus.CONFIRMED
            ):
                # Manager truth survives geometry
                # disappearance and remains executable.
                await (
                    self.materialization_service
                    .materialize_rule(
                        rule
                    )
                )

                preserved_confirmed_count += 1

            elif (
                rule.status
                == TableCombinationRuleStatus.BLOCKED
            ):
                # BLOCKED survives as physical-rule
                # memory but must never remain executable.
                await (
                    self.materialization_service
                    .materialize_rule(
                        rule
                    )
                )

                preserved_blocked_count += 1

        return SmartLayoutAnalysisResult(
            discovered_count=len(
                discovered_keys
            ),
            created_auto_count=created_auto_count,
            preserved_auto_count=(
                preserved_auto_count
            ),
            preserved_confirmed_count=(
                preserved_confirmed_count
            ),
            preserved_blocked_count=(
                preserved_blocked_count
            ),
            deleted_obsolete_auto_count=(
                deleted_obsolete_auto_count
            ),
        )