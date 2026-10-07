from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.ai_suggestion import (
    AISuggestionStatus,
    AISuggestionType,
)
from app.models.reservation import ReservationStatus
from app.services.ai_suggestion_service import AISuggestionService


@pytest.mark.asyncio
async def test_live_seated_modification_creates_pending_proposal_without_mutating_reservation():
    reservation_id = uuid4()
    restaurant_id = uuid4()
    table_43_id = uuid4()
    table_50_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        customer_name="Andrea Liveparty",
        party_size=2,
        reservation_time=datetime(
            2026,
            10,
            17,
            11,
            30,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        table_id=table_43_id,
        assigned_table_ids=[table_43_id],
    )

    assignment = SimpleNamespace(
        table_ids=[table_50_id],
        table_numbers=["50"],
    )

    plan = SimpleNamespace(
        new_reservation_assignment=assignment,
        moves=(),
        moved_reservations_count=0,
        score=100.0,
        temporal_autopilot_safety=None,
    )

    plan.model_dump = lambda *, mode, exclude=None: {
        "new_reservation_assignment": {
            "table_ids": [str(table_50_id)],
            "primary_table_id": str(table_50_id),
        },
        "moves": [],
        "score": 100.0,
        "moved_reservations_count": 0,
        "explanation": "Direct live-service reassignment.",
    }

    result = SimpleNamespace(
        available=True,
        recommended=plan,
        engine_version="aie-reoptimizer-v1",
        mode="read_only",
    )

    repository = SimpleNamespace(
        db=object(),
        create=AsyncMock(
            side_effect=lambda suggestion: suggestion,
        ),
        expire_pending_for_reservation=AsyncMock(
            return_value=[],
        ),
    )

    service = AISuggestionService(
        repository=repository,
        reservation_repository=SimpleNamespace(),
        intelligence_service=SimpleNamespace(
            reoptimize=AsyncMock(return_value=result),
        ),
    )

    service._record_ai_suggestion_event = AsyncMock()
    service._refresh_learning_profile = AsyncMock()

    created = await service.analyze_live_seated_modification(
        reservation,
        requested_party_size=4,
    )

    assert created is not None
    assert (
        created.suggestion_type
        == AISuggestionType.LIVE_SEATED_MODIFICATION
    )
    assert created.status == AISuggestionStatus.PENDING

    assert created.payload["reservation"]["party_size"] == 2
    assert created.payload["reservation"]["status"] == "seated"
    assert created.payload["reservation"]["table_ids"] == [
        str(table_43_id)
    ]
    assert (
        created.payload["requested_modification"]["party_size"]
        == 4
    )
    assert created.payload["plan"][
        "new_reservation_assignment"
    ]["table_ids"] == [str(table_50_id)]
    assert created.payload["plan"]["moves"] == []

    # Proposal phase must not alter authoritative live state.
    assert reservation.party_size == 2
    assert reservation.table_id == table_43_id
    assert reservation.assigned_table_ids == [table_43_id]
    assert reservation.status == ReservationStatus.SEATED

    repository.create.assert_awaited_once()

    repository.expire_pending_for_reservation.assert_awaited_once_with(
        reservation_id,
        suggestion_type=(
            AISuggestionType.LIVE_SEATED_MODIFICATION
        ),
    )


