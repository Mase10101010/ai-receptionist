import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.floor_plan_repository import (
    FloorPlanRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.repositories.table_repository import (
    TableRepository,
)
from app.schemas.table import (
    TableCreate,
    TableResponse,
    TableUpdate,
)
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
        placement_repository=TablePlacementRepository(db),
        restaurant_repository=RestaurantRepository(db),
        floor_plan_repository=FloorPlanRepository(db),
    )


@router.get(
    "",
    response_model=list[TableResponse],
)
async def list_tables(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    floor_plan_id: uuid.UUID = Query(...),
    service: TableService = Depends(
        get_table_service,
    ),
) -> list[TableResponse]:
    tables = await service.list_tables(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        floor_plan_id=floor_plan_id,
    )

    return [
        TableResponse.from_table_and_placement(
            table,
            placement,
        )
        for table, placement in tables
    ]


@router.post(
    "",
    response_model=TableResponse,
)
async def create_table(
    restaurant_id: uuid.UUID,
    payload: TableCreate,
    current_user: CurrentUserDep,
    service: TableService = Depends(
        get_table_service,
    ),
) -> TableResponse:
    table = await service.create_table(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        payload=payload,
    )

    placement = await service.placement_repository.get(
        floor_plan_id=payload.floor_plan_id,
        table_id=table.id,
    )

    if placement is None:
        raise RuntimeError(
            "Table was created without its placement"
        )

    await service.repository.db.commit()

    return TableResponse.from_table_and_placement(
        table,
        placement,
    )


@router.patch(
    "/{table_id}",
    response_model=TableResponse,
)
async def update_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    payload: TableUpdate,
    current_user: CurrentUserDep,
    floor_plan_id: uuid.UUID = Query(...),
    
    service: TableService = Depends(
        get_table_service,
    ),
) -> TableResponse:
    table = await service.update_table(
        restaurant_id=restaurant_id,
        table_id=table_id,
        owner_id=current_user.id,
        payload=payload,
    )

    placement = await service.placement_repository.get(
        floor_plan_id=floor_plan_id,
        table_id=table.id,
    )

    if placement is None:
        raise RuntimeError(
            "Table placement not found for the selected floor plan"
        )

    await service.repository.db.commit()

    return TableResponse.from_table_and_placement(
        table,
        placement,
    )


@router.delete(
    "/{table_id}",
    status_code=204,
)
async def delete_table(
    restaurant_id: uuid.UUID,
    table_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TableService = Depends(
        get_table_service,
    ),
) -> None:
    await service.delete_table(
        restaurant_id=restaurant_id,
        table_id=table_id,
        owner_id=current_user.id,
    )

    await service.repository.db.commit()