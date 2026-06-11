import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    CurrentUserDep, 
    ActiveRestaurantByIdDep,
)
from app.db.session import get_db
from app.models.user import User
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantResponse,
    RestaurantUpdate,
)
from app.repositories.user_repository import UserRepository
from app.services.restaurant_service import RestaurantService
from app.services.email_service import EmailService

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


def get_restaurant_service(
    db: AsyncSession = Depends(get_db),
) -> RestaurantService:
    repository = RestaurantRepository(db)
    user_repository = UserRepository(db)
    return RestaurantService(
        repository=repository,
        email_service=EmailService(),
        user_repository=user_repository,
    )


@router.post(
    "",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a restaurant",
)
async def create_restaurant(
    payload: RestaurantCreate,
    current_user: CurrentUserDep,
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantResponse:
    restaurant = await service.create_restaurant(
        payload=payload,
        owner_id=current_user.id,
    )

    await service.repository.db.commit()

    return RestaurantResponse.model_validate(restaurant)


@router.get(
    "",
    response_model=list[RestaurantResponse],
    summary="List restaurants",
)
async def list_restaurants(
    current_user: CurrentUserDep,
    service: RestaurantService = Depends(get_restaurant_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[RestaurantResponse]:
    restaurants = await service.list_restaurants(
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    return [RestaurantResponse.model_validate(r) for r in restaurants]

@router.get(
    "/public/{restaurant_slug}",
    response_model=RestaurantResponse,
    summary="Get public restaurant details",
)
async def get_public_restaurant(
    restaurant_slug: str,
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantResponse:
    restaurant = await service.repository.get_by_slug(restaurant_slug)

    if restaurant is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Restaurant '{restaurant_slug}' not found")

    return RestaurantResponse.model_validate(restaurant)


@router.get(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Get a restaurant",
)
async def get_restaurant(
    restaurant_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantResponse:
    restaurant = await service.get_restaurant(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
    )

    return RestaurantResponse.model_validate(restaurant)


@router.patch(
    "/{restaurant_id}",
    response_model=RestaurantResponse,
    summary="Update a restaurant",
)
async def update_restaurant(
    restaurant_id: uuid.UUID,
    payload: RestaurantUpdate,
    current_user: CurrentUserDep,
    active_restaurant: ActiveRestaurantByIdDep,
    service: RestaurantService = Depends(get_restaurant_service),
) -> RestaurantResponse:
    restaurant = await service.update_restaurant(
        restaurant_id=restaurant_id,
        owner_id=current_user.id,
        payload=payload,
    )

    await service.repository.db.commit()

    return RestaurantResponse.model_validate(restaurant)