import secrets
import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.table import Table
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.repositories.table_repository import TableRepository
from app.schemas.table import TableCreate, TableUpdate
from app.repositories.floor_plan_repository import FloorPlanRepository
from app.models.table_placement import TablePlacement
from fastapi import HTTPException, status


class TableService:
    def __init__(
        self,
        repository: TableRepository,
        placement_repository: TablePlacementRepository,
        restaurant_repository: RestaurantRepository,
        floor_plan_repository: FloorPlanRepository,
    ) -> None:
        self.repository = repository
        self.placement_repository = placement_repository
        self.restaurant_repository = restaurant_repository
        self.floor_plan_repository = floor_plan_repository

    def _ensure_active_subscription(self, restaurant) -> None:
        if restaurant.subscription_status not in {"active", "trialing"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required",
            )

    async def _get_floor_plan_for_restaurant(
        self,
        restaurant_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
    ):
        floor_plan = await self.floor_plan_repository.get_by_id(
            floor_plan_id,
        )

        if (
            floor_plan is None
            or floor_plan.service_area.restaurant_id != restaurant_id
        ):
            raise NotFoundError("Floor plan not found")

        return floor_plan

    async def create_table(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: TableCreate,
    ) -> Table:
        restaurant = (
            await self.restaurant_repository.get_by_id_for_owner(
                restaurant_id=restaurant_id,
                owner_id=owner_id,
            )
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        self._ensure_active_subscription(restaurant)

        floor_plan = await self._get_floor_plan_for_restaurant(
            restaurant_id=restaurant_id,
            floor_plan_id=payload.floor_plan_id,
        )

        existing = await self.repository.get_by_number(
            restaurant_id=restaurant_id,
            table_number=payload.table_number,
        )

        if existing is not None:
            raise ConflictError(
                "A table with this number already exists",
            )

        table = Table(
            restaurant_id=restaurant_id,
            service_area_id=floor_plan.service_area_id,
            table_code=self._generate_table_code(),
            table_number=payload.table_number,
            seats=payload.seats,
            shape=payload.shape,
            is_active=True,
        )

        table = await self.repository.create(table)

        placement = TablePlacement(
            floor_plan_id=payload.floor_plan_id,
            table_id=table.id,
            x=payload.x,
            y=payload.y,
            width=payload.width,
            height=payload.height,
            rotation=payload.rotation,
            is_visible=True,
        )

        await self.placement_repository.create(
            placement,
        )

        return table

    async def list_tables(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        floor_plan_id: uuid.UUID | None = None,
    ) -> list[Table]:
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        self._ensure_active_subscription(restaurant)

        if floor_plan_id is not None:
            await self._get_floor_plan_for_restaurant(
                restaurant_id=restaurant_id,
                floor_plan_id=floor_plan_id,
            )

            return await self.repository.list_by_floor_plan(
                restaurant_id=restaurant_id,
                floor_plan_id=floor_plan_id,
            )

        return await self.repository.list_by_restaurant(
            restaurant_id=restaurant_id,
        )

    async def update_table(
        self,
        restaurant_id: uuid.UUID,
        table_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: TableUpdate,
    ) -> Table:
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")
        
        self._ensure_active_subscription(restaurant)

        table = await self.repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None:
            raise NotFoundError("Table not found")

        updates = payload.model_dump(exclude_unset=True)

        new_table_number = table_updates.get("table_number")

        if (
            new_table_number
            and new_table_number != table.table_number
        ):
            existing = await self.repository.get_by_number(
                restaurant_id=restaurant_id,
                table_number=new_table_number,
            )

            if existing is not None:
                raise ConflictError(
                    "A table with this number already exists"
                )


        if placement_updates:
            await self.placement_repository.update(
                placement,
                placement_updates,
            )

        if table_updates:
            table = await self.repository.update(
                table,
                table_updates,
            )

        return table
        
    async def delete_table(
        self,
        restaurant_id: uuid.UUID,
        table_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> None:
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")
        
        self._ensure_active_subscription(restaurant)

        table = await self.repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None:
            raise NotFoundError("Table not found")

        await self.repository.delete(table)

    def _generate_table_code(self) -> str:
        return f"TBL_{secrets.token_hex(4).upper()}"