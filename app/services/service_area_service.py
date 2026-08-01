import uuid

from fastapi import HTTPException, status

from app.core.exceptions import ConflictError, NotFoundError
from app.models.floor_plan import FloorPlan
from app.models.service_area import ServiceArea
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.schemas.service_area import (
    ServiceAreaCreate,
    ServiceAreaUpdate,
)


class ServiceAreaService:
    def __init__(
        self,
        repository: ServiceAreaRepository,
        floor_plan_repository: FloorPlanRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.repository = repository
        self.floor_plan_repository = floor_plan_repository
        self.restaurant_repository = restaurant_repository

    def _ensure_active_subscription(self, restaurant) -> None:
        if restaurant.subscription_status not in {
            "active",
            "trialing",
            "lifetime",
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required",
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

    async def list_service_areas(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> list[ServiceArea]:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        return await self.repository.list_by_restaurant(
            restaurant_id=restaurant_id,
            include_inactive=include_inactive,
        )

    async def create_service_area(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: ServiceAreaCreate,
    ) -> ServiceArea:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        normalized_name = payload.name.strip()

        existing = await self.repository.get_by_name(
            restaurant_id=restaurant_id,
            name=normalized_name,
        )

        if existing is not None:
            raise ConflictError(
                "A service area with this name already exists",
            )

        area = ServiceArea(
            restaurant_id=restaurant_id,
            name=normalized_name,
            area_type=payload.area_type,
            color=payload.color,
            sort_order=payload.sort_order,
            is_active=True,
        )

        area = await self.repository.create(area)

        default_layout = FloorPlan(
            service_area_id=area.id,
            name="Default Layout",
            width=1200,
            height=800,
            sort_order=0,
            is_default=True,
            is_active=True,
        )

        await self.floor_plan_repository.create(default_layout)

        return area

    async def update_service_area(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: ServiceAreaUpdate,
    ) -> ServiceArea:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        area = await self.repository.get_by_id(area_id)

        if (
            area is None
            or area.restaurant_id != restaurant_id
        ):
            raise NotFoundError("Service area not found")

        updates = payload.model_dump(exclude_unset=True)

        if "name" in updates:
            normalized_name = updates["name"].strip()

            existing = await self.repository.get_by_name(
                restaurant_id=restaurant_id,
                name=normalized_name,
            )

            if (
                existing is not None
                and existing.id != area.id
            ):
                raise ConflictError(
                    "A service area with this name already exists",
                )

            updates["name"] = normalized_name

        return await self.repository.update(
            area=area,
            fields=updates,
        )

    async def deactivate_service_area(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> ServiceArea:
        await self._get_owned_restaurant(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        area = await self.repository.get_by_id(area_id)

        if (
            area is None
            or area.restaurant_id != restaurant_id
        ):
            raise NotFoundError("Service area not found")

        active_areas = await self.repository.list_by_restaurant(
            restaurant_id=restaurant_id,
        )

        if (
            area.is_active
            and len(active_areas) <= 1
        ):
            raise ConflictError(
                "A restaurant must have at least one active service area",
            )

        return await self.repository.update(
            area=area,
            fields={"is_active": False},
        )