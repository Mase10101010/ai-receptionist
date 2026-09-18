from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .learning import (
    TemporalLearningService,
    TemporalSampleState,
)
from .snapshot import TemporalLearningSnapshot


class ExpectedTurnSource(str, Enum):
    PLANNED_FALLBACK = "planned_fallback"
    RESTAURANT = "restaurant"
    PARTY_SIZE = "party_size"
    DAY_OF_WEEK = "day_of_week"
    DAYPART = "daypart"
    SERVICE_AREA = "service_area"


class ExpectedTurnConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExpectedTurnRequest(BaseModel):
    party_size: int = Field(
        ge=1,
        le=100,
    )

    planned_duration_minutes: int = Field(
        ge=15,
        le=720,
    )

    day_of_week: int = Field(
        ge=0,
        le=6,
    )

    hour: int = Field(
        ge=0,
        le=23,
    )

    service_area_id: UUID | None = None


class ExpectedTurnPrediction(BaseModel):
    expected_duration_minutes: int

    planned_duration_minutes: int
    adjustment_minutes: int

    source: ExpectedTurnSource

    source_sample_count: int | None = None

    confidence: ExpectedTurnConfidence

    used_learned_pattern: bool


class ExpectedTurnService:
    """
    Deterministic Expected Turn Time V1.

    T3 rules:
    - planned duration remains the baseline
    - only ESTABLISHED profiles influence prediction
    - contextual profiles are preferred over restaurant-wide profile
    - contextual candidates compete by sample count
    - restaurant profile is the final learned fallback
    - if no established evidence exists, planned duration wins
    - confidence expresses evidence strength only
    - calibration is intentionally deferred to T4
    """

    MIN_DURATION_MINUTES = 15
    MAX_DURATION_MINUTES = 720

    HIGH_CONFIDENCE_MIN_SAMPLES = 30
    MEDIUM_CONFIDENCE_MIN_SAMPLES = 15

    @staticmethod
    def _confidence_for_sample_count(
        sample_count: int | None,
    ) -> ExpectedTurnConfidence:
        if sample_count is None:
            return ExpectedTurnConfidence.LOW

        if (
            sample_count
            >= ExpectedTurnService
            .HIGH_CONFIDENCE_MIN_SAMPLES
        ):
            return ExpectedTurnConfidence.HIGH

        if (
            sample_count
            >= ExpectedTurnService
            .MEDIUM_CONFIDENCE_MIN_SAMPLES
        ):
            return ExpectedTurnConfidence.MEDIUM

        return ExpectedTurnConfidence.LOW

    @staticmethod
    def _apply_adjustment(
        *,
        planned_duration_minutes: int,
        mean_duration_delta_minutes: float,
    ) -> tuple[int, int]:
        adjustment = round(
            mean_duration_delta_minutes
        )

        predicted = (
            planned_duration_minutes
            + adjustment
        )

        predicted = max(
            ExpectedTurnService
            .MIN_DURATION_MINUTES,
            predicted,
        )

        predicted = min(
            ExpectedTurnService
            .MAX_DURATION_MINUTES,
            predicted,
        )

        effective_adjustment = (
            predicted
            - planned_duration_minutes
        )

        return (
            predicted,
            effective_adjustment,
        )

    @staticmethod
    def predict(
        *,
        snapshot: TemporalLearningSnapshot,
        request: ExpectedTurnRequest,
    ) -> ExpectedTurnPrediction:
        contextual_candidates: list[
            tuple[
                int,
                int,
                ExpectedTurnSource,
                object,
            ]
        ] = []

        priority = {
            ExpectedTurnSource.PARTY_SIZE: 4,
            ExpectedTurnSource.SERVICE_AREA: 3,
            ExpectedTurnSource.DAYPART: 2,
            ExpectedTurnSource.DAY_OF_WEEK: 1,
        }

        party_profile = next(
            (
                profile
                for profile
                in snapshot.party_size_profiles
                if (
                    profile.party_size
                    == request.party_size
                    and profile.sample_state
                    == TemporalSampleState.ESTABLISHED
                )
            ),
            None,
        )

        if party_profile is not None:
            contextual_candidates.append(
                (
                    party_profile.sample_count,
                    priority[
                        ExpectedTurnSource.PARTY_SIZE
                    ],
                    ExpectedTurnSource.PARTY_SIZE,
                    party_profile,
                )
            )

        if request.service_area_id is not None:
            area_profile = next(
                (
                    profile
                    for profile
                    in snapshot.service_area_profiles
                    if (
                        profile.service_area_id
                        == request.service_area_id
                        and profile.sample_state
                        == TemporalSampleState.ESTABLISHED
                    )
                ),
                None,
            )

            if area_profile is not None:
                contextual_candidates.append(
                    (
                        area_profile.sample_count,
                        priority[
                            ExpectedTurnSource
                            .SERVICE_AREA
                        ],
                        ExpectedTurnSource
                        .SERVICE_AREA,
                        area_profile,
                    )
                )

        daypart = (
            TemporalLearningService
            ._daypart_for_hour(
                request.hour
            )
        )

        daypart_profile = next(
            (
                profile
                for profile
                in snapshot.daypart_profiles
                if (
                    profile.daypart == daypart
                    and profile.sample_state
                    == TemporalSampleState.ESTABLISHED
                )
            ),
            None,
        )

        if daypart_profile is not None:
            contextual_candidates.append(
                (
                    daypart_profile.sample_count,
                    priority[
                        ExpectedTurnSource.DAYPART
                    ],
                    ExpectedTurnSource.DAYPART,
                    daypart_profile,
                )
            )

        weekday_profile = next(
            (
                profile
                for profile
                in snapshot.day_of_week_profiles
                if (
                    profile.day_of_week
                    == request.day_of_week
                    and profile.sample_state
                    == TemporalSampleState.ESTABLISHED
                )
            ),
            None,
        )

        if weekday_profile is not None:
            contextual_candidates.append(
                (
                    weekday_profile.sample_count,
                    priority[
                        ExpectedTurnSource
                        .DAY_OF_WEEK
                    ],
                    ExpectedTurnSource
                    .DAY_OF_WEEK,
                    weekday_profile,
                )
            )

        if contextual_candidates:
            (
                _,
                _,
                source,
                profile,
            ) = max(
                contextual_candidates,
                key=lambda candidate: (
                    candidate[0],
                    candidate[1],
                ),
            )

            (
                expected_duration,
                adjustment,
            ) = (
                ExpectedTurnService
                ._apply_adjustment(
                    planned_duration_minutes=(
                        request
                        .planned_duration_minutes
                    ),
                    mean_duration_delta_minutes=(
                        profile
                        .mean_duration_delta_minutes
                    ),
                )
            )

            return ExpectedTurnPrediction(
                expected_duration_minutes=(
                    expected_duration
                ),
                planned_duration_minutes=(
                    request.planned_duration_minutes
                ),
                adjustment_minutes=adjustment,
                source=source,
                source_sample_count=(
                    profile.sample_count
                ),
                confidence=(
                    ExpectedTurnService
                    ._confidence_for_sample_count(
                        profile.sample_count
                    )
                ),
                used_learned_pattern=True,
            )

        restaurant_profile = (
            snapshot.restaurant_profile
        )

        if (
            restaurant_profile is not None
            and restaurant_profile.sample_state
            == TemporalSampleState.ESTABLISHED
        ):
            (
                expected_duration,
                adjustment,
            ) = (
                ExpectedTurnService
                ._apply_adjustment(
                    planned_duration_minutes=(
                        request
                        .planned_duration_minutes
                    ),
                    mean_duration_delta_minutes=(
                        restaurant_profile
                        .mean_duration_delta_minutes
                    ),
                )
            )

            return ExpectedTurnPrediction(
                expected_duration_minutes=(
                    expected_duration
                ),
                planned_duration_minutes=(
                    request.planned_duration_minutes
                ),
                adjustment_minutes=adjustment,
                source=ExpectedTurnSource.RESTAURANT,
                source_sample_count=(
                    restaurant_profile.sample_count
                ),
                confidence=(
                    ExpectedTurnService
                    ._confidence_for_sample_count(
                        restaurant_profile
                        .sample_count
                    )
                ),
                used_learned_pattern=True,
            )

        return ExpectedTurnPrediction(
            expected_duration_minutes=(
                request.planned_duration_minutes
            ),
            planned_duration_minutes=(
                request.planned_duration_minutes
            ),
            adjustment_minutes=0,
            source=(
                ExpectedTurnSource
                .PLANNED_FALLBACK
            ),
            source_sample_count=None,
            confidence=(
                ExpectedTurnConfidence.LOW
            ),
            used_learned_pattern=False,
        )