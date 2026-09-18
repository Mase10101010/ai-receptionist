from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.schemas import (
    IntelligenceOptimizeRequest,
)
from app.intelligence.sqlalchemy_service import (
    IntelligenceOptimizationService,
)

from .schemas import (
    FutureCapacityRequest,
    FutureCapacityResponse,
    FutureCapacitySlot,
    FutureCapacitySummary,
)


class TemporalCapacityService:
    """
    Deterministic future-capacity profile.

    T1 intentionally reuses Alias Intelligence's existing direct optimizer.
    It does not perform reoptimization, prediction, learning, or ML.
    """

    def __init__(
        self,
        *,
        optimization_service: IntelligenceOptimizationService | None = None,
    ) -> None:
        self.optimization_service = (
            optimization_service
            or IntelligenceOptimizationService()
        )

    @staticmethod
    def _build_summary(
        slots: list[FutureCapacitySlot],
    ) -> FutureCapacitySummary:
        total_slots = len(slots)

        directly_available_slots = sum(
            1
            for slot in slots
            if slot.directly_available
        )

        unavailable_slots = (
            total_slots - directly_available_slots
        )

        availability_ratio = (
            directly_available_slots / total_slots
            if total_slots
            else 0.0
        )

        first_directly_available_at = next(
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
                directly_available_slots
            ),
            unavailable_slots=unavailable_slots,
            availability_ratio=round(
                availability_ratio,
                4,
            ),
            first_directly_available_at=(
                first_directly_available_at
            ),
            longest_directly_available_run=(
                longest_run
            ),
        )

    async def profile(
        self,
        *,
        session: AsyncSession,
        request: FutureCapacityRequest,
    ) -> FutureCapacityResponse:
        slots: list[FutureCapacitySlot] = []

        offset_minutes = 0

        while offset_minutes <= request.horizon_minutes:
            slot_start = request.start_at + timedelta(
                minutes=offset_minutes,
            )

            result = await self.optimization_service.optimize(
                session=session,
                payload=IntelligenceOptimizeRequest(
                    restaurant_id=request.restaurant_id,
                    reservation_id=None,
                    requested_start=slot_start,
                    party_size=request.party_size,
                    duration_minutes=request.duration_minutes,
                    buffer_before_minutes=0,
                    buffer_after_minutes=0,
                    preferred_service_area_id=None,
                    max_alternatives=1,
                ),
            )

            recommendation = (
                result.recommended
                if result.available
                else None
            )

            slot_end = slot_start + timedelta(
                minutes=request.duration_minutes,
            )

            if (
                recommendation is not None
                and recommendation.table_ids
            ):
                slots.append(
                    FutureCapacitySlot(
                        start_at=slot_start,
                        end_at=slot_end,
                        directly_available=True,
                        table_ids=list(
                            recommendation.table_ids,
                        ),
                        table_numbers=list(
                            recommendation.table_numbers,
                        ),
                        assignment_capacity=(
                            recommendation.capacity
                        ),
                        seat_waste=(
                            recommendation.seat_waste
                        ),
                    )
                )
            else:
                slots.append(
                    FutureCapacitySlot(
                        start_at=slot_start,
                        end_at=slot_end,
                        directly_available=False,
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