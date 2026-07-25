import uuid

from fastapi import HTTPException, status

from app.core.exceptions import ConflictError, NotFoundError
from app.models.floor_plan import FloorPlan
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)

from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.schemas.floor_plan import (
    FloorPlanCreate,
    FloorPlanUpdate,
)


class FloorPlanService:
    def __init__(
        self,
        repository: FloorPlanRepository,
        placement_repository: TablePlacementRepository,
        service_area_repository: ServiceAreaRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.repository = repository
        self.placement_repository = placement_repository
        self.service_area_repository = service_area_repository
        self.restaurant_repository = restaurant_repository

    def _ensure_active_subscription(self, restaurant) -> None:
        if restaurant.subscription_status not in {
            "active",
            "trialing",
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription or trial required",
            )

    async def _get_owned_restaurant(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
    ):
        restaurant = (
            await self.restaurant_repository.get_by_id_for_owner(
                restaurant_id=restaurant_id,
                owner_id=owner_id,
            )
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        self._ensure_active_subscription(restaurant)

        return restaurant

    async def _get_area_for_restaurant(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
    ):
        area = await self.service_area_repository.get_by_id(
            area_id,
        )

        if (
            area is None
            or area.restaurant_id != restaurant_id
        ):
            raise NotFoundError("Service area not found")

        return area

    async def _get_floor_plan_for_area(
        self,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
    ) -> FloorPlan:
        floor_plan = await self.repository.get_by_id(
            floor_plan_id,
        )

        if (
            floor_plan is None
            or floor_plan.service_area_id != area_id
        ):
            raise NotFoundError("Floor plan not found")

        return floor_plan

    async def list_floor_plans(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> list[FloorPlan]:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        await self._get_area_for_restaurant(
            restaurant_id=restaurant_id,
            area_id=area_id,
        )

        return await self.repository.list_by_service_area(
            service_area_id=area_id,
        )

    async def create_floor_plan(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: FloorPlanCreate,
    ) -> FloorPlan:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        await self._get_area_for_restaurant(
            restaurant_id=restaurant_id,
            area_id=area_id,
        )

        normalized_name = payload.name.strip()

        existing_plans = (
            await self.repository.list_by_service_area(
                service_area_id=area_id,
            )
        )

        if any(
            plan.name.lower() == normalized_name.lower()
            for plan in existing_plans
        ):
            raise ConflictError(
                "A floor plan with this name already exists",
            )

        if payload.is_default:
            await self._clear_existing_default(
                service_area_id=area_id,
            )

        active_plans = [
            plan
            for plan in existing_plans
            if plan.is_active
        ]

        plans_with_counts = []

        for plan in active_plans:
            placement_count = (
                await self.placement_repository.count_by_floor_plan(
                    plan.id,
                )
            )

            plans_with_counts.append(
                (plan, placement_count),
            )

        default_with_tables = next(
            (
                plan
                for plan, placement_count in plans_with_counts
                if plan.is_default and placement_count > 0
            ),
            None,
        )

        if default_with_tables is not None:
            source_floor_plan = default_with_tables
        else:
            source_floor_plan = next(
                (
                    plan
                    for plan, placement_count in sorted(
                        plans_with_counts,
                        key=lambda item: item[1],
                        reverse=True,
                    )
                    if placement_count > 0
                ),
                None,
            )
        
        floor_plan = FloorPlan(
            service_area_id=area_id,
            name=normalized_name,
            width=payload.width,
            height=payload.height,
            sort_order=payload.sort_order,
            is_default=payload.is_default,
            is_active=True,
        )

        floor_plan = await self.repository.create(floor_plan)

        if source_floor_plan is not None:
            await self.placement_repository.copy_floor_plan(
                source_floor_plan_id=source_floor_plan.id,
                target_floor_plan_id=floor_plan.id,
            )

        return floor_plan

    async def update_floor_plan(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: FloorPlanUpdate,
    ) -> FloorPlan:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        await self._get_area_for_restaurant(
            restaurant_id=restaurant_id,
            area_id=area_id,
        )

        floor_plan = await self._get_floor_plan_for_area(
            area_id=area_id,
            floor_plan_id=floor_plan_id,
        )

        updates = payload.model_dump(exclude_unset=True)

        if "name" in updates:
            normalized_name = updates["name"].strip()

            existing_plans = (
                await self.repository.list_by_service_area(
                    service_area_id=area_id,
                )
            )

            duplicate = any(
                plan.id != floor_plan.id
                and plan.name.lower()
                == normalized_name.lower()
                for plan in existing_plans
            )

            if duplicate:
                raise ConflictError(
                    "A floor plan with this name already exists",
                )

            updates["name"] = normalized_name

        if updates.get("is_default") is True:
            await self._clear_existing_default(
                service_area_id=area_id,
                excluded_floor_plan_id=floor_plan.id,
            )

        if (
            updates.get("is_active") is False
            and floor_plan.is_default
        ):
            raise ConflictError(
                "The default floor plan cannot be deactivated",
            )

        return await self.repository.update(
            floor_plan=floor_plan,
            fields=updates,
        )

    async def deactivate_floor_plan(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> FloorPlan:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        await self._get_area_for_restaurant(
            restaurant_id=restaurant_id,
            area_id=area_id,
        )

        floor_plan = await self._get_floor_plan_for_area(
            area_id=area_id,
            floor_plan_id=floor_plan_id,
        )

        if floor_plan.is_default:
            raise ConflictError(
                "The default floor plan cannot be deactivated",
            )

        return await self.repository.update(
            floor_plan=floor_plan,
            fields={"is_active": False},
        )

    async def _clear_existing_default(
        self,
        service_area_id: uuid.UUID,
        excluded_floor_plan_id: uuid.UUID | None = None,
    ) -> None:
        floor_plans = (
            await self.repository.list_by_service_area(
                service_area_id=service_area_id,
            )
        )

        for floor_plan in floor_plans:
            if (
                floor_plan.is_default
                and floor_plan.id
                != excluded_floor_plan_id
            ):
                await self.repository.update(
                    floor_plan=floor_plan,
                    fields={"is_default": False},
                )