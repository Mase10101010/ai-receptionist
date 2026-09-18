from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.intelligence.types import (
    AssignmentKind,
    CandidateAssignment,
    ScoredAssignment,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.learning import (
    PartySizeTurnProfile,
    ServiceAreaTurnProfile,
    TemporalSampleState,
)
from app.intelligence_temporal.optimization_duration import (
    TemporalOptimizationDurationSource,
)
from app.intelligence_temporal.optimization_duration_resolver import (
    TemporalOptimizationDurationResolver,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.snapshot import (
    TemporalLearningSnapshot,
)


NOW = datetime(
    2026,
    9,
    7,
    19,
    0,
    tzinfo=timezone.utc,
)

RESTAURANT_ID = uuid4()
SERVICE_AREA_ID = uuid4()
TABLE_ID = uuid4()


def _candidate(
    *,
    area_id: str | None = None,
    duration_minutes: int = 90,
) -> ScoredAssignment:
    return ScoredAssignment(
        candidate=CandidateAssignment(
            kind=AssignmentKind.SINGLE_TABLE,
            resource_id=str(TABLE_ID),
            table_ids=(str(TABLE_ID),),
            start_at=NOW,
            end_at=(
                NOW
                + timedelta(
                    minutes=duration_minutes,
                )
            ),
            capacity=4,
            minimum_capacity=1,
            area_id=area_id,
            floor_id=None,
            setup_minutes=0,
        ),
        score=90.0,
        seat_waste=0,
        fragmentation_minutes=0,
        explanation="Candidate.",
    )


def _calibration(
    state: TemporalCalibrationState,
):
    return SimpleNamespace(
        state=state,
    )


def _empty_snapshot():
    return TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=0,
    )


def _party_snapshot(
    *,
    sample_count: int = 40,
    delta_minutes: float = 15.0,
):
    actual_duration = (
        90.0 + delta_minutes
    )

    return TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=(
            sample_count
        ),
        party_size_profiles=[
            PartySizeTurnProfile(
                restaurant_id=RESTAURANT_ID,
                party_size=4,
                sample_count=sample_count,
                included_sample_count=(
                    sample_count
                ),
                excluded_outlier_count=0,
                sample_state=(
                    TemporalSampleState.ESTABLISHED
                ),
                mean_actual_dining_minutes=(
                    actual_duration
                ),
                median_actual_dining_minutes=(
                    actual_duration
                ),
                min_actual_dining_minutes=(
                    actual_duration
                ),
                max_actual_dining_minutes=(
                    actual_duration
                ),
                mean_planned_duration_minutes=90.0,
                mean_duration_delta_minutes=(
                    delta_minutes
                ),
            )
        ],
    )


def _area_snapshot(
    *,
    sample_count: int = 50,
    delta_minutes: float = 20.0,
):
    actual_duration = (
        90.0 + delta_minutes
    )

    return TemporalLearningSnapshot(
        restaurant_id=RESTAURANT_ID,
        generated_from_sample_count=(
            sample_count
        ),
        service_area_profiles=[
            ServiceAreaTurnProfile(
                restaurant_id=RESTAURANT_ID,
                service_area_id=SERVICE_AREA_ID,
                sample_count=sample_count,
                included_sample_count=(
                    sample_count
                ),
                excluded_outlier_count=0,
                sample_state=(
                    TemporalSampleState.ESTABLISHED
                ),
                mean_actual_dining_minutes=(
                    actual_duration
                ),
                median_actual_dining_minutes=(
                    actual_duration
                ),
                min_actual_dining_minutes=(
                    actual_duration
                ),
                max_actual_dining_minutes=(
                    actual_duration
                ),
                mean_planned_duration_minutes=90.0,
                mean_duration_delta_minutes=(
                    delta_minutes
                ),
            )
        ],
    )


def test_no_learning_preserves_planned_duration():
    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=_candidate(),
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_empty_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert (
        result.decision.duration_minutes
        == 90
    )

    assert (
        result.decision.used_expected_duration
        is False
    )

    assert (
        result.prediction.source
        == ExpectedTurnSource.PLANNED_FALLBACK
    )


def test_high_confidence_well_calibrated_pattern_is_used():
    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=_candidate(),
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_party_snapshot(
                sample_count=40,
                delta_minutes=15,
            ),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert (
        result.prediction.confidence
        == ExpectedTurnConfidence.HIGH
    )

    assert (
        result.prediction
        .expected_duration_minutes
        == 105
    )

    assert (
        result.decision.duration_minutes
        == 105
    )

    assert (
        result.decision.source
        == TemporalOptimizationDurationSource
        .EXPECTED
    )


def test_unreliable_calibration_preserves_planned_duration():
    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=_candidate(),
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_party_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .UNRELIABLE
            ),
        )
    )

    assert (
        result.prediction.used_learned_pattern
        is True
    )

    assert (
        result.decision.duration_minutes
        == 90
    )

    assert (
        result.decision.used_expected_duration
        is False
    )


def test_valid_candidate_area_is_forwarded_to_prediction():
    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=_candidate(
                area_id=str(
                    SERVICE_AREA_ID
                ),
            ),
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_area_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert (
        result.service_area_id
        == SERVICE_AREA_ID
    )

    assert (
        result.prediction.source
        == ExpectedTurnSource.SERVICE_AREA
    )

    assert (
        result.decision.duration_minutes
        == 110
    )


def test_non_uuid_candidate_area_falls_back_without_failure():
    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=_candidate(
                area_id="main",
            ),
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_empty_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert result.service_area_id is None

    assert (
        result.decision.duration_minutes
        == 90
    )


def test_candidate_time_is_used_for_prediction_context():
    candidate = _candidate()

    result = (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=candidate,
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_empty_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    # No learned pattern means planned fallback,
    # but resolution must still succeed using the
    # candidate's weekday/hour context.
    assert (
        result.prediction
        .planned_duration_minutes
        == 90
    )


def test_resolution_does_not_mutate_candidate():
    candidate = _candidate(
        duration_minutes=90,
    )

    original_start = (
        candidate.candidate.start_at
    )

    original_end = (
        candidate.candidate.end_at
    )

    (
        TemporalOptimizationDurationResolver
        .resolve(
            candidate=candidate,
            party_size=4,
            planned_duration_minutes=90,
            snapshot=_party_snapshot(),
            calibration=_calibration(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
        )
    )

    assert (
        candidate.candidate.start_at
        == original_start
    )

    assert (
        candidate.candidate.end_at
        == original_end
    )


@pytest.mark.parametrize(
    "party_size",
    [
        0,
        -1,
    ],
)
def test_invalid_party_size_fails_closed(
    party_size,
):
    with pytest.raises(
        ValueError,
        match="party_size",
    ):
        (
            TemporalOptimizationDurationResolver
            .resolve(
                candidate=_candidate(),
                party_size=party_size,
                planned_duration_minutes=90,
                snapshot=_empty_snapshot(),
                calibration=_calibration(
                    TemporalCalibrationState
                    .WELL_CALIBRATED
                ),
            )
        )


def test_invalid_planned_duration_fails_closed():
    with pytest.raises(
        ValueError,
        match="planned duration",
    ):
        (
            TemporalOptimizationDurationResolver
            .resolve(
                candidate=_candidate(),
                party_size=4,
                planned_duration_minutes=0,
                snapshot=_empty_snapshot(),
                calibration=_calibration(
                    TemporalCalibrationState
                    .WELL_CALIBRATED
                ),
            )
        )