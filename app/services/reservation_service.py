"""
Reservation service.

This is the business-logic layer. It enforces domain rules that go beyond
schema validation:
  * Reservations must be in the future
  * Reservations must fall within opening hours
  * Daily capacity must not be exceeded
  * Status transitions follow a defined lifecycle
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.reservation import Reservation, ReservationStatus
from app.repositories.reservation_repository import ReservationRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate

logger = get_logger(__name__)


class ReservationService:
    """Domain service orchestrating reservation operations."""

    def __init__(self, repository: ReservationRepository) -> None:
        self.repository = repository

    # ── Core CRUD ─────────────────────────────────────────────────────────
    async def create_reservation(self, payload: ReservationCreate) -> Reservation:
        """Validate domain rules, then persist the reservation."""
        self._validate_reservation_time(payload.reservation_time)
        await self._enforce_capacity(payload.reservation_time, payload.party_size)

        reservation = Reservation(
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            customer_email=payload.customer_email,
            party_size=payload.party_size,
            reservation_time=payload.reservation_time,
            duration_minutes=payload.duration_minutes,
            special_requests=payload.special_requests,
            session_id=payload.session_id,
            status=ReservationStatus.CONFIRMED,
        )
        created = await self.repository.create(reservation)
        logger.info(
            "Reservation created: id=%s party=%d time=%s",
            created.id, created.party_size, created.reservation_time.isoformat(),
        )
        return created

    async def get_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        """Get one reservation, raising NotFoundError if missing."""
        reservation = await self.repository.get_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError(f"Reservation {reservation_id} not found")
        return reservation

    async def list_reservations(
        self,
        skip: int = 0,
        limit: int = 100,
        status: ReservationStatus | None = None,
    ) -> list[Reservation]:
        """List reservations with optional pagination and status filter."""
        return await self.repository.list_all(skip=skip, limit=limit, status=status)

    async def update_reservation(
        self, reservation_id: uuid.UUID, payload: ReservationUpdate
    ) -> Reservation:
        """Update a reservation, re-validating any changed time/party_size."""
        reservation = await self.get_reservation(reservation_id)

        # Build a dict of only the fields the client actually provided.
        # `model_dump(exclude_unset=True)` is the Pydantic 2 idiom for partial updates.
        updates = payload.model_dump(exclude_unset=True)

        # Re-validate if time or party size changed
        new_time = updates.get("reservation_time", reservation.reservation_time)
        new_party = updates.get("party_size", reservation.party_size)
        if "reservation_time" in updates:
            self._validate_reservation_time(new_time)
        if "reservation_time" in updates or "party_size" in updates:
            await self._enforce_capacity(
                new_time, new_party, exclude_id=reservation.id
            )

        updated = await self.repository.update(reservation, updates)
        logger.info("Reservation updated: id=%s fields=%s", updated.id, list(updates.keys()))
        return updated

    async def cancel_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        """Soft-cancel: flip status to cancelled rather than hard-deleting."""
        reservation = await self.get_reservation(reservation_id)
        if reservation.status == ReservationStatus.CANCELLED:
            return reservation  # Idempotent
        return await self.repository.update(
            reservation, {"status": ReservationStatus.CANCELLED}
        )

    # ── Helpers used by the AI tool layer ─────────────────────────────────
    async def check_availability(
        self, reservation_time: datetime, party_size: int
    ) -> bool:
        """
        Quick yes/no check used by the AI before promising a slot.

        We re-use the same validation as create_reservation but catch the
        exceptions and translate to a boolean.
        """
        try:
            self._validate_reservation_time(reservation_time)
            await self._enforce_capacity(reservation_time, party_size)
            return True
        except (ValidationError, ConflictError):
            return False

    # ── Private validators ────────────────────────────────────────────────
    def _validate_reservation_time(self, reservation_time: datetime) -> None:
        """Ensure the requested time is in the future and within opening hours."""
        # Normalize to a tz-aware datetime in UTC for comparison
        if reservation_time.tzinfo is None:
            reservation_time = reservation_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if reservation_time <= now:
            raise ValidationError("Reservation time must be in the future")

        # Check opening hours (using local hour-of-day; a richer impl would
        # convert to RESTAURANT_TIMEZONE — kept simple for clarity).
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
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        """
        Make sure adding `party_size` at `reservation_time` won't exceed
        the restaurant's seating capacity for that time window.

        We define "concurrent" as any reservation whose window overlaps the
        proposed one. For simplicity we use a fixed default duration around
        the requested time.
        """
        half = timedelta(minutes=settings.RESERVATION_DURATION_MINUTES)
        window_start = reservation_time - half
        window_end = reservation_time + half

        concurrent = await self.repository.list_in_window(window_start, window_end)

        # If this is an update, ignore the reservation we're updating
        if exclude_id is not None:
            concurrent = [r for r in concurrent if r.id != exclude_id]

        seats_taken = sum(r.party_size for r in concurrent)
        if seats_taken + party_size > settings.MAX_DAILY_CAPACITY:
            raise ConflictError(
                "Sorry, we don't have availability for that time. "
                "Please try a different time slot."
            )
