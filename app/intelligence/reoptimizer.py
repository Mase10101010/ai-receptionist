from __future__ import annotations

from dataclasses import replace

from .candidate_generator import generate_candidates
from .interval_engine import (
    calculate_fragmentation_minutes,
    is_assignment_available,
    reservation_blocks_tables,
)
from .scoring import score_candidate
from .types import (
    CandidateAssignment,
    ExistingReservation,
    IntelligenceTable,
    OptimizationRequest,
    ReoptimizationPlan,
    ReoptimizationRequest,
    ReoptimizationResult,
    ReservationMove,
    ScoredAssignment,
    TableCombination,
)


class ReservationReoptimizer:
    """
    Assisted room reoptimization engine.

    It never writes to the database. It only simulates:
    - the assignment of the incoming reservation;
    - moving at most a limited number of existing reservations;
    - deterministic, explainable plans.

    Version 1 currently evaluates one moved reservation per plan.
    """

    MAX_TWO_MOVE_EVALUATIONS = 2000

    def reoptimize(
        self,
        request: ReoptimizationRequest,
        tables: list[IntelligenceTable],
        reservations: list[ExistingReservation],
        combinations: list[TableCombination] | None = None,
    ) -> ReoptimizationResult:
        combinations = combinations or []

        direct_result = self._find_direct_assignment(
            request=request,
            tables=tables,
            reservations=reservations,
            combinations=combinations,
        )

        # If a normal assignment is already possible, return it as a plan
        # with no movements. This gives callers one consistent response shape.
        if direct_result is not None:
            return ReoptimizationResult(
                available=True,
                recommended=ReoptimizationPlan(
                    new_reservation_assignment=direct_result,
                    moves=(),
                    score=direct_result.score,
                    total_seat_waste=direct_result.seat_waste,
                    moved_reservations_count=0,
                    explanation=(
                        "The new reservation can be assigned without moving "
                        "any existing reservation."
                    ),
                ),
                alternatives=(),
                evaluated_plans=1,
                rejected_plans=0,
            )

        movable_reservations = [
            reservation
            for reservation in reservations
            if not reservation.locked
            and reservation.table_ids
            and (
                request.reservation_id is None
                or reservation.id != request.reservation_id
            )
        ]

        plans: list[ReoptimizationPlan] = []
        evaluated_plans = 0
        rejected_plans = 0

        incoming_candidates = generate_candidates(
            request=self._to_optimization_request(request),
            tables=tables,
            combinations=combinations,
        )

        for incoming_candidate in incoming_candidates:
            blocking_reservations = self._blocking_reservations(
                candidate=incoming_candidate,
                reservations=reservations,
                request=request,
            )

            # V1 only handles exactly one blocking reservation.
            if len(blocking_reservations) != 1:
                rejected_plans += 1
                continue

            blocking = blocking_reservations[0]

            if blocking.locked:
                rejected_plans += 1
                continue

            move_candidates = generate_candidates(
                request=OptimizationRequest(
                    requested_start=blocking.start_at,
                    party_size=blocking.party_size,
                    duration_minutes=int(
                        (
                            blocking.end_at
                            - blocking.start_at
                        ).total_seconds()
                        // 60
                    ),
                    buffer_before_minutes=request.buffer_before_minutes,
                    buffer_after_minutes=request.buffer_after_minutes,
                    preferred_area_id=None,
                    preferred_floor_id=None,
                    allow_combinations=request.allow_combinations,
                    max_alternatives=request.max_plans,
                ),
                tables=tables,
                combinations=combinations,
            )

            for move_candidate in move_candidates:
                evaluated_plans += 1

                if set(move_candidate.table_ids) == set(
                    blocking.table_ids,
                ):
                    rejected_plans += 1
                    continue

                reservations_without_blocking = [
                    reservation
                    for reservation in reservations
                    if reservation.id != blocking.id
                ]

                move_available = is_assignment_available(
                    table_ids=move_candidate.table_ids,
                    start_at=move_candidate.start_at,
                    end_at=move_candidate.end_at,
                    reservations=reservations_without_blocking,
                    buffer_before_minutes=request.buffer_before_minutes,
                    buffer_after_minutes=request.buffer_after_minutes,
                    setup_minutes=move_candidate.setup_minutes,
                    respect_live_occupancy=True,
                )

                if not move_available:
                    rejected_plans += 1
                    continue

                simulated_reservations = [
                    reservation
                    for reservation in reservations
                    if reservation.id != blocking.id
                ]

                simulated_reservations.append(
                    replace(
                        blocking,
                        table_ids=move_candidate.table_ids,
                    ),
                )

                incoming_available = is_assignment_available(
                    table_ids=incoming_candidate.table_ids,
                    start_at=incoming_candidate.start_at,
                    end_at=incoming_candidate.end_at,
                    reservations=simulated_reservations,
                    buffer_before_minutes=request.buffer_before_minutes,
                    buffer_after_minutes=request.buffer_after_minutes,
                    setup_minutes=incoming_candidate.setup_minutes,
                    respect_live_occupancy=True,
                )

                if not incoming_available:
                    rejected_plans += 1
                    continue

                move_fragmentation = calculate_fragmentation_minutes(
                    table_ids=move_candidate.table_ids,
                    start_at=move_candidate.start_at,
                    end_at=move_candidate.end_at,
                    reservations=reservations_without_blocking,
                    useful_gap_threshold_minutes=int(
                        (
                            blocking.end_at
                            - blocking.start_at
                        ).total_seconds()
                        // 60
                    ),
                )

                move_score, move_waste, move_explanation = score_candidate(
                    candidate=move_candidate,
                    request=OptimizationRequest(
                        requested_start=blocking.start_at,
                        party_size=blocking.party_size,
                        duration_minutes=int(
                            (
                                blocking.end_at
                                - blocking.start_at
                            ).total_seconds()
                            // 60
                        ),
                        buffer_before_minutes=request.buffer_before_minutes,
                        buffer_after_minutes=request.buffer_after_minutes,
                        allow_combinations=request.allow_combinations,
                    ),
                    fragmentation_minutes=move_fragmentation,
                )

                incoming_fragmentation = (
                    calculate_fragmentation_minutes(
                        table_ids=incoming_candidate.table_ids,
                        start_at=incoming_candidate.start_at,
                        end_at=incoming_candidate.end_at,
                        reservations=simulated_reservations,
                        useful_gap_threshold_minutes=(
                            request.duration_minutes
                        ),
                    )
                )

                (
                    incoming_score,
                    incoming_waste,
                    incoming_explanation,
                ) = score_candidate(
                    candidate=incoming_candidate,
                    request=self._to_optimization_request(
                        request,
                    ),
                    fragmentation_minutes=incoming_fragmentation,
                )

                movement_penalty = 18.0
                plan_score = (
                    incoming_score
                    + move_score
                    - movement_penalty
                )

                move = ReservationMove(
                    reservation_id=blocking.id,
                    from_table_ids=blocking.table_ids,
                    to_table_ids=move_candidate.table_ids,
                    party_size=blocking.party_size,
                    start_at=blocking.start_at,
                    end_at=blocking.end_at,
                    destination_capacity=move_candidate.capacity,
                    seat_waste=move_waste,
                    explanation=move_explanation,
                    destination_resource_id=move_candidate.resource_id,
                    destination_setup_minutes=move_candidate.setup_minutes,
                )

                assignment = ScoredAssignment(
                    candidate=incoming_candidate,
                    score=incoming_score,
                    seat_waste=incoming_waste,
                    fragmentation_minutes=(
                        incoming_fragmentation
                    ),
                    explanation=incoming_explanation,
                )

                plans.append(
                    ReoptimizationPlan(
                        new_reservation_assignment=assignment,
                        moves=(move,),
                        score=plan_score,
                        total_seat_waste=(
                            incoming_waste + move_waste
                        ),
                        moved_reservations_count=1,
                        explanation=(
                            f"Move reservation {blocking.id} "
                            f"from tables "
                            f"{', '.join(blocking.table_ids)} "
                            f"to tables "
                            f"{', '.join(move_candidate.table_ids)}, "
                            f"then assign the new reservation to "
                            f"{', '.join(incoming_candidate.table_ids)}."
                        ),
                    ),
                )

        if request.max_reservations_to_move >= 2:
            two_move_plans = self._find_two_move_plans(
                request=request,
                tables=tables,
                reservations=reservations,
                combinations=combinations,
            )
            plans.extend(two_move_plans)

        plans.sort(
            key=lambda plan: (
                -plan.score,
                plan.moved_reservations_count,
                plan.total_seat_waste,
                plan.new_reservation_assignment.candidate.resource_id,
            ),
        )

        limited = plans[: max(request.max_plans, 1)]

        return ReoptimizationResult(
            available=bool(limited),
            recommended=limited[0] if limited else None,
            alternatives=tuple(limited[1:]),
            evaluated_plans=evaluated_plans,
            rejected_plans=rejected_plans,
        )


    def _find_two_move_plans(
        self,
        *,
        request: ReoptimizationRequest,
        tables: list[IntelligenceTable],
        reservations: list[ExistingReservation],
        combinations: list[TableCombination],
    ) -> list[ReoptimizationPlan]:
        """Find safe, bounded plans with exactly two coordinated moves."""
        plans: list[ReoptimizationPlan] = []
        evaluations = 0

        incoming_candidates = generate_candidates(
            request=self._to_optimization_request(request),
            tables=tables,
            combinations=combinations,
        )

        for incoming in incoming_candidates:
            blockers = self._blocking_reservations(
                candidate=incoming,
                reservations=reservations,
                request=request,
            )

            if len(blockers) != 2:
                continue

            if any(
                r.locked
                or r.status.lower() == "seated"
                or not r.table_ids
                or r.id == request.reservation_id
                for r in blockers
            ):
                continue

            first, second = blockers

            remaining = [
                r for r in reservations
                if r.id not in {first.id, second.id}
            ]

            def destinations(reservation):
                duration = int(
                    (reservation.end_at - reservation.start_at)
                    .total_seconds() // 60
                )
                if duration <= 0:
                    return []

                move_request = OptimizationRequest(
                    requested_start=reservation.start_at,
                    party_size=reservation.party_size,
                    duration_minutes=duration,
                    buffer_before_minutes=request.buffer_before_minutes,
                    buffer_after_minutes=request.buffer_after_minutes,
                    allow_combinations=request.allow_combinations,
                )

                return [
                    candidate
                    for candidate in generate_candidates(
                        request=move_request,
                        tables=tables,
                        combinations=combinations,
                    )
                    if set(candidate.table_ids) != set(reservation.table_ids)
                    and is_assignment_available(
                        table_ids=candidate.table_ids,
                        start_at=candidate.start_at,
                        end_at=candidate.end_at,
                        reservations=remaining,
                        buffer_before_minutes=request.buffer_before_minutes,
                        buffer_after_minutes=request.buffer_after_minutes,
                        setup_minutes=candidate.setup_minutes,
                        respect_live_occupancy=True,
                    )
                ]

            first_destinations = destinations(first)
            second_destinations = destinations(second)

            for first_candidate in first_destinations:
                for second_candidate in second_destinations:
                    if evaluations >= self.MAX_TWO_MOVE_EVALUATIONS:
                        return plans

                    evaluations += 1

                    simulated = [
                        *remaining,
                        replace(first, table_ids=first_candidate.table_ids),
                        replace(second, table_ids=second_candidate.table_ids),
                    ]

                    assignments = [
                        (first_candidate, second_candidate),
                        (second_candidate, first_candidate),
                    ]

                    if any(
                        not is_assignment_available(
                            table_ids=candidate.table_ids,
                            start_at=candidate.start_at,
                            end_at=candidate.end_at,
                            reservations=[
                                replace(
                                    first if other is first_candidate else second,
                                    table_ids=other.table_ids,
                                )
                            ],
                            buffer_before_minutes=request.buffer_before_minutes,
                            buffer_after_minutes=request.buffer_after_minutes,
                            setup_minutes=candidate.setup_minutes,
                            respect_live_occupancy=True,
                        )
                        for candidate, other in assignments
                    ):
                        continue

                    if not is_assignment_available(
                        table_ids=incoming.table_ids,
                        start_at=incoming.start_at,
                        end_at=incoming.end_at,
                        reservations=simulated,
                        buffer_before_minutes=request.buffer_before_minutes,
                        buffer_after_minutes=request.buffer_after_minutes,
                        setup_minutes=incoming.setup_minutes,
                        respect_live_occupancy=True,
                    ):
                        continue

                    move_results = []
                    move_score_total = 0.0
                    move_waste_total = 0

                    for reservation, candidate in (
                        (first, first_candidate),
                        (second, second_candidate),
                    ):
                        duration = int(
                            (reservation.end_at - reservation.start_at)
                            .total_seconds() // 60
                        )

                        others = [
                            r for r in simulated
                            if r.id != reservation.id
                        ]

                        fragmentation = calculate_fragmentation_minutes(
                            table_ids=candidate.table_ids,
                            start_at=candidate.start_at,
                            end_at=candidate.end_at,
                            reservations=others,
                            useful_gap_threshold_minutes=duration,
                        )

                        score, waste, explanation = score_candidate(
                            candidate=candidate,
                            request=OptimizationRequest(
                                requested_start=reservation.start_at,
                                party_size=reservation.party_size,
                                duration_minutes=duration,
                                buffer_before_minutes=request.buffer_before_minutes,
                                buffer_after_minutes=request.buffer_after_minutes,
                                allow_combinations=request.allow_combinations,
                            ),
                            fragmentation_minutes=fragmentation,
                        )

                        move_score_total += score
                        move_waste_total += waste

                        move_results.append(
                            ReservationMove(
                                reservation_id=reservation.id,
                                from_table_ids=reservation.table_ids,
                                to_table_ids=candidate.table_ids,
                                party_size=reservation.party_size,
                                start_at=reservation.start_at,
                                end_at=reservation.end_at,
                                destination_capacity=candidate.capacity,
                                seat_waste=waste,
                                explanation=explanation,
                                destination_resource_id=candidate.resource_id,
                                destination_setup_minutes=candidate.setup_minutes,
                            )
                        )

                    incoming_fragmentation = calculate_fragmentation_minutes(
                        table_ids=incoming.table_ids,
                        start_at=incoming.start_at,
                        end_at=incoming.end_at,
                        reservations=simulated,
                        useful_gap_threshold_minutes=request.duration_minutes,
                    )

                    incoming_score, incoming_waste, incoming_explanation = (
                        score_candidate(
                            candidate=incoming,
                            request=self._to_optimization_request(request),
                            fragmentation_minutes=incoming_fragmentation,
                        )
                    )

                    assignment = ScoredAssignment(
                        candidate=incoming,
                        score=incoming_score,
                        seat_waste=incoming_waste,
                        fragmentation_minutes=incoming_fragmentation,
                        explanation=incoming_explanation,
                    )

                    plans.append(
                        ReoptimizationPlan(
                            new_reservation_assignment=assignment,
                            moves=tuple(move_results),
                            score=(
                                incoming_score
                                + move_score_total
                                - 36.0
                            ),
                            total_seat_waste=(
                                incoming_waste + move_waste_total
                            ),
                            moved_reservations_count=2,
                            explanation=(
                                "Two coordinated reservation reassignments "
                                "make the incoming booking feasible without "
                                "changing existing reservation times."
                            ),
                        )
                    )

        return plans

    def _find_direct_assignment(
        self,
        request: ReoptimizationRequest,
        tables: list[IntelligenceTable],
        reservations: list[ExistingReservation],
        combinations: list[TableCombination],
    ) -> ScoredAssignment | None:
        candidates = generate_candidates(
            request=self._to_optimization_request(request),
            tables=tables,
            combinations=combinations,
        )

        accepted: list[ScoredAssignment] = []

        for candidate in candidates:
            available = is_assignment_available(
                table_ids=candidate.table_ids,
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                reservations=reservations,
                buffer_before_minutes=request.buffer_before_minutes,
                buffer_after_minutes=request.buffer_after_minutes,
                setup_minutes=candidate.setup_minutes,
                respect_live_occupancy=True,
            )

            if not available:
                continue

            fragmentation = calculate_fragmentation_minutes(
                table_ids=candidate.table_ids,
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                reservations=reservations,
                useful_gap_threshold_minutes=request.duration_minutes,
            )

            score, seat_waste, explanation = score_candidate(
                candidate=candidate,
                request=self._to_optimization_request(request),
                fragmentation_minutes=fragmentation,
            )

            accepted.append(
                ScoredAssignment(
                    candidate=candidate,
                    score=score,
                    seat_waste=seat_waste,
                    fragmentation_minutes=fragmentation,
                    explanation=explanation,
                ),
            )

        accepted.sort(
            key=lambda item: (
                -item.score,
                item.seat_waste,
                len(item.candidate.table_ids),
                item.candidate.resource_id,
            ),
        )

        return accepted[0] if accepted else None

    def _blocking_reservations(
        self,
        candidate: CandidateAssignment,
        reservations: list[ExistingReservation],
        request: ReoptimizationRequest,
    ) -> list[ExistingReservation]:
        candidate_table_ids = set(candidate.table_ids)

        return [
            reservation
            for reservation in reservations
            if reservation_blocks_tables(
                reservation=reservation,
                candidate_table_ids=candidate_table_ids,
                candidate_start=candidate.start_at,
                candidate_end=candidate.end_at,
                respect_live_occupancy=True,
            )
        ]

    def _to_optimization_request(
        self,
        request: ReoptimizationRequest,
    ) -> OptimizationRequest:
        return OptimizationRequest(
            requested_start=request.requested_start,
            party_size=request.party_size,
            duration_minutes=request.duration_minutes,
            buffer_before_minutes=request.buffer_before_minutes,
            buffer_after_minutes=request.buffer_after_minutes,
            preferred_area_id=request.preferred_area_id,
            preferred_floor_id=request.preferred_floor_id,
            allow_combinations=request.allow_combinations,
            max_alternatives=request.max_plans,
        )