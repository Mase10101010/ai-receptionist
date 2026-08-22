from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.intelligence_behaviour.schemas import (
    AISuggestionBehaviourProfile,
    PlanPreference,
)
from app.intelligence_policy.schemas import (
    RecommendationPolicy,
)
from app.intelligence_reasoning.schemas import (
    LearnedSignal,
    LearnedSignalDirection,
    LearnedSignalStrength,
    ReasonImportance,
    ReasonItem,
    RecommendationReasoning,
)


class IntelligenceReasoningService:
    def build_recommendation_reasoning(
        self,
        *,
        restaurant_id: uuid.UUID,
        reservation_id: uuid.UUID | None,
        base_score: float,
        personalized_score: float,
        moved_reservations_count: int,
        total_seat_waste: int,
        behaviour: AISuggestionBehaviourProfile,
        policy: RecommendationPolicy,
    ) -> RecommendationReasoning:
        reasons: list[ReasonItem] = []

        learned_signals = (
            self._build_learned_signals(
                behaviour=behaviour,
            )
        )

        self._add_move_reason(
            reasons=reasons,
            moved_reservations_count=(
                moved_reservations_count
            ),
            behaviour=behaviour,
            policy=policy,
        )

        self._add_seat_waste_reason(
            reasons=reasons,
            total_seat_waste=total_seat_waste,
            behaviour=behaviour,
            policy=policy,
        )

        self._add_score_reason(
            reasons=reasons,
            base_score=base_score,
            policy=policy,
        )

        self._add_personalization_reason(
            reasons=reasons,
            base_score=base_score,
            personalized_score=(
                personalized_score
            ),
        )

        return RecommendationReasoning(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            base_score=round(
                base_score,
                2,
            ),
            personalized_score=round(
                personalized_score,
                2,
            ),
            moved_reservations_count=(
                moved_reservations_count
            ),
            total_seat_waste=(
                total_seat_waste
            ),
            reasons=reasons,
            learned_signals=learned_signals,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )

    @staticmethod
    def _add_move_reason(
        *,
        reasons: list[ReasonItem],
        moved_reservations_count: int,
        behaviour: AISuggestionBehaviourProfile,
        policy: RecommendationPolicy,
    ) -> None:
        if moved_reservations_count == 0:
            reasons.append(
                ReasonItem(
                    code="no_moves_required",
                    title="No reservation moves required",
                    description=(
                        "This plan can be applied without "
                        "moving any existing reservation."
                    ),
                    importance=ReasonImportance.HIGH,
                )
            )
            return

        if (
            moved_reservations_count == 1
            and behaviour.preferred_plan
            == PlanPreference.SINGLE_MOVE
        ):
            reasons.append(
                ReasonItem(
                    code="preferred_single_move",
                    title="Matches preferred move structure",
                    description=(
                        "This plan requires moving only one "
                        "reservation, which matches the "
                        "manager's observed preferences."
                    ),
                    importance=ReasonImportance.HIGH,
                )
            )
            return

        if (
            policy.maximum_preferred_moves
            is not None
            and moved_reservations_count
            <= policy.maximum_preferred_moves
        ):
            reasons.append(
                ReasonItem(
                    code="within_preferred_move_limit",
                    title="Within preferred move limit",
                    description=(
                        "The number of reservation moves is "
                        "within the range currently preferred "
                        "for this restaurant."
                    ),
                    importance=ReasonImportance.MEDIUM,
                )
            )
        else:
            reasons.append(
                ReasonItem(
                    code="above_preferred_move_limit",
                    title="More moves than usually preferred",
                    description=(
                        "This plan requires more reservation "
                        "moves than the current learned "
                        "preference."
                    ),
                    importance=ReasonImportance.LOW,
                )
            )

    @staticmethod
    def _add_seat_waste_reason(
        *,
        reasons: list[ReasonItem],
        total_seat_waste: int,
        behaviour: AISuggestionBehaviourProfile,
        policy: RecommendationPolicy,
    ) -> None:
        if total_seat_waste == 0:
            reasons.append(
                ReasonItem(
                    code="exact_capacity_fit",
                    title="Exact capacity fit",
                    description=(
                        "This plan creates no unused seating "
                        "capacity."
                    ),
                    importance=ReasonImportance.HIGH,
                )
            )
            return

        if (
            policy.maximum_preferred_seat_waste
            is not None
            and total_seat_waste
            <= policy.maximum_preferred_seat_waste
        ):
            reasons.append(
                ReasonItem(
                    code="within_preferred_seat_waste",
                    title="Seat waste within preferred range",
                    description=(
                        "Unused seating capacity remains "
                        "within the restaurant's learned "
                        "preference."
                    ),
                    importance=ReasonImportance.MEDIUM,
                )
            )
            return

        if (
            behaviour.average_seat_waste_accepted
            is not None
        ):
            reasons.append(
                ReasonItem(
                    code="above_typical_seat_waste",
                    title="Higher seat waste than usual",
                    description=(
                        "This plan leaves more unused seating "
                        "capacity than plans usually accepted "
                        "by the manager."
                    ),
                    importance=ReasonImportance.LOW,
                )
            )

    @staticmethod
    def _add_score_reason(
        *,
        reasons: list[ReasonItem],
        base_score: float,
        policy: RecommendationPolicy,
    ) -> None:
        minimum_score = (
            policy.minimum_recommended_score
        )

        if minimum_score is None:
            return

        if base_score >= minimum_score:
            reasons.append(
                ReasonItem(
                    code="above_learned_score_reference",
                    title="Strong technical score",
                    description=(
                        "The technical score is above the "
                        "current learned recommendation "
                        "reference."
                    ),
                    importance=ReasonImportance.HIGH,
                )
            )
        else:
            reasons.append(
                ReasonItem(
                    code="below_learned_score_reference",
                    title="Below learned score reference",
                    description=(
                        "The technical score is below the "
                        "current learned reference, so manager "
                        "review remains advisable."
                    ),
                    importance=ReasonImportance.LOW,
                )
            )

    @staticmethod
    def _add_personalization_reason(
        *,
        reasons: list[ReasonItem],
        base_score: float,
        personalized_score: float,
    ) -> None:
        difference = (
            personalized_score
            - base_score
        )

        if difference > 0.01:
            reasons.append(
                ReasonItem(
                    code="personalization_bonus",
                    title="Boosted by learned preferences",
                    description=(
                        "Alias ranked this plan higher after "
                        "applying the restaurant's learned "
                        "preferences."
                    ),
                    importance=ReasonImportance.HIGH,
                )
            )
        elif difference < -0.01:
            reasons.append(
                ReasonItem(
                    code="personalization_penalty",
                    title="Reduced by learned preferences",
                    description=(
                        "Alias ranked this plan more "
                        "cautiously after applying the "
                        "restaurant's learned preferences."
                    ),
                    importance=ReasonImportance.MEDIUM,
                )
            )

    @classmethod
    def _build_learned_signals(
        cls,
        *,
        behaviour: AISuggestionBehaviourProfile,
    ) -> list[LearnedSignal]:
        return [
            cls._build_lower_is_preferred_signal(
                code="move_structure",
                title="Plan structure",
                strength_value=(
                    behaviour.move_preference_strength
                ),
                accepted_value=(
                    behaviour.average_moves_accepted
                ),
                dismissed_value=(
                    behaviour.average_moves_dismissed
                ),
                unit_name="reservation moves",
            ),
            cls._build_lower_is_preferred_signal(
                code="seat_waste",
                title="Capacity usage",
                strength_value=(
                    behaviour
                    .seat_waste_preference_strength
                ),
                accepted_value=(
                    behaviour
                    .average_seat_waste_accepted
                ),
                dismissed_value=(
                    behaviour
                    .average_seat_waste_dismissed
                ),
                unit_name="unused seats",
            ),
            cls._build_higher_is_preferred_signal(
                code="technical_score",
                title="Technical score",
                strength_value=(
                    behaviour.score_preference_strength
                ),
                accepted_value=(
                    behaviour.accepted_score_reference
                ),
                dismissed_value=(
                    behaviour.dismissed_score_reference
                ),
            ),
        ]


    @classmethod
    def _build_lower_is_preferred_signal(
        cls,
        *,
        code: str,
        title: str,
        strength_value: float,
        accepted_value: float | None,
        dismissed_value: float | None,
        unit_name: str,
    ) -> LearnedSignal:
        strength = cls._signal_strength(
            strength_value
        )

        if (
            accepted_value is None
            or dismissed_value is None
        ):
            return LearnedSignal(
                code=code,
                title=title,
                strength=LearnedSignalStrength.NONE,
                direction=(
                    LearnedSignalDirection.NEUTRAL
                ),
                strength_value=round(
                    strength_value,
                    4,
                ),
                accepted_value=accepted_value,
                dismissed_value=dismissed_value,
                description=(
                    "Alias does not yet have enough "
                    "comparable manager decisions to "
                    "measure this preference."
                ),
            )

        if accepted_value < dismissed_value:
            direction = (
                LearnedSignalDirection.PREFERRED
            )

            description = (
                f"Accepted plans average "
                f"{accepted_value:.2f} {unit_name}, "
                f"while dismissed plans average "
                f"{dismissed_value:.2f}. "
                f"This suggests the manager tends "
                f"to prefer lower values."
            )

        elif accepted_value > dismissed_value:
            direction = (
                LearnedSignalDirection.AVOIDED
            )

            description = (
                f"Accepted plans average "
                f"{accepted_value:.2f} {unit_name}, "
                f"while dismissed plans average "
                f"{dismissed_value:.2f}. "
                f"Lower values do not currently "
                f"appear to drive acceptance."
            )

        else:
            direction = (
                LearnedSignalDirection.NEUTRAL
            )

            description = (
                f"Accepted and dismissed plans "
                f"currently average about "
                f"{accepted_value:.2f} "
                f"{unit_name}, so this signal does "
                f"not yet distinguish manager "
                f"decisions."
            )

        return LearnedSignal(
            code=code,
            title=title,
            strength=strength,
            direction=direction,
            strength_value=round(
                strength_value,
                4,
            ),
            accepted_value=accepted_value,
            dismissed_value=dismissed_value,
            description=description,
        )


    @classmethod
    def _build_higher_is_preferred_signal(
        cls,
        *,
        code: str,
        title: str,
        strength_value: float,
        accepted_value: float | None,
        dismissed_value: float | None,
    ) -> LearnedSignal:
        strength = cls._signal_strength(
            strength_value
        )

        if (
            accepted_value is None
            or dismissed_value is None
        ):
            return LearnedSignal(
                code=code,
                title=title,
                strength=LearnedSignalStrength.NONE,
                direction=(
                    LearnedSignalDirection.NEUTRAL
                ),
                strength_value=round(
                    strength_value,
                    4,
                ),
                accepted_value=accepted_value,
                dismissed_value=dismissed_value,
                description=(
                    "Alias does not yet have enough "
                    "comparable manager decisions to "
                    "measure this preference."
                ),
            )

        if accepted_value > dismissed_value:
            direction = (
                LearnedSignalDirection.PREFERRED
            )

            description = (
                f"Accepted plans have an average "
                f"technical score of "
                f"{accepted_value:.2f}, compared "
                f"with {dismissed_value:.2f} for "
                f"dismissed plans. Higher scores "
                f"currently align with acceptance."
            )

        elif accepted_value < dismissed_value:
            direction = (
                LearnedSignalDirection.AVOIDED
            )

            description = (
                f"Accepted plans have an average "
                f"technical score of "
                f"{accepted_value:.2f}, compared "
                f"with {dismissed_value:.2f} for "
                f"dismissed plans. Higher technical "
                f"scores do not currently predict "
                f"manager acceptance."
            )

        else:
            direction = (
                LearnedSignalDirection.NEUTRAL
            )

            description = (
                f"Accepted and dismissed plans have "
                f"the same average technical score "
                f"of {accepted_value:.2f}, so score "
                f"does not yet distinguish manager "
                f"decisions."
            )

        return LearnedSignal(
            code=code,
            title=title,
            strength=strength,
            direction=direction,
            strength_value=round(
                strength_value,
                4,
            ),
            accepted_value=accepted_value,
            dismissed_value=dismissed_value,
            description=description,
        )


    @staticmethod
    def _signal_strength(
        value: float,
    ) -> LearnedSignalStrength:
        if value <= 0.0:
            return LearnedSignalStrength.NONE

        if value < 0.20:
            return LearnedSignalStrength.LOW

        if value < 0.50:
            return LearnedSignalStrength.MEDIUM

        return LearnedSignalStrength.HIGH