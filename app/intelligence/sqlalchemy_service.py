from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import logging

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.reservation_table_assignment import (
    ReservationTableAssignment,
)

from app.models.reservation import Reservation, ReservationStatus
from app.models.table import Table
from app.models.table_combination import (
    TableCombination as ORMTableCombination,
    TableCombinationMember,
)

from .optimizer import ReservationOptimizer
from .schemas import (
    IntelligenceAssignmentResponse,
    IntelligenceOptimizeRequest,
    IntelligenceOptimizeResponse,
    IntelligenceApplyRequest,
    IntelligenceApplyResponse,
    IntelligenceReoptimizeRequest,
    IntelligenceReoptimizeResponse,
    IntelligenceReoptimizationPlanResponse,
    IntelligenceReservationMoveResponse,
    IntelligenceApplyReoptimizationRequest,
    IntelligenceApplyReoptimizationResponse,
    IntelligenceAppliedMoveResponse,
)
from .sqlalchemy_adapter import (
    combinations_to_intelligence,
    reservations_to_intelligence,
    tables_to_intelligence,
)
from .types import (
    OptimizationRequest,
    ReoptimizationRequest,
)

from app.intelligence_behaviour.service import (
    IntelligenceBehaviourService,
)
from app.intelligence_features.repository import (
    IntelligenceFeatureRepository,
)
from app.intelligence_features.service import (
    IntelligenceFeatureService,
)
from app.intelligence_policy.schemas import (
    RecommendationPolicy,
)
from app.intelligence_policy.service import (
    RecommendationPolicyService,
)

from .reoptimizer import ReservationReoptimizer

logger = logging.getLogger(__name__)


BLOCKING_STATUSES = (
    ReservationStatus.PENDING,
    ReservationStatus.CONFIRMED,
    ReservationStatus.SEATED,
)