@pytest.mark.asyncio
async def test_live_seated_modification_rejects_plan_that_moves_other_reservations():
    reservation_id = uuid4()
    restaurant_id = uuid4()
    table_43_id = uuid4()
    table_50_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        customer_name="Andrea Liveparty",
        party_size=2,
        reservation_time=datetime(
            2026,
            10,
            17,
            11,
            30,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        table_id=table_43_id,
        assigned_table_ids=[table_43_id],
    )

    assignment = SimpleNamespace(
        table_ids=[table_50_id],
        table_numbers=["50"],
    )

    plan = SimpleNamespace(
        new_reservation_assignment=assignment,
        moves=(object(),),
        moved_reservations_count=1,
        score=80.0,
        temporal_autopilot_safety=None,
    )

    result = SimpleNamespace(
        available=True,
        recommended=plan,
        engine_version="aie-reoptimizer-v1",
        mode="read_only",
    )

    repository = SimpleNamespace(
        db=object(),
        create=AsyncMock(),
        expire_pending_for_reservation=AsyncMock(
            return_value=[],
        ),
    )

    service = AISuggestionService(
        repository=repository,
        reservation_repository=SimpleNamespace(),
        intelligence_service=SimpleNamespace(
            reoptimize=AsyncMock(return_value=result),
        ),
    )

    created = await service.analyze_live_seated_modification(
        reservation,
        requested_party_size=4,
    )

    assert created is None

    repository.create.assert_not_awaited()
    repository.expire_pending_for_reservation.assert_not_awaited()

    assert reservation.party_size == 2
    assert reservation.table_id == table_43_id
    assert reservation.assigned_table_ids == [table_43_id]
    assert reservation.status == ReservationStatus.SEATED


