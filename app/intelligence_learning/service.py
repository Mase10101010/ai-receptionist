from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventType,
)
from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)
from app.intelligence_learning.models import (
    RestaurantLearningProfile,
)
from app.intelligence_learning.repository import (
    RestaurantLearningProfileRepository,
)
from app.intelligence_learning.schemas import (
    LearningProfileUpdateResult,
)


class RestaurantLearningService:
    SUPPORTED_EVENT_TYPES = {
        IntelligenceEventType.AI_SUGGESTION_CREATED,
        IntelligenceEventType.AI_SUGGESTION_READ,
        IntelligenceEventType.AI_SUGGESTION_ACCEPTED,
        IntelligenceEventType.AI_SUGGESTION_DISMISSED,
        IntelligenceEventType.AI_SUGGESTION_EXPIRED,
    }

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self.session = session

        self.profile_repository = (
            RestaurantLearningProfileRepository(
                session,
            )
        )

        self.event_repository = (
            IntelligenceEventRepository(
                session,
            )
        )

    async def update_profile(
        self,
        *,
        restaurant_id: uuid.UUID,
        batch_size: int = 500,
    ) -> LearningProfileUpdateResult:
        profile = (
            await self.profile_repository
            .get_by_restaurant_id(
                restaurant_id,
                for_update=True,
            )
        )

        profile_created = False

        if profile is None:
            profile = (
                await self.profile_repository.create(
                    restaurant_id=restaurant_id,
                )
            )
            profile_created = True

        events = (
            await self.event_repository
            .list_after_cursor(
                restaurant_id=restaurant_id,
                created_after=(
                    profile.last_processed_event_at
                ),
                last_event_id=(
                    profile.last_processed_event_id
                ),
                limit=batch_size,
            )
        )

        processed_events = 0

        for event in events:
            if (
                event.event_type
                in self.SUPPORTED_EVENT_TYPES
            ):
                self._apply_event(
                    profile=profile,
                    event=event,
                )

            self._advance_cursor(
                profile=profile,
                event=event,
            )

            # Counts every event consumed by the cursor,
            # including events that do not affect learning metrics.
            processed_events += 1

        if processed_events > 0 or profile_created:
            self._recalculate_rates(
                profile,
            )

            self._recalculate_confidence(
                profile,
            )

            profile = (
                await self.profile_repository.save(
                    profile,
                )
            )

        return LearningProfileUpdateResult(
            restaurant_id=restaurant_id,
            processed_events=processed_events,
            profile_created=profile_created,
            profile=profile,
        )

    async def get_profile(
        self,
        *,
        restaurant_id: uuid.UUID,
    ):
        repository = (
            RestaurantLearningProfileRepository(
                self.session,
            )
        )

        return await repository.get_by_restaurant_id(
            restaurant_id,
        )

    def _apply_event(
        self,
        *,
        profile: RestaurantLearningProfile,
        event: IntelligenceEvent,
    ) -> None:
        payload = event.payload or {}

        if (
            event.event_type
            == IntelligenceEventType
            .AI_SUGGESTION_CREATED
        ):
            profile.suggestions_created += 1
            return

        if (
            event.event_type
            == IntelligenceEventType
            .AI_SUGGESTION_READ
        ):
            profile.suggestions_read += 1
            return

        if (
            event.event_type
            == IntelligenceEventType
            .AI_SUGGESTION_ACCEPTED
        ):
            previous_count = (
                profile.suggestions_accepted
            )

            profile.suggestions_accepted += 1

            profile.accepted_score_average = (
                self._incremental_average(
                    current_average=(
                        profile
                        .accepted_score_average
                    ),
                    previous_count=previous_count,
                    new_value=self._float_value(
                        payload.get("score")
                    ),
                )
            )

            profile.accepted_moves_average = (
                self._incremental_average(
                    current_average=(
                        profile
                        .accepted_moves_average
                    ),
                    previous_count=previous_count,
                    new_value=self._float_value(
                        payload.get(
                            "moved_reservations_count"
                        )
                    ),
                )
            )

            profile.accepted_seat_waste_average = (
                self._incremental_average(
                    current_average=(
                        profile
                        .accepted_seat_waste_average
                    ),
                    previous_count=previous_count,
                    new_value=self._float_value(
                        payload.get(
                            "total_seat_waste"
                        )
                    ),
                )
            )

            return

        if (
            event.event_type
            == IntelligenceEventType
            .AI_SUGGESTION_DISMISSED
        ):
            previous_count = (
                profile.suggestions_dismissed
            )

            profile.suggestions_dismissed += 1

            profile.dismissed_score_average = (
                self._incremental_average(
                    current_average=(
                        profile
                        .dismissed_score_average
                    ),
                    previous_count=previous_count,
                    new_value=self._float_value(
                        payload.get("score")
                    ),
                )
            )

            return

        if (
            event.event_type
            == IntelligenceEventType
            .AI_SUGGESTION_EXPIRED
        ):
            profile.suggestions_expired += 1

    @staticmethod
    def _incremental_average(
        *,
        current_average: float | None,
        previous_count: int,
        new_value: float | None,
    ) -> float | None:
        if new_value is None:
            return current_average

        if (
            current_average is None
            or previous_count <= 0
        ):
            return new_value

        return (
            (
                current_average
                * previous_count
            )
            + new_value
        ) / (
            previous_count + 1
        )

    @staticmethod
    def _float_value(
        value: object,
    ) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _recalculate_rates(
        profile: RestaurantLearningProfile,
    ) -> None:
        created = profile.suggestions_created

        if created <= 0:
            profile.acceptance_rate = 0.0
            profile.dismissal_rate = 0.0
            profile.read_rate = 0.0
            return

        profile.acceptance_rate = round(
            profile.suggestions_accepted
            / created,
            6,
        )

        profile.dismissal_rate = round(
            profile.suggestions_dismissed
            / created,
            6,
        )

        profile.read_rate = round(
            profile.suggestions_read
            / created,
            6,
        )

    @staticmethod
    def _recalculate_confidence(
        profile: RestaurantLearningProfile,
    ) -> None:
        decisions = (
            profile.suggestions_accepted
            + profile.suggestions_dismissed
        )

        observations = (
            profile.suggestions_created
        )

        decision_component = min(
            decisions / 20,
            1.0,
        )

        observation_component = min(
            observations / 50,
            1.0,
        )

        profile.confidence_score = round(
            (
                decision_component * 0.7
                + observation_component * 0.3
            ),
            6,
        )

    @staticmethod
    def _advance_cursor(
        *,
        profile: RestaurantLearningProfile,
        event: IntelligenceEvent,
    ) -> None:
        profile.last_processed_event_id = (
            event.id
        )

        profile.last_processed_event_at = (
            event.created_at
        )