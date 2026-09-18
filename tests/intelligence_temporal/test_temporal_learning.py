from datetime import datetime, timedelta
from uuid import uuid4

import pytest


from app.intelligence_temporal.observations import (
    TemporalTurnObservation,
)
from app.intelligence_temporal.learning import (
    TemporalDaypart,
    TemporalLearningService,
    TemporalSampleState,
)


def _observation(
    *,
    restaurant_id,
    actual_minutes,
    planned_minutes=90,
    service_area_id=None,
):
    seated_at = datetime(
        2026,
        9,
        10,
        18,
        0,
    )

    return TemporalTurnObservation(
        reservation_id=uuid4(),
        restaurant_id=restaurant_id,
        table_id=uuid4(),
        service_area_id=service_area_id,
        party_size=4,
        reservation_time=seated_at,
        seated_at=seated_at,
        completed_at=(
            seated_at
            + timedelta(minutes=actual_minutes)
        ),
        planned_duration_minutes=planned_minutes,
        actual_dining_minutes=actual_minutes,
        duration_delta_minutes=(
            actual_minutes - planned_minutes
        ),
    )


def test_builds_restaurant_turn_profile():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=70,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=100,
        ),
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None

    assert result.restaurant_id == restaurant_id
    assert result.sample_count == 3

    assert (
        result.mean_actual_dining_minutes
        == 83.33
    )

    assert (
        result.median_actual_dining_minutes
        == 80
    )

    assert (
        result.min_actual_dining_minutes
        == 70
    )

    assert (
        result.max_actual_dining_minutes
        == 100
    )

    assert (
        result.mean_duration_delta_minutes
        == -6.67
    )


def test_empty_observations_return_no_profile():
    result = (
        TemporalLearningService
        .build_restaurant_profile([])
    )

    assert result is None


def test_profile_rejects_mixed_restaurants():
    observations = [
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=90,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalLearningService
            .build_restaurant_profile(
                observations,
            )
        )


def test_profile_tracks_planned_vs_actual_delta():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=75,
            planned_minutes=90,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=105,
            planned_minutes=90,
        ),
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None

    assert (
        result.mean_actual_dining_minutes
        == 90
    )

    assert (
        result.mean_duration_delta_minutes
        == 0
    )

def test_builds_party_size_profiles():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=60,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=70,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=90,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=110,
        ),
    ]

    observations[0].party_size = 2
    observations[1].party_size = 2
    observations[2].party_size = 4
    observations[3].party_size = 4

    profiles = (
        TemporalLearningService
        .build_party_size_profiles(
            observations,
        )
    )

    assert len(profiles) == 2

    party_two = profiles[0]

    assert party_two.party_size == 2
    assert party_two.sample_count == 2
    assert (
        party_two.mean_actual_dining_minutes
        == 65
    )
    assert (
        party_two.median_actual_dining_minutes
        == 65
    )
    assert (
        party_two.mean_duration_delta_minutes
        == -25
    )

    party_four = profiles[1]

    assert party_four.party_size == 4
    assert party_four.sample_count == 2
    assert (
        party_four.mean_actual_dining_minutes
        == 100
    )
    assert (
        party_four.median_actual_dining_minutes
        == 100
    )
    assert (
        party_four.mean_duration_delta_minutes
        == 10
    )


def test_party_size_profiles_are_sorted():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=100,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=70,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=85,
        ),
    ]

    observations[0].party_size = 6
    observations[1].party_size = 2
    observations[2].party_size = 4

    profiles = (
        TemporalLearningService
        .build_party_size_profiles(
            observations,
        )
    )

    assert [
        profile.party_size
        for profile in profiles
    ] == [
        2,
        4,
        6,
    ]


def test_empty_observations_return_no_party_size_profiles():
    profiles = (
        TemporalLearningService
        .build_party_size_profiles([])
    )

    assert profiles == []


def test_party_size_profiles_reject_mixed_restaurants():
    observations = [
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=90,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalLearningService
            .build_party_size_profiles(
                observations,
            )
        )

def test_builds_day_of_week_profiles():
    restaurant_id = uuid4()

    monday = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=70,
    )
    monday.reservation_time = datetime(
        2026,
        9,
        7,
        18,
        0,
    )

    friday_one = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=90,
    )
    friday_one.reservation_time = datetime(
        2026,
        9,
        11,
        18,
        0,
    )

    friday_two = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=110,
    )
    friday_two.reservation_time = datetime(
        2026,
        9,
        11,
        20,
        0,
    )

    profiles = (
        TemporalLearningService
        .build_day_of_week_profiles(
            [
                monday,
                friday_one,
                friday_two,
            ],
        )
    )

    assert len(profiles) == 2

    monday_profile = profiles[0]

    assert monday_profile.day_of_week == 0
    assert monday_profile.sample_count == 1
    assert (
        monday_profile.mean_actual_dining_minutes
        == 70
    )

    friday_profile = profiles[1]

    assert friday_profile.day_of_week == 4
    assert friday_profile.sample_count == 2
    assert (
        friday_profile.mean_actual_dining_minutes
        == 100
    )
    assert (
        friday_profile.median_actual_dining_minutes
        == 100
    )


