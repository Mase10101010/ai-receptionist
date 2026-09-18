from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_temporal.calibration_snapshot import (
    TemporalCalibrationSnapshotService,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnSource,
)
from app.intelligence_temporal.prediction_truth import (
    TemporalTurnPredictionOutcome,
)


def _outcome(
    *,
    restaurant_id,
    confidence: ExpectedTurnConfidence,
    signed_error_minutes: int,
) -> TemporalTurnPredictionOutcome:
    predicted_duration_minutes = 100

    return TemporalTurnPredictionOutcome(
        reservation_id=uuid4(),
        restaurant_id=restaurant_id,
        predicted_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            9,
            6,
            19,
            40,
            tzinfo=timezone.utc,
        ),
        predicted_duration_minutes=(
            predicted_duration_minutes
        ),
        actual_duration_minutes=(
            predicted_duration_minutes
            + signed_error_minutes
        ),
        signed_error_minutes=(
            signed_error_minutes
        ),
        absolute_error_minutes=abs(
            signed_error_minutes
        ),
        source=ExpectedTurnSource.PARTY_SIZE,
        source_sample_count=30,
        confidence=confidence,
        used_learned_pattern=True,
    )


@pytest.mark.asyncio
async def test_builds_empty_snapshot_as_insufficient_data():
    restaurant_id = uuid4()

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = []

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert snapshot.restaurant_id == restaurant_id

    assert snapshot.metrics.sample_count == 0

    assert (
        snapshot.assessment.state
        == TemporalCalibrationState
        .INSUFFICIENT_DATA
    )

    assert (
        snapshot.confidence.low.metrics.sample_count
        == 0
    )

    assert (
        snapshot.confidence.medium.metrics.sample_count
        == 0
    )

    assert (
        snapshot.confidence.high.metrics.sample_count
        == 0
    )


@pytest.mark.asyncio
async def test_builds_well_calibrated_snapshot():
    restaurant_id = uuid4()

    outcomes = [
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=2,
        )
        for _ in range(15)
    ]

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = outcomes

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert snapshot.metrics.sample_count == 15

    assert (
        snapshot.metrics
        .mean_absolute_error_minutes
        == 2
    )

    assert (
        snapshot.metrics
        .mean_signed_error_minutes
        == 2
    )

    assert (
        snapshot.assessment.state
        == TemporalCalibrationState
        .WELL_CALIBRATED
    )

    assert (
        snapshot.confidence.high.metrics
        .sample_count
        == 15
    )


@pytest.mark.asyncio
async def test_snapshot_preserves_confidence_breakdown():
    restaurant_id = uuid4()

    outcomes = [
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.LOW,
            signed_error_minutes=20,
        ),
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.MEDIUM,
            signed_error_minutes=10,
        ),
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=3,
        ),
    ]

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = outcomes

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert (
        snapshot.confidence.low.metrics
        .mean_absolute_error_minutes
        == 20
    )

    assert (
        snapshot.confidence.medium.metrics
        .mean_absolute_error_minutes
        == 10
    )

    assert (
        snapshot.confidence.high.metrics
        .mean_absolute_error_minutes
        == 3
    )


@pytest.mark.asyncio
async def test_snapshot_detects_underpredicting():
    restaurant_id = uuid4()

    outcomes = [
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=8,
        )
        for _ in range(20)
    ]

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = outcomes

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert (
        snapshot.assessment.state
        == TemporalCalibrationState
        .UNDERPREDICTING
    )


@pytest.mark.asyncio
async def test_snapshot_detects_unreliable_predictions():
    restaurant_id = uuid4()

    outcomes = []

    for index in range(20):
        signed_error = (
            20
            if index % 2 == 0
            else -20
        )

        outcomes.append(
            _outcome(
                restaurant_id=restaurant_id,
                confidence=ExpectedTurnConfidence.HIGH,
                signed_error_minutes=signed_error,
            )
        )

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = outcomes

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    assert (
        snapshot.metrics
        .mean_signed_error_minutes
        == 0
    )

    assert (
        snapshot.metrics
        .mean_absolute_error_minutes
        == 20
    )

    assert (
        snapshot.assessment.state
        == TemporalCalibrationState
        .UNRELIABLE
    )


@pytest.mark.asyncio
async def test_snapshot_passes_reader_filters_through():
    restaurant_id = uuid4()

    occurred_after = datetime(
        2026,
        8,
        1,
        tzinfo=timezone.utc,
    )

    occurred_before = datetime(
        2026,
        9,
        1,
        tzinfo=timezone.utc,
    )

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = []

    session = object()

    await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=session,
            restaurant_id=restaurant_id,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
            limit=500,
        )
    )

    reader.list_for_restaurant.assert_awaited_once_with(
        session=session,
        restaurant_id=restaurant_id,
        occurred_after=occurred_after,
        occurred_before=occurred_before,
        limit=500,
    )

@pytest.mark.asyncio
async def test_snapshot_preserves_source_breakdown():
    restaurant_id = uuid4()

    outcomes = [
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=4,
        ),
        _outcome(
            restaurant_id=restaurant_id,
            confidence=ExpectedTurnConfidence.HIGH,
            signed_error_minutes=-6,
        ),
    ]

    outcomes[0] = outcomes[0].model_copy(
        update={
            "source": ExpectedTurnSource.PARTY_SIZE,
        }
    )

    outcomes[1] = outcomes[1].model_copy(
        update={
            "source": ExpectedTurnSource.DAYPART,
        }
    )

    reader = AsyncMock()
    reader.list_for_restaurant.return_value = outcomes

    snapshot = await (
        TemporalCalibrationSnapshotService(
            outcome_reader=reader,
        )
        .build(
            session=object(),
            restaurant_id=restaurant_id,
        )
    )

    party_size = snapshot.sources.for_source(
        ExpectedTurnSource.PARTY_SIZE
    )

    daypart = snapshot.sources.for_source(
        ExpectedTurnSource.DAYPART
    )

    assert party_size.metrics.sample_count == 1
    assert (
        party_size.metrics.mean_absolute_error_minutes
        == 4
    )

    assert daypart.metrics.sample_count == 1
    assert (
        daypart.metrics.mean_absolute_error_minutes
        == 6
    )