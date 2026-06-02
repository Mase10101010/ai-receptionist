"""
Reservation service.
"""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.reservation import Reservation, ReservationStatus
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.email_service import EmailService

logger = get_logger(__name__)


class ReservationService:
    def __init__(
        self, 
        repository: ReservationRepository,
        restaurant_repository: RestaurantRepository,
        table_repository: TableRepository,
        email_service: EmailService,
    ) -> None:
        self.repository = repository
        self.restaurant_repository = restaurant_repository
        self.table_repository = table_repository
        self.email_service = email_service

    async def create_reservation(self, payload: ReservationCreate) -> Reservation:
        await self._validate_reservation_time(
            payload.reservation_time,
            payload.restaurant_id,
        )

        await self._enforce_capacity(
            reservation_time=payload.reservation_time,
            party_size=payload.party_size,
            restaurant_id=payload.restaurant_id,
        )

        if payload.table_id is not None:
            table_id = await self._validate_selected_table(
                table_id=payload.table_id,
                reservation_time=payload.reservation_time,
                party_size=payload.party_size,
                restaurant_id=payload.restaurant_id,
            )
        else:
            table_id = await self._assign_available_table(
                reservation_time=payload.reservation_time,
                party_size=payload.party_size,
                restaurant_id=payload.restaurant_id,
            )

        reservation = Reservation(
            restaurant_id=payload.restaurant_id,
            table_id=table_id,
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

        if created.customer_email:
            try:
                restaurant_name = settings.RESTAURANT_NAME
                restaurant_timezone = "UTC"
                restaurant_language = "en"

                if created.restaurant_id:
                    restaurant = await self.restaurant_repository.get_by_id(
                        created.restaurant_id
                    )

                    if restaurant is not None:
                        restaurant_name = restaurant.name
                        restaurant_timezone = restaurant.timezone or "UTC"
                        restaurant_language = restaurant.preferred_language or "en"

                try:
                    localized_time = created.reservation_time.astimezone(
                        ZoneInfo(restaurant_timezone)
                    )
                except Exception:
                    logger.exception(
                        "Invalid restaurant timezone: %s. Falling back to UTC.",
                        restaurant_timezone,
                    )
                    localized_time = created.reservation_time.astimezone(
                        ZoneInfo("UTC")
                    )

                await self.email_service.send_reservation_confirmation(
                    to_email=created.customer_email,
                    restaurant_name=restaurant_name,
                    customer_name=created.customer_name,
                    reservation_id=str(created.id),
                    reservation_time=localized_time.strftime(
                        "%B %d, %Y at %I:%M %p"
                    ),
                    party_size=created.party_size,
                    language=restaurant_language,
                )

                if restaurant is not None and restaurant.email:
                    await self.email_service.send_restaurant_reservation_notification(
                        restaurant_email=restaurant.email,
                        restaurant_name=restaurant.name,
                        customer_name=created.customer_name,
                        customer_email=created.customer_email,
                        customer_phone=created.customer_phone,
                        reservation_time=localized_time.strftime(
                            "%B %d, %Y at %I:%M %p"
                        ),
                        party_size=created.party_size,
                        table_number=created.table_number,
                        special_requests=created.special_requests,
                        language=restaurant.preferred_language,
                    )
            except Exception:
                logger.exception(
                    "Reservation confirmation email failed, but reservation was created."
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

    async def find_upcoming_reservations_by_customer(
            self,
            customer_name: str | None = None,
            customer_phone: str | None = None,
            restaurant_id: uuid.UUID | None = None,
    ) -> list[Reservation]:
        return await self.repository.find_upcoming_by_customer(
            customer_name=customer_name,
            customer_phone=customer_phone,
            restaurant_id=restaurant_id,
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
            await self._validate_reservation_time(
                new_time,
                reservation.restaurant_id,
            )

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
            await self._validate_reservation_time(
                new_time,
                reservation.restaurant_id,
            )

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
            await self._validate_reservation_time(
                reservation_time,
                restaurant_id,
            )

            await self._enforce_capacity(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
            )

            await self._assign_available_table(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
            )

            return True
        except (ValidationError, ConflictError):
            return False
        
    async def suggest_alternative_slots(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
    ) -> list[datetime]:
        """
        Suggest nearby available solts around the requested reservation time.
        We check ±30, ±60, ±90 minutes and return the first available options.
        """
        offsets = [-90, -60, -30, 30, 60, 90]
        suggestions: list[datetime] = []

        for minutes in offsets:
            candidate = reservation_time + timedelta(minutes=minutes)

            try:
                await self._validate_reservation_time(
                    candidate,
                    restaurant_id,
                )

                await self._enforce_capacity(
                    reservation_time=candidate,
                    party_size=party_size,
                    restaurant_id=restaurant_id,
                )

                await self._assign_available_table(
                    reservation_time=candidate,
                    party_size=party_size,
                    restaurant_id=restaurant_id,
                )

                suggestions.append(candidate)

                if len(suggestions) >= 3:
                    break

            except (ValidationError, ConflictError):
                continue


        return suggestions
    
    async def _assign_available_table(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
    ) -> uuid.UUID | None:
        if restaurant_id is None:
            return None

        candidates = await self.table_repository.list_capacity_candidates(
            restaurant_id=restaurant_id,
            party_size=party_size,
        )

        if not candidates:
            return None

        half = timedelta(minutes=settings.RESERVATION_DURATION_MINUTES)
        window_start = reservation_time - half
        window_end = reservation_time + half

        concurrent = await self.repository.list_in_window(
            start=window_start,
            end=window_end,
            restaurant_id=restaurant_id,
        )

        occupied_table_ids = {
            reservation.table_id
            for reservation in concurrent
            if reservation.table_id is not None
        }

        for table in candidates:
            if table.id not in occupied_table_ids:
                return table.id

        raise ConflictError(
            "Sorry, we don't have an available table for that time. "
            "Please try a different time slot."
        )
    
    async def _validate_selected_table(
        self,
        table_id: uuid.UUID,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        if restaurant_id is None:
            raise ValidationError("Restaurant is required to select a table.")

        table = await self.table_repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None or not table.is_active:
            raise ValidationError("Selected table was not found or is inactive.")

        if table.seats < party_size:
            raise ValidationError(
                "Selected table does not have enough seats for this party size."
            )

        half = timedelta(minutes=settings.RESERVATION_DURATION_MINUTES)
        window_start = reservation_time - half
        window_end = reservation_time + half

        concurrent = await self.repository.list_in_window(
            start=window_start,
            end=window_end,
            restaurant_id=restaurant_id,
        )

        for reservation in concurrent:
            if reservation.table_id == table_id:
                raise ConflictError(
                    "Selected table is not available at this date and time."
                )

        return table.id

    async def _validate_reservation_time(
        self, 
        reservation_time: datetime,
        restaurant_id: uuid.UUID | None = None,
        ) -> None:
        if reservation_time.tzinfo is None:
            reservation_time = reservation_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        if reservation_time <= now:
            raise ValidationError("Reservation time must be in the future")

        opening_hour = settings.OPENING_HOUR
        closing_hour = settings.CLOSING_HOUR
        local_time = reservation_time

        if restaurant_id is not None:
            restaurant = await self.restaurant_repository.get_by_id(restaurant_id)

            if restaurant is not None:
                opening_hour = restaurant.opening_hour
                closing_hour = restaurant.closing_hour
                try:
                    local_time = reservation_time.astimezone(
                        ZoneInfo(restaurant.timezone or "UTC")
                    )
                except Exception:
                    logger.exception(
                        "Invalid restaurant timezone: %s. Falling back to UTC.",
                        restaurant.timezone,
                    )
                    local_time = reservation_time.astimezone(ZoneInfo("UTC"))

                reservation_date = local_time.date().isoformat()

                for closure in restaurant.special_closures or []:
                    if closure.get("date") == reservation_date:
                        reason = closure.get("reason") or "special closure"
                        raise ValidationError(
                            f"The restaurant is closed on this date due to {reason}."
                        )

                day_name = local_time.strftime("%a")

                for schedule in restaurant.weekly_schedule or []:
                    if schedule.get("day") == day_name:
                        is_open = schedule.get("is_open", True)

                        if not is_open:
                            raise ValidationError(
                                "The restaurant is closed on this day."
                            )

                        opening_hour = int(schedule.get("opening_hour", opening_hour))
                        closing_hour = int(schedule.get("closing_hour", closing_hour))
                        break

        hour = local_time.hour

        if hour < opening_hour or hour >= closing_hour:
            raise ValidationError(
                f"Reservations are only accepted between "
                f"{opening_hour:02d}:00 and {closing_hour:02d}:00"
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
