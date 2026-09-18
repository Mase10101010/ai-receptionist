from __future__ import annotations

from collections import defaultdict
from enum import Enum
from statistics import mean, median
from uuid import UUID

from pydantic import BaseModel

from .observations import TemporalTurnObservation


class TemporalDaypart(str, Enum):
    LUNCH = "lunch"
    AFTERNOON = "afternoon"
    DINNER = "dinner"
    LATE = "late"
    OTHER = "other"


class TemporalSampleState(str, Enum):
    SPARSE = "sparse"
    DEVELOPING = "developing"
    ESTABLISHED = "established"


class TemporalProfileStats(BaseModel):
    sample_count: int
    included_sample_count: int
    excluded_outlier_count: int

    sample_state: TemporalSampleState

    mean_actual_dining_minutes: float
    median_actual_dining_minutes: float

    min_actual_dining_minutes: int
    max_actual_dining_minutes: int

    mean_duration_delta_minutes: float


class RestaurantTurnProfile(TemporalProfileStats):
    restaurant_id: UUID


class PartySizeTurnProfile(TemporalProfileStats):
    restaurant_id: UUID
    party_size: int


class DayOfWeekTurnProfile(TemporalProfileStats):
    restaurant_id: UUID
    day_of_week: int


class DaypartTurnProfile(TemporalProfileStats):
    restaurant_id: UUID
    daypart: TemporalDaypart


class ServiceAreaTurnProfile(TemporalProfileStats):
    restaurant_id: UUID
    service_area_id: UUID


