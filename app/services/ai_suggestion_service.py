from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.intelligence.schemas import (
    IntelligenceReoptimizeRequest,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.models.ai_suggestion import (
    AISuggestion,
    AISuggestionStatus,
    AISuggestionType,
)
from app.models.reservation import (
    Reservation,
    ReservationStatus,
)
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)
from app.repositories.reservation_repository import (
    ReservationRepository,
)

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_events.service import (
    IntelligenceEventService,
)


class AISuggestionService:
    def __init__(
        self,
        repository: AISuggestionRepository,
        reservation_repository: ReservationRepository,
        intelligence_service: (
            IntelligenceOptimizationService | None
        ) = None,
    ) -> None:
        self.repository = repository
        self.reservation_repository = (
            reservation_repository
        )
        self.intelligence_service = (
            intelligence_service
            or IntelligenceOptimizationService()
        )

    async def _record_ai_suggestion_event(
        self,
        *,
        suggestion: AISuggestion,
        event_type: IntelligenceEventType,
        source: IntelligenceEventSource,
        previous_status: AISuggestionStatus | None = None,
    ) -> None:
        payload = suggestion.payload or {}
        plan = payload.get("plan") or {}
        reservation_payload = (
            payload.get("reservation") or {}
        )
        assignment = (
            plan.get(
                "new_reservation_assignment",
            )
            or {}
        )

        service = IntelligenceEventService(
            IntelligenceEventRepository(
                self.repository.db,
            )
        )

        await service.record(
            restaurant_id=suggestion.restaurant_id,
            event_type=event_type,
            source=source,
            entity_type="ai_suggestion",
            entity_id=suggestion.id,
            payload={
                "suggestion_id": str(
                    suggestion.id,
                ),
                "reservation_id": (
                    str(suggestion.reservation_id)
                    if suggestion.reservation_id
                    is not None
                    else None
                ),
                "suggestion_type": (
                    suggestion.suggestion_type.value
                ),
                "status": suggestion.status.value,
                "previous_status": (
                    previous_status.value
                    if previous_status is not None
                    else None
                ),
                "score": suggestion.score,
                "is_read": suggestion.is_read,
                "customer_name": (
                    reservation_payload.get(
                        "customer_name",
                    )
                ),
                "party_size": (
                    reservation_payload.get(
                        "party_size",
                    )
                ),
                "moved_reservations_count": (
                    plan.get(
                        "moved_reservations_count",
                        0,
                    )
                ),
                "total_seat_waste": (
                    plan.get(
                        "total_seat_waste",
                        0,
                    )
                ),
                "destination_table_ids": (
                    assignment.get(
                        "table_ids",
                        [],
                    )
                ),
                "destination_table_numbers": (
                    assignment.get(
                        "table_numbers",
                        [],
                    )
                ),
                "engine_version": payload.get(
                    "engine_version",
                ),
                "mode": payload.get("mode"),
            },
            metadata={
                "service": (
                    "ai_suggestion_service"
                ),
                "event_schema": (
                    f"{event_type.value}.v1"
                ),
            },
        )

    async def analyze_reservation(
        self,
        reservation: Reservation,
    ) -> AISuggestion | None:
        """
        Analyze one reservation and persist a live AI suggestion
        only when Alias finds a meaningful reoptimization plan.

        Direct assignments with zero moves are not stored as live
        suggestions because they do not require manager attention.
        """
        if reservation.restaurant_id is None:
            return None

        if reservation.status in {
            ReservationStatus.CANCELLED,
            ReservationStatus.COMPLETED,
            ReservationStatus.NO_SHOW,
        }:
            return None

        existing = (
            await self.repository
            .find_pending_for_reservation(
                reservation.id,
            )
        )

        if existing is not None:
            return existing

        result = (
            await self.intelligence_service.reoptimize(
                session=self.repository.db,
                payload=IntelligenceReoptimizeRequest(
                    restaurant_id=(
                        reservation.restaurant_id
                    ),
                    reservation_id=reservation.id,
                    requested_start=(
                        reservation.reservation_time
                    ),
                    party_size=reservation.party_size,
                    duration_minutes=(
                        reservation.duration_minutes
                    ),
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_reservations_to_move=1,
                    max_plans=5,
                ),
            )
        )

        plan = result.recommended

        if (
            not result.available
            or plan is None
            or plan.moved_reservations_count < 1
        ):
            return None

        assignment = (
            plan.new_reservation_assignment
        )

        table_label = self._format_tables(
            assignment.table_numbers,
        )

        move_count = (
            plan.moved_reservations_count
        )

        title = "Better seating plan available"

        description = (
            f"Alias can seat "
            f"{reservation.customer_name} at "
            f"{table_label} by moving "
            f"{move_count} existing "
            f"{'reservation' if move_count == 1 else 'reservations'}."
        )

        payload = {
            "reservation": {
                "id": str(reservation.id),
                "customer_name": (
                    reservation.customer_name
                ),
                "party_size": (
                    reservation.party_size
                ),
                "reservation_time": (
                    reservation
                    .reservation_time
                    .isoformat()
                ),
                "duration_minutes": (
                    reservation.duration_minutes
                ),
            },
            "plan": plan.model_dump(
                mode="json",
            ),
            "engine_version": (
                result.engine_version
            ),
            "mode": result.mode,
        }

        suggestion = AISuggestion(
            restaurant_id=(
                reservation.restaurant_id
            ),
            reservation_id=reservation.id,
            suggestion_type=(
                AISuggestionType.REOPTIMIZATION
            ),
            status=AISuggestionStatus.PENDING,
            title=title,
            description=description,
            score=plan.score,
            payload=payload,
            is_read=False,
            expires_at=(
                reservation.reservation_time
                + timedelta(
                    minutes=(
                        reservation
                        .duration_minutes
                    ),
                )
            ),
        )

        created = await self.repository.create(
            suggestion,
        )

        await self._record_ai_suggestion_event(
            suggestion=created,
            event_type=(
                IntelligenceEventType
                .AI_SUGGESTION_CREATED
            ),
            source=IntelligenceEventSource.AI,
        )

        return created

    async def analyze_reservation_by_id(
        self,
        reservation_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> AISuggestion | None:
        reservation = (
            await self.reservation_repository
            .get_by_id_for_restaurants(
                reservation_id=reservation_id,
                restaurant_ids=restaurant_ids,
            )
        )

        if reservation is None:
            return None

        return await self.analyze_reservation(
            reservation,
        )

    async def list_pending(
        self,
        restaurant_ids: list[uuid.UUID],
        limit: int = 50,
    ) -> list[AISuggestion]:
        return await self.repository.list_pending(
            restaurant_ids=restaurant_ids,
            limit=limit,
        )

    async def mark_read(
        self,
        suggestion_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> AISuggestion | None:
        suggestion = (
            await self.repository.get_by_id(
                suggestion_id=suggestion_id,
                restaurant_ids=restaurant_ids,
            )
        )

        if suggestion is None:
            return None

        was_already_read = suggestion.is_read

        updated = await self.repository.mark_read(
            suggestion,
        )

        if not was_already_read:
            await self._record_ai_suggestion_event(
                suggestion=updated,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_READ
                ),
                source=(
                    IntelligenceEventSource.MANAGER
                ),
            )

        return updated

    async def dismiss(
        self,
        suggestion_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> AISuggestion | None:
        suggestion = (
            await self.repository.get_by_id(
                suggestion_id=suggestion_id,
                restaurant_ids=restaurant_ids,
            )
        )

        if suggestion is None:
            return None

        if (
            suggestion.status
            != AISuggestionStatus.PENDING
        ):
            return suggestion

        previous_status = suggestion.status

        updated = await self.repository.update_status(
            suggestion=suggestion,
            status=AISuggestionStatus.DISMISSED,
        )

        await self._record_ai_suggestion_event(
            suggestion=updated,
            event_type=(
                IntelligenceEventType
                .AI_SUGGESTION_DISMISSED
            ),
            source=IntelligenceEventSource.MANAGER,
            previous_status=previous_status,
        )

        return updated

    async def accept(
        self,
        suggestion_id: uuid.UUID,
        restaurant_ids: list[uuid.UUID],
    ) -> AISuggestion | None:
        suggestion = (
            await self.repository.get_by_id(
                suggestion_id=suggestion_id,
                restaurant_ids=restaurant_ids,
            )
        )

        if suggestion is None:
            return None

        if (
            suggestion.status
            != AISuggestionStatus.PENDING
        ):
            return suggestion

        previous_status = suggestion.status

        updated = await self.repository.update_status(
            suggestion=suggestion,
            status=AISuggestionStatus.ACCEPTED,
        )

        await self._record_ai_suggestion_event(
            suggestion=updated,
            event_type=(
                IntelligenceEventType
                .AI_SUGGESTION_ACCEPTED
            ),
            source=IntelligenceEventSource.MANAGER,
            previous_status=previous_status,
        )

        return updated

    async def expire_for_reservation(
        self,
        reservation_id: uuid.UUID,
    ) -> int:
        return await (
            self.repository
            .expire_pending_for_reservation(
                reservation_id,
            )
        )

    async def expire_outdated(
        self,
        restaurant_ids: list[uuid.UUID],
    ) -> int:
        """
        Mark already-expired pending suggestions as expired.

        This first version operates on the current pending list and
        can later be moved into a scheduled cleanup task.
        """
        pending = await self.repository.list_pending(
            restaurant_ids=restaurant_ids,
            limit=500,
        )

        now = datetime.now(timezone.utc)
        expired_count = 0

        for suggestion in pending:
            if (
                suggestion.expires_at is not None
                and suggestion.expires_at <= now
            ):
                previous_status = suggestion.status

                updated = await self.repository.update_status(
                    suggestion=suggestion,
                    status=AISuggestionStatus.EXPIRED,
                )

                await self._record_ai_suggestion_event(
                    suggestion=updated,
                    event_type=(
                        IntelligenceEventType
                        .AI_SUGGESTION_EXPIRED
                    ),
                    source=IntelligenceEventSource.SYSTEM,
                    previous_status=previous_status,
                )

                expired_count += 1

        return expired_count

    async def expire_for_restaurant(
        self,
        restaurant_id: uuid.UUID,
    ) -> int:
        return await (
            self.repository
            .expire_pending_for_restaurant(
                restaurant_id,
            )
        )

    @staticmethod
    def _format_tables(
        table_numbers: list[str],
    ) -> str:
        if not table_numbers:
            return "the recommended tables"

        joined = " + ".join(
            table_numbers,
        )

        prefix = (
            "Table"
            if len(table_numbers) == 1
            else "Tables"
        )

        return f"{prefix} {joined}"