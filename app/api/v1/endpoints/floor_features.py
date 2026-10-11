"""REST endpoints for environmental floor-plan features."""

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep
from app.db.session import get_db
from app.repositories.floor_feature_repository import FloorFeatureRepository
from app.repositories.floor_plan_repository import FloorPlanRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.service_area_repository import ServiceAreaRepository
from app.schemas.floor_feature import (
    FloorFeatureCreate,
    FloorFeatureResponse,
    FloorFeatureUpdate,
)
from app.services.floor_feature_service import FloorFeatureService


router = APIRouter(
    prefix=(
        "/restaurants/{restaurant_id}"
        "/service-areas/{area_id}"
        "/floor-plans/{floor_plan_id}"
        "/features"
    ),
    tags=["floor features"],
)


def get_floor_feature_service(
    db: AsyncSession = Depends(get_db),
) -> FloorFeatureService:
    return FloorFeatureService(
        repository=FloorFeatureRepository(db),
        floor_plan_repository=FloorPlanRepository(db),
        service_area_repository=ServiceAreaRepository(db),
        restaurant_repository=RestaurantRepository(db),
    )


@router.get("", response_model=list[FloorFeatureResponse])
async def list_floor_features(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: FloorFeatureService = Depends(get_floor_feature_service),
) -> list[FloorFeatureResponse]:
    features = await service.list_features(
        restaurant_id, area_id, floor_plan_id, current_user.id
    )
    return [
        FloorFeatureResponse.model_validate(feature)
        for feature in features
    ]


@router.get("/{feature_id}", response_model=FloorFeatureResponse)
async def get_floor_feature(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    feature_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: FloorFeatureService = Depends(get_floor_feature_service),
) -> FloorFeatureResponse:
    feature = await service.get_feature(
        restaurant_id, area_id, floor_plan_id,
        feature_id, current_user.id
    )
    return FloorFeatureResponse.model_validate(feature)


@router.post(
    "",
    response_model=FloorFeatureResponse,
    status_code=201,
)
async def create_floor_feature(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    payload: FloorFeatureCreate,
    current_user: CurrentUserDep,
    service: FloorFeatureService = Depends(get_floor_feature_service),
) -> FloorFeatureResponse:
    feature = await service.create_feature(
        restaurant_id, area_id, floor_plan_id,
        current_user.id, payload
    )
    await service.repository.db.commit()
    return FloorFeatureResponse.model_validate(feature)


@router.patch(
    "/{feature_id}",
    response_model=FloorFeatureResponse,
)
async def update_floor_feature(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    feature_id: uuid.UUID,
    payload: FloorFeatureUpdate,
    current_user: CurrentUserDep,
    service: FloorFeatureService = Depends(get_floor_feature_service),
) -> FloorFeatureResponse:
    feature = await service.update_feature(
        restaurant_id, area_id, floor_plan_id,
        feature_id, current_user.id, payload
    )
    await service.repository.db.commit()
    return FloorFeatureResponse.model_validate(feature)


@router.delete("/{feature_id}", status_code=204)
async def delete_floor_feature(
    restaurant_id: uuid.UUID,
    area_id: uuid.UUID,
    floor_plan_id: uuid.UUID,
    feature_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: FloorFeatureService = Depends(get_floor_feature_service),
) -> Response:
    await service.delete_feature(
        restaurant_id, area_id, floor_plan_id,
        feature_id, current_user.id
    )
    await service.repository.db.commit()
    return Response(status_code=204)