@pytest.mark.asyncio
async def test_reservation_service_live_proposal_boundary_delegates_only_for_seated(
    monkeypatch,
):
    from app.services.reservation_service import ReservationService

    reservation_id = uuid4()
    restaurant_id = uuid4()
    table_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        customer_name="Andrea Liveparty",
        party_size=2,
        reservation_time=datetime(
            2026,
            10,
            17,
            11,
            30,
            tzinfo=timezone.utc,
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        table_id=table_id,
        assigned_table_ids=[table_id],
    )

    repository = SimpleNamespace(
        db=object(),
        get_by_id=AsyncMock(
            return_value=reservation,
        ),
    )

    expected_suggestion = object()

    analyze_live = AsyncMock(
        return_value=expected_suggestion,
    )

    monkeypatch.setattr(
        AISuggestionService,
        "analyze_live_seated_modification",
        analyze_live,
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    result = await service.propose_live_seated_modification(
        reservation_id=reservation_id,
        requested_party_size=4,
    )

    assert result is expected_suggestion

    repository.get_by_id.assert_awaited_once_with(
        reservation_id
    )

    analyze_live.assert_awaited_once()

    call = analyze_live.await_args

    assert call.args[0] is reservation
    assert call.kwargs["requested_party_size"] == 4

    assert reservation.party_size == 2
    assert reservation.table_id == table_id
    assert reservation.status == ReservationStatus.SEATED



@pytest.mark.asyncio
async def test_apply_live_seated_modification_preserves_seated_lifecycle():
    from app.services.reservation_service import ReservationService
    """
    LAB-012:
    A manager-approved LIVE move changes requested party size and
    physical assignment on the SAME reservation while preserving the
    SEATED lifecycle and seated_at timestamp.
    """
    reservation_id = uuid4()
    restaurant_id = uuid4()
    original_table_id = uuid4()
    destination_table_id = uuid4()
    seated_at = datetime.fromisoformat(
        "2026-10-17T11:35:00+00:00"
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        seated_at=seated_at,
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
    )

    destination_table = SimpleNamespace(
        id=destination_table_id,
        restaurant_id=restaurant_id,
        seats=4,
        is_active=True,
        table_number="50",
    )

    class FakeReservationRepository:
        def __init__(self):
            self.db = SimpleNamespace()
            self.update_calls = []
            self.replace_calls = []

        async def get_by_id_for_restaurants_for_update(
            self,
            requested_reservation_id,
            restaurant_ids,
        ):
            assert requested_reservation_id == reservation_id
            assert restaurant_ids == [restaurant_id]
            return reservation

        async def find_seated_on_table_ids(
            self,
            table_ids,
            *,
            exclude_reservation_id=None,
        ):
            assert table_ids == [destination_table_id]
            assert exclude_reservation_id == reservation_id
            return None

        async def update(
            self,
            current_reservation,
            fields,
        ):
            self.update_calls.append(dict(fields))
            for key, value in fields.items():
                setattr(current_reservation, key, value)
            return current_reservation

        async def replace_table_assignments(
            self,
            current_reservation,
            table_ids,
            primary_table_id=None,
        ):
            self.replace_calls.append(
                {
                    "table_ids": list(table_ids),
                    "primary_table_id": primary_table_id,
                }
            )
            current_reservation.table_id = primary_table_id
            current_reservation.assigned_table_ids = list(
                table_ids
            )
            return current_reservation

    class FakeRestaurantRepository:
        async def get_by_id(self, restaurant_id):
            return SimpleNamespace(
                id=restaurant_id,
            )

    class FakeTableRepository:
        def __init__(self):
            self.lock_calls = []

        async def lock_by_ids(self, table_ids):
            self.lock_calls.append(list(table_ids))
            return [destination_table]

    repository = FakeReservationRepository()
    table_repository = FakeTableRepository()

    service = ReservationService(
        repository=repository,
        restaurant_repository=FakeRestaurantRepository(),
        table_repository=table_repository,
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    result = await (
        service.apply_live_seated_modification_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=[restaurant_id],
            requested_party_size=4,
            destination_table_ids=[destination_table_id],
            destination_primary_table_id=destination_table_id,
        )
    )

    assert result.id == reservation_id
    assert result.party_size == 4
    assert result.status == ReservationStatus.SEATED
    assert result.seated_at == seated_at
    assert result.table_id == destination_table_id
    assert result.assigned_table_ids == [
        destination_table_id
    ]

    assert table_repository.lock_calls == [
        [destination_table_id]
    ]

    assert repository.update_calls == [
        {
            "party_size": 4,
        }
    ]

    assert repository.replace_calls == [
        {
            "table_ids": [destination_table_id],
            "primary_table_id": destination_table_id,
        }
    ]



@pytest.mark.asyncio
async def test_apply_live_seated_modification_rejects_live_occupied_destination():
    from app.core.exceptions import ConflictError
    from app.services.reservation_service import ReservationService

    reservation_id = uuid4()
    restaurant_id = uuid4()
    original_table_id = uuid4()
    destination_table_id = uuid4()
    blocker_reservation_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        seated_at=datetime.fromisoformat(
            "2026-10-17T11:35:00+00:00"
        ),
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
    )

    destination_table = SimpleNamespace(
        id=destination_table_id,
        restaurant_id=restaurant_id,
        seats=4,
        is_active=True,
        table_number="50",
    )

    blocker = SimpleNamespace(
        id=blocker_reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.SEATED,
        table_id=destination_table_id,
    )

    class FakeReservationRepository:
        def __init__(self):
            self.db = SimpleNamespace()
            self.update_calls = []
            self.replace_calls = []

        async def get_by_id_for_restaurants_for_update(
            self,
            requested_reservation_id,
            restaurant_ids,
        ):
            assert requested_reservation_id == reservation_id
            assert restaurant_ids == [restaurant_id]
            return reservation

        async def find_seated_on_table_ids(
            self,
            table_ids,
            *,
            exclude_reservation_id=None,
        ):
            assert table_ids == [destination_table_id]
            assert exclude_reservation_id == reservation_id
            return blocker

        async def update(
            self,
            current_reservation,
            fields,
        ):
            self.update_calls.append(dict(fields))
            raise AssertionError(
                "Reservation must not mutate when destination is occupied."
            )

        async def replace_table_assignments(
            self,
            current_reservation,
            table_ids,
            primary_table_id=None,
        ):
            self.replace_calls.append(
                {
                    "table_ids": list(table_ids),
                    "primary_table_id": primary_table_id,
                }
            )
            raise AssertionError(
                "Assignments must not mutate when destination is occupied."
            )

    class FakeTableRepository:
        async def lock_by_ids(self, table_ids):
            assert table_ids == [destination_table_id]
            return [destination_table]

    repository = FakeReservationRepository()

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=FakeTableRepository(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    with pytest.raises(
        ConflictError,
        match="currently occupied",
    ):
        await service.apply_live_seated_modification_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=[restaurant_id],
            requested_party_size=4,
            destination_table_ids=[destination_table_id],
            destination_primary_table_id=destination_table_id,
        )

    assert reservation.party_size == 2
    assert reservation.table_id == original_table_id
    assert reservation.status == ReservationStatus.SEATED

    assert repository.update_calls == []
    assert repository.replace_calls == []



