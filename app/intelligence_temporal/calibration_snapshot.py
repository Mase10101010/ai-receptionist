from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .calibration_metrics import (
    TemporalAccuracyMetrics,
    TemporalCalibrationMetricsService,
)
from .calibration_state import (
    TemporalCalibrationAssessment,
    TemporalCalibrationStateService,
)
from .confidence_calibration import (
    TemporalConfidenceCalibrationSnapshot,
    TemporalConfidenceCalibrationService,
)
from .outcome_reader import (
    TemporalOutcomeEventReader,
)
from .source_calibration import (
    TemporalSourceCalibrationService,
    TemporalSourceCalibrationSnapshot,
)


class TemporalCalibrationSnapshot(BaseModel):
    restaurant_id: UUID

    metrics: TemporalAccuracyMetrics

    confidence: TemporalConfidenceCalibrationSnapshot

    sources: TemporalSourceCalibrationSnapshot

    assessment: TemporalCalibrationAssessment


class TemporalCalibrationSnapshotService:
    """
    Builds a read-only temporal calibration snapshot.

    Pipeline:
        persisted outcome events
            ->
        typed outcomes
            ->
        aggregate metrics
            ->
        confidence breakdown
            ->
        source breakdown
            ->
        calibration assessment

    No persistence.
    No event writes.
    No Brain integration.
    No optimizer integration.
    No Autopilot integration.
    """

    def __init__(
        self,
        *,
        outcome_reader: TemporalOutcomeEventReader | None = None,
    ) -> None:
        self.outcome_reader = (
            outcome_reader
            or TemporalOutcomeEventReader()
        )

    async def build(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
        limit: int = TemporalOutcomeEventReader.DEFAULT_LIMIT,
    ) -> TemporalCalibrationSnapshot:
        outcomes = await (
            self.outcome_reader.list_for_restaurant(
                session=session,
                restaurant_id=restaurant_id,
                occurred_after=occurred_after,
                occurred_before=occurred_before,
                limit=limit,
            )
        )

        metrics = (
            TemporalCalibrationMetricsService
            .calculate(outcomes)
        )

        confidence = (
            TemporalConfidenceCalibrationService
            .calculate(outcomes)
        )

        sources = (
            TemporalSourceCalibrationService
            .calculate(outcomes)
        )

        assessment = (
            TemporalCalibrationStateService
            .assess(metrics)
        )

        return TemporalCalibrationSnapshot(
            restaurant_id=restaurant_id,
            metrics=metrics,
            confidence=confidence,
            sources=sources,
            assessment=assessment,
        )