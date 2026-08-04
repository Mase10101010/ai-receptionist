import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
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
    TableCombinationMemberResponse,
    TableCombinationResponse,
    TableCombinationUpdate,
)
from app.services.table_combination_service import (
    TableCombinationService,
)


router = APIRouter(
    prefix="/restaurants/{restaurant_id}/table-combinations",
    tags=["table combinations"],
)


def get_table_combination_service(
    db: AsyncSession = Depends(get_db),
) -> TableCombinationService:
    return TableCombinationService(
        repository=TableCombinationRepository(db),
        restaurant_repository=RestaurantRepository(db),
        service_area_repository=ServiceAreaRepository(db),
        table_repository=TableRepository(db),
    )


def serialize_combination(
    combination,
) -> TableCombinationResponse:
    return TableCombinationResponse(
        id=combination.id,
        restaurant_id=combination.restaurant_id,
        service_area_id=combination.service_area_id,
        name=combination.name,
        min_capacity=combination.min_capacity,
        max_capacity=combination.max_capacity,
        setup_minutes=combination.setup_minutes,
        is_active=combination.is_active,
        members=[
            TableCombinationMemberResponse(
                table_id=member.table_id,
                table_number=member.table.table_number,
                seats=member.table.seats,
                sort_order=member.sort_order,
            )
            for member in combination.members
        ],
    )


@router.get(
    "",
    response_model=list[TableCombinationResponse],
)
async def list_table_combinations(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    service_area_id: uuid.UUID | None = Query(
        default=None,
    ),
    service: TableCombinationService = Depends(
        get_table_combination_service,
    ),
) -> list[TableCombinationResponse]:
    combinations = await service.list_combinations(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        service_area_id=service_area_id,
    )

    return [
        serialize_combination(combination)
        for combination in combinations
    ]


@router.get(
    "/{combination_id}",
    response_model=TableCombinationResponse,
)
async def get_table_combination(
    restaurant_id: uuid.UUID,
    combination_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TableCombinationService = Depends(
        get_table_combination_service,
    ),
) -> TableCombinationResponse:
    combination = await service.get_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        combination_id=combination_id,
    )

    return serialize_combination(
        combination,
    )


@router.post(
    "",
    response_model=TableCombinationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_table_combination(
    restaurant_id: uuid.UUID,
    payload: TableCombinationCreate,
    current_user: CurrentUserDep,
    service: TableCombinationService = Depends(
        get_table_combination_service,
    ),
) -> TableCombinationResponse:
    combination = await service.create_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    combination = await service.get_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        combination_id=combination.id,
    )

    return serialize_combination(
        combination,
    )


@router.patch(
    "/{combination_id}",
    response_model=TableCombinationResponse,
)
async def update_table_combination(
    restaurant_id: uuid.UUID,
    combination_id: uuid.UUID,
    payload: TableCombinationUpdate,
    current_user: CurrentUserDep,
    service: TableCombinationService = Depends(
        get_table_combination_service,
    ),
) -> TableCombinationResponse:
    combination = await service.update_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        combination_id=combination_id,
        payload=payload,
    )

    await service.repository.db.commit()

    combination = await service.get_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        combination_id=combination.id,
    )

    return serialize_combination(
        combination,
    )


@router.delete(
    "/{combination_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_table_combination(
    restaurant_id: uuid.UUID,
    combination_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TableCombinationService = Depends(
        get_table_combination_service,
    ),
) -> None:
    await service.delete_combination(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        combination_id=combination_id,
    )

    await service.repository.db.commit()