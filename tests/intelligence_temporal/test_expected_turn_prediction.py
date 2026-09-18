from uuid import uuid4

from app.intelligence_temporal.learning import (
    DaypartTurnProfile,
    PartySizeTurnProfile,
    RestaurantTurnProfile,
    ServiceAreaTurnProfile,
    TemporalDaypart,
    TemporalSampleState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnRequest,
    ExpectedTurnService,
    ExpectedTurnSource,
)
from app.intelligence_temporal.snapshot import (
    TemporalLearningSnapshot,
)


def _stats(
    *,
    sample_count,
    delta,
    state=TemporalSampleState.ESTABLISHED,
):
    return {
        "sample_count": sample_count,
        "included_sample_count": sample_count,
        "excluded_outlier_count": 0,
        "sample_state": state,
        "mean_actual_dining_minutes": (
            90 + delta
        ),
        "median_actual_dining_minutes": (
            90 + delta
        ),
        "min_actual_dining_minutes": (
            80 + delta
        ),
        "max_actual_dining_minutes": (
            100 + delta
        ),
        "mean_duration_delta_minutes": delta,
    }


def _snapshot(
    *,
    restaurant_id,
    restaurant_profile=None,
    party_profiles=None,
    daypart_profiles=None,
    service_area_profiles=None,
):
    return TemporalLearningSnapshot(
        restaurant_id=restaurant_id,
        generated_from_sample_count=100,
        restaurant_profile=restaurant_profile,
        party_size_profiles=(
            party_profiles or []
        ),
        day_of_week_profiles=[],
        daypart_profiles=(
            daypart_profiles or []
        ),
        service_area_profiles=(
            service_area_profiles or []
        ),
    )


def _request(
    *,
    planned=90,
    party_size=4,
    service_area_id=None,
):
    return ExpectedTurnRequest(
        party_size=party_size,
        planned_duration_minutes=planned,
        day_of_week=4,
        hour=19,
        service_area_id=service_area_id,
    )


def test_falls_back_to_planned_duration_without_learning():
    restaurant_id = uuid4()

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
        ),
        request=_request(
            planned=90,
        ),
    )

    assert (
        result.expected_duration_minutes
        == 90
    )

    assert result.adjustment_minutes == 0

    assert (
        result.source
        == ExpectedTurnSource.PLANNED_FALLBACK
    )

    assert (
        result.used_learned_pattern
        is False
    )


def test_sparse_context_does_not_change_prediction():
    restaurant_id = uuid4()

    party_profile = PartySizeTurnProfile(
        restaurant_id=restaurant_id,
        party_size=4,
        **_stats(
            sample_count=2,
            delta=40,
            state=TemporalSampleState.SPARSE,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            party_profiles=[
                party_profile,
            ],
        ),
        request=_request(),
    )

    assert (
        result.expected_duration_minutes
        == 90
    )

    assert (
        result.source
        == ExpectedTurnSource.PLANNED_FALLBACK
    )


def test_established_restaurant_profile_adjusts_planned_duration():
    restaurant_id = uuid4()

    restaurant_profile = (
        RestaurantTurnProfile(
            restaurant_id=restaurant_id,
            **_stats(
                sample_count=20,
                delta=12,
            ),
        )
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=(
                restaurant_profile
            ),
        ),
        request=_request(
            planned=120,
        ),
    )

    assert (
        result.expected_duration_minutes
        == 132
    )

    assert result.adjustment_minutes == 12

    assert (
        result.source
        == ExpectedTurnSource.RESTAURANT
    )


def test_contextual_profile_beats_restaurant_profile():
    restaurant_id = uuid4()

    restaurant_profile = (
        RestaurantTurnProfile(
            restaurant_id=restaurant_id,
            **_stats(
                sample_count=100,
                delta=5,
            ),
        )
    )

    party_profile = PartySizeTurnProfile(
        restaurant_id=restaurant_id,
        party_size=4,
        **_stats(
            sample_count=10,
            delta=18,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=(
                restaurant_profile
            ),
            party_profiles=[
                party_profile,
            ],
        ),
        request=_request(),
    )

    assert (
        result.expected_duration_minutes
        == 108
    )

    assert (
        result.source
        == ExpectedTurnSource.PARTY_SIZE
    )


