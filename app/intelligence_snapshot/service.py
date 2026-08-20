from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)
from app.intelligence_behaviour.service import (
    IntelligenceBehaviourService,
)
from app.intelligence_learning.repository import (
    RestaurantLearningProfileRepository,
)
from app.intelligence_policy.service import (
    RecommendationPolicyService,
)
from app.intelligence_snapshot.schemas import (
    IntelligenceLearningSnapshot,
    IntelligenceSnapshotResponse,
)
from app.intelligence_calibration.metrics import (
    IntelligenceCalibrationMetricsService,
)
from app.intelligence_calibration.repository import (
    IntelligenceCalibrationRepository,
)
from app.intelligence_automation_path.service import (
    IntelligenceAutomationPathService,
)


class IntelligenceSnapshotService:
    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def build_snapshot(
        self,
        *,
        restaurant_id: uuid.UUID,
    ) -> IntelligenceSnapshotResponse | None:
        learning_repository = (
            RestaurantLearningProfileRepository(
                self.session,
            )
        )

        profile = (
            await learning_repository
            .get_by_restaurant_id(
                restaurant_id,
            )
        )

        if profile is None:
            return None

        intelligence_service = (
            IntelligenceOptimizationService()
        )

        features = (
            intelligence_service
            ._features_from_learning_profile(
                profile=profile,
            )
        )

        behaviour = (
            IntelligenceBehaviourService()
            .build_ai_suggestion_profile(
                features=features,
            )
        )

        manager_decisions = (
            profile.suggestions_accepted
            + profile.suggestions_dismissed
        )

        calibration = (
            await IntelligenceCalibrationMetricsService(
                repository=(
                    IntelligenceCalibrationRepository(
                        self.session,
                    )
                )
            ).calculate(
                restaurant_id=restaurant_id,
            )
        )

        policy = None
        automation_path = None

        if manager_decisions > 0:
            policy = (
                RecommendationPolicyService()
                .build_policy(
                    profile=behaviour,
                    calibration=calibration,
                )
            )

        if policy is not None:
            automation_path = (
                IntelligenceAutomationPathService()
                .build(
                    profile=behaviour,
                    policy=policy,
                    calibration=calibration,
                )
            )

        learning = IntelligenceLearningSnapshot(
            suggestions_observed=(
                profile.suggestions_created
            ),
            suggestions_read=(
                profile.suggestions_read
            ),
            suggestions_accepted=(
                profile.suggestions_accepted
            ),
            suggestions_dismissed=(
                profile.suggestions_dismissed
            ),
            suggestions_expired=(
                profile.suggestions_expired
            ),
            manager_decisions=(
                manager_decisions
            ),
            acceptance_rate=(
                profile.acceptance_rate
            ),
            dismissal_rate=(
                profile.dismissal_rate
            ),
            read_rate=profile.read_rate,
            confidence_score=(
                profile.confidence_score
            ),
            profile_version=(
                profile.profile_version
            ),
            last_processed_event_at=(
                profile.last_processed_event_at
            ),
        )

        return IntelligenceSnapshotResponse(
            restaurant_id=restaurant_id,
            learning=learning,
            behaviour=behaviour,
            policy=policy,
            calibration=calibration,
            automation_path=automation_path,
            generated_at=datetime.now(
                timezone.utc,
            ),
        )