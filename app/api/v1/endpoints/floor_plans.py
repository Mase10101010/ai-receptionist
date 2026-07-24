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
from app.schemas.floor_plan import (
    FloorPlanCreate,
    FloorPlanResponse,
    FloorPlanUpdate,
)
from app.services.floor_plan_service import FloorPlanService


router = APIRouter(
    prefix=(
        "/restaurants/{restaurant_id}"
        "/service-areas/{area_id}"
        "/floor-plans"
    ),
    tags=["floor plans"],
)


def get_floor_plan_service(
    db: AsyncSession = Depends(get_db),
) -> FloorPlanService:
    return FloorPlanService(
        repository=FloorPlanRepository(db),
        service_area_repository=ServiceAreaRepository(db),
        restaurant_repository=RestaurantRepository(db),
    )


@router.get(
    "",
    response_model=list[FloorPlanResponse],
)
async def list_floor_plans(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: FloorPlanService = Depends(
        get_floor_plan_service,
    ),
) -> list[FloorPlanResponse]:
    floor_plans = await service.list_floor_plans(
        restaurant_id=restaurant_id,
        area_id=area_id,
        owner_id=current_user.id,
    )

    return [
        FloorPlanResponse.model_validate(floor_plan)
        for floor_plan in floor_plans
    ]


@router.post(
    "",
    response_model=FloorPlanResponse,
    status_code=201,
)
async def create_floor_plan(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    payload: FloorPlanCreate,
    current_user: CurrentUserDep,
    service: FloorPlanService = Depends(
        get_floor_plan_service,
    ),
) -> FloorPlanResponse:
    floor_plan = await service.create_floor_plan(
        restaurant_id=restaurant_id,
        area_id=area_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return FloorPlanResponse.model_validate(floor_plan)


@router.patch(
    "/{floor_plan_id}",
    response_model=FloorPlanResponse,
)
async def update_floor_plan(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    payload: FloorPlanUpdate,
    current_user: CurrentUserDep,
    service: FloorPlanService = Depends(
        get_floor_plan_service,
    ),
) -> FloorPlanResponse:
    floor_plan = await service.update_floor_plan(
        restaurant_id=restaurant_id,
        area_id=area_id,
        floor_plan_id=floor_plan_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return FloorPlanResponse.model_validate(floor_plan)


@router.post(
    "/{floor_plan_id}/deactivate",
    response_model=FloorPlanResponse,
)
async def deactivate_floor_plan(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: FloorPlanService = Depends(
        get_floor_plan_service,
    ),
) -> FloorPlanResponse:
    floor_plan = await service.deactivate_floor_plan(
        restaurant_id=restaurant_id,
        area_id=area_id,
        floor_plan_id=floor_plan_id,
        owner_id=current_user.id,
    )

    await service.repository.db.commit()

    return FloorPlanResponse.model_validate(floor_plan)