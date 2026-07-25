import uuid

from fastapi import APIRouter, Depends
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
from app.repositories.table_repository import TableRepository
from app.schemas.table_placement import (
    TablePlacementResponse,
    TablePlacementUpdate,
)
from app.services.table_placement_service import (
    TablePlacementService,
)


router = APIRouter(
    prefix=(
        "/restaurants/{restaurant_id}"
        "/floor-plans/{floor_plan_id}"
        "/tables/{table_id}/placement"
    ),
    tags=["table placements"],
)


def get_table_placement_service(
    db: AsyncSession = Depends(get_db),
) -> TablePlacementService:
    return TablePlacementService(
        placement_repository=TablePlacementRepository(db),
        table_repository=TableRepository(db),
        floor_plan_repository=FloorPlanRepository(db),
        restaurant_repository=RestaurantRepository(db),
    )


@router.patch(
    "",
    response_model=TablePlacementResponse,
)
async def update_table_placement(
    restaurant_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    table_id: uuid.UUID,
    payload: TablePlacementUpdate,
    current_user: CurrentUserDep,
    service: TablePlacementService = Depends(
        get_table_placement_service,
    ),
) -> TablePlacementResponse:
    placement = await service.update_placement(
        restaurant_id=restaurant_id,
        floor_plan_id=floor_plan_id,
        table_id=table_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.placement_repository.db.commit()

    return TablePlacementResponse.model_validate(
        placement,
    )