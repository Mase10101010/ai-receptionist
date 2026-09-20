import uuid

from app.core.exceptions import NotFoundError
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.repositories.table_repository import TableRepository
from app.schemas.table_placement import TablePlacementUpdate
from app.services.smart_layout.service import SmartLayoutService


class TablePlacementService:
    def __init__(
        self,
        placement_repository: TablePlacementRepository,
        table_repository: TableRepository,
        floor_plan_repository: FloorPlanRepository,
        restaurant_repository: RestaurantRepository,
        smart_layout_service: SmartLayoutService | None = None,
    ) -> None:
        self.placement_repository = placement_repository
        self.table_repository = table_repository
        self.floor_plan_repository = floor_plan_repository
        self.restaurant_repository = restaurant_repository
        self.smart_layout_service = smart_layout_service

    async def update_placement(
        self,
        restaurant_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
        table_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: TablePlacementUpdate,
    ):
        restaurant = (
            await self.restaurant_repository.get_by_id_for_owner(
                restaurant_id=restaurant_id,
                owner_id=owner_id,
            )
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        floor_plan = await self.floor_plan_repository.get_by_id(
            floor_plan_id,
        )

        if (
            floor_plan is None
            or floor_plan.service_area.restaurant_id != restaurant_id
        ):
            raise NotFoundError("Floor plan not found")

        table = await self.table_repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None:
            raise NotFoundError("Table not found")

        placement = await self.placement_repository.get(
            floor_plan_id=floor_plan_id,
            table_id=table_id,
        )

        if placement is None:
            raise NotFoundError("Table placement not found")

        updates = payload.model_dump(exclude_unset=True)

        if not updates:
            return placement

        placement = await self.placement_repository.update(
            placement,
            updates,
        )

        geometry_fields = {
            "x",
            "y",
            "width",
            "height",
            "rotation",
            "is_visible",
        }

        geometry_changed = any(
            field in updates
            for field in geometry_fields
        )

        if (
            geometry_changed
            and self.smart_layout_service is not None
        ):
            await self.smart_layout_service.analyze_floor_plan(
                restaurant_id=restaurant_id,
                service_area_id=floor_plan.service_area_id,
                floor_plan_id=floor_plan_id,
            )

        return placement