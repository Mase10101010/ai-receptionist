from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.intelligence.types import (
    IntelligenceTable,
    ReoptimizationPlan,
)

from .prediction import (
    ExpectedTurnConfidence,
    ExpectedTurnRequest,
    ExpectedTurnService,
)
from .reoptimization_safety import (
    TemporalAffectedReservationEvidence,
)
from .snapshot import TemporalLearningSnapshot


class TemporalReoptimizationTurnEvidence(BaseModel):
    """
    Expected-turn confidence evidence for every reservation
    affected by one exact reoptimization plan.
    """

    affected_reservations: tuple[
        TemporalAffectedReservationEvidence,
        ...
    ]


class TemporalReoptimizationTurnEvidenceService:
    """
    Pure expected-turn evidence resolver for reoptimization.

    Affected reservations:
    - the new reservation
    - every moved existing reservation

    Invariants:
    - no DB
    - no persistence
    - no calibration calculation
    - no future-capacity calculation
    - no ranking
    - no execution
    - no Brain
    - no ML
    - prediction confidence comes only from T3
    """

    @classmethod
    def evaluate(
        cls,
        *,
        plan: ReoptimizationPlan,
        new_reservation_id: UUID,
        new_reservation_party_size: int,
        snapshot: TemporalLearningSnapshot,
        tables: list[IntelligenceTable],
    ) -> TemporalReoptimizationTurnEvidence:
        evidence: list[
            TemporalAffectedReservationEvidence
        ] = []

        new_assignment = (
            plan.new_reservation_assignment.candidate
        )

        new_prediction = ExpectedTurnService.predict(
            snapshot=snapshot,
            request=ExpectedTurnRequest(
                party_size=new_reservation_party_size,
                planned_duration_minutes=(
                    cls._duration_minutes(
                        start_at=new_assignment.start_at,
                        end_at=new_assignment.end_at,
                    )
                ),
                day_of_week=(
                    new_assignment.start_at.weekday()
                ),
                hour=new_assignment.start_at.hour,
                service_area_id=(
                    cls._service_area_for_tables(
                        table_ids=(
                            new_assignment.table_ids
                        ),
                        tables=tables,
                    )
                ),
            ),
        )

        evidence.append(
            TemporalAffectedReservationEvidence(
                reservation_id=new_reservation_id,
                expected_turn_confidence=(
                    new_prediction.confidence
                ),
            )
        )

        seen_reservation_ids: set[UUID] = {
            new_reservation_id,
        }

        for move in plan.moves:
            try:
                reservation_id = UUID(
                    move.reservation_id
                )
            except ValueError as exc:
                raise ValueError(
                    "Moved reservation IDs must be "
                    "valid UUIDs."
                ) from exc

            if reservation_id in seen_reservation_ids:
                raise ValueError(
                    "Affected reservation IDs must "
                    "be unique."
                )

            seen_reservation_ids.add(
                reservation_id
            )

            prediction = ExpectedTurnService.predict(
                snapshot=snapshot,
                request=ExpectedTurnRequest(
                    party_size=move.party_size,
                    planned_duration_minutes=(
                        cls._duration_minutes(
                            start_at=move.start_at,
                            end_at=move.end_at,
                        )
                    ),
                    day_of_week=(
                        move.start_at.weekday()
                    ),
                    hour=move.start_at.hour,
                    service_area_id=(
                        cls._service_area_for_tables(
                            table_ids=(
                                move.to_table_ids
                            ),
                            tables=tables,
                        )
                    ),
                ),
            )

            evidence.append(
                TemporalAffectedReservationEvidence(
                    reservation_id=reservation_id,
                    expected_turn_confidence=(
                        prediction.confidence
                    ),
                )
            )

        return TemporalReoptimizationTurnEvidence(
            affected_reservations=tuple(
                evidence
            ),
        )

    @staticmethod
    def _duration_minutes(
        *,
        start_at,
        end_at,
    ) -> int:
        duration_seconds = (
            end_at - start_at
        ).total_seconds()

        duration_minutes = int(
            duration_seconds // 60
        )

        if (
            duration_seconds <= 0
            or duration_seconds % 60 != 0
            or duration_minutes < 15
            or duration_minutes > 720
        ):
            raise ValueError(
                "Affected reservation duration must "
                "be between 15 and 720 whole minutes."
            )

        return duration_minutes

    @staticmethod
    def _service_area_for_tables(
        *,
        table_ids: tuple[str, ...],
        tables: list[IntelligenceTable],
    ) -> UUID | None:
        table_by_id = {
            table.id: table
            for table in tables
        }

        area_ids: set[UUID] = set()

        for table_id in table_ids:
            table = table_by_id.get(table_id)

            if (
                table is None
                or table.area_id is None
            ):
                continue

            try:
                area_ids.add(
                    UUID(table.area_id)
                )
            except ValueError:
                continue

        if len(area_ids) != 1:
            return None

        return next(iter(area_ids))