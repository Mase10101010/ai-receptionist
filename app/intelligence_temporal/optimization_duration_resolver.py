from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.intelligence.types import (
    ScoredAssignment,
)

from .calibration_state import (
    TemporalCalibrationAssessment,
)
from .optimization_duration import (
    TemporalOptimizationDurationDecision,
    TemporalOptimizationDurationPolicy,
)
from .prediction import (
    ExpectedTurnPrediction,
    ExpectedTurnRequest,
    ExpectedTurnService,
)
from .snapshot import (
    TemporalLearningSnapshot,
)


class TemporalOptimizationDurationResolution(
    BaseModel
):
    """
    Candidate-aware temporal duration resolution.

    prediction:
        Expected Turn Time truth produced by T3.

    decision:
        Trusted-duration authority produced by T7.11.

    service_area_id:
        Candidate service-area context when it is a valid UUID.
    """

    prediction: ExpectedTurnPrediction

    decision: TemporalOptimizationDurationDecision

    service_area_id: UUID | None = None


class TemporalOptimizationDurationResolver:
    """
    Resolves the occupancy duration that temporal optimization
    may use for one technical optimizer candidate.

    Pipeline:

        technical candidate
            +
        temporal learning snapshot
            +
        temporal calibration
            ->
        ExpectedTurnService
            ->
        TemporalOptimizationDurationPolicy
            ->
        trusted occupancy duration

    Invariants:
    - technical candidate is immutable
    - reservation planned duration is immutable
    - no DB
    - no persistence
    - no event writes
    - no optimizer calls
    - no ranking
    - no Brain
    - no Autopilot
    - no ML
    - invalid/missing service area simply removes area context
    """

    @classmethod
    def resolve(
        cls,
        *,
        candidate: ScoredAssignment,
        party_size: int,
        planned_duration_minutes: int,
        snapshot: TemporalLearningSnapshot,
        calibration: TemporalCalibrationAssessment,
    ) -> TemporalOptimizationDurationResolution:
        if party_size <= 0:
            raise ValueError(
                "Temporal optimization party_size "
                "must be positive."
            )

        if planned_duration_minutes <= 0:
            raise ValueError(
                "Temporal optimization planned duration "
                "must be positive."
            )

        assignment = candidate.candidate

        if assignment.end_at <= assignment.start_at:
            raise ValueError(
                "Temporal optimization candidate end_at "
                "must be after start_at."
            )

        service_area_id = (
            cls._service_area_id(
                assignment.area_id
            )
        )

        prediction = ExpectedTurnService.predict(
            snapshot=snapshot,
            request=ExpectedTurnRequest(
                party_size=party_size,
                planned_duration_minutes=(
                    planned_duration_minutes
                ),
                day_of_week=(
                    assignment.start_at.weekday()
                ),
                hour=assignment.start_at.hour,
                service_area_id=service_area_id,
            ),
        )

        decision = (
            TemporalOptimizationDurationPolicy
            .decide(
                prediction=prediction,
                calibration=calibration,
            )
        )

        return (
            TemporalOptimizationDurationResolution(
                prediction=prediction,
                decision=decision,
                service_area_id=service_area_id,
            )
        )

    @staticmethod
    def _service_area_id(
        area_id: str | None,
    ) -> UUID | None:
        if area_id is None:
            return None

        try:
            return UUID(area_id)
        except (ValueError, TypeError):
            return None