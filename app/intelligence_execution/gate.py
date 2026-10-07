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
        current_reservation_state: dict | None = None,
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

        requested_modification = (
            payload.get("requested_modification")
        )

        # Legacy reoptimization suggestions do not represent a
        # reservation modification. Preserve their existing execution
        # contract unchanged.
        if requested_modification is None:
            return

        original_reservation = (
            payload.get("reservation")
        )

        if not isinstance(
            original_reservation,
            dict,
        ):
            raise ValidationError(
                "Modification reoptimization does not contain "
                "the original reservation state."
            )

        if not isinstance(
            current_reservation_state,
            dict,
        ):
            raise ValidationError(
                "Modification reoptimization cannot verify "
                "the original reservation state."
            )

        stored_reservation_id = (
            original_reservation.get("id")
        )

        if (
            stored_reservation_id is None
            or str(stored_reservation_id)
            != str(new_reservation_id)
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state does not match the reservation."
            )

        current_reservation_id = (
            current_reservation_state.get("id")
        )

        if (
            current_reservation_id is None
            or str(current_reservation_id)
            != str(new_reservation_id)
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state no longer matches the current reservation."
            )

        stored_party_size = (
            original_reservation.get(
                "party_size"
            )
        )

        current_party_size = (
            current_reservation_state.get(
                "party_size"
            )
        )

        if (
            stored_party_size
            != current_party_size
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: party size changed."
            )

        stored_reservation_time = (
            original_reservation.get(
                "reservation_time"
            )
        )

        current_reservation_time = (
            current_reservation_state.get(
                "reservation_time"
            )
        )

        if (
            stored_reservation_time
            != current_reservation_time
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: reservation time changed."
            )

        stored_duration_minutes = (
            original_reservation.get(
                "duration_minutes"
            )
        )

        current_duration_minutes = (
            current_reservation_state.get(
                "duration_minutes"
            )
        )

        if (
            stored_duration_minutes
            != current_duration_minutes
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: duration changed."
            )

        stored_status = (
            original_reservation.get(
                "status"
            )
        )

        current_status = (
            current_reservation_state.get(
                "status"
            )
        )

        if (
            stored_status
            != current_status
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: status changed."
            )

        stored_primary_table_id = (
            original_reservation.get(
                "primary_table_id"
            )
        )

        current_primary_table_id = (
            current_reservation_state.get(
                "primary_table_id"
            )
        )

        if (
            (
                str(stored_primary_table_id)
                if stored_primary_table_id is not None
                else None
            )
            != (
                str(current_primary_table_id)
                if current_primary_table_id is not None
                else None
            )
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: primary table changed."
            )

        stored_original_table_ids = {
            str(table_id)
            for table_id in (
                original_reservation.get(
                    "table_ids"
                )
                or []
            )
        }

        current_original_table_ids = {
            str(table_id)
            for table_id in (
                current_reservation_state.get(
                    "table_ids"
                )
                or []
            )
        }

        if (
            stored_original_table_ids
            != current_original_table_ids
        ):
            raise ValidationError(
                "Modification reoptimization original reservation "
                "state is stale: table assignments changed."
            )


    async def validate_live_seated_modification(
        self,
        *,
        suggestion_id: UUID,
        allowed_restaurant_ids: list[UUID],
        reservation_id: UUID,
        destination_table_ids: list[UUID],
        destination_primary_table_id: UUID,
        current_reservation_state: dict | None = None,
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
            != AISuggestionType.LIVE_SEATED_MODIFICATION
        ):
            raise ValidationError(
                "AI suggestion is not a live seated modification."
            )

        if suggestion.status != AISuggestionStatus.PENDING:
            raise ValidationError(
                "AI suggestion is no longer pending."
            )

        now = datetime.now(timezone.utc)

        if (
            suggestion.expires_at is not None
            and suggestion.expires_at <= now
        ):
            raise ValidationError(
                "AI suggestion has expired."
            )

        if suggestion.reservation_id != reservation_id:
            raise ValidationError(
                "AI suggestion does not match the reservation."
            )

        payload = suggestion.payload or {}
        plan = payload.get("plan") or {}
        assignment = (
            plan.get("new_reservation_assignment")
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
                "Live seated modification does not contain "
                "a valid table assignment."
            )

        if (
            set(stored_table_id_list)
            != set(destination_table_ids)
        ):
            raise ValidationError(
                "Requested tables do not match "
                "the live seated modification."
            )

        if (
            destination_primary_table_id
            != stored_table_id_list[0]
        ):
            raise ValidationError(
                "Primary table does not match "
                "the live seated modification."
            )

        moves = plan.get("moves") or []

        if moves:
            raise ValidationError(
                "Live seated modification cannot move "
                "other reservations."
            )

        if int(
            plan.get(
                "moved_reservations_count",
                len(moves),
            )
            or 0
        ) != 0:
            raise ValidationError(
                "Live seated modification cannot move "
                "other reservations."
            )

        requested_modification = (
            payload.get("requested_modification")
        )

        if not isinstance(
            requested_modification,
            dict,
        ):
            raise ValidationError(
                "Live seated modification does not contain "
                "a valid requested modification."
            )

        requested_party_size = (
            requested_modification.get("party_size")
        )

        if (
            not isinstance(requested_party_size, int)
            or isinstance(requested_party_size, bool)
            or requested_party_size < 1
        ):
            raise ValidationError(
                "Live seated modification does not contain "
                "a valid requested party size."
            )

        original_reservation = payload.get("reservation")

        if not isinstance(original_reservation, dict):
            raise ValidationError(
                "Live seated modification does not contain "
                "the original reservation state."
            )

        if not isinstance(current_reservation_state, dict):
            raise ValidationError(
                "Live seated modification cannot verify "
                "the original reservation state."
            )

        if (
            str(original_reservation.get("id"))
            != str(reservation_id)
            or str(current_reservation_state.get("id"))
            != str(reservation_id)
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state does not match the reservation."
            )

        if (
            original_reservation.get("party_size")
            != current_reservation_state.get("party_size")
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state is stale: party size changed."
            )

        if (
            original_reservation.get("reservation_time")
            != current_reservation_state.get("reservation_time")
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state is stale: reservation time changed."
            )

        if (
            original_reservation.get("duration_minutes")
            != current_reservation_state.get("duration_minutes")
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state is stale: duration changed."
            )

        if (
            original_reservation.get("status")
            != current_reservation_state.get("status")
            or current_reservation_state.get("status")
            != "seated"
        ):
            raise ValidationError(
                "Live seated modification requires the "
                "reservation to remain seated."
            )

        stored_primary_table_id = (
            original_reservation.get("primary_table_id")
        )
        current_primary_table_id = (
            current_reservation_state.get(
                "primary_table_id"
            )
        )

        if (
            (
                str(stored_primary_table_id)
                if stored_primary_table_id is not None
                else None
            )
            != (
                str(current_primary_table_id)
                if current_primary_table_id is not None
                else None
            )
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state is stale: primary table changed."
            )

        stored_original_table_ids = {
            str(table_id)
            for table_id in (
                original_reservation.get("table_ids")
                or []
            )
        }

        current_original_table_ids = {
            str(table_id)
            for table_id in (
                current_reservation_state.get("table_ids")
                or []
            )
        }

        if (
            stored_original_table_ids
            != current_original_table_ids
        ):
            raise ValidationError(
                "Live seated modification original reservation "
                "state is stale: table assignments changed."
            )

        requested_reservation_time = (
            requested_modification.get(
                "reservation_time"
            )
        )

        if (
            requested_reservation_time
            != original_reservation.get(
                "reservation_time"
            )
        ):
            raise ValidationError(
                "Live seated modification cannot change "
                "reservation time."
            )
