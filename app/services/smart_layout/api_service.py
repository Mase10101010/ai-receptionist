from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.core.exceptions import NotFoundError
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.services.smart_layout.service import (
    SmartLayoutAnalysisResult,
    SmartLayoutService,
)

from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.models.table_combination_rule import (
    TableCombinationRule,
    TableCombinationRuleStatus,
)


class SmartLayoutApiService:
    def __init__(
        self,
        smart_layout_service: SmartLayoutService,
        restaurant_repository: RestaurantRepository,
        service_area_repository: ServiceAreaRepository,
        floor_plan_repository: FloorPlanRepository,
        rule_repository: TableCombinationRuleRepository,
    ) -> None:
        self.smart_layout_service = smart_layout_service
        self.restaurant_repository = restaurant_repository
        self.service_area_repository = service_area_repository
        self.floor_plan_repository = floor_plan_repository
        self.rule_repository = rule_repository

    async def list_rules(
        self,
        *,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> list[TableCombinationRule]:
        await self._authorize_floor_plan(
            restaurant_id=restaurant_id,
            area_id=area_id,
            floor_plan_id=floor_plan_id,
            owner_id=owner_id,
        )

        return await self.rule_repository.list_by_floor_plan(
            floor_plan_id=floor_plan_id,
        )

    def _ensure_active_subscription(
        self,
        restaurant,
    ) -> None:
        if restaurant.subscription_status not in {
            "active",
            "trialing",
            "lifetime",
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription or trial required",
            )

    async def _authorize_floor_plan(
        self,
        *,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        restaurant = (
            await self.restaurant_repository
            .get_by_id_for_owner(
                restaurant_id=restaurant_id,
                owner_id=owner_id,
            )
        )

        if restaurant is None:
            raise NotFoundError(
                "Restaurant not found"
            )

        self._ensure_active_subscription(
            restaurant
        )

        area = (
            await self.service_area_repository
            .get_by_id(
                area_id
            )
        )

        if (
            area is None
            or area.restaurant_id != restaurant_id
        ):
            raise NotFoundError(
                "Service area not found"
            )

        floor_plan = (
            await self.floor_plan_repository
            .get_by_id(
                floor_plan_id
            )
        )

        if (
            floor_plan is None
            or floor_plan.service_area_id != area_id
        ):
            raise NotFoundError(
                "Floor plan not found"
            )

    async def analyze_floor_plan(
        self,
        *,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> SmartLayoutAnalysisResult:
        await self._authorize_floor_plan(
            restaurant_id=restaurant_id,
            area_id=area_id,
            floor_plan_id=floor_plan_id,
            owner_id=owner_id,
        )

        return await (
            self.smart_layout_service
            .analyze_floor_plan(
                restaurant_id=restaurant_id,
                service_area_id=area_id,
                floor_plan_id=floor_plan_id,
            )
        )

    async def update_rule_status(
        self,
        *,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        rule_id: uuid.UUID,
        owner_id: uuid.UUID,
        new_status: TableCombinationRuleStatus,
    ) -> TableCombinationRule | None:
        await self._authorize_floor_plan(
            restaurant_id=restaurant_id,
            area_id=area_id,
            floor_plan_id=floor_plan_id,
            owner_id=owner_id,
        )

        rule = await self.rule_repository.get_by_id(
            rule_id=rule_id,
            restaurant_id=restaurant_id,
        )

        if (
            rule is None
            or rule.service_area_id != area_id
            or rule.floor_plan_id != floor_plan_id
        ):
            raise NotFoundError("Smart Layout rule not found")

        rule = await self.rule_repository.set_status(
            rule=rule,
            status=new_status,
        )

        await self.smart_layout_service.analyze_floor_plan(
            restaurant_id=restaurant_id,
            service_area_id=area_id,
            floor_plan_id=floor_plan_id,
        )

        return await self.rule_repository.get_by_id(
            rule_id=rule_id,
            restaurant_id=restaurant_id,
        )