class TemporalLearningService:
    """
    Deterministic aggregation of valid temporal observations.

    T2 intentionally does not:
    - predict future turns
    - persist learned models
    - perform ML

    Sample-state semantics describe observation maturity only.
    They are not prediction confidence.
    """

    OUTLIER_FILTER_MIN_SAMPLES = 8

    @staticmethod
    def _validate_single_restaurant(
        observations: list[TemporalTurnObservation],
    ) -> UUID | None:
        if not observations:
            return None

        restaurant_ids = {
            observation.restaurant_id
            for observation in observations
        }

        if len(restaurant_ids) != 1:
            raise ValueError(
                "All temporal observations must belong "
                "to the same restaurant."
            )

        return observations[0].restaurant_id

    @staticmethod
    def _sample_state(
        sample_count: int,
    ) -> TemporalSampleState:
        if sample_count <= 2:
            return TemporalSampleState.SPARSE

        if sample_count <= 7:
            return TemporalSampleState.DEVELOPING

        return TemporalSampleState.ESTABLISHED

    @staticmethod
    def _percentile(
        values: list[int],
        percentile: float,
    ) -> float:
        if not values:
            raise ValueError(
                "Cannot calculate percentile "
                "for empty values."
            )

        ordered = sorted(values)

        if len(ordered) == 1:
            return float(ordered[0])

        position = (
            len(ordered) - 1
        ) * percentile

        lower_index = int(position)
        upper_index = min(
            lower_index + 1,
            len(ordered) - 1,
        )

        fraction = (
            position - lower_index
        )

        lower_value = ordered[
            lower_index
        ]
        upper_value = ordered[
            upper_index
        ]

        return (
            lower_value
            + (
                upper_value - lower_value
            )
            * fraction
        )

    @staticmethod
    def _filter_outliers(
        observations: list[TemporalTurnObservation],
    ) -> list[TemporalTurnObservation]:
        if (
            len(observations)
            < TemporalLearningService
            .OUTLIER_FILTER_MIN_SAMPLES
        ):
            return list(observations)

        actual_minutes = [
            observation.actual_dining_minutes
            for observation in observations
        ]

        q1 = TemporalLearningService._percentile(
            actual_minutes,
            0.25,
        )

        q3 = TemporalLearningService._percentile(
            actual_minutes,
            0.75,
        )

        iqr = q3 - q1

        if iqr <= 0:
            return list(observations)

        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        return [
            observation
            for observation in observations
            if (
                lower_bound
                <= observation.actual_dining_minutes
                <= upper_bound
            )
        ]

    @staticmethod
    def _stats(
        observations: list[TemporalTurnObservation],
    ) -> dict:
        if not observations:
            raise ValueError(
                "Cannot build temporal statistics "
                "without observations."
            )

        filtered = (
            TemporalLearningService
            ._filter_outliers(
                observations,
            )
        )

        if not filtered:
            filtered = list(observations)

        actual_minutes = [
            observation.actual_dining_minutes
            for observation in filtered
        ]

        duration_deltas = [
            observation.duration_delta_minutes
            for observation in filtered
        ]

        sample_count = len(observations)
        included_sample_count = len(filtered)

        return {
            "sample_count": sample_count,
            "included_sample_count": (
                included_sample_count
            ),
            "excluded_outlier_count": (
                sample_count
                - included_sample_count
            ),
            "sample_state": (
                TemporalLearningService
                ._sample_state(
                    sample_count,
                )
            ),
            "mean_actual_dining_minutes": round(
                mean(actual_minutes),
                2,
            ),
            "median_actual_dining_minutes": round(
                median(actual_minutes),
                2,
            ),
            "min_actual_dining_minutes": min(
                actual_minutes,
            ),
            "max_actual_dining_minutes": max(
                actual_minutes,
            ),
            "mean_duration_delta_minutes": round(
                mean(duration_deltas),
                2,
            ),
        }

    @staticmethod
    def _daypart_for_hour(
        hour: int,
    ) -> TemporalDaypart:
        if 11 <= hour <= 14:
            return TemporalDaypart.LUNCH

        if 15 <= hour <= 17:
            return TemporalDaypart.AFTERNOON

        if 18 <= hour <= 21:
            return TemporalDaypart.DINNER

        if hour >= 22 or hour <= 2:
            return TemporalDaypart.LATE

        return TemporalDaypart.OTHER

    @staticmethod
    def build_restaurant_profile(
        observations: list[TemporalTurnObservation],
    ) -> RestaurantTurnProfile | None:
        restaurant_id = (
            TemporalLearningService
            ._validate_single_restaurant(
                observations,
            )
        )

        if restaurant_id is None:
            return None

        return RestaurantTurnProfile(
            restaurant_id=restaurant_id,
            **TemporalLearningService._stats(
                observations,
            ),
        )

    @staticmethod
    def build_party_size_profiles(
        observations: list[TemporalTurnObservation],
    ) -> list[PartySizeTurnProfile]:
        restaurant_id = (
            TemporalLearningService
            ._validate_single_restaurant(
                observations,
            )
        )

        if restaurant_id is None:
            return []

        grouped: dict[
            int,
            list[TemporalTurnObservation],
        ] = defaultdict(list)

        for observation in observations:
            grouped[
                observation.party_size
            ].append(
                observation
            )

        return [
            PartySizeTurnProfile(
                restaurant_id=restaurant_id,
                party_size=party_size,
                **TemporalLearningService._stats(
                    grouped[party_size],
                ),
            )
            for party_size in sorted(grouped)
        ]

    @staticmethod
    def build_day_of_week_profiles(
        observations: list[TemporalTurnObservation],
    ) -> list[DayOfWeekTurnProfile]:
        restaurant_id = (
            TemporalLearningService
            ._validate_single_restaurant(
                observations,
            )
        )

        if restaurant_id is None:
            return []

        grouped: dict[
            int,
            list[TemporalTurnObservation],
        ] = defaultdict(list)

        for observation in observations:
            day_of_week = (
                observation.reservation_time.weekday()
            )

            grouped[day_of_week].append(
                observation
            )

        return [
            DayOfWeekTurnProfile(
                restaurant_id=restaurant_id,
                day_of_week=day_of_week,
                **TemporalLearningService._stats(
                    grouped[day_of_week],
                ),
            )
            for day_of_week in sorted(grouped)
        ]

    @staticmethod
    def build_daypart_profiles(
        observations: list[TemporalTurnObservation],
    ) -> list[DaypartTurnProfile]:
        restaurant_id = (
            TemporalLearningService
            ._validate_single_restaurant(
                observations,
            )
        )

        if restaurant_id is None:
            return []

        grouped: dict[
            TemporalDaypart,
            list[TemporalTurnObservation],
        ] = defaultdict(list)

        for observation in observations:
            daypart = (
                TemporalLearningService
                ._daypart_for_hour(
                    observation.reservation_time.hour,
                )
            )

            grouped[daypart].append(
                observation
            )

        order = [
            TemporalDaypart.LUNCH,
            TemporalDaypart.AFTERNOON,
            TemporalDaypart.DINNER,
            TemporalDaypart.LATE,
            TemporalDaypart.OTHER,
        ]

        return [
            DaypartTurnProfile(
                restaurant_id=restaurant_id,
                daypart=daypart,
                **TemporalLearningService._stats(
                    grouped[daypart],
                ),
            )
            for daypart in order
            if daypart in grouped
        ]

    @staticmethod
    def build_service_area_profiles(
        observations: list[TemporalTurnObservation],
    ) -> list[ServiceAreaTurnProfile]:
        restaurant_id = (
            TemporalLearningService
            ._validate_single_restaurant(
                observations,
            )
        )

        if restaurant_id is None:
            return []

        grouped: dict[
            UUID,
            list[TemporalTurnObservation],
        ] = defaultdict(list)

        for observation in observations:
            if observation.service_area_id is None:
                continue

            grouped[
                observation.service_area_id
            ].append(
                observation
            )

        return [
            ServiceAreaTurnProfile(
                restaurant_id=restaurant_id,
                service_area_id=service_area_id,
                **TemporalLearningService._stats(
                    grouped[service_area_id],
                ),
            )
            for service_area_id in sorted(
                grouped,
                key=str,
            )
        ]