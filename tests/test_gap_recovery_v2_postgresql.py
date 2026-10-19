"""PostgreSQL integration tests for Gap Recovery V2."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
    IntelligenceReoptimizationMoveApply,
)
from app.intelligence.sqlalchemy_service import IntelligenceOptimizationService
from app.models.reservation import Reservation, ReservationStatus
from app.models.reservation_table_assignment import ReservationTableAssignment
from app.models.restaurant import Restaurant
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.user import User


@pytest.mark.asyncio
async def test_gap_recovery_applies_two_moves_atomically():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )
            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])
            await session.flush()

            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import IntelligenceEventSource

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            payload.suggestion_id = suggestion.id

            result = await IntelligenceExecutionOrchestrator().apply_reoptimization(
                session=session,
                payload=payload,
                allowed_restaurant_ids=[restaurant.id],
                source=IntelligenceEventSource.MANAGER,
                actor_user_id=user.id,
            )

            assert result.applied is True
            assert len(result.applied_moves) == 2

            await session.commit()

            from app.models.ai_suggestion import (
                AISuggestion,
                AISuggestionStatus,
            )
            from app.intelligence_events.models import (
                IntelligenceEvent,
                IntelligenceEventType,
            )

            suggestion_result = await session.execute(
                select(AISuggestion).where(
                    AISuggestion.id == suggestion.id,
                )
            )

            persisted_suggestion = suggestion_result.scalar_one()

            assert (
                persisted_suggestion.status
                == AISuggestionStatus.ACCEPTED
            )

            audit_result = await session.execute(
                select(IntelligenceEvent).where(
                    IntelligenceEvent.restaurant_id == restaurant.id,
                    IntelligenceEvent.event_type
                    == IntelligenceEventType.SEATING_PLAN_APPLIED,
                    IntelligenceEvent.entity_id == reservations[2].id,
                )
            )

            audit_events = audit_result.scalars().all()

            assert len(audit_events) == 1
            assert (
                audit_events[0].payload["suggestion_id"]
                == str(suggestion.id)
            )
            assert len(audit_events[0].payload["moves"]) == 2

            rows = (
                await session.execute(
                    select(Reservation).where(
                        Reservation.id.in_([r.id for r in reservations])
                    )
                )
            ).scalars().all()

            by_id = {r.id: r for r in rows}

            assert by_id[reservations[0].id].table_id == tables[2].id
            assert by_id[reservations[1].id].table_id == tables[3].id
            assert by_id[reservations[2].id].table_id == tables[0].id
            assert by_id[reservations[2].id].status == ReservationStatus.CONFIRMED

            assignments = (
                await session.execute(
                    select(ReservationTableAssignment).where(
                        ReservationTableAssignment.reservation_id.in_(
                            [r.id for r in reservations]
                        )
                    )
                )
            ).scalars().all()

            assignment_map = {}
            for assignment in assignments:
                assignment_map.setdefault(
                    assignment.reservation_id, set()
                ).add(assignment.table_id)

            assert assignment_map[reservations[0].id] == {tables[2].id}
            assert assignment_map[reservations[1].id] == {tables[3].id}
            assert assignment_map[reservations[2].id] == {
                tables[0].id, tables[1].id
            }

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_gap_recovery_rejects_two_moves_without_partial_changes():
    """An invalid destination must reject the entire two-move plan."""
    from app.core.exceptions import ValidationError

    suffix = uuid4().hex
    user_id = None

    try:
        async with AsyncSessionLocal() as session:
            user = User(
                email=f"gap-rollback-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Rollback {suffix}",
                slug=f"gap-rollback-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"ROLL-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=(
                        tables[0].id if i == 0 else
                        tables[1].id if i == 1 else
                        tables[3].id if i == 3 else None
                    ),
                    customer_name=f"Rollback Guest {i}",
                    customer_phone="+15550000123",
                    party_size=4 if i == 2 else 2,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.PENDING
                        if i == 2
                        else ReservationStatus.CONFIRMED
                    ),
                )
                for i in range(4)
            ]
            session.add_all(reservations)
            await session.flush()

            for index, table_index in ((0, 0), (1, 1), (3, 3)):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[table_index].id,
                        is_primary=True,
                    )
                )

            restaurant_id = restaurant.id
            reservation_ids = [r.id for r in reservations]
            table_ids = [t.id for t in tables]

            await session.commit()

        payload = IntelligenceApplyReoptimizationRequest(
            new_reservation_id=reservation_ids[2],
            new_reservation_table_ids=table_ids[:2],
            new_reservation_primary_table_id=table_ids[0],
            moves=[
                IntelligenceReoptimizationMoveApply(
                    reservation_id=reservation_ids[0],
                    to_table_ids=[table_ids[2]],
                    primary_table_id=table_ids[2],
                ),
                IntelligenceReoptimizationMoveApply(
                    reservation_id=reservation_ids[1],
                    to_table_ids=[table_ids[3]],
                    primary_table_id=table_ids[3],
                ),
            ],
        )

        async with AsyncSessionLocal() as apply_session:
            with pytest.raises(ValidationError):
                await IntelligenceOptimizationService().apply_reoptimization(
                    session=apply_session,
                    payload=payload,
                    allowed_restaurant_ids=[restaurant_id],
                )
            await apply_session.rollback()

        async with AsyncSessionLocal() as verification:
            rows = (
                await verification.execute(
                    select(Reservation).where(
                        Reservation.id.in_(reservation_ids)
                    )
                )
            ).scalars().all()

            by_id = {r.id: r for r in rows}

            assert by_id[reservation_ids[0]].table_id == table_ids[0]
            assert by_id[reservation_ids[1]].table_id == table_ids[1]
            assert by_id[reservation_ids[2]].table_id is None
            assert by_id[reservation_ids[3]].table_id == table_ids[3]

            assert (
                by_id[reservation_ids[2]].status
                == ReservationStatus.PENDING
            )

            assignments = (
                await verification.execute(
                    select(ReservationTableAssignment).where(
                        ReservationTableAssignment.reservation_id.in_(
                            reservation_ids
                        )
                    )
                )
            ).scalars().all()

            assignment_map = {}
            for assignment in assignments:
                assignment_map.setdefault(
                    assignment.reservation_id, set()
                ).add(assignment.table_id)

            assert assignment_map == {
                reservation_ids[0]: {table_ids[0]},
                reservation_ids[1]: {table_ids[1]},
                reservation_ids[3]: {table_ids[3]},
            }

    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup.commit()


@pytest.mark.asyncio
async def test_gap_recovery_rolls_back_after_successful_flush():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Rollback Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )

            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])

            await session.flush()
            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import (
                IntelligenceEventSource,
            )

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            suggestion_id = suggestion.id

            # Persist the authoritative suggestion before Apply.
            await session.commit()

            payload.suggestion_id = suggestion_id

            result = await IntelligenceExecutionOrchestrator().apply_reoptimization(
                session=session,
                payload=payload,
                allowed_restaurant_ids=[restaurant.id],
                source=IntelligenceEventSource.MANAGER,
                actor_user_id=user.id,
            )

            assert result.applied is True
            assert len(result.applied_moves) == 2

            # Preserve identifiers before rollback expires ORM state.
            reservation_ids = [r.id for r in reservations]
            table_ids = [t.id for t in tables]

            # Apply has flushed both moves, but nothing is committed.
            await session.rollback()

            rows = (
                await session.execute(
                    select(Reservation).where(
                        Reservation.id.in_(reservation_ids)
                    )
                )
            ).scalars().all()

            by_id = {r.id: r for r in rows}

            assert by_id[reservation_ids[0]].table_id == table_ids[0]
            assert by_id[reservation_ids[1]].table_id == table_ids[1]
            assert by_id[reservation_ids[2]].table_id is None
            assert by_id[reservation_ids[2]].status == ReservationStatus.PENDING

            assignments = (
                await session.execute(
                    select(ReservationTableAssignment).where(
                        ReservationTableAssignment.reservation_id.in_(
                            reservation_ids
                        )
                    )
                )
            ).scalars().all()

            assignment_map = {}
            for assignment in assignments:
                assignment_map.setdefault(
                    assignment.reservation_id, set()
                ).add(assignment.table_id)

            assert assignment_map[reservation_ids[0]] == {table_ids[0]}
            assert assignment_map[reservation_ids[1]] == {table_ids[1]}
            assert reservation_ids[2] not in assignment_map

            # Verify that approval and audit were rolled back too.
            from app.models.ai_suggestion import (
                AISuggestion,
                AISuggestionStatus,
            )
            from app.intelligence_events.models import (
                IntelligenceEvent,
                IntelligenceEventType,
            )

            persisted_suggestion = (
                await session.execute(
                    select(AISuggestion).where(
                        AISuggestion.id == suggestion_id,
                    )
                )
            ).scalar_one()

            assert (
                persisted_suggestion.status
                == AISuggestionStatus.PENDING
            )

            audit_events = (
                await session.execute(
                    select(IntelligenceEvent).where(
                        IntelligenceEvent.restaurant_id
                        == persisted_suggestion.restaurant_id,
                        IntelligenceEvent.event_type.in_(
                            [
                                IntelligenceEventType.SEATING_PLAN_APPLIED,
                                IntelligenceEventType.AI_SUGGESTION_ACCEPTED,
                            ]
                        ),
                    )
                )
            ).scalars().all()

            assert audit_events == []

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()



@pytest.mark.asyncio
async def test_gap_recovery_rejects_new_special_request_at_apply():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            # Preserve UUIDs before commit/rollback expires ORM state.
            reservation_ids = [r.id for r in reservations]
            table_ids = [t.id for t in tables]

            # Preserve UUIDs before commit/rollback expires ORM state.
            reservation_ids = [r.id for r in reservations]
            table_ids = [t.id for t in tables]

            # A special request was added after the plan was generated.
            reservations[0].special_requests = "Window seat requested"
            await session.commit()

            from app.core.exceptions import ValidationError

            with pytest.raises(ValidationError):
                await IntelligenceOptimizationService().apply_reoptimization(
                    session=session,
                    payload=payload,
                    allowed_restaurant_ids=[restaurant.id],
                )

            await session.rollback()

            rows = (
                await session.execute(
                    select(Reservation).where(
                        Reservation.id.in_(reservation_ids)
                    )
                )
            ).scalars().all()

            by_id = {r.id: r for r in rows}

            assert by_id[reservation_ids[0]].table_id == table_ids[0]
            assert by_id[reservation_ids[1]].table_id == table_ids[1]
            assert by_id[reservation_ids[2]].table_id is None
            assert by_id[reservation_ids[2]].status == ReservationStatus.PENDING

            assignments = (
                await session.execute(
                    select(ReservationTableAssignment).where(
                        ReservationTableAssignment.reservation_id.in_(
                            reservation_ids
                        )
                    )
                )
            ).scalars().all()

            assignment_map = {}
            for assignment in assignments:
                assignment_map.setdefault(
                    assignment.reservation_id, set()
                ).add(assignment.table_id)

            assert assignment_map[reservation_ids[0]] == {table_ids[0]}
            assert assignment_map[reservation_ids[1]] == {table_ids[1]}
            assert reservation_ids[2] not in assignment_map

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()



@pytest.mark.asyncio
async def test_gap_recovery_waits_for_concurrent_special_request_update():
    """Apply must observe a special request committed while waiting for a row lock."""
    import asyncio

    from app.core.exceptions import ValidationError
    from app.repositories.reservation_repository import ReservationRepository

    suffix = uuid4().hex
    user_id = None

    try:
        # Create and commit the initial database state.
        async with AsyncSessionLocal() as setup:
            user = User(
                email=f"gap-concurrent-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            setup.add(user)
            await setup.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Concurrent {suffix}",
                slug=f"gap-concurrent-{suffix}",
            )
            setup.add(restaurant)
            await setup.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            setup.add(area)
            await setup.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"CON-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            setup.add_all(tables)
            await setup.flush()

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Concurrent Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            setup.add_all(reservations)
            await setup.flush()

            for i in range(2):
                setup.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[i].id,
                        table_id=tables[i].id,
                        is_primary=True,
                    )
                )

            restaurant_id = restaurant.id
            reservation_ids = [r.id for r in reservations]
            table_ids = [t.id for t in tables]

            await setup.commit()

        payload = IntelligenceApplyReoptimizationRequest(
            new_reservation_id=reservation_ids[2],
            new_reservation_table_ids=table_ids[:2],
            new_reservation_primary_table_id=table_ids[0],
            moves=[
                IntelligenceReoptimizationMoveApply(
                    reservation_id=reservation_ids[0],
                    to_table_ids=[table_ids[2]],
                    primary_table_id=table_ids[2],
                ),
                IntelligenceReoptimizationMoveApply(
                    reservation_id=reservation_ids[1],
                    to_table_ids=[table_ids[3]],
                    primary_table_id=table_ids[3],
                ),
            ],
        )

        # Persist the authoritative V2 suggestion before
        # starting the two concurrent PostgreSQL transactions.
        async with AsyncSessionLocal() as suggestion_session:
            suggestion = await create_gap_v2_test_suggestion(
                suggestion_session,
                restaurant_id=restaurant_id,
                reservation_id=reservation_ids[2],
                incoming_table_ids=table_ids[:2],
                moves=payload.moves,
                reservation_time=start,
            )

            suggestion_id = suggestion.id
            await suggestion_session.commit()

        payload.suggestion_id = suggestion_id

        first_session = AsyncSessionLocal()
        apply_session = AsyncSessionLocal()

        try:
            # Transaction A locks the first reservation.
            locked = await ReservationRepository(
                first_session
            ).get_by_id_for_restaurants_for_update(
                reservation_id=reservation_ids[0],
                restaurant_ids=[restaurant_id],
            )

            assert locked is not None

            locked.special_requests = "Guaranteed window preference"
            await first_session.flush()

            # Transaction B attempts the two-move Apply.
            async def attempt_apply():
                try:
                    await IntelligenceOptimizationService().apply_reoptimization(
                        session=apply_session,
                        payload=payload,
                        allowed_restaurant_ids=[restaurant_id],
                    )
                    await apply_session.commit()
                    return "applied"
                except ValidationError:
                    await apply_session.rollback()
                    return "rejected"

            task = asyncio.create_task(attempt_apply())

            # Transaction B should be waiting for A's reservation lock.
            await asyncio.sleep(0.2)

            assert not task.done(), (
                "Gap Recovery Apply did not wait for the reservation lock."
            )

            # Commit the newly added special request.
            await first_session.commit()

            outcome = await asyncio.wait_for(task, timeout=5)
            assert outcome == "rejected"

        finally:
            await first_session.rollback()
            await first_session.close()

            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

            await apply_session.rollback()
            await apply_session.close()

        # Verify durable database state using a fresh session.
        async with AsyncSessionLocal() as verification:
            rows = (
                await verification.execute(
                    select(Reservation).where(
                        Reservation.id.in_(reservation_ids)
                    )
                )
            ).scalars().all()

            by_id = {r.id: r for r in rows}

            assert by_id[reservation_ids[0]].table_id == table_ids[0]
            assert by_id[reservation_ids[1]].table_id == table_ids[1]
            assert by_id[reservation_ids[2]].table_id is None
            assert by_id[reservation_ids[2]].status == ReservationStatus.PENDING

            assert (
                by_id[reservation_ids[0]].special_requests
                == "Guaranteed window preference"
            )

    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup.commit()


@pytest.mark.asyncio
async def test_gap_recovery_v2_requires_authoritative_suggestion():
    """Two-move Apply must reject missing suggestion before DB access."""
    from app.core.exceptions import ValidationError

    incoming_table = uuid4()
    first_destination = uuid4()
    second_destination = uuid4()

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=None,
        new_reservation_id=uuid4(),
        new_reservation_table_ids=[incoming_table],
        new_reservation_primary_table_id=incoming_table,
        moves=[
            IntelligenceReoptimizationMoveApply(
                reservation_id=uuid4(),
                to_table_ids=[first_destination],
                primary_table_id=first_destination,
            ),
            IntelligenceReoptimizationMoveApply(
                reservation_id=uuid4(),
                to_table_ids=[second_destination],
                primary_table_id=second_destination,
            ),
        ],
    )

    with pytest.raises(
        ValidationError,
        match="suggestion",
    ):
        await IntelligenceOptimizationService().apply_reoptimization(
            session=None,
            payload=payload,
            allowed_restaurant_ids=[],
        )


async def create_gap_v2_test_suggestion(
    session,
    *,
    restaurant_id,
    reservation_id,
    incoming_table_ids,
    moves,
    reservation_time,
    incoming_resource_id=None,
):
    """Persist a real, tenant-scoped two-move AI suggestion."""
    from app.models.ai_suggestion import (
        AISuggestion,
        AISuggestionStatus,
        AISuggestionType,
    )

    suggestion = AISuggestion(
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        status=AISuggestionStatus.PENDING,
        title="Gap Recovery V2 seating plan",
        description="Two coordinated table reassignments",
        score=80.0,
        payload={
            "plan": {
                "new_reservation_assignment": {
                    "table_ids": [
                        str(table_id)
                        for table_id in incoming_table_ids
                    ],
                    "resource_id": (
                        str(incoming_resource_id)
                        if incoming_resource_id is not None
                        else None
                    ),
                    "setup_minutes": 0,
                },
                "moves": [
                    {
                        "reservation_id": str(move.reservation_id),
                        "to_table_ids": [
                            str(table_id)
                            for table_id in move.to_table_ids
                        ],
                        "destination_resource_id": (
                            str(move.to_table_ids[0])
                            if len(move.to_table_ids) == 1
                            else None
                        ),
                        "destination_setup_minutes": 0,
                    }
                    for move in moves
                ],
                "moved_reservations_count": len(moves),
            },
        },
        expires_at=reservation_time + timedelta(hours=3),
    )

    session.add(suggestion)
    await session.flush()

    return suggestion


@pytest.mark.asyncio
async def test_gap_recovery_rejects_deactivated_combination():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )
            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])
            await session.flush()

            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import IntelligenceEventSource

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            payload.suggestion_id = suggestion.id

            # The combination becomes inactive after proposal creation.
            combination.is_active = False
            await session.flush()

            from app.core.exceptions import ValidationError

            with pytest.raises(ValidationError):
                await IntelligenceExecutionOrchestrator().apply_reoptimization(
                    session=session,
                    payload=payload,
                    allowed_restaurant_ids=[restaurant.id],
                    source=IntelligenceEventSource.MANAGER,
                    actor_user_id=user.id,
                )

            await session.rollback()

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()



@pytest.mark.asyncio
async def test_gap_recovery_rejects_insufficient_setup_time():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=15,
                is_active=True,
            )
            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])
            await session.flush()

            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import IntelligenceEventSource

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            payload.suggestion_id = suggestion.id

            # Preserve the proposal's original preparation requirement.
            suggestion.payload = {
                **suggestion.payload,
                "plan": {
                    **suggestion.payload["plan"],
                    "new_reservation_assignment": {
                        **suggestion.payload["plan"]["new_reservation_assignment"],
                        "setup_minutes": 15,
                    },
                },
            }

            # An unrelated reservation occupies T1 until only
            # 10 minutes before the incoming booking.
            previous_reservation = Reservation(
                restaurant_id=restaurant.id,
                table_id=tables[0].id,
                customer_name="Setup Conflict Guest",
                customer_phone="+15550000999",
                party_size=2,
                reservation_time=start - timedelta(minutes=100),
                duration_minutes=90,
                status=ReservationStatus.CONFIRMED,
            )

            session.add(previous_reservation)
            await session.flush()

            session.add(
                ReservationTableAssignment(
                    reservation_id=previous_reservation.id,
                    table_id=tables[0].id,
                    is_primary=True,
                )
            )

            await session.flush()

            from app.core.exceptions import ValidationError

            with pytest.raises(ValidationError) as exc_info:
                await IntelligenceExecutionOrchestrator().apply_reoptimization(
                    session=session,
                    payload=payload,
                    allowed_restaurant_ids=[restaurant.id],
                    source=IntelligenceEventSource.MANAGER,
                    actor_user_id=user.id,
                )

            assert (
                "already occupied during the proposed reservation time"
                in str(exc_info.value)
            )

            await session.rollback()

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()



@pytest.mark.asyncio
async def test_gap_recovery_allows_zero_setup_time():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )
            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])
            await session.flush()

            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import IntelligenceEventSource

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            payload.suggestion_id = suggestion.id

            # Preserve the proposal's original preparation requirement.
            suggestion.payload = {
                **suggestion.payload,
                "plan": {
                    **suggestion.payload["plan"],
                    "new_reservation_assignment": {
                        **suggestion.payload["plan"]["new_reservation_assignment"],
                        "setup_minutes": 0,
                    },
                },
            }

            # An unrelated reservation occupies T1 until only
            # 10 minutes before the incoming booking.
            previous_reservation = Reservation(
                restaurant_id=restaurant.id,
                table_id=tables[0].id,
                customer_name="Setup Conflict Guest",
                customer_phone="+15550000999",
                party_size=2,
                reservation_time=start - timedelta(minutes=100),
                duration_minutes=90,
                status=ReservationStatus.CONFIRMED,
            )

            session.add(previous_reservation)
            await session.flush()

            session.add(
                ReservationTableAssignment(
                    reservation_id=previous_reservation.id,
                    table_id=tables[0].id,
                    is_primary=True,
                )
            )

            await session.flush()

            from app.core.exceptions import ValidationError

            result = await IntelligenceExecutionOrchestrator().apply_reoptimization(
                session=session,
                payload=payload,
                allowed_restaurant_ids=[restaurant.id],
                source=IntelligenceEventSource.MANAGER,
                actor_user_id=user.id,
            )

            assert result.applied is True
            assert len(result.applied_moves) == 2

            await session.rollback()

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()




@pytest.mark.asyncio
async def test_gap_recovery_rejects_changed_combination_members():
    user_id = None
    suffix = uuid4().hex

    async with AsyncSessionLocal() as session:
        try:
            user = User(
                email=f"gap-v2-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Recovery V2 {suffix}",
                slug=f"gap-v2-{suffix}",
            )
            session.add(restaurant)
            await session.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            session.add(area)
            await session.flush()

            tables = [
                Table(
                    restaurant_id=restaurant.id,
                    service_area_id=area.id,
                    table_code=f"GAP-{suffix}-{i}",
                    table_number=str(i),
                    seats=2,
                )
                for i in range(1, 5)
            ]
            session.add_all(tables)
            await session.flush()

            from app.models.table_combination import (
                TableCombination,
                TableCombinationMember,
            )

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Gap V2 Combination {suffix}",
                min_capacity=3,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )
            session.add(combination)
            await session.flush()

            session.add_all([
                TableCombinationMember(
                    combination_id=combination.id,
                    table_id=tables[index].id,
                    sort_order=index,
                )
                for index in range(2)
            ])
            await session.flush()

            combination_id = combination.id

            start = datetime.now(timezone.utc) + timedelta(days=10)

            reservations = [
                Reservation(
                    restaurant_id=restaurant.id,
                    table_id=tables[i].id if i < 2 else None,
                    customer_name=f"Guest {i}",
                    customer_phone="+15550000123",
                    party_size=2 if i < 2 else 4,
                    reservation_time=start,
                    duration_minutes=90,
                    status=(
                        ReservationStatus.CONFIRMED
                        if i < 2
                        else ReservationStatus.PENDING
                    ),
                )
                for i in range(3)
            ]

            session.add_all(reservations)
            await session.flush()

            for index in range(2):
                session.add(
                    ReservationTableAssignment(
                        reservation_id=reservations[index].id,
                        table_id=tables[index].id,
                        is_primary=True,
                    )
                )

            await session.commit()

            payload = IntelligenceApplyReoptimizationRequest(
                new_reservation_id=reservations[2].id,
                new_reservation_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                new_reservation_primary_table_id=tables[0].id,
                moves=[
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[0].id,
                        to_table_ids=[tables[2].id],
                        primary_table_id=tables[2].id,
                    ),
                    IntelligenceReoptimizationMoveApply(
                        reservation_id=reservations[1].id,
                        to_table_ids=[tables[3].id],
                        primary_table_id=tables[3].id,
                    ),
                ],
            )

            from app.intelligence_execution.orchestrator import (
                IntelligenceExecutionOrchestrator,
            )
            from app.intelligence_events.models import IntelligenceEventSource

            suggestion = await create_gap_v2_test_suggestion(
                session,
                restaurant_id=restaurant.id,
                reservation_id=reservations[2].id,
                incoming_table_ids=[
                    tables[0].id,
                    tables[1].id,
                ],
                moves=payload.moves,
                reservation_time=start,
                incoming_resource_id=combination_id,
            )

            payload.suggestion_id = suggestion.id

            # The physical combination changes after proposal creation.
            # Replace T2 with T3 while keeping the combination active.
            members = (
                await session.execute(
                    select(TableCombinationMember).where(
                        TableCombinationMember.combination_id
                        == combination_id
                    )
                )
            ).scalars().all()

            assert len(members) == 2

            second_member = next(
                member
                for member in members
                if member.table_id == tables[1].id
            )

            second_member.table_id = tables[2].id

            await session.flush()

            assert combination.is_active is True

            from app.core.exceptions import ValidationError

            with pytest.raises(ValidationError):
                await IntelligenceExecutionOrchestrator().apply_reoptimization(
                    session=session,
                    payload=payload,
                    allowed_restaurant_ids=[restaurant.id],
                    source=IntelligenceEventSource.MANAGER,
                    actor_user_id=user.id,
                )

            await session.rollback()

        finally:
            await session.rollback()

    if user_id is not None:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()




@pytest.mark.asyncio
async def test_gap_recovery_combination_update_waits_for_apply_lock():
    """Combination updates must wait for an authoritative row lock."""
    import asyncio

    from app.models.table_combination import TableCombination
    from app.repositories.table_combination_repository import (
        TableCombinationRepository,
    )

    suffix = uuid4().hex
    user_id = None

    try:
        async with AsyncSessionLocal() as setup:
            user = User(
                email=f"gap-lock-{suffix}@example.com",
                hashed_password="test",
                is_active=True,
                is_email_verified=True,
            )
            setup.add(user)
            await setup.flush()
            user_id = user.id

            restaurant = Restaurant(
                owner_id=user.id,
                name=f"Gap Lock {suffix}",
                slug=f"gap-lock-{suffix}",
            )
            setup.add(restaurant)
            await setup.flush()

            area = ServiceArea(
                restaurant_id=restaurant.id,
                name="Main",
            )
            setup.add(area)
            await setup.flush()

            combination = TableCombination(
                restaurant_id=restaurant.id,
                service_area_id=area.id,
                name=f"Lock Combination {suffix}",
                min_capacity=1,
                max_capacity=4,
                setup_minutes=0,
                is_active=True,
            )
            setup.add(combination)
            await setup.flush()

            restaurant_id = restaurant.id
            combination_id = combination.id

            await setup.commit()

        apply_session = AsyncSessionLocal()
        update_session = AsyncSessionLocal()
        task = None

        try:
            # Simulate Apply holding the authoritative combination lock.
            locked = await TableCombinationRepository(
                apply_session
            ).get_by_id_for_update(
                combination_id=combination_id,
                restaurant_id=restaurant_id,
            )

            assert locked is not None

            async def concurrent_update():
                repository = TableCombinationRepository(
                    update_session
                )

                current = await repository.get_by_id(
                    combination_id=combination_id,
                    restaurant_id=restaurant_id,
                )

                assert current is not None

                await repository.update(
                    combination=current,
                    fields={"setup_minutes": 15},
                )

                await update_session.commit()
                return "updated"

            task = asyncio.create_task(concurrent_update())

            await asyncio.sleep(0.2)

            assert not task.done(), (
                "Combination update bypassed the Apply row lock."
            )

            await apply_session.commit()

            outcome = await asyncio.wait_for(task, timeout=5)
            assert outcome == "updated"

        finally:
            await apply_session.rollback()
            await apply_session.close()

            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

            await update_session.rollback()
            await update_session.close()

        async with AsyncSessionLocal() as verification:
            persisted = await TableCombinationRepository(
                verification
            ).get_by_id(
                combination_id=combination_id,
                restaurant_id=restaurant_id,
            )

            assert persisted is not None
            assert persisted.setup_minutes == 15

    finally:
        if user_id is not None:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(User).where(User.id == user_id)
                )
                await cleanup.commit()
