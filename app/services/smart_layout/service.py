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
from app.services.smart_layout.derivation import (
    derive_table_combinations,
)
from app.services.smart_layout.derived_materialization import (
    SmartLayoutDerivedMaterializationService,
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
        derived_materialization_service: (
            SmartLayoutDerivedMaterializationService
            | None
        ) = None,
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

        # Legacy M4 materializer remains available during
        # the topology migration so existing callers do not
        # break. New Analyze execution truth is owned by the
        # derived materializer.
        self.materialization_service = (
            materialization_service
        )

        if derived_materialization_service is None:
            combination_repository = (
                materialization_service
                .combination_repository
            )

            derived_materialization_service = (
                SmartLayoutDerivedMaterializationService(
                    combination_repository=(
                        combination_repository
                    ),
                )
            )

        self.derived_materialization_service = (
            derived_materialization_service
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

        # Discovery now returns physical join edges only:
        # every discovered set contains exactly two tables.
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

        # Topology migration cleanup:
        #
        # M4 used TableCombination.smart_layout_rule_id as
        # executable identity. The topology architecture uses
        # Floor-Plan-scoped smart_layout_key instead.
        #
        # Remove any remaining legacy executable while the
        # authoritative physical rule still exists. This must
        # happen before obsolete AUTO rules can be deleted,
        # otherwise ON DELETE SET NULL could make a legacy
        # executable indistinguishable from a manual one.
        #
        # dematerialize_rule() only targets combinations linked
        # directly through smart_layout_rule_id, so manual
        # combinations and new smart_layout_key combinations
        # are outside this cleanup.
        for rule in existing_rules:
            await (
                self.materialization_service
                .dematerialize_rule(
                    rule
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

        # Reconcile current geometric join proposals into
        # persistent physical-rule memory.
        for table_set in discovered_keys:
            existing = existing_by_members.get(
                table_set
            )

            if existing is None:
                await self.rule_repository.create(
                    restaurant_id=restaurant_id,
                    service_area_id=service_area_id,
                    floor_plan_id=floor_plan_id,
                    table_ids=list(table_set),
                    status=(
                        TableCombinationRuleStatus.AUTO
                    ),
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

        # Reconcile rules no longer proposed by geometry.
        #
        # AUTO follows geometry and disappears.
        # CONFIRMED survives as manager physical truth.
        # BLOCKED survives as manager negative truth.
        for table_set, rule in (
            existing_by_members.items()
        ):
            if table_set in discovered_keys:
                continue

            if (
                rule.status
                == TableCombinationRuleStatus.AUTO
            ):
                # Defensive legacy cleanup remains safe and
                # idempotent. The migration pass above should
                # already have removed any M4 executable.
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
                preserved_confirmed_count += 1

            elif (
                rule.status
                == TableCombinationRuleStatus.BLOCKED
            ):
                preserved_blocked_count += 1

        # Reload authoritative physical-rule truth after
        # reconciliation. This includes newly-created AUTO
        # joins and persistent CONFIRMED/BLOCKED joins.
        reconciled_rules = (
            await self.rule_repository
            .list_by_floor_plan(
                floor_plan_id
            )
        )

        effective_joins = []

        for rule in reconciled_rules:
            member_ids = frozenset(
                member.table_id
                for member in rule.members
            )

            # New topology contract:
            # a physical rule is one join edge only.
            #
            # Legacy multi-table rules are deliberately
            # excluded from the new derivation pipeline.
            if len(member_ids) != 2:
                continue

            if (
                rule.status
                == TableCombinationRuleStatus.BLOCKED
            ):
                # Manager BLOCKED always overrides
                # automatic geometry.
                continue

            if rule.status in {
                TableCombinationRuleStatus.AUTO,
                TableCombinationRuleStatus.CONFIRMED,
            }:
                effective_joins.append(
                    member_ids
                )

        derived_table_sets = (
            derive_table_combinations(
                effective_joins
            )
        )

        # Materialization needs Table models for capacity
        # calculation. Placement rows already represent the
        # tables participating in this Floor Plan.
        tables_by_id = {
            placement.table_id: placement.table
            for placement in placements
            if placement.table is not None
        }

        await (
            self.derived_materialization_service
            .sync(
                restaurant_id=restaurant_id,
                service_area_id=service_area_id,
                floor_plan_id=floor_plan_id,
                derived_table_sets=(
                    derived_table_sets
                ),
                tables_by_id=tables_by_id,
            )
        )

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