class IntelligenceOptimizationService:
    def __init__(
        self,
        optimizer: ReservationOptimizer | None = None,
        reoptimizer: ReservationReoptimizer | None = None,
    ) -> None:
        self.optimizer = (
            optimizer
            or ReservationOptimizer()
        )

        self.reoptimizer = (
            reoptimizer
            or ReservationReoptimizer()
        )

    async def _build_recommendation_policy(
        self,
        *,
        session: AsyncSession,
        restaurant_id: UUID,
    ) -> RecommendationPolicy | None:
        try:
            feature_service = IntelligenceFeatureService(
                IntelligenceFeatureRepository(
                    session,
                )
            )

            features = (
                await feature_service
                .get_ai_suggestion_features(
                    restaurant_id=restaurant_id,
                )
            )

            manager_decisions = (
                features.suggestions_accepted
                + features.suggestions_dismissed
            )

            if manager_decisions == 0:
                return None

            behaviour_profile = (
                IntelligenceBehaviourService()
                .build_ai_suggestion_profile(
                    features=features,
                )
            )

            return (
                RecommendationPolicyService()
                .build_policy(
                    profile=behaviour_profile,
                )
            )

        except Exception:
            logger.exception(
                (
                    "Unable to build personalized "
                    "recommendation policy: "
                    "restaurant_id=%s"
                ),
                restaurant_id,
            )

            return None


    @staticmethod
    def _personalize_plan_score(
        *,
        base_score: float,
        moved_reservations_count: int,
        total_seat_waste: int,
        policy: RecommendationPolicy | None,
    ) -> tuple[float, bool, list[str]]:
        if policy is None:
            return (
                round(base_score, 4),
                False,
                [
                    "Technical AIE ranking used because no "
                    "personalized policy was available."
                ],
            )

        personalized_score = (
            base_score * policy.score_weight
        )

        reasons: list[str] = []

        move_penalty = (
            moved_reservations_count
            * policy.move_penalty_weight
        )

        personalized_score -= move_penalty

        reasons.append(
            (
                f"Move penalty: -{move_penalty:.2f} "
                f"for {moved_reservations_count} move(s)."
            )
        )

        seat_waste_penalty = (
            total_seat_waste
            * policy.seat_waste_penalty_weight
        )

        personalized_score -= seat_waste_penalty

        reasons.append(
            (
                f"Seat-waste penalty: "
                f"-{seat_waste_penalty:.2f} "
                f"for {total_seat_waste} unused seat(s)."
            )
        )

        if (
            moved_reservations_count == 1
            and policy.single_move_bonus > 0
        ):
            personalized_score += (
                policy.single_move_bonus
            )

            reasons.append(
                (
                    "Single-move preference bonus: "
                    f"+{policy.single_move_bonus:.2f}."
                )
            )

        if (
            policy.low_seat_waste_bonus > 0
            and (
                policy.maximum_preferred_seat_waste
                is None
                or total_seat_waste
                <= policy.maximum_preferred_seat_waste
            )
        ):
            personalized_score += (
                policy.low_seat_waste_bonus
            )

            reasons.append(
                (
                    "Low-seat-waste preference bonus: "
                    f"+{policy.low_seat_waste_bonus:.2f}."
                )
            )

        if (
            policy.minimum_recommended_score
            is not None
            and base_score
            < policy.minimum_recommended_score
        ):
            score_gap = (
                policy.minimum_recommended_score
                - base_score
            )

            personalized_score -= score_gap

            reasons.append(
                (
                    "Below learned score reference: "
                    f"-{score_gap:.2f}."
                )
            )

        return (
            round(personalized_score, 4),
            True,
            reasons,
        )

    async def optimize(
        self,
        session: AsyncSession,
        payload: IntelligenceOptimizeRequest,
    ) -> IntelligenceOptimizeResponse:
        tables_result = await session.execute(
            select(Table)
            .where(
                Table.restaurant_id == payload.restaurant_id,
                Table.is_active.is_(True),
            )
            .order_by(Table.table_number)
        )
        tables = list(tables_result.scalars().all())

        combinations_result = await session.execute(
            select(ORMTableCombination)
            .options(
                selectinload(
                    ORMTableCombination.members,
                ).selectinload(
                    TableCombinationMember.table,
                )
            )
            .where(
                ORMTableCombination.restaurant_id
                == payload.restaurant_id,
                ORMTableCombination.is_active.is_(True),
            )
            .order_by(ORMTableCombination.name)
        )

        combinations = list(
            combinations_result.scalars().unique().all()
        )

        range_start = payload.requested_start - timedelta(hours=12)
        range_end = (
            payload.requested_start
            + timedelta(minutes=payload.duration_minutes)
            + timedelta(hours=12)
        )

        reservations_stmt = (
            select(Reservation)
            .options(
                selectinload(
                    Reservation.table_assignments,
                )
            )
            .where(
                Reservation.restaurant_id
                == payload.restaurant_id,
                Reservation.status.in_(
                    BLOCKING_STATUSES,
                ),
                Reservation.reservation_time
                >= range_start,
                Reservation.reservation_time
                < range_end,
            )
        )

        if payload.reservation_id is not None:
            reservations_stmt = reservations_stmt.where(
                Reservation.id
                != payload.reservation_id,
            )

        reservations_result = await session.execute(
            reservations_stmt
        )

        reservations = list(
            reservations_result.scalars().unique().all()
        )

        result = self.optimizer.optimize(
            request=OptimizationRequest(
                requested_start=payload.requested_start,
                party_size=payload.party_size,
                duration_minutes=payload.duration_minutes,
                buffer_before_minutes=payload.buffer_before_minutes,
                buffer_after_minutes=payload.buffer_after_minutes,
                preferred_area_id=(
                    str(payload.preferred_service_area_id)
                    if payload.preferred_service_area_id
                    else None
                ),
                preferred_floor_id=None,
                allow_combinations=True,
                max_alternatives=payload.max_alternatives,
            ),
            tables=tables_to_intelligence(tables),
            reservations=reservations_to_intelligence(reservations),
            combinations=combinations_to_intelligence(
                combinations,
            ),
        )

        table_number_by_id = {
            str(table.id): table.table_number for table in tables
        }

        def serialize(item):
            candidate = item.candidate
            return IntelligenceAssignmentResponse(
                table_ids=[UUID(table_id) for table_id in candidate.table_ids],
                table_numbers=[
                    table_number_by_id.get(table_id, table_id)
                    for table_id in candidate.table_ids
                ],
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                capacity=candidate.capacity,
                score=item.score,
                seat_waste=item.seat_waste,
                fragmentation_minutes=item.fragmentation_minutes,
                explanation=item.explanation,
            )

        return IntelligenceOptimizeResponse(
            available=result.available,
            recommended=serialize(result.recommended) if result.recommended else None,
            alternatives=[serialize(item) for item in result.alternatives],
            rejected_candidates=result.rejected_candidates,
        )

    async def reoptimize(
        self,
        session: AsyncSession,
        payload: IntelligenceReoptimizeRequest,
    ) -> IntelligenceReoptimizeResponse:
        tables_result = await session.execute(
            select(Table)
            .where(
                Table.restaurant_id == payload.restaurant_id,
                Table.is_active.is_(True),
            )
            .order_by(Table.table_number)
        )

        tables = list(
            tables_result.scalars().all(),
        )

        combinations_result = await session.execute(
            select(ORMTableCombination)
            .options(
                selectinload(
                    ORMTableCombination.members,
                ).selectinload(
                    TableCombinationMember.table,
                )
            )
            .where(
                ORMTableCombination.restaurant_id
                == payload.restaurant_id,
                ORMTableCombination.is_active.is_(True),
            )
            .order_by(
                ORMTableCombination.name,
            )
        )

        combinations = list(
            combinations_result.scalars().unique().all(),
        )

        range_start = (
            payload.requested_start
            - timedelta(hours=12)
        )

        range_end = (
            payload.requested_start
            + timedelta(
                minutes=payload.duration_minutes,
            )
            + timedelta(hours=12)
        )

        reservations_stmt = (
            select(Reservation)
            .options(
                selectinload(
                    Reservation.table_assignments,
                )
            )
            .where(
                Reservation.restaurant_id
                == payload.restaurant_id,
                Reservation.status.in_(
                    BLOCKING_STATUSES,
                ),
                Reservation.reservation_time
                >= range_start,
                Reservation.reservation_time
                < range_end,
            )
        )

        if payload.reservation_id is not None:
            reservations_stmt = reservations_stmt.where(
                Reservation.id
                != payload.reservation_id,
            )

        reservations_result = await session.execute(
            reservations_stmt,
        )

        reservations = list(
            reservations_result.scalars().unique().all(),
        )

        intelligence_tables = tables_to_intelligence(
            tables,
        )

        intelligence_reservations = (
            reservations_to_intelligence(
                reservations,
            )
        )

        intelligence_combinations = (
            combinations_to_intelligence(
                combinations,
            )
        )

        result = self.reoptimizer.reoptimize(
            request=ReoptimizationRequest(
                requested_start=payload.requested_start,
                party_size=payload.party_size,
                duration_minutes=payload.duration_minutes,
                reservation_id=(
                    str(payload.reservation_id)
                    if payload.reservation_id
                    else None
                ),
                buffer_before_minutes=(
                    payload.buffer_before_minutes
                ),
                buffer_after_minutes=(
                    payload.buffer_after_minutes
                ),
                preferred_area_id=(
                    str(
                        payload.preferred_service_area_id,
                    )
                    if payload.preferred_service_area_id
                    else None
                ),
                preferred_floor_id=None,
                allow_combinations=True,
                max_reservations_to_move=(
                    payload.max_reservations_to_move
                ),
                max_plans=payload.max_plans,
            ),
            tables=intelligence_tables,
            reservations=intelligence_reservations,
            combinations=intelligence_combinations,
        )

        policy = await self._build_recommendation_policy(
            session=session,
            restaurant_id=payload.restaurant_id,
        )

        table_number_by_id = {
            str(table.id): table.table_number
            for table in tables
        }

        def serialize_assignment(
            item,
        ) -> IntelligenceAssignmentResponse:
            candidate = item.candidate

            return IntelligenceAssignmentResponse(
                table_ids=[
                    UUID(table_id)
                    for table_id in candidate.table_ids
                ],
                table_numbers=[
                    table_number_by_id.get(
                        table_id,
                        table_id,
                    )
                    for table_id in candidate.table_ids
                ],
                start_at=candidate.start_at,
                end_at=candidate.end_at,
                capacity=candidate.capacity,
                score=item.score,
                seat_waste=item.seat_waste,
                fragmentation_minutes=(
                    item.fragmentation_minutes
                ),
                explanation=item.explanation,
            )

        def serialize_plan(
            plan,
        ) -> IntelligenceReoptimizationPlanResponse:
            moves = []

            for move in plan.moves:
                moves.append(
                    IntelligenceReservationMoveResponse(
                        reservation_id=UUID(
                            move.reservation_id,
                        ),
                        from_table_ids=[
                            UUID(table_id)
                            for table_id
                            in move.from_table_ids
                        ],
                        from_table_numbers=[
                            table_number_by_id.get(
                                table_id,
                                table_id,
                            )
                            for table_id
                            in move.from_table_ids
                        ],
                        to_table_ids=[
                            UUID(table_id)
                            for table_id
                            in move.to_table_ids
                        ],
                        to_table_numbers=[
                            table_number_by_id.get(
                                table_id,
                                table_id,
                            )
                            for table_id
                            in move.to_table_ids
                        ],
                        party_size=move.party_size,
                        start_at=move.start_at,
                        end_at=move.end_at,
                        destination_capacity=(
                            move.destination_capacity
                        ),
                        seat_waste=move.seat_waste,
                        explanation=move.explanation,
                    )
                )

            (
                personalized_score,
                personalization_applied,
                personalization_reasons,
            ) = self._personalize_plan_score(
                base_score=plan.score,
                moved_reservations_count=(
                    plan.moved_reservations_count
                ),
                total_seat_waste=(
                    plan.total_seat_waste
                ),
                policy=policy,
            )

            return IntelligenceReoptimizationPlanResponse(
                new_reservation_assignment=(
                    serialize_assignment(
                        plan.new_reservation_assignment,
                    )
                ),
                moves=moves,

                # Original technical score remains unchanged.
                score=plan.score,
                base_score=plan.score,

                personalized_score=personalized_score,
                personalization_applied=(
                    personalization_applied
                ),
                personalization_reasons=(
                    personalization_reasons
                ),

                total_seat_waste=(
                    plan.total_seat_waste
                ),
                moved_reservations_count=(
                    plan.moved_reservations_count
                ),
                explanation=plan.explanation,
            )

        serialized_plans: list[
            IntelligenceReoptimizationPlanResponse
        ] = []

        if result.recommended is not None:
            serialized_plans.append(
                serialize_plan(
                    result.recommended,
                )
            )

        serialized_plans.extend(
            serialize_plan(plan)
            for plan in result.alternatives
        )

        # Prevent accidental duplicates if the original
        # recommendation is also present in alternatives.
        unique_plans: list[
            IntelligenceReoptimizationPlanResponse
        ] = []

        seen_plan_keys: set[
            tuple[
                tuple[UUID, ...],
                tuple[
                    tuple[UUID, tuple[UUID, ...]],
                    ...,
                ],
            ]
        ] = set()

        for plan in serialized_plans:
            plan_key = (
                tuple(
                    plan
                    .new_reservation_assignment
                    .table_ids
                ),
                tuple(
                    (
                        move.reservation_id,
                        tuple(move.to_table_ids),
                    )
                    for move in plan.moves
                ),
            )

            if plan_key in seen_plan_keys:
                continue

            seen_plan_keys.add(plan_key)
            unique_plans.append(plan)

        ranked_plans = sorted(
            unique_plans,
            key=lambda plan: (
                plan.personalized_score,
                plan.base_score,
            ),
            reverse=True,
        )

        recommended = (
            ranked_plans[0]
            if ranked_plans
            else None
        )

        alternatives = (
            ranked_plans[1:]
            if len(ranked_plans) > 1
            else []
        )

        return IntelligenceReoptimizeResponse(
            available=(
                result.available
                and recommended is not None
            ),
            recommended=recommended,
            alternatives=alternatives,
            evaluated_plans=result.evaluated_plans,
            rejected_plans=result.rejected_plans,
        )

    async def apply_reoptimization(
        self,
        session: AsyncSession,
        payload: IntelligenceApplyReoptimizationRequest,
        allowed_restaurant_ids: list[UUID],
    ) -> IntelligenceApplyReoptimizationResponse:
        if (
            payload.new_reservation_primary_table_id
            not in payload.new_reservation_table_ids
        ):
            raise ValidationError(
                "New reservation primary table must be included "
                "in new_reservation_table_ids."
            )

        new_table_ids = list(
            dict.fromkeys(
                payload.new_reservation_table_ids,
            )
        )

        move_reservation_ids = [
            move.reservation_id
            for move in payload.moves
        ]

        if len(move_reservation_ids) != len(
            set(move_reservation_ids)
        ):
            raise ValidationError(
                "The same reservation cannot be moved more than once."
            )

        if payload.new_reservation_id in move_reservation_ids:
            raise ValidationError(
                "The new reservation cannot also appear in moves."
            )

        new_reservation_result = await session.execute(
            select(Reservation)
            .options(
                selectinload(
                    Reservation.table_assignments,
                )
            )
            .where(
                Reservation.id
                == payload.new_reservation_id,
                Reservation.restaurant_id.in_(
                    allowed_restaurant_ids,
                ),
            )
        )

        new_reservation = (
            new_reservation_result.scalar_one_or_none()
        )

        if new_reservation is None:
            raise NotFoundError(
                f"Reservation {payload.new_reservation_id} not found"
            )

        if new_reservation.restaurant_id is None:
            raise ValidationError(
                "New reservation is not associated with a restaurant."
            )

        if new_reservation.status in {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }:
            raise ValidationError(
                "Completed, cancelled, or no-show reservations "
                "cannot be reassigned."
            )

        moved_reservations: dict[UUID, Reservation] = {}

        if move_reservation_ids:
            moved_reservations_result = await session.execute(
                select(Reservation)
                .options(
                    selectinload(
                        Reservation.table_assignments,
                    )
                )
                .where(
                    Reservation.id.in_(
                        move_reservation_ids,
                    ),
                    Reservation.restaurant_id
                    == new_reservation.restaurant_id,
                )
            )

            moved_reservations = {
                reservation.id: reservation
                for reservation in (
                    moved_reservations_result
                    .scalars()
                    .unique()
                    .all()
                )
            }

            if len(moved_reservations) != len(
                move_reservation_ids
            ):
                raise ValidationError(
                    "One or more reservations to move were not found "
                    "or belong to another restaurant."
                )

        for reservation in moved_reservations.values():
            if reservation.status in {
                ReservationStatus.COMPLETED,
                ReservationStatus.CANCELLED,
                ReservationStatus.NO_SHOW,
            }:
                raise ValidationError(
                    "Completed, cancelled, or no-show reservations "
                    "cannot be moved."
                )

        all_selected_table_ids = set(new_table_ids)

        for move in payload.moves:
            if move.primary_table_id not in move.to_table_ids:
                raise ValidationError(
                    "Move primary table must be included in to_table_ids."
                )

            all_selected_table_ids.update(
                move.to_table_ids,
            )

        tables_result = await session.execute(
            select(Table).where(
                Table.id.in_(
                    all_selected_table_ids,
                ),
                Table.restaurant_id
                == new_reservation.restaurant_id,
                Table.is_active.is_(True),
            )
        )

        tables = list(
            tables_result.scalars().all()
        )

        table_by_id = {
            table.id: table
            for table in tables
        }

        if len(table_by_id) != len(
            all_selected_table_ids
        ):
            raise ValidationError(
                "One or more selected tables were not found, "
                "are inactive, or belong to another restaurant."
            )

        def validate_same_service_area(
            table_ids: list[UUID],
        ) -> None:
            service_area_ids = {
                table_by_id[table_id].service_area_id
                for table_id in table_ids
            }

            if len(service_area_ids) != 1:
                raise ValidationError(
                    "Combined tables must belong to the same service area."
                )

        validate_same_service_area(
            new_table_ids,
        )

        new_capacity = sum(
            table_by_id[table_id].seats
            for table_id in new_table_ids
        )

        if new_capacity < new_reservation.party_size:
            raise ValidationError(
                "Selected tables do not have enough capacity "
                "for the new reservation."
            )

        move_table_ids_by_reservation: dict[
            UUID,
            list[UUID],
        ] = {}

        for move in payload.moves:
            unique_move_table_ids = list(
                dict.fromkeys(
                    move.to_table_ids,
                )
            )

            validate_same_service_area(
                unique_move_table_ids,
            )

            reservation = moved_reservations[
                move.reservation_id
            ]

            move_capacity = sum(
                table_by_id[table_id].seats
                for table_id in unique_move_table_ids
            )

            if move_capacity < reservation.party_size:
                raise ValidationError(
                    "Selected destination tables do not have enough "
                    f"capacity for reservation {reservation.id}."
                )

            move_table_ids_by_reservation[
                reservation.id
            ] = unique_move_table_ids

        affected_reservation_ids = {
            payload.new_reservation_id,
            *move_reservation_ids,
        }

        range_start = min(
            [
                new_reservation.reservation_time,
                *[
                    reservation.reservation_time
                    for reservation
                    in moved_reservations.values()
                ],
            ]
        ) - timedelta(hours=12)

        range_end = max(
            [
                (
                    new_reservation.reservation_time
                    + timedelta(
                        minutes=(
                            new_reservation.duration_minutes
                        ),
                    )
                ),
                *[
                    (
                        reservation.reservation_time
                        + timedelta(
                            minutes=(
                                reservation.duration_minutes
                            ),
                        )
                    )
                    for reservation
                    in moved_reservations.values()
                ],
            ]
        ) + timedelta(hours=12)

        nearby_result = await session.execute(
            select(Reservation)
            .options(
                selectinload(
                    Reservation.table_assignments,
                )
            )
            .where(
                Reservation.restaurant_id
                == new_reservation.restaurant_id,
                Reservation.id.notin_(
                    affected_reservation_ids,
                ),
                Reservation.status.in_(
                    BLOCKING_STATUSES,
                ),
                Reservation.reservation_time
                < range_end,
                Reservation.reservation_time
                >= range_start,
            )
        )

        nearby_reservations = list(
            nearby_result.scalars().unique().all()
        )

        proposed_assignments: list[
            tuple[
                Reservation,
                list[UUID],
            ]
        ] = [
            (
                new_reservation,
                new_table_ids,
            )
        ]

        for reservation_id, table_ids in (
            move_table_ids_by_reservation.items()
        ):
            proposed_assignments.append(
                (
                    moved_reservations[
                        reservation_id
                    ],
                    table_ids,
                )
            )

        for index, (
            reservation,
            table_ids,
        ) in enumerate(proposed_assignments):
            requested_start = (
                reservation.reservation_time
            )

            requested_end = (
                requested_start
                + timedelta(
                    minutes=(
                        reservation.duration_minutes
                    ),
                )
            )

            selected_table_id_set = set(
                table_ids,
            )

            for existing in nearby_reservations:
                existing_start = (
                    existing.reservation_time
                )

                existing_end = (
                    existing_start
                    + timedelta(
                        minutes=(
                            existing.duration_minutes
                        ),
                    )
                )

                overlaps = (
                    existing_start < requested_end
                    and existing_end > requested_start
                )

                if not overlaps:
                    continue

                existing_table_ids = set(
                    existing.assigned_table_ids
                    or (
                        [existing.table_id]
                        if existing.table_id
                        is not None
                        else []
                    )
                )

                if selected_table_id_set.intersection(
                    existing_table_ids,
                ):
                    raise ValidationError(
                        "One or more selected tables are already occupied "
                        "during the proposed reservation time."
                    )

            for (
                other_reservation,
                other_table_ids,
            ) in proposed_assignments[
                index + 1:
            ]:
                other_start = (
                    other_reservation.reservation_time
                )

                other_end = (
                    other_start
                    + timedelta(
                        minutes=(
                            other_reservation.duration_minutes
                        ),
                    )
                )

                overlaps = (
                    other_start < requested_end
                    and other_end > requested_start
                )

                if (
                    overlaps
                    and selected_table_id_set.intersection(
                        other_table_ids,
                    )
                ):
                    raise ValidationError(
                        "The proposed reoptimization plan assigns "
                        "overlapping reservations to the same table."
                    )

        reservations_to_replace = [
            new_reservation,
            *moved_reservations.values(),
        ]

        reservation_ids_to_replace = [
            reservation.id
            for reservation in reservations_to_replace
        ]

        await session.execute(
            sa.delete(
                ReservationTableAssignment,
            ).where(
                ReservationTableAssignment
                .reservation_id.in_(
                    reservation_ids_to_replace,
                )
            )
        )

        new_reservation.table_id = (
            payload.new_reservation_primary_table_id
        )

        for table_id in new_table_ids:
            session.add(
                ReservationTableAssignment(
                    reservation_id=(
                        new_reservation.id
                    ),
                    table_id=table_id,
                    is_primary=(
                        table_id
                        == payload
                        .new_reservation_primary_table_id
                    ),
                )
            )

        for move in payload.moves:
            reservation = moved_reservations[
                move.reservation_id
            ]

            table_ids = (
                move_table_ids_by_reservation[
                    move.reservation_id
                ]
            )

            reservation.table_id = (
                move.primary_table_id
            )

            for table_id in table_ids:
                session.add(
                    ReservationTableAssignment(
                        reservation_id=(
                            reservation.id
                        ),
                        table_id=table_id,
                        is_primary=(
                            table_id
                            == move.primary_table_id
                        ),
                    )
                )

        await session.flush()

        table_number_by_id = {
            table.id: table.table_number
            for table in tables
        }

        applied_moves = []

        for move in payload.moves:
            table_ids = (
                move_table_ids_by_reservation[
                    move.reservation_id
                ]
            )

            applied_moves.append(
                IntelligenceAppliedMoveResponse(
                    reservation_id=(
                        move.reservation_id
                    ),
                    primary_table_id=(
                        move.primary_table_id
                    ),
                    table_ids=table_ids,
                    table_numbers=[
                        table_number_by_id[
                            table_id
                        ]
                        for table_id in table_ids
                    ],
                )
            )

        return IntelligenceApplyReoptimizationResponse(
            new_reservation_id=(
                new_reservation.id
            ),
            new_reservation_primary_table_id=(
                payload
                .new_reservation_primary_table_id
            ),
            new_reservation_table_ids=(
                new_table_ids
            ),
            new_reservation_table_numbers=[
                table_number_by_id[
                    table_id
                ]
                for table_id in new_table_ids
            ],
            applied_moves=applied_moves,
        )

    async def apply_recommendation(
        self,
        session: AsyncSession,
        payload: IntelligenceApplyRequest,
        allowed_restaurant_ids: list[UUID],
    ) -> IntelligenceApplyResponse:
        if payload.primary_table_id not in payload.table_ids:
            raise ValidationError(
                "Primary table must be included in table_ids."
            )

        unique_table_ids = list(dict.fromkeys(payload.table_ids))

        reservation_result = await session.execute(
            select(Reservation).where(
                Reservation.id == payload.reservation_id,
                Reservation.restaurant_id.in_(allowed_restaurant_ids),
            )
        )

        reservation = reservation_result.scalar_one_or_none()

        if reservation is None:
            raise NotFoundError(
                f"Reservation {payload.reservation_id} not found"
            )

        if reservation.restaurant_id is None:
            raise ValidationError(
                "Reservation is not associated with a restaurant."
            )

        if reservation.status in {
            ReservationStatus.COMPLETED,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }:
            raise ValidationError(
                "Completed, cancelled, or no-show reservations "
                "cannot be reassigned."
            )

        tables_result = await session.execute(
            select(Table).where(
                Table.id.in_(unique_table_ids),
                Table.restaurant_id == reservation.restaurant_id,
                Table.is_active.is_(True),
            )
        )

        tables = list(tables_result.scalars().all())

        if len(tables) != len(unique_table_ids):
            raise ValidationError(
                "One or more selected tables were not found, are inactive, "
                "or belong to another restaurant."
            )

        service_area_ids = {
            table.service_area_id
            for table in tables
        }

        if len(service_area_ids) != 1:
            raise ValidationError(
                "Combined tables must belong to the same service area."
            )

        selected_capacity = sum(table.seats for table in tables)

        if selected_capacity < reservation.party_size:
            raise ValidationError(
                "Selected tables do not have enough total capacity."
            )

        requested_start = reservation.reservation_time
        requested_end = (
            reservation.reservation_time
            + timedelta(minutes=reservation.duration_minutes)
        )

        nearby_result = await session.execute(
            select(Reservation)
            .options(
                selectinload(Reservation.table_assignments)
            )
            .where(
                Reservation.restaurant_id == reservation.restaurant_id,
                Reservation.id != reservation.id,
                Reservation.status.in_(BLOCKING_STATUSES),
                Reservation.reservation_time
                < requested_end,
                Reservation.reservation_time
                >= requested_start - timedelta(minutes=720),
            )
        )

        nearby_reservations = list(
            nearby_result.scalars().unique().all()
        )

        selected_table_id_set = set(unique_table_ids)

        for existing in nearby_reservations:
            existing_start = existing.reservation_time
            existing_end = (
                existing.reservation_time
                + timedelta(minutes=existing.duration_minutes)
            )

            if not (
                existing_start < requested_end
                and existing_end > requested_start
            ):
                continue

            existing_table_ids = set(
                existing.assigned_table_ids
                or (
                    [existing.table_id]
                    if existing.table_id is not None
                    else []
                )
            )

            if selected_table_id_set.intersection(
                existing_table_ids
            ):
                raise ValidationError(
                    "One or more selected tables are already occupied "
                    "during this reservation."
                )

        await session.execute(
            sa.delete(ReservationTableAssignment).where(
                ReservationTableAssignment.reservation_id
                == reservation.id,
            )
        )

        reservation.table_id = payload.primary_table_id

        for table_id in unique_table_ids:
            session.add(
                ReservationTableAssignment(
                    reservation_id=reservation.id,
                    table_id=table_id,
                    is_primary=(
                        table_id == payload.primary_table_id
                    ),
                )
            )

        await session.flush()
        await session.refresh(reservation)

        table_number_by_id = {
            table.id: table.table_number
            for table in tables
        }

        ordered_table_numbers = [
            table_number_by_id[table_id]
            for table_id in unique_table_ids
        ]

        return IntelligenceApplyResponse(
            reservation_id=reservation.id,
            restaurant_id=reservation.restaurant_id,
            primary_table_id=payload.primary_table_id,
            table_ids=unique_table_ids,
            table_numbers=ordered_table_numbers,
            status=reservation.status.value,
        )