@pytest.mark.asyncio
async def test_apply_live_seated_modification_rejects_multitable_without_exact_combination(
    monkeypatch,
):
    from app.core.exceptions import ValidationError
    from app.services import reservation_service as reservation_service_module
    from app.services.reservation_service import ReservationService

    reservation_id = uuid4()
    restaurant_id = uuid4()
    original_table_id = uuid4()
    destination_table_a_id = uuid4()
    destination_table_b_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        seated_at=datetime.fromisoformat(
            "2026-10-17T11:35:00+00:00"
        ),
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
    )

    destination_tables = [
        SimpleNamespace(
            id=destination_table_a_id,
            restaurant_id=restaurant_id,
            seats=4,
            is_active=True,
            table_number="50",
        ),
        SimpleNamespace(
            id=destination_table_b_id,
            restaurant_id=restaurant_id,
            seats=4,
            is_active=True,
            table_number="51",
        ),
    ]

    class FakeReservationRepository:
        def __init__(self):
            self.db = SimpleNamespace()
            self.update_calls = []
            self.replace_calls = []
            self.occupancy_calls = []

        async def get_by_id_for_restaurants_for_update(
            self,
            requested_reservation_id,
            restaurant_ids,
        ):
            assert requested_reservation_id == reservation_id
            assert restaurant_ids == [restaurant_id]
            return reservation

        async def find_seated_on_table_ids(
            self,
            table_ids,
            *,
            exclude_reservation_id=None,
        ):
            self.occupancy_calls.append(
                {
                    "table_ids": list(table_ids),
                    "exclude_reservation_id": exclude_reservation_id,
                }
            )
            return None

        async def update(
            self,
            current_reservation,
            fields,
        ):
            self.update_calls.append(dict(fields))
            raise AssertionError(
                "Invalid multi-table destination must not mutate."
            )

        async def replace_table_assignments(
            self,
            current_reservation,
            table_ids,
            primary_table_id=None,
        ):
            self.replace_calls.append(
                {
                    "table_ids": list(table_ids),
                    "primary_table_id": primary_table_id,
                }
            )
            raise AssertionError(
                "Invalid multi-table destination must not mutate."
            )

    class FakeTableRepository:
        async def lock_by_ids(self, table_ids):
            assert table_ids == [
                destination_table_a_id,
                destination_table_b_id,
            ]
            return destination_tables

    class FakeTableCombinationRepository:
        def __init__(self, db):
            self.db = db

        async def list_by_restaurant(
            self,
            restaurant_id,
            service_area_id=None,
            include_inactive=False,
        ):
            # Deliberately no exact combination for A+B.
            return []

    monkeypatch.setattr(
        reservation_service_module,
        "TableCombinationRepository",
        FakeTableCombinationRepository,
    )

    repository = FakeReservationRepository()

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=FakeTableRepository(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    with pytest.raises(
        ValidationError,
        match="valid active combination",
    ):
        await service.apply_live_seated_modification_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=[restaurant_id],
            requested_party_size=6,
            destination_table_ids=[
                destination_table_a_id,
                destination_table_b_id,
            ],
            destination_primary_table_id=destination_table_a_id,
        )

    assert reservation.party_size == 2
    assert reservation.table_id == original_table_id
    assert reservation.status == ReservationStatus.SEATED

    assert repository.update_calls == []
    assert repository.replace_calls == []

    # Capacity validation must fail before occupancy/mutation.
    assert repository.occupancy_calls == []