def test_day_of_week_profiles_are_sorted():
    restaurant_id = uuid4()

    sunday = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=100,
    )
    sunday.reservation_time = datetime(
        2026,
        9,
        13,
        18,
        0,
    )

    tuesday = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=80,
    )
    tuesday.reservation_time = datetime(
        2026,
        9,
        8,
        18,
        0,
    )

    friday = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=90,
    )
    friday.reservation_time = datetime(
        2026,
        9,
        11,
        18,
        0,
    )

    profiles = (
        TemporalLearningService
        .build_day_of_week_profiles(
            [
                sunday,
                tuesday,
                friday,
            ],
        )
    )

    assert [
        profile.day_of_week
        for profile in profiles
    ] == [
        1,
        4,
        6,
    ]


def test_empty_observations_return_no_day_of_week_profiles():
    profiles = (
        TemporalLearningService
        .build_day_of_week_profiles([])
    )

    assert profiles == []


def test_day_of_week_profiles_reject_mixed_restaurants():
    observations = [
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=90,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalLearningService
            .build_day_of_week_profiles(
                observations,
            )
        )

def test_builds_daypart_profiles():
    restaurant_id = uuid4()

    lunch_one = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=60,
    )
    lunch_one.reservation_time = datetime(
        2026,
        9,
        10,
        12,
        0,
    )

    lunch_two = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=70,
    )
    lunch_two.reservation_time = datetime(
        2026,
        9,
        10,
        14,
        30,
    )

    dinner_one = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=90,
    )
    dinner_one.reservation_time = datetime(
        2026,
        9,
        10,
        19,
        0,
    )

    dinner_two = _observation(
        restaurant_id=restaurant_id,
        actual_minutes=110,
    )
    dinner_two.reservation_time = datetime(
        2026,
        9,
        10,
        21,
        30,
    )

    profiles = (
        TemporalLearningService
        .build_daypart_profiles(
            [
                lunch_one,
                lunch_two,
                dinner_one,
                dinner_two,
            ],
        )
    )

    assert len(profiles) == 2

    lunch = profiles[0]

    assert lunch.daypart == TemporalDaypart.LUNCH
    assert lunch.sample_count == 2
    assert (
        lunch.mean_actual_dining_minutes
        == 65
    )

    dinner = profiles[1]

    assert dinner.daypart == TemporalDaypart.DINNER
    assert dinner.sample_count == 2
    assert (
        dinner.mean_actual_dining_minutes
        == 100
    )


def test_daypart_boundaries_are_stable():
    assert (
        TemporalLearningService
        ._daypart_for_hour(10)
        == TemporalDaypart.OTHER
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(11)
        == TemporalDaypart.LUNCH
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(15)
        == TemporalDaypart.AFTERNOON
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(18)
        == TemporalDaypart.DINNER
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(22)
        == TemporalDaypart.LATE
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(2)
        == TemporalDaypart.LATE
    )

    assert (
        TemporalLearningService
        ._daypart_for_hour(3)
        == TemporalDaypart.OTHER
    )


def test_empty_observations_return_no_daypart_profiles():
    profiles = (
        TemporalLearningService
        .build_daypart_profiles([])
    )

    assert profiles == []


def test_daypart_profiles_reject_mixed_restaurants():
    observations = [
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=uuid4(),
            actual_minutes=90,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalLearningService
            .build_daypart_profiles(
                observations,
            )
        )


def test_builds_service_area_profiles():
    restaurant_id = uuid4()

    indoor_id = uuid4()
    terrace_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=indoor_id,
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=indoor_id,
            actual_minutes=100,
        ),
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=terrace_id,
            actual_minutes=60,
        ),
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=terrace_id,
            actual_minutes=70,
        ),
    ]

    profiles = (
        TemporalLearningService
        .build_service_area_profiles(
            observations,
        )
    )

    assert len(profiles) == 2

    profiles_by_area = {
        profile.service_area_id: profile
        for profile in profiles
    }

    indoor = profiles_by_area[indoor_id]

    assert indoor.sample_count == 2
    assert (
        indoor.mean_actual_dining_minutes
        == 90
    )
    assert (
        indoor.median_actual_dining_minutes
        == 90
    )

    terrace = profiles_by_area[terrace_id]

    assert terrace.sample_count == 2
    assert (
        terrace.mean_actual_dining_minutes
        == 65
    )
    assert (
        terrace.median_actual_dining_minutes
        == 65
    )


