from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
    IntelligenceApplyLiveSeatedModificationRequest,
    IntelligenceApplyLiveSeatedModificationResponse,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
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
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)
from app.repositories.reservation_repository import (
    ReservationRepository,
)
from app.repositories.restaurant_repository import (
    RestaurantRepository,
)
from app.repositories.table_repository import (
    TableRepository,
)
from app.services.email_service import EmailService
from app.services.ai_suggestion_service import (
    AISuggestionService,
)

from .gate import IntelligenceExecutionGate


class IntelligenceExecutionOrchestrator:
    def __init__(
        self,
        *,
        intelligence_service: IntelligenceOptimizationService | None = None,
    ) -> None:
        self.intelligence_service = (
            intelligence_service
            or IntelligenceOptimizationService()
        )

    @staticmethod
    def _build_current_reservation_state(
        reservation,
    ) -> dict:
        status = reservation.status

        if hasattr(status, "value"):
            status = status.value

        reservation_time = (
            reservation.reservation_time
        )

        if hasattr(
            reservation_time,
            "isoformat",
        ):
            reservation_time = (
                reservation_time.isoformat()
            )

        primary_table_id = getattr(
            reservation,
            "table_id",
            None,
        )

        assigned_table_ids = getattr(
            reservation,
            "assigned_table_ids",
            None,
        )

        if assigned_table_ids is None:
            table_ids = (
                [primary_table_id]
                if primary_table_id is not None
                else []
            )
        else:
            table_ids = list(
                assigned_table_ids
            )

        return {
            "id": str(reservation.id),
            "party_size": reservation.party_size,
            "reservation_time": reservation_time,
            "duration_minutes": (
                reservation.duration_minutes
            ),
            "status": status,
            "primary_table_id": (
                str(primary_table_id)
                if primary_table_id is not None
                else None
            ),
            "table_ids": [
                str(table_id)
                for table_id in table_ids
            ],
        }

    async def apply_live_seated_modification(
        self,
        *,
        session: AsyncSession,
        payload: IntelligenceApplyLiveSeatedModificationRequest,
        allowed_restaurant_ids: list[UUID],
        source: IntelligenceEventSource,
        actor_user_id: UUID | None = None,
    ) -> IntelligenceApplyLiveSeatedModificationResponse:
        # Local import avoids ReservationService <-> orchestrator
        # module-level circular import.
        from app.services.reservation_service import ReservationService

        reservation_repository = ReservationRepository(
            session
        )
        suggestion_repository = AISuggestionRepository(
            session
        )

        current_reservation = (
            await reservation_repository.get_by_id_for_restaurants(
                reservation_id=payload.reservation_id,
                restaurant_ids=allowed_restaurant_ids,
            )
        )

        if current_reservation is None:
            raise ValidationError(
                "Reservation could not be resolved "
                "for live seated modification validation."
            )

        current_reservation_state = (
            self._build_current_reservation_state(
                current_reservation
            )
        )

        suggestion = await suggestion_repository.get_by_id(
            payload.suggestion_id,
            restaurant_ids=allowed_restaurant_ids,
        )

        if suggestion is None:
            raise ValidationError(
                "Live seated modification suggestion "
                "could not be resolved."
            )

        await IntelligenceExecutionGate(
            repository=suggestion_repository,
        ).validate_live_seated_modification(
            suggestion_id=payload.suggestion_id,
            allowed_restaurant_ids=allowed_restaurant_ids,
            reservation_id=payload.reservation_id,
            destination_table_ids=(
                payload.destination_table_ids
            ),
            destination_primary_table_id=(
                payload.destination_primary_table_id
            ),
            current_reservation_state=(
                current_reservation_state
            ),
        )

        suggestion_payload = suggestion.payload or {}
        requested_modification = (
            suggestion_payload.get(
                "requested_modification"
            )
            or {}
        )
        requested_party_size = (
            requested_modification.get(
                "party_size"
            )
        )

        if (
            isinstance(requested_party_size, bool)
            or not isinstance(requested_party_size, int)
            or requested_party_size < 1
        ):
            raise ValidationError(
                "Live seated modification suggestion has "
                "an invalid requested party size."
            )

        reservation_service = ReservationService(
            repository=reservation_repository,
            restaurant_repository=RestaurantRepository(
                session
            ),
            table_repository=TableRepository(
                session
            ),
            email_service=EmailService(),
            intelligence_service=self.intelligence_service,
        )

        original_table_ids = list(
            getattr(
                current_reservation,
                "assigned_table_ids",
                None,
            )
            or (
                [current_reservation.table_id]
                if getattr(
                    current_reservation,
                    "table_id",
                    None,
                ) is not None
                else []
            )
        )

        result = await (
            reservation_service
            .apply_live_seated_modification_for_restaurants(
                reservation_id=payload.reservation_id,
                restaurant_ids=allowed_restaurant_ids,
                requested_party_size=requested_party_size,
                destination_table_ids=(
                    payload.destination_table_ids
                ),
                destination_primary_table_id=(
                    payload.destination_primary_table_id
                ),
            )
        )

        accepted_suggestion = await AISuggestionService(
            repository=suggestion_repository,
            reservation_repository=reservation_repository,
            intelligence_service=self.intelligence_service,
        ).accept(
            suggestion_id=payload.suggestion_id,
            restaurant_ids=allowed_restaurant_ids,
            source=source,
        )

        if accepted_suggestion is None:
            raise ValidationError(
                "Live seated modification suggestion "
                "could not be accepted."
            )

        table_ids = list(
            getattr(
                result,
                "assigned_table_ids",
                None,
            )
            or (
                [result.table_id]
                if getattr(
                    result,
                    "table_id",
                    None,
                ) is not None
                else []
            )
        )

        table_numbers = []
        for assignment in (
            getattr(
                result,
                "table_assignments",
                None,
            )
            or []
        ):
            table = getattr(
                assignment,
                "table",
                None,
            )
            if table is not None:
                table_numbers.append(
                    str(table.table_number)
                )

        await IntelligenceEventService(
            repository=IntelligenceEventRepository(
                session
            ),
        ).record(
            restaurant_id=result.restaurant_id,
            event_type=(
                IntelligenceEventType.SEATING_PLAN_APPLIED
            ),
            source=source,
            entity_type="reservation",
            entity_id=result.id,
            actor_user_id=actor_user_id,
            payload={
                "suggestion_id": str(
                    payload.suggestion_id
                ),
                "requested_party_size": (
                    requested_party_size
                ),
                "from_table_ids": [
                    str(table_id)
                    for table_id in original_table_ids
                ],
                "to_table_ids": [
                    str(table_id)
                    for table_id in table_ids
                ],
                "status": (
                    result.status.value
                    if hasattr(
                        result.status,
                        "value",
                    )
                    else str(result.status)
                ),
                "mode": "assisted_live_service",
                "applied": True,
            },
        )

        status = result.status
        if hasattr(status, "value"):
            status = status.value

        return IntelligenceApplyLiveSeatedModificationResponse(
            reservation_id=result.id,
            restaurant_id=result.restaurant_id,
            party_size=result.party_size,
            primary_table_id=result.table_id,
            table_ids=table_ids,
            table_numbers=table_numbers,
            status=status,
        )

    async def apply_reoptimization(
        self,
        *,
        session: AsyncSession,
        payload: IntelligenceApplyReoptimizationRequest,
        allowed_restaurant_ids: list[UUID],
        source: IntelligenceEventSource,
        actor_user_id: UUID | None = None,
    ) -> IntelligenceApplyReoptimizationResponse:
        reservation_repository = ReservationRepository(
            session
        )
        suggestion_repository = AISuggestionRepository(
            session
        )

        if payload.suggestion_id is not None:
            current_reservation = (
                await reservation_repository.get_by_id_for_restaurants(
                    reservation_id=payload.new_reservation_id,
                    restaurant_ids=allowed_restaurant_ids,
                )
            )

            if current_reservation is None:
                raise ValidationError(
                    "Reservation could not be resolved "
                    "for reoptimization validation."
                )

            current_reservation_state = (
                self._build_current_reservation_state(
                    current_reservation
                )
            )

            await IntelligenceExecutionGate(
                repository=suggestion_repository,
            ).validate_reoptimization(
                suggestion_id=payload.suggestion_id,
                allowed_restaurant_ids=allowed_restaurant_ids,
                new_reservation_id=payload.new_reservation_id,
                new_reservation_table_ids=(
                    payload.new_reservation_table_ids
                ),
                new_reservation_primary_table_id=(
                    payload.new_reservation_primary_table_id
                ),
                moves=[
                    move.model_dump()
                    for move in payload.moves
                ],
                current_reservation_state=(
                    current_reservation_state
                ),
            )

        result = (
            await self.intelligence_service.apply_reoptimization(
                session=session,
                payload=payload,
                allowed_restaurant_ids=allowed_restaurant_ids,
            )
        )

        if payload.suggestion_id is not None:
            accepted_suggestion = await AISuggestionService(
                repository=suggestion_repository,
                reservation_repository=reservation_repository,
                intelligence_service=self.intelligence_service,
            ).accept(
                suggestion_id=payload.suggestion_id,
                restaurant_ids=allowed_restaurant_ids,
                source=source,
            )

            if accepted_suggestion is None:
                raise ValidationError(
                    "AI suggestion could not be accepted."
                )

        audit_reservation = (
            await reservation_repository.get_by_id_for_restaurants(
                reservation_id=payload.new_reservation_id,
                restaurant_ids=allowed_restaurant_ids,
            )
        )

        if (
            audit_reservation is None
            or audit_reservation.restaurant_id is None
        ):
            raise ValidationError(
                "Applied reservation could not be resolved for audit."
            )

        await IntelligenceEventService(
            repository=IntelligenceEventRepository(
                session
            ),
        ).record(
            restaurant_id=audit_reservation.restaurant_id,
            event_type=(
                IntelligenceEventType.SEATING_PLAN_APPLIED
            ),
            source=source,
            entity_type="reservation",
            entity_id=payload.new_reservation_id,
            actor_user_id=actor_user_id,
            payload={
                "suggestion_id": (
                    str(payload.suggestion_id)
                    if payload.suggestion_id is not None
                    else None
                ),
                "new_reservation_primary_table_id": str(
                    result.new_reservation_primary_table_id
                ),
                "new_reservation_table_ids": [
                    str(table_id)
                    for table_id
                    in result.new_reservation_table_ids
                ],
                "new_reservation_table_numbers": (
                    result.new_reservation_table_numbers
                ),
                "moves": [
                    {
                        "reservation_id": str(
                            move.reservation_id
                        ),
                        "primary_table_id": str(
                            move.primary_table_id
                        ),
                        "table_ids": [
                            str(table_id)
                            for table_id in move.table_ids
                        ],
                        "table_numbers": (
                            move.table_numbers
                        ),
                    }
                    for move in result.applied_moves
                ],
                "mode": result.mode,
                "applied": result.applied,
            },
        )

        return result