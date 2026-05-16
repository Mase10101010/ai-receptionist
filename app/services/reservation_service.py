"""
Reservation service.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.reservation import Reservation, ReservationStatus
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate

logger = get_logger(__name__)


class ReservationService:
    def __init__(
        self, 
        repository: ReservationRepository,
        restaurant_repository: RestaurantRepository,
    ) -> None:
        self.repository = repository
        self.restaurant_repository = restaurant_repository

    async def create_reservation(self, payload: ReservationCreate) -> Reservation:
        self._validate_reservation_time(payload.reservation_time)

        await self._enforce_capacity(
            reservation_time=payload.reservation_time,
            party_size=payload.party_size,
            restaurant_id=payload.restaurant_id,
        )

        reservation = Reservation(
            restaurant_id=payload.restaurant_id,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            customer_email=str(payload.customer_email)
            if payload.customer_email
            else None,
            party_size=payload.party_size,
            reservation_time=payload.reservation_time,
            duration_minutes=payload.duration_minutes,
            special_requests=payload.special_requests,
            session_id=payload.session_id,
            status=ReservationStatus.CONFIRMED,
        )

        created = await self.repository.create(reservation)

        logger.info(
            "Reservation created: id=%s restaurant_id=%s party=%d time=%s",
            created.id,
            created.restaurant_id,
            created.party_size,
            created.reservation_time.isoformat(),
        )

        return created

    async def get_reservation(
        self,
        reservation_id: uuid.UUID,
        restaurant_id: uuid.UUID | None = None,
    ) -> Reservation:
        reservation = await self.repository.get_by_id(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
        )

        if reservation is None:
            raise NotFoundError(f"Reservation {reservation_id} not found")

        return reservation

    async def get_reservation_for_restaurants(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> Reservation:
        reservation = await self.repository.get_by_id_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=restaurant_ids,
        )

        if reservation is None:
            raise NotFoundError(f"Reservation {reservation_id} not found")

        return reservation

    async def list_reservations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
        restaurant_id: uuid.UUID | None = None,
    ) -> list[Reservation]:
        return await self.repository.list_all(
            skip=skip,
            limit=limit,
            status=status,
            restaurant_id=restaurant_id,
        )

    async def list_reservations_for_restaurants(
        self,
        restaurant_ids: list[uuid.UUID],
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        return await self.repository.list_by_restaurant_ids(
            restaurant_ids=restaurant_ids,
            skip=skip,
            limit=limit,
            status=status,
        )

    async def update_reservation(
        self,
        reservation_id: uuid.UUID,
        payload: ReservationUpdate,
    ) -> Reservation:
        reservation = await self.get_reservation(reservation_id)

        updates = payload.model_dump(exclude_unset=True)

        if "customer_email" in updates and updates["customer_email"] is not None:
            updates["customer_email"] = str(updates["customer_email"])

        new_time = updates.get("reservation_time", reservation.reservation_time)
        new_party = updates.get("party_size", reservation.party_size)

        if "reservation_time" in updates:
            self._validate_reservation_time(new_time)

        if "reservation_time" in updates or "party_size" in updates:
            await self._enforce_capacity(
                reservation_time=new_time,
                party_size=new_party,
                restaurant_id=reservation.restaurant_id,
                exclude_id=reservation.id,
            )

        updated = await self.repository.update(reservation, updates)

        logger.info(
            "Reservation updated: id=%s fields=%s",
            updated.id,
            list(updates.keys()),
        )

        return updated

    async def update_reservation_for_restaurants(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
        payload: ReservationUpdate,
    ) -> Reservation:
        reservation = await self.get_reservation_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=restaurant_ids,
        )

        updates = payload.model_dump(exclude_unset=True)

        if "customer_email" in updates and updates["customer_email"] is not None:
            updates["customer_email"] = str(updates["customer_email"])

        new_time = updates.get("reservation_time", reservation.reservation_time)
        new_party = updates.get("party_size", reservation.party_size)

        if "reservation_time" in updates:
            self._validate_reservation_time(new_time)

        if "reservation_time" in updates or "party_size" in updates:
            await self._enforce_capacity(
                reservation_time=new_time,
                party_size=new_party,
                restaurant_id=reservation.restaurant_id,
                exclude_id=reservation.id,
            )

        return await self.repository.update(reservation, updates)

    async def cancel_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        reservation = await self.get_reservation(reservation_id)

        if reservation.status == ReservationStatus.CANCELLED:
            return reservation

        return await self.repository.update(
            reservation,
            {"status": ReservationStatus.CANCELLED},
        )

    async def cancel_reservation_for_restaurants(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> Reservation:
        reservation = await self.get_reservation_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=restaurant_ids,
        )

        if reservation.status == ReservationStatus.CANCELLED:
            return reservation

        return await self.repository.update(
            reservation,
            {"status": ReservationStatus.CANCELLED},
        )

    async def check_availability(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
    ) -> bool:
        try:
            self._validate_reservation_time(reservation_time)

            await self._enforce_capacity(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
            )

            return True
        except (ValidationError, ConflictError):
            return False

    def _validate_reservation_time(self, reservation_time: datetime) -> None:
        if reservation_time.tzinfo is None:
            reservation_time = reservation_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if reservation_time <= now:
            raise ValidationError("Reservation time must be in the future")

        hour = reservation_time.hour

        if hour < settings.OPENING_HOUR or hour >= settings.CLOSING_HOUR:
            raise ValidationError(
                f"Reservations are only accepted between "
                f"{settings.OPENING_HOUR:02d}:00 and {settings.CLOSING_HOUR:02d}:00"
            )

    async def _enforce_capacity(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        half = timedelta(minutes=settings.RESERVATION_DURATION_MINUTES)
        window_start = reservation_time - half
        window_end = reservation_time + half

        concurrent = await self.repository.list_in_window(
            start=window_start,
            end=window_end,
            restaurant_id=restaurant_id,
        )

        if exclude_id is not None:
            concurrent = [r for r in concurrent if r.id != exclude_id]

        seats_taken = sum(r.party_size for r in concurrent)

        max_capacity = settings.MAX_DAILY_CAPACITY

        if restaurant_id is not None:
            restaurant = await self.restaurant_repository.get_by_id(restaurant_id)

            if restaurant is not None:
                max_capacity = restaurant.number_of_tables * 4
            
        if seats_taken + party_size > max_capacity:
            raise ConflictError(
                "Sorry, we don't have availability for that time. "
                "Please try a different time slot."
            )
