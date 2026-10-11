"""Business rules for environmental floor-plan features."""

import math
import uuid

from fastapi import HTTPException, status

from app.core.exceptions import NotFoundError
from app.models.floor_feature import FloorFeature
from app.repositories.floor_feature_repository import FloorFeatureRepository
from app.repositories.floor_plan_repository import FloorPlanRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.service_area_repository import ServiceAreaRepository
from app.schemas.floor_feature import FloorFeatureCreate, FloorFeatureUpdate


class FloorFeatureService:
    def __init__(
        self,
        repository: FloorFeatureRepository,
        floor_plan_repository: FloorPlanRepository,
        service_area_repository: ServiceAreaRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.repository = repository
        self.floor_plan_repository = floor_plan_repository
        self.service_area_repository = service_area_repository
        self.restaurant_repository = restaurant_repository

    async def _get_owned_floor_plan(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ):
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )
        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        if restaurant.subscription_status not in {
            "active", "trialing", "lifetime"
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription or trial required",
            )

        area = await self.service_area_repository.get_by_id(area_id)
        if area is None or area.restaurant_id != restaurant_id:
            raise NotFoundError("Service area not found")

        floor_plan = await self.floor_plan_repository.get_by_id(floor_plan_id)
        if floor_plan is None or floor_plan.service_area_id != area_id:
            raise NotFoundError("Floor plan not found")

        return floor_plan

    @staticmethod
    def _validate_geometry(data: dict, floor_plan) -> None:
        x = data["x"]
        y = data["y"]
        width = data["width"]
        height = data["height"]
        rotation = data["rotation"]

        angle = math.radians(rotation)
        bounding_width = (
            abs(width * math.cos(angle))
            + abs(height * math.sin(angle))
        )
        bounding_height = (
            abs(width * math.sin(angle))
            + abs(height * math.cos(angle))
        )

        center_x = x + width / 2
        center_y = y + height / 2
        epsilon = 1e-7

        if (
            center_x - bounding_width / 2 < -epsilon
            or center_y - bounding_height / 2 < -epsilon
            or center_x + bounding_width / 2 > floor_plan.width + epsilon
            or center_y + bounding_height / 2 > floor_plan.height + epsilon
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Feature geometry exceeds floor plan boundaries",
            )

    async def list_features(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> list[FloorFeature]:
        await self._get_owned_floor_plan(
            restaurant_id, area_id, floor_plan_id, owner_id
        )
        return await self.repository.list_by_floor_plan(floor_plan_id)

    async def get_feature(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        feature_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> FloorFeature:
        await self._get_owned_floor_plan(
            restaurant_id, area_id, floor_plan_id, owner_id
        )

        feature = await self.repository.get_by_id(
            feature_id, floor_plan_id
        )
        if feature is None:
            raise NotFoundError("Floor feature not found")

        return feature

    async def create_feature(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: FloorFeatureCreate,
    ) -> FloorFeature:
        floor_plan = await self._get_owned_floor_plan(
            restaurant_id, area_id, floor_plan_id, owner_id
        )
        data = payload.model_dump()
        self._validate_geometry(data, floor_plan)

        feature = FloorFeature(floor_plan_id=floor_plan_id, **data)
        return await self.repository.create(feature)

    async def update_feature(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        feature_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: FloorFeatureUpdate,
    ) -> FloorFeature:
        floor_plan = await self._get_owned_floor_plan(
            restaurant_id, area_id, floor_plan_id, owner_id
        )
        feature = await self.repository.get_by_id(
            feature_id, floor_plan_id
        )
        if feature is None:
            raise NotFoundError("Floor feature not found")

        updates = payload.model_dump(exclude_unset=True)

        if "feature_type" in updates and updates["feature_type"] is None:
            raise HTTPException(
                status_code=422,
                detail="Feature type cannot be null",
            )

        geometry = {
            key: updates.get(key, getattr(feature, key))
            for key in ("x", "y", "width", "height", "rotation")
        }
        if any(value is None for value in geometry.values()):
            raise HTTPException(
                status_code=422,
                detail="Feature geometry cannot be null",
            )

        self._validate_geometry(geometry, floor_plan)
        return await self.repository.update(feature, updates)

    async def delete_feature(
        self,
        restaurant_id: uuid.UUID,
        area_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        feature_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        await self._get_owned_floor_plan(
            restaurant_id, area_id, floor_plan_id, owner_id
        )
        feature = await self.repository.get_by_id(
            feature_id, floor_plan_id
        )
        if feature is None:
            raise NotFoundError("Floor feature not found")

        await self.repository.delete(feature)