def test_service_area_profiles_ignore_unknown_area():
    restaurant_id = uuid4()
    service_area_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=service_area_id,
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=restaurant_id,
            service_area_id=None,
            actual_minutes=150,
        ),
    ]

    profiles = (
        TemporalLearningService
        .build_service_area_profiles(
            observations,
        )
    )

    assert len(profiles) == 1

    assert (
        profiles[0].service_area_id
        == service_area_id
    )

    assert profiles[0].sample_count == 1

    assert (
        profiles[0].mean_actual_dining_minutes
        == 80
    )


def test_empty_observations_return_no_service_area_profiles():
    profiles = (
        TemporalLearningService
        .build_service_area_profiles([])
    )

    assert profiles == []


def test_service_area_profiles_reject_mixed_restaurants():
    observations = [
        _observation(
            restaurant_id=uuid4(),
            service_area_id=uuid4(),
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=uuid4(),
            service_area_id=uuid4(),
            actual_minutes=90,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="same restaurant",
    ):
        (
            TemporalLearningService
            .build_service_area_profiles(
                observations,
            )
        )

def test_sparse_sample_state():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=90,
        ),
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None
    assert (
        result.sample_state
        == TemporalSampleState.SPARSE
    )
    assert result.sample_count == 2
    assert result.included_sample_count == 2
    assert result.excluded_outlier_count == 0


def test_developing_sample_state():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=80 + index,
        )
        for index in range(5)
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None
    assert (
        result.sample_state
        == TemporalSampleState.DEVELOPING
    )
    assert result.sample_count == 5


def test_established_sample_state():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=80 + index,
        )
        for index in range(8)
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None
    assert (
        result.sample_state
        == TemporalSampleState.ESTABLISHED
    )
    assert result.sample_count == 8


def test_small_samples_are_not_outlier_filtered():
    restaurant_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=70,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=80,
        ),
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=300,
        ),
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None

    assert result.sample_count == 3
    assert result.included_sample_count == 3
    assert result.excluded_outlier_count == 0

    assert (
        result.max_actual_dining_minutes
        == 300
    )


def test_established_profile_filters_extreme_outlier():
    restaurant_id = uuid4()

    durations = [
        78,
        80,
        82,
        84,
        85,
        86,
        88,
        300,
    ]

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=duration,
        )
        for duration in durations
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None

    assert result.sample_count == 8
    assert result.included_sample_count == 7
    assert result.excluded_outlier_count == 1

    assert (
        result.sample_state
        == TemporalSampleState.ESTABLISHED
    )

    assert (
        result.max_actual_dining_minutes
        == 88
    )

    assert (
        result.median_actual_dining_minutes
        == 84
    )


def test_normal_established_profile_keeps_all_samples():
    restaurant_id = uuid4()

    durations = [
        76,
        78,
        80,
        82,
        84,
        86,
        88,
        90,
    ]

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            actual_minutes=duration,
        )
        for duration in durations
    ]

    result = (
        TemporalLearningService
        .build_restaurant_profile(
            observations,
        )
    )

    assert result is not None

    assert result.sample_count == 8
    assert result.included_sample_count == 8
    assert result.excluded_outlier_count == 0


def test_outlier_filtering_is_applied_per_segment():
    restaurant_id = uuid4()

    observations = []

    for duration in [
        70,
        72,
        74,
        76,
        78,
        80,
        82,
        250,
    ]:
        observation = _observation(
            restaurant_id=restaurant_id,
            actual_minutes=duration,
        )
        observation.party_size = 2
        observations.append(observation)

    for duration in [
        100,
        105,
        110,
    ]:
        observation = _observation(
            restaurant_id=restaurant_id,
            actual_minutes=duration,
        )
        observation.party_size = 6
        observations.append(observation)

    profiles = (
        TemporalLearningService
        .build_party_size_profiles(
            observations,
        )
    )

    profiles_by_party = {
        profile.party_size: profile
        for profile in profiles
    }

    party_two = profiles_by_party[2]

    assert party_two.sample_count == 8
    assert party_two.included_sample_count == 7
    assert party_two.excluded_outlier_count == 1

    party_six = profiles_by_party[6]

    assert party_six.sample_count == 3
    assert party_six.included_sample_count == 3
    assert party_six.excluded_outlier_count == 0