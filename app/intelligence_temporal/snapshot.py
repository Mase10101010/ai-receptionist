from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from .collector import TemporalObservationCollector
from .learning import (
    DayOfWeekTurnProfile,
    DaypartTurnProfile,
    PartySizeTurnProfile,
    RestaurantTurnProfile,
    ServiceAreaTurnProfile,
    TemporalLearningService,
)


class TemporalLearningSnapshot(BaseModel):
    restaurant_id: UUID
    generated_from_sample_count: int

    restaurant_profile: RestaurantTurnProfile | None = None

    party_size_profiles: list[
        PartySizeTurnProfile
    ] = Field(
        default_factory=list,
    )

    day_of_week_profiles: list[
        DayOfWeekTurnProfile
    ] = Field(
        default_factory=list,
    )

    daypart_profiles: list[
        DaypartTurnProfile
    ] = Field(
        default_factory=list,
    )

    service_area_profiles: list[
        ServiceAreaTurnProfile
    ] = Field(
        default_factory=list,
    )


class TemporalLearningSnapshotService:
    """
    Composes temporal lifecycle observations into a deterministic
    learning snapshot.

    T2 snapshot semantics:
    - read-only
    - deterministic
    - no prediction
    - no calibration
    - no ML
    - no persistence of learned models
    """

    def __init__(
        self,
        *,
        collector: TemporalObservationCollector | None = None,
    ) -> None:
        self.collector = (
            collector
            or TemporalObservationCollector()
        )

    async def build(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
        completed_since: datetime | None = None,
        limit: int = (
            TemporalObservationCollector.DEFAULT_LIMIT
        ),
    ) -> TemporalLearningSnapshot:
        observations = await self.collector.collect(
            session=session,
            restaurant_id=restaurant_id,
            completed_since=completed_since,
            limit=limit,
        )

        return TemporalLearningSnapshot(
            restaurant_id=restaurant_id,
            generated_from_sample_count=len(
                observations
            ),
            restaurant_profile=(
                TemporalLearningService
                .build_restaurant_profile(
                    observations,
                )
            ),
            party_size_profiles=(
                TemporalLearningService
                .build_party_size_profiles(
                    observations,
                )
            ),
            day_of_week_profiles=(
                TemporalLearningService
                .build_day_of_week_profiles(
                    observations,
                )
            ),
            daypart_profiles=(
                TemporalLearningService
                .build_daypart_profiles(
                    observations,
                )
            ),
            service_area_profiles=(
                TemporalLearningService
                .build_service_area_profiles(
                    observations,
                )
            ),
        )