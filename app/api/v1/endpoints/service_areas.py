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
from app.repositories.service_area_repository import (
    ServiceAreaRepository,
)
from app.schemas.service_area import (
    ServiceAreaCreate,
    ServiceAreaResponse,
    ServiceAreaUpdate,
)
from app.services.service_area_service import (
    ServiceAreaService,
)

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/service-areas",
    tags=["service areas"],
)


def get_service_area_service(
    db: AsyncSession = Depends(get_db),
) -> ServiceAreaService:
    return ServiceAreaService(
        repository=ServiceAreaRepository(db),
        floor_plan_repository=FloorPlanRepository(db),
        restaurant_repository=RestaurantRepository(db),
    )


@router.get(
    "",
    response_model=list[ServiceAreaResponse],
)
async def list_service_areas(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    include_inactive: bool = Query(default=False),
    service: ServiceAreaService = Depends(
        get_service_area_service,
    ),
) -> list[ServiceAreaResponse]:
    areas = await service.list_service_areas(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        include_inactive=include_inactive,
    )

    return [
        ServiceAreaResponse.model_validate(area)
        for area in areas
    ]


@router.post(
    "",
    response_model=ServiceAreaResponse,
    status_code=201,
)
async def create_service_area(
    restaurant_id: uuid.UUID,
    payload: ServiceAreaCreate,
    current_user: CurrentUserDep,
    service: ServiceAreaService = Depends(
        get_service_area_service,
    ),
) -> ServiceAreaResponse:
    area = await service.create_service_area(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return ServiceAreaResponse.model_validate(area)


@router.patch(
    "/{area_id}",
    response_model=ServiceAreaResponse,
)
async def update_service_area(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    payload: ServiceAreaUpdate,
    current_user: CurrentUserDep,
    service: ServiceAreaService = Depends(
        get_service_area_service,
    ),
) -> ServiceAreaResponse:
    area = await service.update_service_area(
        restaurant_id=restaurant_id,
        area_id=area_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return ServiceAreaResponse.model_validate(area)


@router.post(
    "/{area_id}/deactivate",
    response_model=ServiceAreaResponse,
)
async def deactivate_service_area(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ServiceAreaService = Depends(
        get_service_area_service,
    ),
) -> ServiceAreaResponse:
    area = await service.deactivate_service_area(
        restaurant_id=restaurant_id,
        area_id=area_id,
        owner_id=current_user.id,
    )

    await service.repository.db.commit()

    return ServiceAreaResponse.model_validate(area)