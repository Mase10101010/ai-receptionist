from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from app.intelligence.optimizer import ReservationOptimizer
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
    ScoredAssignment,
    TableCombination,
)

from .candidate_scenario import (
    TemporalCandidateScenarioBuilder,
)
from .schemas import (
    FutureCapacityRequest,
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)


class TemporalCounterfactualCapacityRun(BaseModel):
    baseline: FutureCapacityResponse
    candidate: FutureCapacityResponse

    candidate_occupancy_duration_minutes: int


class TemporalCounterfactualCapacityRunner:
    """
    Runs the same deterministic optimizer against:

    1. existing baseline reservations
    2. the same reservations plus one candidate scenario

    Invariants:
    - same optimizer for both profiles
    - same tables / combinations
    - same future-capacity request
    - optional temporal occupancy affects only the synthetic candidate
    - no DB
    - no persistence
    - no candidate ranking changes
    - no score mutation
    - no Brain
    - no Autopilot
    """

    def __init__(
        self,
        *,
        optimizer: ReservationOptimizer | None = None,
    ) -> None:
        self.optimizer = (
            optimizer
            or ReservationOptimizer()
        )

    def run(
        self,
        *,
        request: FutureCapacityRequest,
        candidate: ScoredAssignment,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None = None,
        candidate_party_size: int,
        candidate_occupancy_duration_minutes: int | None = None,
    ) -> TemporalCounterfactualCapacityRun:
        scenario = TemporalCandidateScenarioBuilder.build(
            candidate=candidate,
            reservations=reservations,
            party_size=candidate_party_size,
            occupancy_duration_minutes=(
                candidate_occupancy_duration_minutes
            ),
        )

        baseline = self._profile(
            request=request,
            tables=tables,
            reservations=list(
                scenario.baseline_reservations
            ),
            combinations=combinations,
        )

        candidate_profile = self._profile(
            request=request,
            tables=tables,
            reservations=list(
                scenario.candidate_reservations
            ),
            combinations=combinations,
        )

        return TemporalCounterfactualCapacityRun(
            baseline=baseline,
            candidate=candidate_profile,
            candidate_occupancy_duration_minutes=(
                scenario.occupancy_duration_minutes
            ),
        )

    def _profile(
        self,
        *,
        request: FutureCapacityRequest,
        tables: list[IntelligenceTable],
        reservations: list[ExistingReservation],
        combinations: list[TableCombination] | None,
    ) -> FutureCapacityResponse:
        slots: list[FutureCapacitySlot] = []

        offset_minutes = 0

        while offset_minutes <= request.horizon_minutes:
            slot_start = (
                request.start_at
                + timedelta(
                    minutes=offset_minutes,
                )
            )

            result = self.optimizer.optimize(
                request=OptimizationRequest(
                    requested_start=slot_start,
                    party_size=request.party_size,
                    duration_minutes=(
                        request.duration_minutes
                    ),
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_area_id=None,
                    preferred_floor_id=None,
                    allow_combinations=True,
                    max_alternatives=1,
                ),
                tables=tables,
                reservations=reservations,
                combinations=combinations,
            )

            slot_end = (
                slot_start
                + timedelta(
                    minutes=request.duration_minutes,
                )
            )

            recommendation = (
                result.recommended
                if result.available
                else None
            )

            if recommendation is None:
                slots.append(
                    FutureCapacitySlot(
                        start_at=slot_start,
                        end_at=slot_end,
                        directly_available=False,
                    )
                )
            else:
                slots.append(
                    self._available_slot(
                        recommendation=(
                            recommendation
                        ),
                        tables=tables,
                    )
                )

            offset_minutes += request.slot_minutes

        return FutureCapacityResponse(
            restaurant_id=request.restaurant_id,
            start_at=request.start_at,
            party_size=request.party_size,
            duration_minutes=request.duration_minutes,
            horizon_minutes=request.horizon_minutes,
            slot_minutes=request.slot_minutes,
            slots=slots,
            summary=self._build_summary(slots),
        )

    @staticmethod
    def _available_slot(
        *,
        recommendation: ScoredAssignment,
        tables: list[IntelligenceTable],
    ) -> FutureCapacitySlot:
        candidate = recommendation.candidate

        table_number_by_id = {
            table.id: table.table_number
            for table in tables
        }

        try:
            table_ids = [
                UUID(table_id)
                for table_id in candidate.table_ids
            ]
        except ValueError as exc:
            raise ValueError(
                "Optimizer table IDs must be valid UUIDs "
                "for temporal capacity profiles."
            ) from exc

        return FutureCapacitySlot(
            start_at=candidate.start_at,
            end_at=candidate.end_at,
            directly_available=True,
            table_ids=table_ids,
            table_numbers=[
                table_number_by_id.get(
                    table_id,
                    table_id,
                )
                for table_id in candidate.table_ids
            ],
            assignment_capacity=candidate.capacity,
            seat_waste=recommendation.seat_waste,
        )

    @staticmethod
    def _build_summary(
        slots: list[FutureCapacitySlot],
    ) -> FutureCapacitySummary:
        total_slots = len(slots)

        available_slots = sum(
            1
            for slot in slots
            if slot.directly_available
        )

        unavailable_slots = (
            total_slots - available_slots
        )

        longest_run = 0
        current_run = 0

        for slot in slots:
            if slot.directly_available:
                current_run += 1
                longest_run = max(
                    longest_run,
                    current_run,
                )
            else:
                current_run = 0

        first_available = next(
            (
                slot.start_at
                for slot in slots
                if slot.directly_available
            ),
            None,
        )

        return FutureCapacitySummary(
            total_slots=total_slots,
            directly_available_slots=available_slots,
            unavailable_slots=unavailable_slots,
            availability_ratio=round(
                (
                    available_slots / total_slots
                    if total_slots
                    else 0.0
                ),
                4,
            ),
            first_directly_available_at=(
                first_available
            ),
            longest_directly_available_run=(
                longest_run
            ),
        )
