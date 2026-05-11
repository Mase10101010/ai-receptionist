"""REST endpoints for managing reservations."""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import ReservationServiceDep
from app.models.reservation import ReservationStatus
from app.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
    ReservationUpdate,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reservation",
)
async def create_reservation(
    payload: ReservationCreate, service: ReservationServiceDep
) -> ReservationResponse:
    """Create a reservation. Validates time, party size, and capacity."""
    reservation = await service.create_reservation(payload)
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

    return [
        ReservationResponse.model_validate(r)
        for r in reservations
    ]


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get a single reservation",
)
async def get_reservation(
    reservation_id: uuid.UUID, service: ReservationServiceDep
) -> ReservationResponse:
    """Look up a reservation by id. 404s if not found."""
    reservation = await service.get_reservation(reservation_id)
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
) -> ReservationResponse:
    """Partially update a reservation. Re-validates if time/party_size change."""
    reservation = await service.update_reservation(reservation_id, payload)
    return ReservationResponse.model_validate(reservation)


@router.delete(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Cancel a reservation",
)
async def cancel_reservation(
    reservation_id: uuid.UUID, service: ReservationServiceDep
) -> ReservationResponse:
    """Soft-cancel a reservation (sets status=cancelled, doesn't delete row)."""
    reservation = await service.cancel_reservation(reservation_id)
    return ReservationResponse.model_validate(reservation)
