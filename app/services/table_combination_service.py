import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.table_combination import (
    TableCombination,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.repositories.table_repository import (
    TableRepository,
)
from app.schemas.table_combination import (
    TableCombinationCreate,
    TableCombinationUpdate,
)


class TableCombinationService:
    def __init__(
        self,
        repository: TableCombinationRepository,
        restaurant_repository: RestaurantRepository,
        service_area_repository: ServiceAreaRepository,
        table_repository: TableRepository,
    ) -> None:
        self.repository = repository
        self.restaurant_repository = restaurant_repository
        self.service_area_repository = service_area_repository
        self.table_repository = table_repository

    async def _get_restaurant_for_owner(
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
            raise NotFoundError(
                "Restaurant not found"
            )

        return restaurant

    async def _validate_service_area(
        self,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID,
    ):
        service_area = (
            await self.service_area_repository.get_by_id(
                service_area_id,
            )
        )

        if (
            service_area is None
            or service_area.restaurant_id
            != restaurant_id
        ):
            raise NotFoundError(
                "Service area not found"
            )

        return service_area

    async def _validate_tables(
        self,
        restaurant_id: uuid.UUID,
        service_area_id: uuid.UUID,
        table_ids: list[uuid.UUID],
    ) -> None:
        if len(table_ids) < 2:
            raise ValueError(
                "A table combination requires at least two tables."
            )

        seen: set[uuid.UUID] = set()

        for table_id in table_ids:
            if table_id in seen:
                raise ValueError(
                    "A table combination cannot contain duplicate tables."
                )

            seen.add(table_id)

            table = await self.table_repository.get_by_id(
                table_id=table_id,
                restaurant_id=restaurant_id,
            )

            if table is None:
                raise NotFoundError(
                    "One or more tables were not found"
                )

            if table.service_area_id != service_area_id:
                raise ValueError(
                    "All tables in a combination must belong to the selected service area."
                )

            if not table.is_active:
                raise ValueError(
                    "Inactive tables cannot be added to a combination."
                )

    async def create_combination(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: TableCombinationCreate,
    ) -> TableCombination:
        await self._get_restaurant_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        await self._validate_service_area(
            restaurant_id=restaurant_id,
            service_area_id=payload.service_area_id,
        )

        await self._validate_tables(
            restaurant_id=restaurant_id,
            service_area_id=payload.service_area_id,
            table_ids=payload.table_ids,
        )

        existing = await self.repository.get_by_name(
            restaurant_id=restaurant_id,
            name=payload.name,
        )

        if existing is not None:
            raise ConflictError(
                "A table combination with this name already exists"
            )

        combination = TableCombination(
            restaurant_id=restaurant_id,
            service_area_id=payload.service_area_id,
            name=payload.name,
            min_capacity=payload.min_capacity,
            max_capacity=payload.max_capacity,
            setup_minutes=payload.setup_minutes,
            is_active=True,
        )

        combination = await self.repository.create(
            combination,
        )

        combination = await self.repository.replace_members(
            combination=combination,
            table_ids=payload.table_ids,
        )

        return combination

    async def list_combinations(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        service_area_id: uuid.UUID | None = None,
    ) -> list[TableCombination]:
        await self._get_restaurant_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        return await self.repository.list_by_restaurant(
            restaurant_id=restaurant_id,
            service_area_id=service_area_id,
        )

    async def get_combination(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        combination_id: uuid.UUID,
    ) -> TableCombination:
        await self._get_restaurant_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        combination = await self.repository.get_by_id(
            combination_id=combination_id,
            restaurant_id=restaurant_id,
        )

        if combination is None:
            raise NotFoundError(
                "Table combination not found"
            )

        return combination

    async def update_combination(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        combination_id: uuid.UUID,
        payload: TableCombinationUpdate,
    ) -> TableCombination:
        combination = await self.get_combination(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
            combination_id=combination_id,
        )

        updates = payload.model_dump(
            exclude_unset=True,
        )

        new_name = updates.get("name")

        if (
            new_name
            and new_name != combination.name
        ):
            existing = await self.repository.get_by_name(
                restaurant_id=restaurant_id,
                name=new_name,
            )

            if existing is not None:
                raise ConflictError(
                    "A table combination with this name already exists"
                )

        table_ids = updates.pop(
            "table_ids",
            None,
        )

        next_min_capacity = updates.get(
            "min_capacity",
            combination.min_capacity,
        )

        next_max_capacity = updates.get(
            "max_capacity",
            combination.max_capacity,
        )

        if next_min_capacity > next_max_capacity:
            raise ValueError(
                "Minimum capacity cannot exceed maximum capacity."
            )

        if table_ids is not None:
            await self._validate_tables(
                restaurant_id=restaurant_id,
                service_area_id=combination.service_area_id,
                table_ids=table_ids,
            )

        if updates:
            combination = await self.repository.update(
                combination=combination,
                fields=updates,
            )

        if table_ids is not None:
            combination = await self.repository.replace_members(
                combination=combination,
                table_ids=table_ids,
            )

        return combination

    async def delete_combination(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        combination_id: uuid.UUID,
    ) -> None:
        combination = await self.get_combination(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
            combination_id=combination_id,
        )

        await self.repository.delete(
            combination,
        )