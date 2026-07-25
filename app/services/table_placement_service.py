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


class TablePlacementService:
    def __init__(
        self,
        placement_repository: TablePlacementRepository,
        table_repository: TableRepository,
        floor_plan_repository: FloorPlanRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.placement_repository = placement_repository
        self.table_repository = table_repository
        self.floor_plan_repository = floor_plan_repository
        self.restaurant_repository = restaurant_repository

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

        return await self.placement_repository.update(
            placement,
            updates,
        )