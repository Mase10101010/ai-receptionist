import secrets
import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.table import Table
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.table import TableCreate, TableUpdate


class TableService:
    def __init__(
        self,
        repository: TableRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.repository = repository
        self.restaurant_repository = restaurant_repository

    async def create_table(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
        payload: TableCreate,
    ) -> Table:
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

        existing = await self.repository.get_by_number(
            restaurant_id=restaurant_id,
            table_number=payload.table_number,
        )

        if existing is not None:
            raise ConflictError("A table with this number already exists")

        table = Table(
            restaurant_id=restaurant_id,
            table_code=self._generate_table_code(),
            table_number=payload.table_number,
            seats=payload.seats,
            is_active=True,
        )

        return await self.repository.create(table)

    async def list_tables(
        self,
        restaurant_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> list[Table]:
        restaurant = await self.restaurant_repository.get_by_id_for_owner(
            restaurant_id=restaurant_id,
            owner_id=owner_id,
        )

        if restaurant is None:
            raise NotFoundError("Restaurant not found")

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

        table = await self.repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None:
            raise NotFoundError("Table not found")

        updates = payload.model_dump(exclude_unset=True)

        new_table_number = updates.get("table_number")

        if new_table_number and new_table_number != table.table_number:
            existing = await self.repository.get_by_number(
                restaurant_id=restaurant_id,
                table_number=new_table_number,
            )

            if existing is not None:
                raise ConflictError("A table with this number already exists")

        return await self.repository.update(table, updates)

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

        table = await self.repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None:
            raise NotFoundError("Table not found")

        await self.repository.delete(table)

    def _generate_table_code(self) -> str:
        return f"TBL_{secrets.token_hex(4).upper()}"