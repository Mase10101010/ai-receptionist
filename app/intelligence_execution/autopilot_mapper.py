from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ValidationError
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceReoptimizationMoveApply,
)
from app.models.ai_suggestion import (
    AISuggestion,
    AISuggestionType,
)


class AutopilotReoptimizationMapper:
    def build_apply_request(
        self,
        *,
        suggestion: AISuggestion,
    ) -> IntelligenceApplyReoptimizationRequest:
        if (
            suggestion.suggestion_type
            != AISuggestionType.REOPTIMIZATION
        ):
            raise ValidationError(
                "AI suggestion is not a reoptimization suggestion."
            )

        if suggestion.reservation_id is None:
            raise ValidationError(
                "AI suggestion does not reference a reservation."
            )

        payload = suggestion.payload or {}
        plan = payload.get("plan") or {}

        assignment = (
            plan.get("new_reservation_assignment")
            or {}
        )

        raw_table_ids = (
            assignment.get("table_ids")
            or []
        )

        if not raw_table_ids:
            raise ValidationError(
                "AI suggestion does not contain "
                "a valid table assignment."
            )

        try:
            table_ids = [
                UUID(str(table_id))
                for table_id in raw_table_ids
            ]
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError(
                "AI suggestion contains invalid table IDs."
            ) from exc

        moves: list[
            IntelligenceReoptimizationMoveApply
        ] = []

        for stored_move in plan.get("moves") or []:
            raw_move_table_ids = (
                stored_move.get("to_table_ids")
                or []
            )

            if not raw_move_table_ids:
                raise ValidationError(
                    "AI suggestion contains a move "
                    "without destination tables."
                )

            try:
                reservation_id = UUID(
                    str(stored_move["reservation_id"])
                )
                move_table_ids = [
                    UUID(str(table_id))
                    for table_id
                    in raw_move_table_ids
                ]
            except (
                KeyError,
                TypeError,
                ValueError,
                AttributeError,
            ) as exc:
                raise ValidationError(
                    "AI suggestion contains an invalid move."
                ) from exc

            moves.append(
                IntelligenceReoptimizationMoveApply(
                    reservation_id=reservation_id,
                    to_table_ids=move_table_ids,
                    primary_table_id=move_table_ids[0],
                )
            )

        return IntelligenceApplyReoptimizationRequest(
            suggestion_id=suggestion.id,
            new_reservation_id=suggestion.reservation_id,
            new_reservation_table_ids=table_ids,
            new_reservation_primary_table_id=table_ids[0],
            moves=moves,
        )