"""REST endpoints for managing reservations."""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUserDep, ReservationServiceDep
from app.db.session import get_db
from app.models.reservation import ReservationStatus
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
    ReservationUpdate,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


async def get_current_user_restaurant_ids(
    current_user: CurrentUserDep,
    db: AsyncSession = Depends(get_db),
) -> list[uuid.UUID]:
    restaurant_repo = RestaurantRepository(db)
    restaurants = await restaurant_repo.list_by_owner(current_user.id)

    return [restaurant.id for restaurant in restaurants]


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reservation",
)
async def create_reservation(
    payload: ReservationCreate,
    current_user_restaurant_ids: list[uuid.UUID] = Depends(
        get_current_user_restaurant_ids
    ),
    service: ReservationServiceDep = None,
) -> ReservationResponse:
    if not current_user_restaurant_ids:
        raise ValueError("No restaurant workspace found for this user")

    if payload.restaurant_id is None:
        payload.restaurant_id = current_user_restaurant_ids[0]

    if payload.restaurant_id not in current_user_restaurant_ids:
        raise ValueError("Restaurant does not belong to current user")

    reservation = await service.create_reservation(payload)
    await service.repository.db.commit()

    return ReservationResponse.model_validate(reservation)


@router.get(
    "",
    response_model=list[ReservationResponse],
    summary="List reservations",
)
async def list_reservations(
    service: ReservationServiceDep,
    current_user_restaurant_ids: list[uuid.UUID] = Depends(
        get_current_user_restaurant_ids
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status_filter: ReservationStatus | None = Query(None, alias="status"),
) -> list[ReservationResponse]:
    items = await service.list_reservations_for_restaurants(
        restaurant_ids=current_user_restaurant_ids,
        skip=skip,
        limit=limit,
        status=status_filter,
    )

    return [ReservationResponse.model_validate(r) for r in items]


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get a single reservation",
)
async def get_reservation(
    reservation_id: uuid.UUID,
    service: ReservationServiceDep,
    current_user_restaurant_ids: list[uuid.UUID] = Depends(
        get_current_user_restaurant_ids
    ),
) -> ReservationResponse:
    reservation = await service.get_reservation_for_restaurants(
        reservation_id=reservation_id,
        restaurant_ids=current_user_restaurant_ids,
    )

    return ReservationResponse.model_validate(reservation)


@router.patch(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Update a reservation",
)
async def update_reservation(
    reservation_id: uuid.UUID,
    payload: ReservationUpdate,
    service: ReservationServiceDep,
    current_user_restaurant_ids: list[uuid.UUID] = Depends(
        get_current_user_restaurant_ids
    ),
) -> ReservationResponse:
    reservation = await service.update_reservation_for_restaurants(
        reservation_id=reservation_id,
        restaurant_ids=current_user_restaurant_ids,
        payload=payload,
    )

    await service.repository.db.commit()

    return ReservationResponse.model_validate(reservation)


@router.delete(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Cancel a reservation",
)
async def cancel_reservation(
    reservation_id: uuid.UUID,
    service: ReservationServiceDep,
    current_user_restaurant_ids: list[uuid.UUID] = Depends(
        get_current_user_restaurant_ids
    ),
) -> ReservationResponse:
    reservation = await service.cancel_reservation_for_restaurants(
        reservation_id=reservation_id,
        restaurant_ids=current_user_restaurant_ids,
    )

    await service.repository.db.commit()

    return ReservationResponse.model_validate(reservation)
