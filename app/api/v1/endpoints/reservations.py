import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.reservation import ReservationStatus
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
    ReservationUpdate,
)
from app.services.reservation_service import ReservationService

router = APIRouter(prefix="/reservations", tags=["reservations"])


def get_reservation_service(
    db: AsyncSession = Depends(get_db),
) -> ReservationService:
    repository = ReservationRepository(db)
    return ReservationService(repository)


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reservation",
)
async def create_reservation(
    payload: ReservationCreate,
    service: ReservationService = Depends(get_reservation_service),
) -> ReservationResponse:
    reservation = await service.create_reservation(payload)
    await service.repository.db.commit()
    return ReservationResponse.model_validate(reservation)


@router.get(
    "",
    response_model=list[ReservationResponse],
    summary="List reservations",
)
async def list_reservations(
    service: ReservationService = Depends(get_reservation_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: ReservationStatus | None = Query(default=None),
    restaurant_id: uuid.UUID | None = Query(default=None),
) -> list[ReservationResponse]:
    reservations = await service.list_reservations(
        skip=skip,
        limit=limit,
        status=status,
        restaurant_id=restaurant_id,
    )
    return [ReservationResponse.model_validate(r) for r in reservations]


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get a reservation",
)
async def get_reservation(
    reservation_id: uuid.UUID,
    service: ReservationService = Depends(get_reservation_service),
    restaurant_id: uuid.UUID | None = Query(default=None),
) -> ReservationResponse:
    reservation = await service.get_reservation(
        reservation_id=reservation_id,
        restaurant_id=restaurant_id,
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
    service: ReservationService = Depends(get_reservation_service),
) -> ReservationResponse:
    reservation = await service.update_reservation(reservation_id, payload)
    await service.repository.db.commit()
    return ReservationResponse.model_validate(reservation)


@router.delete(
    "/{reservation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reservation",
)
async def delete_reservation(
    reservation_id: uuid.UUID,
    service: ReservationService = Depends(get_reservation_service),
) -> None:
    await service.delete_reservation(reservation_id)
    await service.repository.db.commit()
