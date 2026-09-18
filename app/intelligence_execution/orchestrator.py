from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
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

    async def apply_reoptimization(
        self,
        *,
        session: AsyncSession,
        payload: IntelligenceApplyReoptimizationRequest,
        allowed_restaurant_ids: list[UUID],
        source: IntelligenceEventSource,
        actor_user_id: UUID | None = None,
    ) -> IntelligenceApplyReoptimizationResponse:
        reservation_repository = ReservationRepository(session)
        suggestion_repository = AISuggestionRepository(session)

        if payload.suggestion_id is not None:
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
            )

        result = await self.intelligence_service.apply_reoptimization(
            session=session,
            payload=payload,
            allowed_restaurant_ids=allowed_restaurant_ids,
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
            repository=IntelligenceEventRepository(session),
        ).record(
            restaurant_id=audit_reservation.restaurant_id,
            event_type=IntelligenceEventType.SEATING_PLAN_APPLIED,
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
                    for table_id in result.new_reservation_table_ids
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
                        "table_numbers": move.table_numbers,
                    }
                    for move in result.applied_moves
                ],
                "mode": result.mode,
                "applied": result.applied,
            },
        )

        return result