@pytest.mark.asyncio
async def test_apply_live_seated_modification_accepts_exact_active_multitable_combination(
    monkeypatch,
):
    from app.services import reservation_service as reservation_service_module
    from app.services.reservation_service import ReservationService

    reservation_id = uuid4()
    restaurant_id = uuid4()
    original_table_id = uuid4()
    destination_table_a_id = uuid4()
    destination_table_b_id = uuid4()

    seated_at = datetime.fromisoformat(
        "2026-10-17T11:35:00+00:00"
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        party_size=2,
        reservation_time=datetime.fromisoformat(
            "2026-10-17T11:30:00+00:00"
        ),
        duration_minutes=90,
        status=ReservationStatus.SEATED,
        seated_at=seated_at,
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
        table_assignments=[],
    )

    destination_tables = [
        SimpleNamespace(
            id=destination_table_a_id,
            restaurant_id=restaurant_id,
            seats=4,
            is_active=True,
            table_number="50",
        ),
        SimpleNamespace(
            id=destination_table_b_id,
            restaurant_id=restaurant_id,
            seats=4,
            is_active=True,
            table_number="51",
        ),
    ]

    combination = SimpleNamespace(
        is_active=True,
        min_capacity=5,
        max_capacity=7,
        members=[
            SimpleNamespace(
                table_id=destination_table_a_id,
            ),
            SimpleNamespace(
                table_id=destination_table_b_id,
            ),
        ],
    )

    class FakeReservationRepository:
        def __init__(self):
            self.db = SimpleNamespace()
            self.update_calls = []
            self.replace_calls = []
            self.occupancy_calls = []

        async def get_by_id_for_restaurants_for_update(
            self,
            requested_reservation_id,
            restaurant_ids,
        ):
            assert requested_reservation_id == reservation_id
            assert restaurant_ids == [restaurant_id]
            return reservation

        async def find_seated_on_table_ids(
            self,
            table_ids,
            *,
            exclude_reservation_id=None,
        ):
            self.occupancy_calls.append(
                {
                    "table_ids": list(table_ids),
                    "exclude_reservation_id": exclude_reservation_id,
                }
            )
            return None

        async def update(
            self,
            current_reservation,
            fields,
        ):
            self.update_calls.append(dict(fields))

            for key, value in fields.items():
                setattr(
                    current_reservation,
                    key,
                    value,
                )

            return current_reservation

        async def replace_table_assignments(
            self,
            current_reservation,
            table_ids,
            primary_table_id=None,
        ):
            self.replace_calls.append(
                {
                    "table_ids": list(table_ids),
                    "primary_table_id": primary_table_id,
                }
            )

            current_reservation.table_id = (
                primary_table_id
            )
            current_reservation.assigned_table_ids = list(
                table_ids
            )

            return current_reservation

    class FakeTableRepository:
        def __init__(self):
            self.lock_calls = []

        async def lock_by_ids(self, table_ids):
            self.lock_calls.append(
                list(table_ids)
            )
            return destination_tables

    class FakeTableCombinationRepository:
        def __init__(self, db):
            self.db = db

        async def list_by_restaurant(
            self,
            restaurant_id,
            service_area_id=None,
            include_inactive=False,
        ):
            assert restaurant_id == reservation.restaurant_id
            return [combination]

    monkeypatch.setattr(
        reservation_service_module,
        "TableCombinationRepository",
        FakeTableCombinationRepository,
    )

    repository = FakeReservationRepository()
    table_repository = FakeTableRepository()

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=table_repository,
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    result = await (
        service.apply_live_seated_modification_for_restaurants(
            reservation_id=reservation_id,
            restaurant_ids=[restaurant_id],
            requested_party_size=6,
            destination_table_ids=[
                destination_table_a_id,
                destination_table_b_id,
            ],
            destination_primary_table_id=(
                destination_table_a_id
            ),
        )
    )

    assert result.id == reservation_id
    assert result.party_size == 6
    assert result.status == ReservationStatus.SEATED
    assert result.seated_at == seated_at
    assert result.table_id == destination_table_a_id

    assert result.assigned_table_ids == [
        destination_table_a_id,
        destination_table_b_id,
    ]

    assert table_repository.lock_calls == [[
        destination_table_a_id,
        destination_table_b_id,
    ]]

    assert repository.occupancy_calls == [{
        "table_ids": [
            destination_table_a_id,
            destination_table_b_id,
        ],
        "exclude_reservation_id": reservation_id,
    }]

    assert repository.update_calls == [{
        "party_size": 6,
    }]

    assert repository.replace_calls == [{
        "table_ids": [
            destination_table_a_id,
            destination_table_b_id,
        ],
        "primary_table_id": destination_table_a_id,
    }]
