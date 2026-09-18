from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from app.intelligence.types import (
    ExistingReservation,
    ReoptimizationPlan,
)


class TemporalReoptimizationScenario(BaseModel):
    """
    Counterfactual reservation state after one exact
    ReoptimizationPlan is applied.

    The scenario itself does not evaluate capacity.
    """

    baseline_reservations: tuple[
        ExistingReservation,
        ...
    ]

    candidate_reservations: tuple[
        ExistingReservation,
        ...
    ]

    new_reservation_id: str

    moved_reservation_ids: tuple[str, ...]


class TemporalReoptimizationScenarioBuilder:
    """
    Pure counterfactual scenario builder for one exact
    reoptimization plan.

    Invariants:
    - no optimizer calls
    - no DB
    - no persistence
    - no ranking
    - no scoring
    - no prediction
    - no calibration
    - no Brain
    - no Autopilot authority
    - no ML
    - baseline reservations are never mutated
    """

    @classmethod
    def build(
        cls,
        *,
        reservations: list[ExistingReservation],
        plan: ReoptimizationPlan,
        new_reservation_id: str,
        new_reservation_party_size: int,
    ) -> TemporalReoptimizationScenario:
        baseline = tuple(reservations)

        by_id = {
            reservation.id: reservation
            for reservation in reservations
        }

        moved_ids = tuple(
            move.reservation_id
            for move in plan.moves
        )

        if len(moved_ids) != len(set(moved_ids)):
            raise ValueError(
                "A reservation cannot be moved more than once "
                "in the same reoptimization scenario."
            )

        if new_reservation_id in by_id:
            raise ValueError(
                "The new reservation must not already exist "
                "in baseline reservations."
            )

        candidate_by_id = dict(by_id)

        for move in plan.moves:
            existing = candidate_by_id.get(
                move.reservation_id
            )

            if existing is None:
                raise ValueError(
                    "Moved reservation is missing from "
                    "baseline reservations: "
                    f"{move.reservation_id}"
                )

            candidate_by_id[move.reservation_id] = (
                replace(
                    existing,
                    table_ids=move.to_table_ids,
                )
            )

        assignment = (
            plan.new_reservation_assignment.candidate
        )

        candidate_by_id[new_reservation_id] = (
            ExistingReservation(
                id=new_reservation_id,
                start_at=assignment.start_at,
                end_at=assignment.end_at,
                party_size=new_reservation_party_size,
                table_ids=assignment.table_ids,
                status="confirmed",
                locked=False,
            )
        )

        candidate = tuple(
            candidate_by_id[
                reservation_id
            ]
            for reservation_id
            in sorted(candidate_by_id)
        )

        return TemporalReoptimizationScenario(
            baseline_reservations=baseline,
            candidate_reservations=candidate,
            new_reservation_id=new_reservation_id,
            moved_reservation_ids=moved_ids,
        )