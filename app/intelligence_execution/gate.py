from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.models.ai_suggestion import (
    AISuggestionStatus,
    AISuggestionType,
)
from app.repositories.ai_suggestion_repository import (
    AISuggestionRepository,
)


class IntelligenceExecutionGate:
    def __init__(
        self,
        *,
        repository: AISuggestionRepository,
    ) -> None:
        self.repository = repository

    async def validate_reoptimization(
        self,
        *,
        suggestion_id: UUID,
        allowed_restaurant_ids: list[UUID],
        new_reservation_id: UUID,
        new_reservation_table_ids: list[UUID],
        new_reservation_primary_table_id: UUID,
        moves: list[dict],
    ) -> None:
        suggestion = await self.repository.get_by_id(
            suggestion_id=suggestion_id,
            restaurant_ids=allowed_restaurant_ids,
        )

        if suggestion is None:
            raise NotFoundError(
                f"AI suggestion {suggestion_id} not found"
            )

        if (
            suggestion.suggestion_type
            != AISuggestionType.REOPTIMIZATION
        ):
            raise ValidationError(
                "AI suggestion is not a reoptimization suggestion."
            )

        if (
            suggestion.status
            != AISuggestionStatus.PENDING
        ):
            raise ValidationError(
                "AI suggestion is no longer pending."
            )

        now = datetime.now(
            timezone.utc,
        )

        if (
            suggestion.expires_at is not None
            and suggestion.expires_at <= now
        ):
            raise ValidationError(
                "AI suggestion has expired."
            )

        if (
            suggestion.reservation_id
            != new_reservation_id
        ):
            raise ValidationError(
                "AI suggestion does not match the reservation."
            )

        payload = suggestion.payload or {}

        plan = (
            payload.get("plan")
            or {}
        )

        assignment = (
            plan.get(
                "new_reservation_assignment"
            )
            or {}
        )

        stored_table_id_list = [
            UUID(table_id)
            for table_id in (
                assignment.get("table_ids")
                or []
            )
        ]

        if not stored_table_id_list:
            raise ValidationError(
                "AI suggestion does not contain "
                "a valid table assignment."
            )

        stored_table_ids = set(
            stored_table_id_list
        )

        requested_table_ids = set(
            new_reservation_table_ids
        )

        if (
            stored_table_ids
            != requested_table_ids
        ):
            raise ValidationError(
                "Requested tables do not match "
                "the AI suggestion."
            )

        if (
            new_reservation_primary_table_id
            != stored_table_id_list[0]
        ):
            raise ValidationError(
                "Primary table does not match "
                "the AI suggestion."
            )

        stored_moves = (
            plan.get("moves")
            or []
        )

        stored_move_map = {
            UUID(
                move["reservation_id"]
            ): {
                UUID(table_id)
                for table_id in (
                    move.get("to_table_ids")
                    or []
                )
            }
            for move in stored_moves
        }

        stored_move_primary_map = {
            UUID(
                move["reservation_id"]
            ): UUID(
                move["to_table_ids"][0]
            )
            for move in stored_moves
            if move.get("to_table_ids")
        }

        requested_move_map = {
            move["reservation_id"]: set(
                move["to_table_ids"]
            )
            for move in moves
        }

        if (
            stored_move_map
            != requested_move_map
        ):
            raise ValidationError(
                "Requested reservation moves do not "
                "match the AI suggestion."
            )

        requested_move_primary_map = {
            move["reservation_id"]: (
                move["primary_table_id"]
            )
            for move in moves
        }

        if (
            stored_move_primary_map
            != requested_move_primary_map
        ):
            raise ValidationError(
                "Move primary tables do not match "
                "the AI suggestion."
            )