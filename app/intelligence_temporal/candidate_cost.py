from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
)

from .marginal_capacity import (
    TemporalMarginalCapacityLoss,
)


class TemporalCandidateCost(BaseModel):
    """
    Temporal opportunity-cost truth for one optimizer candidate.

    This model does not rank candidates and does not modify
    the optimizer's technical score.
    """

    table_ids: tuple[UUID, ...] = Field(
        min_length=1,
    )

    start_at: datetime
    end_at: datetime

    base_score: float
    seat_waste: int
    fragmentation_minutes: int

    future_baseline_available_slots: int
    future_candidate_available_slots: int

    lost_future_available_slots: int
    gained_future_available_slots: int

    marginal_capacity_loss_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    first_future_capacity_loss_at: (
        datetime | None
    ) = None

    last_future_capacity_loss_at: (
        datetime | None
    ) = None

    has_temporal_cost: bool


class TemporalCandidateCostService:
    """
    Pure adapter from existing optimizer candidate truth
    plus T6 marginal-capacity truth.

    Invariants:
    - no candidate generation
    - no optimizer calls
    - no DB
    - no persistence
    - no score mutation
    - no ranking
    - no Brain
    - no Autopilot
    """

    @staticmethod
    def calculate(
        *,
        candidate: IntelligenceAssignmentResponse,
        marginal_capacity: TemporalMarginalCapacityLoss,
    ) -> TemporalCandidateCost:
        if not candidate.table_ids:
            raise ValueError(
                "Temporal candidate cost requires "
                "at least one table."
            )

        if candidate.end_at <= candidate.start_at:
            raise ValueError(
                "Candidate end_at must be after start_at."
            )

        table_ids = tuple(
            dict.fromkeys(candidate.table_ids)
        )

        if len(table_ids) != len(
            candidate.table_ids
        ):
            raise ValueError(
                "Candidate table_ids must be unique."
            )

        has_temporal_cost = (
            marginal_capacity.lost_available_slots
            > 0
        )

        return TemporalCandidateCost(
            table_ids=table_ids,
            start_at=candidate.start_at,
            end_at=candidate.end_at,
            base_score=candidate.score,
            seat_waste=candidate.seat_waste,
            fragmentation_minutes=(
                candidate.fragmentation_minutes
            ),
            future_baseline_available_slots=(
                marginal_capacity
                .baseline_available_slots
            ),
            future_candidate_available_slots=(
                marginal_capacity
                .candidate_available_slots
            ),
            lost_future_available_slots=(
                marginal_capacity
                .lost_available_slots
            ),
            gained_future_available_slots=(
                marginal_capacity
                .gained_available_slots
            ),
            marginal_capacity_loss_ratio=(
                marginal_capacity
                .marginal_loss_ratio
            ),
            first_future_capacity_loss_at=(
                marginal_capacity
                .first_capacity_loss_at
            ),
            last_future_capacity_loss_at=(
                marginal_capacity
                .last_capacity_loss_at
            ),
            has_temporal_cost=has_temporal_cost,
        )