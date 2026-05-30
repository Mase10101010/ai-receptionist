import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.table import TableCreate, TableResponse, TableUpdate
from app.services.table_service import TableService

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/tables",
    tags=["tables"],
)


def get_table_service(
    db: AsyncSession = Depends(get_db),
) -> TableService:
    return TableService(
        repository=TableRepository(db),
        restaurant_repository=RestaurantRepository(db),
    )


@router.get("", response_model=list[TableResponse])
async def list_tables(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TableService = Depends(get_table_service),
) -> list[TableResponse]:
    tables = await service.list_tables(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
    )

    return [TableResponse.model_validate(table) for table in tables]


@router.post("", response_model=TableResponse)
async def create_table(
    restaurant_id: uuid.UUID,
    payload: TableCreate,
    current_user: CurrentUserDep,
    service: TableService = Depends(get_table_service),
) -> TableResponse:
    table = await service.create_table(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return TableResponse.model_validate(table)


@router.patch("/{table_id}", response_model=TableResponse)
async def update_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    payload: TableUpdate,
    current_user: CurrentUserDep,
    service: TableService = Depends(get_table_service),
) -> TableResponse:
    table = await service.update_table(
        restaurant_id=restaurant_id,
        table_id=table_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return TableResponse.model_validate(table)


@router.delete("/{table_id}", status_code=204)
async def delete_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TableService = Depends(get_table_service),
) -> None:
    await service.delete_table(
        restaurant_id=restaurant_id,
        table_id=table_id,
        owner_id=current_user.id,
    )

    await service.repository.db.commit()