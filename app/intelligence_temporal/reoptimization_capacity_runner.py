from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from app.intelligence.optimizer import (
    ReservationOptimizer,
)
from app.intelligence.types import (
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
    ReoptimizationPlan,
    ScoredAssignment,
    TableCombination,
)

from .reoptimization_scenario import (
    TemporalReoptimizationScenarioBuilder,
)
from .schemas import (
    FutureCapacityRequest,
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)


class TemporalReoptimizationCapacityRun(BaseModel):
    """
    Future-capacity profiles before and after one exact
    reoptimization plan.
    """

    baseline: FutureCapacityResponse
    candidate: FutureCapacityResponse

    new_reservation_id: str
    moved_reservation_ids: tuple[str, ...]


class TemporalReoptimizationCapacityRunner:
    """
    Deterministic future-capacity counterfactual for one exact
    ReoptimizationPlan.

    Pipeline:

        baseline reservations
            +
        exact reoptimization plan
            ->
        post-plan reservation scenario
            ->
        same raw optimizer over future slots
            ->
        baseline / candidate capacity profiles

    Invariants:
    - same optimizer for both profiles
    - same tables and combinations
    - same FutureCapacityRequest
    - no high-level IntelligenceOptimizationService
    - no recursion
    - no DB
    - no persistence
    - no reoptimizer calls
    - no ranking changes
    - no score mutation
    - no Brain
    - no Autopilot authority
    - no ML
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
        plan: ReoptimizationPlan,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
        combinations: list[TableCombination] | None,
        new_reservation_id: str,
        new_reservation_party_size: int,
    ) -> TemporalReoptimizationCapacityRun:
        scenario = (
            TemporalReoptimizationScenarioBuilder.build(
                reservations=reservations,
                plan=plan,
                new_reservation_id=new_reservation_id,
                new_reservation_party_size=(
                    new_reservation_party_size
                ),
            )
        )

        baseline = self._profile(
            request=request,
            reservations=list(
                scenario.baseline_reservations
            ),
            tables=tables,
            combinations=combinations,
        )

        candidate = self._profile(
            request=request,
            reservations=list(
                scenario.candidate_reservations
            ),
            tables=tables,
            combinations=combinations,
        )

        return TemporalReoptimizationCapacityRun(
            baseline=baseline,
            candidate=candidate,
            new_reservation_id=(
                scenario.new_reservation_id
            ),
            moved_reservation_ids=(
                scenario.moved_reservation_ids
            ),
        )

    def _profile(
        self,
        *,
        request: FutureCapacityRequest,
        reservations: list[ExistingReservation],
        tables: list[IntelligenceTable],
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

            slot_end = (
                slot_start
                + timedelta(
                    minutes=request.duration_minutes,
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
                "for temporal reoptimization capacity."
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
            assignment_capacity=(
                candidate.capacity
            ),
            seat_waste=(
                recommendation.seat_waste
            ),
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

        first_available = next(
            (
                slot.start_at
                for slot in slots
                if slot.directly_available
            ),
            None,
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

        return FutureCapacitySummary(
            total_slots=total_slots,
            directly_available_slots=(
                available_slots
            ),
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