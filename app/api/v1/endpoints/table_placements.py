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
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.repositories.table_combination_rule_repository import (
    TableCombinationRuleRepository,
)
from app.repositories.table_placement_repository import (
    TablePlacementRepository,
)
from app.repositories.table_repository import TableRepository
from app.schemas.table_placement import (
    TablePlacementResponse,
    TablePlacementUpdate,
)
from app.services.smart_layout.materialization import (
    SmartLayoutMaterializationService,
)
from app.services.smart_layout.service import (
    SmartLayoutService,
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
    placement_repository = TablePlacementRepository(db)
    floor_plan_repository = FloorPlanRepository(db)

    materialization_service = SmartLayoutMaterializationService(
        combination_repository=TableCombinationRepository(db),
    )

    smart_layout_service = SmartLayoutService(
        placement_repository=placement_repository,
        rule_repository=TableCombinationRuleRepository(db),
        floor_plan_repository=floor_plan_repository,
        service_area_repository=ServiceAreaRepository(db),
        materialization_service=materialization_service,
    )

    return TablePlacementService(
        placement_repository=placement_repository,
        table_repository=TableRepository(db),
        floor_plan_repository=floor_plan_repository,
        restaurant_repository=RestaurantRepository(db),
        smart_layout_service=smart_layout_service,
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