def test_contextual_candidate_with_more_evidence_wins():
    restaurant_id = uuid4()
    service_area_id = uuid4()

    party_profile = PartySizeTurnProfile(
        restaurant_id=restaurant_id,
        party_size=4,
        **_stats(
            sample_count=8,
            delta=20,
        ),
    )

    area_profile = ServiceAreaTurnProfile(
        restaurant_id=restaurant_id,
        service_area_id=service_area_id,
        **_stats(
            sample_count=30,
            delta=-10,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            party_profiles=[
                party_profile,
            ],
            service_area_profiles=[
                area_profile,
            ],
        ),
        request=_request(
            service_area_id=service_area_id,
        ),
    )

    assert (
        result.expected_duration_minutes
        == 80
    )

    assert (
        result.source
        == ExpectedTurnSource.SERVICE_AREA
    )


def test_equal_evidence_uses_deterministic_specificity_priority():
    restaurant_id = uuid4()

    party_profile = PartySizeTurnProfile(
        restaurant_id=restaurant_id,
        party_size=4,
        **_stats(
            sample_count=10,
            delta=15,
        ),
    )

    daypart_profile = DaypartTurnProfile(
        restaurant_id=restaurant_id,
        daypart=TemporalDaypart.DINNER,
        **_stats(
            sample_count=10,
            delta=-5,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            party_profiles=[
                party_profile,
            ],
            daypart_profiles=[
                daypart_profile,
            ],
        ),
        request=_request(),
    )

    assert (
        result.expected_duration_minutes
        == 105
    )

    assert (
        result.source
        == ExpectedTurnSource.PARTY_SIZE
    )


def test_prediction_is_safely_clamped():
    restaurant_id = uuid4()

    restaurant_profile = (
        RestaurantTurnProfile(
            restaurant_id=restaurant_id,
            **_stats(
                sample_count=20,
                delta=-100,
            ),
        )
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=(
                restaurant_profile
            ),
        ),
        request=_request(
            planned=30,
        ),
    )

    assert (
        result.expected_duration_minutes
        == 15
    )

    assert result.adjustment_minutes == -15

def test_fallback_has_low_confidence():
    restaurant_id = uuid4()

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
        ),
        request=_request(),
    )

    assert (
        result.confidence
        == ExpectedTurnConfidence.LOW
    )


def test_established_profile_with_few_samples_has_low_confidence():
    restaurant_id = uuid4()

    profile = RestaurantTurnProfile(
        restaurant_id=restaurant_id,
        **_stats(
            sample_count=8,
            delta=10,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=profile,
        ),
        request=_request(),
    )

    assert (
        result.confidence
        == ExpectedTurnConfidence.LOW
    )


def test_prediction_has_medium_confidence_with_15_samples():
    restaurant_id = uuid4()

    profile = RestaurantTurnProfile(
        restaurant_id=restaurant_id,
        **_stats(
            sample_count=15,
            delta=10,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=profile,
        ),
        request=_request(),
    )

    assert (
        result.confidence
        == ExpectedTurnConfidence.MEDIUM
    )


def test_prediction_has_high_confidence_with_30_samples():
    restaurant_id = uuid4()

    profile = RestaurantTurnProfile(
        restaurant_id=restaurant_id,
        **_stats(
            sample_count=30,
            delta=10,
        ),
    )

    result = ExpectedTurnService.predict(
        snapshot=_snapshot(
            restaurant_id=restaurant_id,
            restaurant_profile=profile,
        ),
        request=_request(),
    )

    assert (
        result.confidence
        == ExpectedTurnConfidence.HIGH
    )