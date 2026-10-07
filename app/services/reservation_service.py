"""
Reservation service.
"""
import uuid
from enum import Enum
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.intelligence.schemas import (
    IntelligenceOptimizeRequest,
    IntelligenceReoptimizeRequest,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.reservation import Reservation, ReservationStatus
from app.repositories.reservation_repository import ReservationRepository
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)

from app.repositories.table_combination_repository import (
    TableCombinationRepository,
)
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.table_repository import TableRepository
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.email_service import EmailService
from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.services.ai_suggestion_service import (
    AISuggestionService,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.service import (
    IntelligenceEventService,
)

from app.intelligence_execution.autopilot import (
    AutopilotAuthorityService,
)
from app.intelligence_execution.autopilot_mapper import (
    AutopilotReoptimizationMapper,
)
from app.intelligence_execution.orchestrator import (
    IntelligenceExecutionOrchestrator,
)
from app.intelligence_temporal.prediction_coordinator import (
    TemporalTurnPredictionCoordinator,
)
from app.intelligence_temporal.outcome_coordinator import (
    TemporalPredictionOutcomeCoordinator,
)

from app.intelligence_execution.temporal_autopilot import (
    TemporalAutopilotAuthorityService,
)
from app.intelligence_temporal.autopilot_evidence import (
    TemporalAutopilotSafetyEvidenceService,
)
from app.models.ai_suggestion import AISuggestion

logger = get_logger(__name__)

def _format_reservation_time_for_language(
    reservation_time: datetime,
    language: str,
) -> str:
    if language == "it":
        return reservation_time.strftime("%d/%m/%Y alle %H:%M")

    if language == "es":
        return reservation_time.strftime("%d/%m/%Y a las %H:%M")

    if language == "fr":
        return reservation_time.strftime("%d/%m/%Y à %H:%M")

    if language == "de":
        return reservation_time.strftime("%d.%m.%Y um %H:%M")

    return reservation_time.strftime("%B %d, %Y at %I:%M %p")


class BookingAvailabilityOutcome(str, Enum):
    DIRECT_AVAILABLE = "direct_available"
    REOPTIMIZATION_AVAILABLE = "reoptimization_available"
    LIVE_SERVICE_APPROVAL_REQUIRED = "live_service_approval_required"
    UNAVAILABLE = "unavailable"


class ReservationService:
    def __init__(
        self,
        repository: ReservationRepository,
        restaurant_repository: RestaurantRepository,
        table_repository: TableRepository,
        email_service: EmailService,
        intelligence_service: IntelligenceOptimizationService | None = None,
    ) -> None:
        self.repository = repository
        self.restaurant_repository = restaurant_repository
        self.table_repository = table_repository
        self.email_service = email_service
        self.intelligence_service = (
            intelligence_service
            or IntelligenceOptimizationService()
        )

    @staticmethod
    def _apply_lifecycle_timestamps(
        *,
        reservation: Reservation,
        updates: dict,
    ) -> dict:
        normalized_updates = dict(updates)

        requested_status = normalized_updates.get("status")

        if (
            requested_status == ReservationStatus.SEATED
            and reservation.seated_at is None
        ):
            normalized_updates["seated_at"] = datetime.now(timezone.utc)

        if (
            requested_status == ReservationStatus.COMPLETED
            and reservation.completed_at is None
        ):
            normalized_updates["completed_at"] = datetime.now(timezone.utc)

        if (
            requested_status == ReservationStatus.CANCELLED
            and reservation.cancelled_at is None
        ):
            normalized_updates["cancelled_at"] = datetime.now(timezone.utc)

        if (
            requested_status == ReservationStatus.NO_SHOW
            and reservation.no_show_at is None
        ):
            normalized_updates["no_show_at"] = datetime.now(timezone.utc)

        return normalized_updates

    async def _record_reservation_event(
        self,
        *,
        reservation: Reservation,
        event_type: IntelligenceEventType,
        source: IntelligenceEventSource,
        payload: dict,
    ) -> None:
        if reservation.restaurant_id is None:
            return

        service = IntelligenceEventService(
            IntelligenceEventRepository(
                self.repository.db,
            )
        )

        await service.record(
            restaurant_id=reservation.restaurant_id,
            event_type=event_type,
            source=source,
            entity_type="reservation",
            entity_id=reservation.id,
            payload=payload,
            metadata={
                "service": "reservation_service",
                "event_schema": (
                    f"{event_type.value}.v1"
                ),
            },
        )

    async def _try_record_temporal_prediction(
        self,
        *,
        reservation: Reservation,
    ) -> None:
        """
        Best-effort temporal prediction emission.

        The reservation lifecycle remains authoritative:
        temporal intelligence must never make an otherwise valid
        booking fail.

        A SAVEPOINT isolates the temporal attempt so that even a
        persistence/database failure cannot poison the caller's
        surrounding transaction.
        """
        try:
            async with self.repository.db.begin_nested():
                await (
                    TemporalTurnPredictionCoordinator()
                    .predict_for_reservation(
                        session=self.repository.db,
                        reservation=reservation,
                    )
                )
        except Exception:
            logger.exception(
                "Temporal prediction failed closed: "
                "reservation_id=%s restaurant_id=%s",
                reservation.id,
                reservation.restaurant_id,
            )

    async def _try_record_temporal_outcome(
        self,
        *,
        reservation: Reservation,
    ) -> None:
        """
        Best-effort temporal outcome emission.

        Reservation lifecycle truth remains authoritative.
        Temporal outcome persistence must never make an otherwise
        valid COMPLETED transition fail.

        A SAVEPOINT isolates the temporal attempt from the caller's
        surrounding transaction.
        """
        if reservation.status != ReservationStatus.COMPLETED:
            return

        if (
            reservation.restaurant_id is None
            or reservation.seated_at is None
            or reservation.completed_at is None
        ):
            return

        try:
            async with self.repository.db.begin_nested():
                await (
                    TemporalPredictionOutcomeCoordinator()
                    .record_for_completed_reservation(
                        session=self.repository.db,
                        reservation=reservation,
                    )
                )
        except Exception:
            logger.exception(
                "Temporal outcome recording failed closed: "
                "reservation_id=%s restaurant_id=%s",
                reservation.id,
                reservation.restaurant_id,
            )

    async def _try_autopilot_reoptimization(
        self,
        *,
        reservation: Reservation,
        suggestion: AISuggestion,
    ) -> Reservation:
        if reservation.restaurant_id is None:
            return reservation

        restaurant = await self.restaurant_repository.get_by_id(
            reservation.restaurant_id
        )

        if restaurant is None:
            return reservation

        suggestion_payload = (
            suggestion.payload or {}
        )

        plan = suggestion_payload.get(
            "plan"
        )

        try:
            temporal_context = (
                TemporalAutopilotSafetyEvidenceService
                .context_from_payload(
                    payload=suggestion_payload,
                )
            )

            authority = (
                TemporalAutopilotAuthorityService()
                .can_execute_stored_plan_automatically(
                    plan=plan,
                    autopilot_enabled=bool(
                        restaurant.autopilot_enabled
                    ),
                    temporal_context=(
                        temporal_context
                    ),
                )
            )

        except Exception:
            logger.exception(
                "Temporal Autopilot authority "
                "evaluation failed closed: "
                "reservation_id=%s restaurant_id=%s "
                "suggestion_id=%s",
                reservation.id,
                reservation.restaurant_id,
                suggestion.id,
            )

            return reservation

        if not authority.allowed:
            return reservation

        try:
            async with self.repository.db.begin_nested():
                apply_payload = (
                    AutopilotReoptimizationMapper()
                    .build_apply_request(
                        suggestion=suggestion,
                    )
                )

                await IntelligenceExecutionOrchestrator(
                    intelligence_service=self.intelligence_service,
                ).apply_reoptimization(
                    session=self.repository.db,
                    payload=apply_payload,
                    allowed_restaurant_ids=[
                        reservation.restaurant_id
                    ],
                    source=IntelligenceEventSource.AI,
                    actor_user_id=None,
                )

                refreshed = (
                    await self.repository
                    .get_by_id_for_restaurants(
                        reservation_id=reservation.id,
                        restaurant_ids=[
                            reservation.restaurant_id
                        ],
                    )
                )

                if refreshed is None:
                    raise ValidationError(
                        "Autopilot applied the seating plan "
                        "but the reservation could not be reloaded."
                    )

                return refreshed

        except Exception:
            logger.exception(
                "Autopilot execution failed closed: "
                "reservation_id=%s restaurant_id=%s "
                "suggestion_id=%s",
                reservation.id,
                reservation.restaurant_id,
                suggestion.id,
            )

            return reservation

    async def create_reservation(self, payload: ReservationCreate) -> Reservation:
        await self._validate_reservation_time(
            payload.reservation_time,
            payload.restaurant_id,
        )

        assigned_table_ids: list[uuid.UUID] = []
        requires_reoptimization = False

        if payload.table_id is not None:
            table_id = await self._validate_selected_table(
                table_id=payload.table_id,
                reservation_time=payload.reservation_time,
                party_size=payload.party_size,
                restaurant_id=payload.restaurant_id,
                duration_minutes=payload.duration_minutes,
            )
            assigned_table_ids = [table_id]
        else:
            (
                table_id,
                assigned_table_ids,
            ) = await self._assign_tables_with_aie(
                reservation_time=payload.reservation_time,
                party_size=payload.party_size,
                restaurant_id=payload.restaurant_id,
                duration_minutes=payload.duration_minutes,
            )

            if table_id is None or not assigned_table_ids:
                requires_reoptimization = await self._reoptimization_available(
                    reservation_time=payload.reservation_time,
                    party_size=payload.party_size,
                    restaurant_id=payload.restaurant_id,
                    duration_minutes=payload.duration_minutes,
                )

                if not requires_reoptimization:
                    raise ConflictError(
                        "Sorry, Alias could not find a safe seating plan for "
                        "that time. Please try a different time slot."
                    )

        reservation_status = (
            ReservationStatus.PENDING
            if requires_reoptimization
            else ReservationStatus.CONFIRMED
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
            status=reservation_status,
        )

        created = await self.repository.create(reservation)

        if table_id is not None and assigned_table_ids:
            created = await self.repository.replace_table_assignments(
                reservation=created,
                table_ids=assigned_table_ids,
                primary_table_id=table_id,
            )

        await self._record_reservation_event(
            reservation=created,
            event_type=(
                IntelligenceEventType
                .RESERVATION_CREATED
            ),
            source=IntelligenceEventSource.SYSTEM,
            payload={
                "customer_name": created.customer_name,
                "party_size": created.party_size,
                "reservation_time": (
                    created.reservation_time.isoformat()
                ),
                "duration_minutes": (
                    created.duration_minutes
                ),
                "status": created.status.value,
                "booking_outcome": (
                    BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE.value
                    if requires_reoptimization
                    else BookingAvailabilityOutcome.DIRECT_AVAILABLE.value
                ),
                "table_id": (
                    str(created.table_id)
                    if created.table_id is not None
                    else None
                ),
                "table_ids": [
                    str(table_id)
                    for table_id in (
                        created.assigned_table_ids or []
                    )
                ],
                "origin": (
                    "manual"
                    if created.session_id is None
                    else "concierge"
                ),
            },
        )
        await self._try_record_temporal_prediction(
            reservation=created,
        )

        if requires_reoptimization:
            suggestion_service = AISuggestionService(
                repository=AISuggestionRepository(
                    self.repository.db,
                ),
                reservation_repository=self.repository,
                intelligence_service=self.intelligence_service,
            )

            suggestion = await suggestion_service.analyze_reservation(
                created,
            )

            if suggestion is None:
                logger.warning(
                    "Reservation requires reoptimization but no AI suggestion "
                    "was created: reservation_id=%s restaurant_id=%s",
                    created.id,
                    created.restaurant_id,
                )
            else:
                created = await self._try_autopilot_reoptimization(
                    reservation=created,
                    suggestion=suggestion,
                )

        logger.info(
            (
                "Reservation created: id=%s restaurant_id=%s party=%d "
                "time=%s status=%s"
            ),
            created.id,
            created.restaurant_id,
            created.party_size,
            created.reservation_time.isoformat(),
            created.status.value,
        )

        # A pending reservation is a request awaiting a seating decision, not a
        # confirmed booking. Confirmation emails are sent only for reservations
        # that are already operationally confirmed.
        if created.status == ReservationStatus.PENDING:
            try:
                restaurant_name = settings.RESTAURANT_NAME
                restaurant_timezone = "UTC"
                restaurant_language = "en"
                restaurant = None

                if created.restaurant_id:
                    restaurant = await self.restaurant_repository.get_by_id(
                        created.restaurant_id
                    )

                    if restaurant is not None:
                        restaurant_name = restaurant.name
                        restaurant_timezone = restaurant.timezone or "UTC"
                        restaurant_language = (
                            restaurant.preferred_language or "en"
                        )

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

                formatted_time = _format_reservation_time_for_language(
                    localized_time,
                    restaurant_language,
                )

                if created.customer_email:
                    await self.email_service.send_reservation_pending_confirmation(
                        to_email=created.customer_email,
                        restaurant_name=restaurant_name,
                        customer_name=created.customer_name,
                        reservation_id=str(created.id),
                        reservation_time=formatted_time,
                        party_size=created.party_size,
                        language=restaurant_language,
                    )

                if restaurant is not None and restaurant.email:
                    await self.email_service.send_restaurant_pending_reservation_notification(
                        restaurant_email=restaurant.email,
                        restaurant_name=restaurant.name,
                        customer_name=created.customer_name,
                        customer_email=created.customer_email,
                        customer_phone=created.customer_phone,
                        reservation_time=formatted_time,
                        party_size=created.party_size,
                        special_requests=created.special_requests,
                        language=restaurant_language,
                    )

            except Exception:
                logger.exception(
                    "Pending reservation notification failed, "
                    "but reservation was created."
                )
        if (
            created.status == ReservationStatus.CONFIRMED
            and created.customer_email
        ):
            try:
                restaurant_name = settings.RESTAURANT_NAME
                restaurant_timezone = "UTC"
                restaurant_language = "en"
                restaurant = None

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
                    reservation_time=_format_reservation_time_for_language(
                        localized_time,
                        restaurant_language,
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
                        reservation_time=_format_reservation_time_for_language(
                            localized_time,
                            restaurant_language,
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
        restaurant_id: uuid.UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Reservation]:
        if restaurant_id is not None and restaurant_id not in restaurant_ids:
            raise ValidationError(
                "Restaurant is not available for the current user."
            )

        if start is not None and end is not None and start >= end:
            raise ValidationError(
                "Reservation window start must be before end."
            )

        return await self.repository.list_by_restaurant_ids(
            restaurant_ids=restaurant_ids,
            skip=skip,
            limit=limit,
            status=status,
            restaurant_id=restaurant_id,
            start=start,
            end=end,
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

    async def propose_reservation_modification_reoptimization(
        self,
        *,
        reservation_id: uuid.UUID,
        payload: ReservationUpdate,
    ):
        """
        Build a reoptimization proposal for a reservation modification
        without mutating the existing reservation.

        The existing reservation remains authoritative until the proposal
        is successfully executed.
        """
        reservation = await self.repository.get_by_id(
            reservation_id
        )

        if reservation is None:
            raise NotFoundError("Reservation not found.")

        requested_party_size = (
            payload.party_size
            if payload.party_size is not None
            else reservation.party_size
        )

        requested_reservation_time = (
            payload.reservation_time
            if payload.reservation_time is not None
            else reservation.reservation_time
        )

        # M2 only applies to capacity-affecting modifications.
        if (
            requested_party_size == reservation.party_size
            and requested_reservation_time
            == reservation.reservation_time
        ):
            return None

        if payload.reservation_time is not None:
            await self._validate_reservation_time(
                requested_reservation_time,
                reservation.restaurant_id,
            )

        suggestion_repo = AISuggestionRepository(
            self.repository.db
        )

        suggestion_service = AISuggestionService(
            repository=suggestion_repo,
            reservation_repository=self.repository,
            intelligence_service=self.intelligence_service,
        )

        return await (
            suggestion_service
            .analyze_reservation_modification(
                reservation,
                requested_party_size=requested_party_size,
                requested_reservation_time=(
                    requested_reservation_time
                ),
            )
        )

    async def propose_live_seated_modification(
        self,
        *,
        reservation_id: uuid.UUID,
        requested_party_size: int,
    ):
        """
        Build a manager-facing live-service proposal for a SEATED
        reservation without mutating its authoritative reservation
        or physical table assignment.
        """
        reservation = await self.repository.get_by_id(
            reservation_id
        )

        if reservation is None:
            raise NotFoundError("Reservation not found.")

        if reservation.status != ReservationStatus.SEATED:
            return None

        if requested_party_size == reservation.party_size:
            return None

        suggestion_service = AISuggestionService(
            repository=AISuggestionRepository(
                self.repository.db
            ),
            reservation_repository=self.repository,
            intelligence_service=self.intelligence_service,
        )

        return await (
            suggestion_service
            .analyze_live_seated_modification(
                reservation,
                requested_party_size=requested_party_size,
            )
        )

    async def _current_seated_assignment_supports_party_size(
        self,
        *,
        reservation: Reservation,
        party_size: int,
    ) -> bool:
        """
        Return whether the reservation's current physical SEATED assignment
        can accommodate the requested party size without moving the guests.

        A single-table assignment uses that table's physical capacity.
        A multi-table assignment is valid only through an exact active
        TableCombination matching the current physical tables.
        """
        table_assignments = (
            getattr(reservation, "table_assignments", None) or []
        )

        canonical_table_ids = list(
            dict.fromkeys(
                assignment.table_id
                for assignment in table_assignments
            )
        )

        # Canonical assignments are authoritative when present.
        # Otherwise fall back to the legacy primary table_id.
        assigned_table_ids = (
            canonical_table_ids
            if canonical_table_ids
            else (
                [reservation.table_id]
                if reservation.table_id is not None
                else []
            )
        )

        if not assigned_table_ids:
            return False

        if len(assigned_table_ids) == 1:
            assigned_table_id = assigned_table_ids[0]

            table = getattr(reservation, "table", None)

            if (
                table is None
                or table.id != assigned_table_id
            ):
                table = next(
                    (
                        getattr(assignment, "table", None)
                        for assignment in table_assignments
                        if (
                            assignment.table_id == assigned_table_id
                            and getattr(assignment, "table", None)
                            is not None
                        )
                    ),
                    None,
                )

            if table is None:
                return False

            return bool(
                table.is_active
                and 1 <= party_size <= table.seats
            )

        if reservation.restaurant_id is None:
            return False

        combination_repository = TableCombinationRepository(
            self.repository.db
        )

        combinations = await combination_repository.list_by_restaurant(
            restaurant_id=reservation.restaurant_id,
        )

        current_table_ids = set(assigned_table_ids)

        for combination in combinations:
            combination_table_ids = {
                member.table_id
                for member in combination.members
            }

            if combination_table_ids != current_table_ids:
                continue

            return bool(
                combination.is_active
                and combination.min_capacity <= party_size
                <= combination.max_capacity
            )

        return False

    async def apply_live_seated_modification_for_restaurants(
        self,
        *,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
        requested_party_size: int,
        destination_table_ids: list[uuid.UUID],
        destination_primary_table_id: uuid.UUID,
    ) -> Reservation:
        """
        Apply an explicitly manager-approved physical move for a
        currently SEATED reservation.

        The reservation identity and SEATED lifecycle are preserved.
        Party size and physical assignment are mutated inside the same
        surrounding transaction.
        """
        if (
            isinstance(requested_party_size, bool)
            or not isinstance(requested_party_size, int)
            or requested_party_size < 1
        ):
            raise ValidationError(
                "Requested party size must be a positive integer."
            )

        destination_table_ids = list(
            dict.fromkeys(destination_table_ids)
        )

        if not destination_table_ids:
            raise ValidationError(
                "At least one destination table is required."
            )

        if (
            destination_primary_table_id
            not in destination_table_ids
        ):
            raise ValidationError(
                "Destination primary table must be included "
                "in destination tables."
            )

        reservation = await (
            self.repository
            .get_by_id_for_restaurants_for_update(
                reservation_id,
                restaurant_ids,
            )
        )

        if reservation is None:
            raise NotFoundError(
                "Reservation not found."
            )

        if reservation.restaurant_id is None:
            raise ValidationError(
                "Reservation is not attached to a restaurant."
            )

        if reservation.status != ReservationStatus.SEATED:
            raise ValidationError(
                "Live seated modification requires "
                "a SEATED reservation."
            )

        locked_tables = await self.table_repository.lock_by_ids(
            destination_table_ids
        )

        locked_by_id = {
            table.id: table
            for table in locked_tables
        }

        if set(locked_by_id) != set(destination_table_ids):
            raise ValidationError(
                "One or more destination tables could not be resolved."
            )

        for table in locked_tables:
            if table.restaurant_id != reservation.restaurant_id:
                raise ValidationError(
                    "Destination table does not belong "
                    "to the reservation restaurant."
                )

            if not table.is_active:
                raise ValidationError(
                    "Destination table is inactive."
                )

        if len(destination_table_ids) == 1:
            destination_table = locked_by_id[
                destination_table_ids[0]
            ]

            if requested_party_size > destination_table.seats:
                raise ValidationError(
                    "Destination table cannot accommodate "
                    "the requested party size."
                )
        else:
            combination_repository = TableCombinationRepository(
                self.repository.db
            )

            combinations = (
                await combination_repository.list_by_restaurant(
                    restaurant_id=reservation.restaurant_id,
                )
            )

            destination_set = set(
                destination_table_ids
            )
            matching_combination = None

            for combination in combinations:
                combination_table_ids = {
                    member.table_id
                    for member in combination.members
                }

                if combination_table_ids == destination_set:
                    matching_combination = combination
                    break

            if (
                matching_combination is None
                or not matching_combination.is_active
                or not (
                    matching_combination.min_capacity
                    <= requested_party_size
                    <= matching_combination.max_capacity
                )
            ):
                raise ValidationError(
                    "Destination tables are not a valid active "
                    "combination for the requested party size."
                )

        live_blocker = (
            await self.repository.find_seated_on_table_ids(
                destination_table_ids,
                exclude_reservation_id=reservation.id,
            )
        )

        if live_blocker is not None:
            raise ConflictError(
                "One or more destination tables are currently occupied."
            )

        original_status = reservation.status
        original_seated_at = reservation.seated_at

        await self.repository.update(
            reservation,
            {
                "party_size": requested_party_size,
            },
        )

        reservation = (
            await self.repository.replace_table_assignments(
                reservation,
                destination_table_ids,
                primary_table_id=(
                    destination_primary_table_id
                ),
            )
        )

        # LIVE apply must never alter lifecycle state.
        if (
            reservation.status != original_status
            or reservation.seated_at != original_seated_at
        ):
            raise ValidationError(
                "Live seated modification altered "
                "the reservation lifecycle."
            )

        return reservation

    async def update_reservation(
        self,
        reservation_id: uuid.UUID,
        payload: ReservationUpdate,
    ) -> Reservation:
        reservation = await self.get_reservation(reservation_id)
        previous_status = reservation.status

        updates = payload.model_dump(exclude_unset=True)
        updates = self._apply_lifecycle_timestamps(
            reservation=reservation,
            updates=updates,
        )

        new_time = updates.get(
            "reservation_time",
            reservation.reservation_time,
        )
        new_party = updates.get(
            "party_size",
            reservation.party_size,
        )

        capacity_affecting_update = (
            "reservation_time" in updates
            or "party_size" in updates
        )

        if "reservation_time" in updates:
            await self._validate_reservation_time(
                new_time,
                reservation.restaurant_id,
            )

        primary_table_id: uuid.UUID | None = None
        assigned_table_ids: list[uuid.UUID] = []
        preserve_seated_assignment = False

        if capacity_affecting_update:
            if reservation.status == ReservationStatus.SEATED:
                # A seated assignment is an authoritative physical location.
                # A generic reservation modification may update party size only
                # when the guests can remain exactly where they are.
                #
                # Changing reservation time while already seated is not treated
                # as an ordinary capacity modification.
                if "reservation_time" in updates:
                    raise ConflictError(
                        "A seated reservation cannot change its reservation time "
                        "through the standard modification flow."
                    )

                current_assignment_supports_party = (
                    await self._current_seated_assignment_supports_party_size(
                        reservation=reservation,
                        party_size=new_party,
                    )
                )

                if not current_assignment_supports_party:
                    raise ConflictError(
                        "The seated party cannot be accommodated by its current "
                        "physical table assignment."
                    )

                preserve_seated_assignment = True

            else:
                (
                    primary_table_id,
                    assigned_table_ids,
                ) = await self._assign_tables_with_aie(
                    reservation_time=new_time,
                    party_size=new_party,
                    restaurant_id=reservation.restaurant_id,
                    reservation_id=reservation.id,
                )

                if not assigned_table_ids:
                    raise ConflictError(
                        "No direct table assignment is available "
                        "for the requested reservation modification."
                    )

        updated = await self.repository.update(
            reservation,
            updates,
        )

        if capacity_affecting_update and not preserve_seated_assignment:
            updated = await self.repository.replace_table_assignments(
                updated,
                assigned_table_ids,
                primary_table_id=primary_table_id,
            )

        if (
            previous_status != ReservationStatus.COMPLETED
            and updated.status == ReservationStatus.COMPLETED
        ):
            await self._try_record_temporal_outcome(
                reservation=updated,
            )

        if updates:
            await self._record_reservation_event(
                reservation=updated,
                event_type=(
                    IntelligenceEventType
                    .RESERVATION_UPDATED
                ),
                source=(
                    IntelligenceEventSource.SYSTEM
                ),
                payload={
                    "changed_fields": sorted(
                        updates.keys(),
                    ),
                    "changes": {
                        key: (
                            value.isoformat()
                            if isinstance(
                                value,
                                datetime,
                            )
                            else (
                                value.value
                                if hasattr(
                                    value,
                                    "value",
                                )
                                else value
                            )
                        )
                        for key, value
                        in updates.items()
                    },
                    "party_size": updated.party_size,
                    "reservation_time": (
                        updated.reservation_time
                        .isoformat()
                    ),
                    "status": updated.status.value,
                },
            )

        if {
            "reservation_time",
            "party_size",
            "status",
        } & updates.keys():
            await self._expire_pending_ai_suggestions(
                updated.restaurant_id,
            )

        logger.info(
            "Reservation updated: id=%s fields=%s",
            updated.id,
            list(updates.keys()),
        )

        try:
            restaurant = None

            if updated.restaurant_id:
                restaurant = await self.restaurant_repository.get_by_id(
                    updated.restaurant_id
                )

            if restaurant is not None:
                restaurant_timezone = restaurant.timezone or "UTC"
                restaurant_language = restaurant.preferred_language or "en"

                try:
                    localized_time = updated.reservation_time.astimezone(
                        ZoneInfo(restaurant_timezone)
                    )
                except Exception:
                    localized_time = updated.reservation_time.astimezone(
                        ZoneInfo("UTC")
                    )

                formatted_time = _format_reservation_time_for_language(
                    localized_time,
                    restaurant_language,
                )

                if updated.customer_email:
                    await self.email_service.send_reservation_update_confirmation(
                        to_email=updated.customer_email,
                        restaurant_name=restaurant.name,
                        customer_name=updated.customer_name,
                        reservation_id=str(updated.id),
                        reservation_time=formatted_time,
                        party_size=updated.party_size,
                        language=restaurant_language,
                    )

                if restaurant.email:
                    await self.email_service.send_restaurant_reservation_update_notification(
                        restaurant_email=restaurant.email,
                        restaurant_name=restaurant.name,
                        customer_name=updated.customer_name,
                        customer_email=updated.customer_email,
                        customer_phone=updated.customer_phone,
                        reservation_time=formatted_time,
                        party_size=updated.party_size,
                        table_number=updated.table_number,
                        special_requests=updated.special_requests,
                        language=restaurant_language,
                    )

        except Exception:
            logger.exception(
                "Reservation update emails failed."
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

        previous_status = reservation.status

        updates = payload.model_dump(exclude_unset=True)
        updates = self._apply_lifecycle_timestamps(
            reservation=reservation,
            updates=updates,
        )

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

        if (
            previous_status != ReservationStatus.SEATED
            and updates.get("status") == ReservationStatus.SEATED
        ):
            table_ids = [
                assignment.table_id
                for assignment in reservation.table_assignments
            ]

            if not table_ids and reservation.table_id is not None:
                table_ids = [reservation.table_id]

            await self.table_repository.lock_by_ids(table_ids)

            seated_reservation = await self.repository.find_seated_on_table_ids(
                table_ids,
                exclude_reservation_id=reservation.id,
            )

            if seated_reservation is not None:
                raise ConflictError(
                    "One or more assigned tables are still occupied by a seated reservation."
                )

        updated = await self.repository.update(
            reservation,
            updates,
        )

        if (
            previous_status != ReservationStatus.COMPLETED
            and updated.status == ReservationStatus.COMPLETED
        ):
            await self._try_record_temporal_outcome(
                reservation=updated,
            )

        if updates:
            await self._record_reservation_event(
                reservation=updated,
                event_type=(
                    IntelligenceEventType
                    .RESERVATION_UPDATED
                ),
                source=IntelligenceEventSource.MANAGER,
                payload={
                    "changed_fields": sorted(
                        updates.keys(),
                    ),
                    "changes": {
                        key: (
                            value.isoformat()
                            if isinstance(
                                value,
                                datetime,
                            )
                            else (
                                value.value
                                if hasattr(
                                    value,
                                    "value",
                                )
                                else value
                            )
                        )
                        for key, value
                        in updates.items()
                    },
                    "party_size": updated.party_size,
                    "reservation_time": (
                        updated.reservation_time
                        .isoformat()
                    ),
                    "status": updated.status.value,
                },
            )

        if {
            "reservation_time",
            "party_size",
            "status",
        } & updates.keys():
            await self._expire_pending_ai_suggestions(
                updated.restaurant_id,
            )

        return updated

    async def move_reservation_for_restaurants(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
        table_id: uuid.UUID,
    ) -> Reservation:
        reservation = await self.get_reservation_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=restaurant_ids,
        )

        non_movable_statuses = {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }

        if reservation.status in non_movable_statuses:
            raise ValidationError(
                "Completed, cancelled, or no-show reservations "
                "cannot be moved."
            )

        if reservation.restaurant_id is None:
            raise ValidationError(
                "Reservation is not associated with a restaurant."
            )

        if reservation.table_id == table_id:
            return reservation

        previous_table_id = reservation.table_id

        validated_table_id = await self._validate_selected_table(
            table_id=table_id,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
            restaurant_id=reservation.restaurant_id,
            duration_minutes=reservation.duration_minutes,
            exclude_id=reservation.id,
        )

        if reservation.status == ReservationStatus.SEATED:
            await self.table_repository.lock_by_ids(
                [validated_table_id]
            )

            seated_reservation = await self.repository.find_seated_on_table_ids(
                [validated_table_id],
                exclude_reservation_id=reservation.id,
            )

            if seated_reservation is not None:
                raise ConflictError(
                    "The target table is still occupied by a seated reservation."
                )

        moved = await self.repository.replace_table_assignments(
            reservation=reservation,
            table_ids=[validated_table_id],
            primary_table_id=validated_table_id,
        )

        await self._record_reservation_event(
            reservation=moved,
            event_type=(
                IntelligenceEventType
                .RESERVATION_MOVED
            ),
            source=IntelligenceEventSource.MANAGER,
            payload={
                "from_table_id": (
                    str(previous_table_id)
                    if previous_table_id is not None
                    else None
                ),
                "to_table_id": str(
                    moved.table_id,
                ),
                "from_table_ids": (
                    [str(previous_table_id)]
                    if previous_table_id is not None
                    else []
                ),
                "to_table_ids": [
                    str(table_id)
                    for table_id in (
                        moved.assigned_table_ids or []
                    )
                ],
                "party_size": moved.party_size,
                "reservation_time": (
                    moved.reservation_time.isoformat()
                ),
            },
        )

        await self._expire_pending_ai_suggestions(
            moved.restaurant_id,
        )

        logger.info(
            (
                "Reservation moved: id=%s restaurant_id=%s "
                "from_table_id=%s to_table_id=%s status=%s"
            ),
            moved.id,
            moved.restaurant_id,
            previous_table_id,
            moved.table_id,
            moved.status.value,
        )

        return moved

    async def _expire_pending_ai_suggestions(
        self,
        restaurant_id: uuid.UUID | None,
    ) -> None:
        if restaurant_id is None:
            return

        service = AISuggestionService(
            repository=AISuggestionRepository(
                self.repository.db,
            ),
            reservation_repository=(
                self.repository
            ),
        )

        expired_count = (
            await service
            .expire_for_restaurant(
                restaurant_id,
            )
        )

        if expired_count > 0:
            logger.info(
                (
                    "Expired stale AI suggestions: "
                    "restaurant_id=%s count=%d"
                ),
                restaurant_id,
                expired_count,
            )

    async def cancel_reservation(self, reservation_id: uuid.UUID) -> Reservation:
        reservation = await self.get_reservation(reservation_id)

        if reservation.status == ReservationStatus.CANCELLED:
            return reservation

        previous_status = reservation.status

        updates = self._apply_lifecycle_timestamps(
            reservation=reservation,
            updates={"status": ReservationStatus.CANCELLED},
        )

        cancelled = await self.repository.update(
            reservation,
            updates,
        )

        ai_suggestion_repository = AISuggestionRepository(
            self.repository.db,
        )

        ai_suggestion_service = AISuggestionService(
            repository=AISuggestionRepository(
                self.repository.db,
            ),
            reservation_repository=self.repository,
        )

        await ai_suggestion_service.expire_for_reservation(
            cancelled.id,
        )

        await self._expire_pending_ai_suggestions(
            cancelled.restaurant_id,
        )

        logger.info(
            "Reservation cancelled: id=%s",
            cancelled.id,
        )

        await self._record_reservation_event(
            reservation=cancelled,
            event_type=(
                IntelligenceEventType
                .RESERVATION_CANCELLED
            ),
            source=IntelligenceEventSource.SYSTEM,
            payload={
                "customer_name": (
                    cancelled.customer_name
                ),
                "party_size": cancelled.party_size,
                "reservation_time": (
                    cancelled.reservation_time
                    .isoformat()
                ),
                "previous_status": (
                    previous_status.value
                ),
                "new_status": (
                    cancelled.status.value
                ),
                "table_id": (
                    str(cancelled.table_id)
                    if cancelled.table_id is not None
                    else None
                ),
                "table_ids": [
                    str(table_id)
                    for table_id in (
                        cancelled.assigned_table_ids or []
                    )
                ],
            },
        )

        try:
            restaurant = None

            if cancelled.restaurant_id:
                restaurant = await self.restaurant_repository.get_by_id(
                    cancelled.restaurant_id
                )

            if restaurant is not None:
                restaurant_timezone = restaurant.timezone or "UTC"
                restaurant_language = restaurant.preferred_language or "en"

                try:
                    localized_time = cancelled.reservation_time.astimezone(
                        ZoneInfo(restaurant_timezone)
                    )
                except Exception:
                    localized_time = cancelled.reservation_time.astimezone(
                        ZoneInfo("UTC")
                    )

                formatted_time = _format_reservation_time_for_language(
                    localized_time,
                    restaurant_language,
                )

                if cancelled.customer_email:
                    await self.email_service.send_reservation_cancellation_confirmation(
                        to_email=cancelled.customer_email,
                        restaurant_name=restaurant.name,
                        customer_name=cancelled.customer_name,
                        reservation_id=str(cancelled.id),
                        reservation_time=formatted_time,
                        party_size=cancelled.party_size,
                        language=restaurant_language,
                    )

                if restaurant.email:
                    await self.email_service.send_restaurant_reservation_cancellation_notification(
                        restaurant_email=restaurant.email,
                        restaurant_name=restaurant.name,
                        customer_name=cancelled.customer_name,
                        customer_email=cancelled.customer_email,
                        customer_phone=cancelled.customer_phone,
                        reservation_time=formatted_time,
                        party_size=cancelled.party_size,
                        table_number=cancelled.table_number,
                        special_requests=cancelled.special_requests,
                        language=restaurant_language,
                    )

        except Exception:
            logger.exception(
                "Reservation cancellation emails failed."
            )

        return cancelled

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

        previous_status = reservation.status

        updates = self._apply_lifecycle_timestamps(
            reservation=reservation,
            updates={"status": ReservationStatus.CANCELLED},
        )

        cancelled = await self.repository.update(
            reservation,
            updates,
        )

        ai_suggestion_repository = AISuggestionRepository(
            self.repository.db,
        )

        ai_suggestion_service = AISuggestionService(
            repository=AISuggestionRepository(
                self.repository.db,
            ),
            reservation_repository=self.repository,
        )

        await ai_suggestion_service.expire_for_reservation(
            cancelled.id,
        )

        await self._expire_pending_ai_suggestions(
            cancelled.restaurant_id,
        )

        await self._record_reservation_event(
            reservation=cancelled,
            event_type=(
                IntelligenceEventType
                .RESERVATION_CANCELLED
            ),
            source=IntelligenceEventSource.MANAGER,
            payload={
                "customer_name": (
                    cancelled.customer_name
                ),
                "party_size": cancelled.party_size,
                "reservation_time": (
                    cancelled.reservation_time
                    .isoformat()
                ),
                "previous_status": (
                    previous_status.value
                ),
                "new_status": (
                    cancelled.status.value
                ),
                "table_id": (
                    str(cancelled.table_id)
                    if cancelled.table_id is not None
                    else None
                ),
                "table_ids": [
                    str(table_id)
                    for table_id in (
                        cancelled.assigned_table_ids or []
                    )
                ],
            },
        )

        logger.info(
            (
                "Reservation cancelled for restaurant owner: "
                "id=%s expired_pending_ai_suggestions=true"
            ),
            cancelled.id,
        )

        return cancelled

    async def assess_modification_availability(
        self,
        *,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None,
        reservation_id: uuid.UUID,
    ) -> BookingAvailabilityOutcome:
        """
        Classify availability for a capacity-affecting modification
        without mutating the reservation or persisting an AI suggestion.

        The existing reservation remains authoritative. Direct availability
        and reoptimization are both assessed against the same reservation id.
        """
        try:
            await self._validate_reservation_time(
                reservation_time,
                restaurant_id,
            )
        except ValidationError:
            return BookingAvailabilityOutcome.UNAVAILABLE

        if restaurant_id is None:
            return BookingAvailabilityOutcome.UNAVAILABLE

        reservation = await self.repository.get_by_id(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
        )

        if reservation is None:
            return BookingAvailabilityOutcome.UNAVAILABLE

        # LAB-012:
        # Once guests are SEATED, their current table assignment represents
        # their real physical location. Another available table must not be
        # treated as a direct reservation modification.
        if reservation.status == ReservationStatus.SEATED:
            if reservation_time != reservation.reservation_time:
                return BookingAvailabilityOutcome.UNAVAILABLE

            current_assignment_supports_party = (
                await self._current_seated_assignment_supports_party_size(
                    reservation=reservation,
                    party_size=party_size,
                )
            )

            if current_assignment_supports_party:
                return BookingAvailabilityOutcome.DIRECT_AVAILABLE

            # LAB-012:
            # The current physical assignment cannot support the requested
            # party size. This is not direct availability. Assess, read-only,
            # whether AIE can move only this seated reservation to a valid
            # destination. Persisting the proposal happens later through the
            # dedicated LIVE authority lane.
            try:
                live_result = await self.intelligence_service.reoptimize(
                    session=self.repository.db,
                    payload=IntelligenceReoptimizeRequest(
                        restaurant_id=restaurant_id,
                        reservation_id=reservation_id,
                        requested_start=reservation.reservation_time,
                        party_size=party_size,
                        duration_minutes=reservation.duration_minutes,
                        buffer_before_minutes=0,
                        buffer_after_minutes=0,
                        preferred_service_area_id=None,
                        max_reservations_to_move=1,
                        max_plans=5,
                    ),
                )

                live_recommendation = live_result.recommended

                if (
                    live_result.available
                    and live_recommendation is not None
                    and live_recommendation.new_reservation_assignment.table_ids
                    and live_recommendation.moved_reservations_count == 0
                ):
                    return (
                        BookingAvailabilityOutcome
                        .LIVE_SERVICE_APPROVAL_REQUIRED
                    )

            except Exception:
                logger.exception(
                    "AIE live seated modification availability assessment "
                    "failed: restaurant_id=%s reservation_id=%s "
                    "party=%d time=%s",
                    restaurant_id,
                    reservation_id,
                    party_size,
                    reservation.reservation_time.isoformat(),
                )

            return BookingAvailabilityOutcome.UNAVAILABLE

        duration_minutes = reservation.duration_minutes

        try:
            direct_result = await self.intelligence_service.optimize(
                session=self.repository.db,
                payload=IntelligenceOptimizeRequest(
                    restaurant_id=restaurant_id,
                    reservation_id=reservation_id,
                    requested_start=reservation_time,
                    party_size=party_size,
                    duration_minutes=duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_alternatives=1,
                ),
            )

            direct_recommendation = direct_result.recommended

            if (
                direct_result.available
                and direct_recommendation is not None
                and direct_recommendation.table_ids
            ):
                return BookingAvailabilityOutcome.DIRECT_AVAILABLE

        except Exception:
            logger.exception(
                "AIE modification direct availability assessment failed: "
                "restaurant_id=%s reservation_id=%s party=%d time=%s",
                restaurant_id,
                reservation_id,
                party_size,
                reservation_time.isoformat(),
            )

            # Preserve the existing technical-failure fallback semantics.
            if await self.check_availability(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
            ):
                return BookingAvailabilityOutcome.DIRECT_AVAILABLE

        try:
            reoptimization_result = await self.intelligence_service.reoptimize(
                session=self.repository.db,
                payload=IntelligenceReoptimizeRequest(
                    restaurant_id=restaurant_id,
                    reservation_id=reservation_id,
                    requested_start=reservation_time,
                    party_size=party_size,
                    duration_minutes=duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_reservations_to_move=1,
                    max_plans=5,
                ),
            )
        except Exception:
            logger.exception(
                "AIE modification reoptimization assessment failed: "
                "restaurant_id=%s reservation_id=%s party=%d time=%s",
                restaurant_id,
                reservation_id,
                party_size,
                reservation_time.isoformat(),
            )
            return BookingAvailabilityOutcome.UNAVAILABLE

        recommendation = reoptimization_result.recommended

        if (
            reoptimization_result.available
            and recommendation is not None
            and recommendation.new_reservation_assignment.table_ids
            and recommendation.moved_reservations_count >= 1
        ):
            return BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE

        return BookingAvailabilityOutcome.UNAVAILABLE

    async def assess_booking_availability(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
        duration_minutes: int = settings.RESERVATION_DURATION_MINUTES,
    ) -> BookingAvailabilityOutcome:
        """
        Classify a request using Alias Intelligence as the primary source of truth.

        The legacy aggregate-capacity check is used only as part of the legacy
        fallback path if AIE itself fails. It must not veto an executable AIE
        assignment.
        """
        try:
            await self._validate_reservation_time(
                reservation_time,
                restaurant_id,
            )
        except ValidationError:
            return BookingAvailabilityOutcome.UNAVAILABLE

        if restaurant_id is None:
            return BookingAvailabilityOutcome.UNAVAILABLE

        try:
            result = await self.intelligence_service.optimize(
                session=self.repository.db,
                payload=IntelligenceOptimizeRequest(
                    restaurant_id=restaurant_id,
                    reservation_id=None,
                    requested_start=reservation_time,
                    party_size=party_size,
                    duration_minutes=duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_alternatives=1,
                ),
            )

            if (
                result.available
                and result.recommended is not None
                and result.recommended.table_ids
            ):
                return BookingAvailabilityOutcome.DIRECT_AVAILABLE

        except Exception:
            logger.exception(
                "AIE booking assessment optimize step failed; trying legacy "
                "direct availability before reoptimization."
            )

            try:
                await self._enforce_capacity(
                    reservation_time=reservation_time,
                    party_size=party_size,
                    restaurant_id=restaurant_id,
                )

                fallback_table_id = await self._assign_available_table(
                    reservation_time=reservation_time,
                    party_size=party_size,
                    restaurant_id=restaurant_id,
                )
            except (ValidationError, ConflictError):
                fallback_table_id = None

            if fallback_table_id is not None:
                return BookingAvailabilityOutcome.DIRECT_AVAILABLE

        if await self._reoptimization_available(
            reservation_time=reservation_time,
            party_size=party_size,
            restaurant_id=restaurant_id,
            duration_minutes=duration_minutes,
        ):
            return BookingAvailabilityOutcome.REOPTIMIZATION_AVAILABLE

        return BookingAvailabilityOutcome.UNAVAILABLE

    async def _reoptimization_available(
        self,
        *,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None,
        duration_minutes: int,
    ) -> bool:
        if restaurant_id is None:
            return False

        try:
            result = await self.intelligence_service.reoptimize(
                session=self.repository.db,
                payload=IntelligenceReoptimizeRequest(
                    restaurant_id=restaurant_id,
                    reservation_id=None,
                    requested_start=reservation_time,
                    party_size=party_size,
                    duration_minutes=duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_reservations_to_move=1,
                    max_plans=5,
                ),
            )
        except Exception:
            logger.exception(
                "AIE reoptimization assessment failed: restaurant_id=%s "
                "party=%d time=%s",
                restaurant_id,
                party_size,
                reservation_time.isoformat(),
            )
            return False

        recommendation = result.recommended

        return bool(
            result.available
            and recommendation is not None
            and recommendation.new_reservation_assignment.table_ids
            and recommendation.moved_reservations_count >= 1
        )

    async def check_availability(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
        reservation_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Return whether the requested slot has a direct valid assignment.

        Alias Intelligence is the primary source of truth so availability
        uses the same single-table and multi-table optimization logic used
        when a reservation is created. The legacy allocator and aggregate
        capacity check are retained only as resilience fallbacks if the
        intelligence service itself fails.
        """
        try:
            await self._validate_reservation_time(
                reservation_time,
                restaurant_id,
            )
        except ValidationError:
            return False

        if restaurant_id is not None:
            try:
                result = await self.intelligence_service.optimize(
                    session=self.repository.db,
                    payload=IntelligenceOptimizeRequest(
                        restaurant_id=restaurant_id,
                        reservation_id=reservation_id,
                        requested_start=reservation_time,
                        party_size=party_size,
                        duration_minutes=(
                            settings.RESERVATION_DURATION_MINUTES
                        ),
                        buffer_before_minutes=0,
                        buffer_after_minutes=0,
                        preferred_service_area_id=None,
                        max_alternatives=1,
                    ),
                )

                recommendation = result.recommended

                return bool(
                    result.available
                    and recommendation is not None
                    and recommendation.table_ids
                )

            except Exception:
                logger.exception(
                    (
                        "AIE availability check failed. "
                        "Falling back to legacy single-table availability."
                    )
                )

        try:
            await self._enforce_capacity(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
                exclude_id=reservation_id,
            )

            fallback_table_id = await self._assign_available_table(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
            )
        except (ValidationError, ConflictError):
            return False

        return fallback_table_id is not None

    async def suggest_alternative_slots(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
        reservation_id: uuid.UUID | None = None,
    ) -> list[datetime]:
        """
        Suggest nearby directly bookable slots using the same AIE-aware
        availability logic as the requested slot.
        """
        offsets = [-90, -60, -30, 30, 60, 90]
        suggestions: list[datetime] = []

        for minutes in offsets:
            candidate = reservation_time + timedelta(minutes=minutes)

            if await self.check_availability(
                reservation_time=candidate,
                party_size=party_size,
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
            ):
                suggestions.append(candidate)

                if len(suggestions) >= 3:
                    break

        return suggestions


    async def _assign_tables_with_aie(
        self,
        reservation_time: datetime,
        party_size: int,
        restaurant_id: uuid.UUID | None = None,
        duration_minutes: int = settings.RESERVATION_DURATION_MINUTES,
        reservation_id: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID | None, list[uuid.UUID]]:
        """
        Use AIE to choose the best valid single-table or multi-table
        assignment for a new reservation.

        Falls back to the legacy single-table allocator if AIE cannot
        produce a recommendation.
        """

        if restaurant_id is None:
            return None, []

        try:
            result = await self.intelligence_service.optimize(
                session=self.repository.db,
                payload=IntelligenceOptimizeRequest(
                    restaurant_id=restaurant_id,
                    reservation_id=reservation_id,
                    requested_start=reservation_time,
                    party_size=party_size,
                    duration_minutes=duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_alternatives=3,
                ),
            )

            recommendation = result.recommended

            if (
                result.available
                and recommendation is not None
                and recommendation.table_ids
            ):
                table_ids = list(
                    dict.fromkeys(
                        recommendation.table_ids,
                    )
                )

                primary_table_id = table_ids[0]

                logger.info(
                    (
                        "AIE automatic assignment: "
                        "restaurant_id=%s party=%d tables=%s score=%.2f"
                    ),
                    restaurant_id,
                    party_size,
                    [str(table_id) for table_id in table_ids],
                    recommendation.score,
                )

                return primary_table_id, table_ids

            # AIE completed successfully but found no direct executable
            # assignment. This result is authoritative and must not be
            # contradicted by the legacy allocator.
            logger.info(
                (
                    "AIE found no direct assignment: "
                    "restaurant_id=%s reservation_id=%s "
                    "party=%d time=%s"
                ),
                restaurant_id,
                reservation_id,
                party_size,
                reservation_time.isoformat(),
            )

            return None, []

        except Exception:
            logger.exception(
                (
                    "AIE automatic assignment failed. "
                    "Falling back to legacy single-table assignment."
                )
            )

        try:
            fallback_table_id = await self._assign_available_table(
                reservation_time=reservation_time,
                party_size=party_size,
                restaurant_id=restaurant_id,
            )
        except ConflictError:
            logger.info(
                (
                    "No direct table assignment available. "
                    "Creating reservation without a table so that "
                    "assisted reoptimization can be proposed: "
                    "restaurant_id=%s party=%d time=%s"
                ),
                restaurant_id,
                party_size,
                reservation_time.isoformat(),
            )

            return None, []

        if fallback_table_id is None:
            logger.info(
                (
                    "No suitable single table exists. "
                    "Creating reservation without an assignment: "
                    "restaurant_id=%s party=%d time=%s"
                ),
                restaurant_id,
                party_size,
                reservation_time.isoformat(),
            )

            return None, []

        return fallback_table_id, [fallback_table_id]
    
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
        duration_minutes: int = settings.RESERVATION_DURATION_MINUTES,
        exclude_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        if restaurant_id is None:
            raise ValidationError(
                "Restaurant is required to select a table."
            )

        table = await self.table_repository.get_by_id(
            table_id=table_id,
            restaurant_id=restaurant_id,
        )

        if table is None or not table.is_active:
            raise ValidationError(
                "Selected table was not found or is inactive."
            )

        if table.seats < party_size:
            raise ValidationError(
                "Selected table does not have enough seats "
                "for this party size."
            )

        requested_start = reservation_time
        requested_end = reservation_time + timedelta(
            minutes=duration_minutes
        )

        # Reservations can last up to 300 minutes according to the schema.
        # We load a sufficiently wide candidate window and then perform the
        # exact overlap check in Python.
        lookup_start = requested_start - timedelta(minutes=300)

        concurrent = await self.repository.list_in_window(
            start=lookup_start,
            end=requested_end,
            restaurant_id=restaurant_id,
        )

        for existing in concurrent:
            if exclude_id is not None and existing.id == exclude_id:
                continue

            if existing.status in {
                ReservationStatus.CANCELLED,
                ReservationStatus.COMPLETED,
                ReservationStatus.NO_SHOW,
            }:
                continue

            existing_table_ids = set(
                existing.assigned_table_ids
                or (
                    [existing.table_id]
                    if existing.table_id is not None
                    else []
                )
            )

            if table_id not in existing_table_ids:
                continue

            existing_start = existing.reservation_time
            existing_end = (
                existing.reservation_time
                + timedelta(
                    minutes=existing.duration_minutes,
                )
            )

            overlaps = (
                existing_start < requested_end
                and existing_end > requested_start
            )

            if overlaps:
                raise ConflictError(
                    "Selected table is not available during "
                    "this reservation time."
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




