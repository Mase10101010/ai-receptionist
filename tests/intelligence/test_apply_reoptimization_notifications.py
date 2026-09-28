from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence.router import apply_reoptimization
from app.intelligence.schemas import (
    IntelligenceApplyReoptimizationRequest,
)
from app.models.reservation import ReservationStatus
from app.core.exceptions import ValidationError


@pytest.mark.asyncio
async def test_modification_reoptimization_sends_confirmation_after_commit(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    table_id = uuid4()
    user_id = uuid4()

    original_time = datetime(
        2026,
        9,
        28,
        11,
        0,
        tzinfo=timezone.utc,
    )

    requested_time = datetime(
        2026,
        9,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        subscription_status="active",
        timezone="UTC",
        preferred_language="en",
        name="Alias Test Restaurant",
    )

    previous_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=original_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    confirmed_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=10,
        reservation_time=requested_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "requested_modification": {
                "party_size": 10,
                "reservation_time": (
                    requested_time.isoformat()
                ),
            },
        },
    )

    lifecycle_events = []

    class FakeRestaurantRepository:
        def __init__(self, session):
            self.session = session

        async def list_by_owner(self, owner_id):
            return [restaurant]

        async def get_by_id(self, requested_restaurant_id):
            assert requested_restaurant_id == restaurant_id
            return restaurant

    class FakeReservationRepository:
        def __init__(self, session):
            self.session = session
            self.calls = 0

        async def get_by_id_for_restaurants(
            self,
            *,
            reservation_id,
            restaurant_ids,
        ):
            self.calls += 1

            if self.calls == 1:
                return previous_reservation

            return confirmed_reservation

    class FakeAISuggestionRepository:
        def __init__(self, session):
            self.session = session

        async def get_by_id(
            self,
            *,
            suggestion_id,
            restaurant_ids=None,
        ):
            return suggestion

    class FakeOrchestrator:
        def __init__(self, *, intelligence_service):
            self.intelligence_service = intelligence_service

        async def apply_reoptimization(self, **kwargs):
            lifecycle_events.append("apply")

            return SimpleNamespace(
                new_reservation_id=reservation_id,
                new_reservation_primary_table_id=table_id,
                new_reservation_table_ids=[table_id],
                applied_moves=[],
            )

    class FakeEmailService:
        async def send_reservation_confirmation(
            self,
            **kwargs,
        ):
            lifecycle_events.append("email")

            assert kwargs["to_email"] == "guest@example.com"
            assert kwargs["party_size"] == 10
            assert kwargs["reservation_id"] == str(
                reservation_id
            )

    session = SimpleNamespace()

    async def commit():
        lifecycle_events.append("commit")

    session.commit = commit

    monkeypatch.setattr(
        "app.intelligence.router.RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.AISuggestionRepository",
        FakeAISuggestionRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "app.intelligence.router.EmailService",
        FakeEmailService,
    )

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=suggestion_id,
        new_reservation_id=reservation_id,
        new_reservation_table_ids=[
            table_id,
        ],
        new_reservation_primary_table_id=table_id,
        moves=[],
    )

    current_user = SimpleNamespace(
        id=user_id,
    )

    await apply_reoptimization(
        payload=payload,
        current_user=current_user,
        session=session,
    )

    assert lifecycle_events == [
        "apply",
        "commit",
        "email",
    ]

@pytest.mark.asyncio
async def test_ordinary_confirmed_reoptimization_does_not_send_confirmation(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    table_id = uuid4()
    user_id = uuid4()

    reservation_time = datetime(
        2026,
        9,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        subscription_status="active",
        timezone="UTC",
        preferred_language="en",
        name="Alias Test Restaurant",
    )

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=reservation_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "plan": {
                "kind": "ordinary_reoptimization",
            },
        },
    )

    lifecycle_events = []

    class FakeRestaurantRepository:
        def __init__(self, session):
            pass

        async def list_by_owner(self, owner_id):
            return [restaurant]

        async def get_by_id(self, requested_restaurant_id):
            return restaurant

    class FakeReservationRepository:
        def __init__(self, session):
            pass

        async def get_by_id_for_restaurants(
            self,
            *,
            reservation_id,
            restaurant_ids,
        ):
            return reservation

    class FakeAISuggestionRepository:
        def __init__(self, session):
            pass

        async def get_by_id(
            self,
            *,
            suggestion_id,
            restaurant_ids=None,
        ):
            return suggestion

    class FakeOrchestrator:
        def __init__(self, *, intelligence_service):
            pass

        async def apply_reoptimization(self, **kwargs):
            lifecycle_events.append("apply")
            return SimpleNamespace()

    class FakeEmailService:
        async def send_reservation_confirmation(
            self,
            **kwargs,
        ):
            lifecycle_events.append("email")

    session = SimpleNamespace()

    async def commit():
        lifecycle_events.append("commit")

    session.commit = commit

    monkeypatch.setattr(
        "app.intelligence.router.RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.AISuggestionRepository",
        FakeAISuggestionRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "app.intelligence.router.EmailService",
        FakeEmailService,
    )

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=suggestion_id,
        new_reservation_id=reservation_id,
        new_reservation_table_ids=[table_id],
        new_reservation_primary_table_id=table_id,
        moves=[],
    )

    await apply_reoptimization(
        payload=payload,
        current_user=SimpleNamespace(id=user_id),
        session=session,
    )

    assert lifecycle_events == [
        "apply",
        "commit",
    ]


@pytest.mark.asyncio
async def test_legacy_pending_to_confirmed_still_sends_confirmation(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    table_id = uuid4()
    user_id = uuid4()

    reservation_time = datetime(
        2026,
        9,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        subscription_status="active",
        timezone="UTC",
        preferred_language="en",
        name="Alias Test Restaurant",
    )

    pending_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.PENDING,
        party_size=6,
        reservation_time=reservation_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    confirmed_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=reservation_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "plan": {
                "kind": "legacy",
            },
        },
    )

    lifecycle_events = []

    class FakeRestaurantRepository:
        def __init__(self, session):
            pass

        async def list_by_owner(self, owner_id):
            return [restaurant]

        async def get_by_id(self, requested_restaurant_id):
            return restaurant

    class FakeReservationRepository:
        def __init__(self, session):
            self.calls = 0

        async def get_by_id_for_restaurants(
            self,
            *,
            reservation_id,
            restaurant_ids,
        ):
            self.calls += 1
            if self.calls == 1:
                return pending_reservation
            return confirmed_reservation

    class FakeAISuggestionRepository:
        def __init__(self, session):
            pass

        async def get_by_id(
            self,
            *,
            suggestion_id,
            restaurant_ids=None,
        ):
            return suggestion

    class FakeOrchestrator:
        def __init__(self, *, intelligence_service):
            pass

        async def apply_reoptimization(self, **kwargs):
            lifecycle_events.append("apply")
            return SimpleNamespace()

    class FakeEmailService:
        async def send_reservation_confirmation(
            self,
            **kwargs,
        ):
            lifecycle_events.append("email")
            assert kwargs["party_size"] == 6

    session = SimpleNamespace()

    async def commit():
        lifecycle_events.append("commit")

    session.commit = commit

    monkeypatch.setattr(
        "app.intelligence.router.RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.AISuggestionRepository",
        FakeAISuggestionRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "app.intelligence.router.EmailService",
        FakeEmailService,
    )

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=suggestion_id,
        new_reservation_id=reservation_id,
        new_reservation_table_ids=[table_id],
        new_reservation_primary_table_id=table_id,
        moves=[],
    )

    await apply_reoptimization(
        payload=payload,
        current_user=SimpleNamespace(id=user_id),
        session=session,
    )

    assert lifecycle_events == [
        "apply",
        "commit",
        "email",
    ]


@pytest.mark.asyncio
async def test_failed_modification_reoptimization_does_not_commit_or_email(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    table_id = uuid4()
    user_id = uuid4()

    reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        subscription_status="active",
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "requested_modification": {
                "party_size": 10,
                "reservation_time": (
                    "2026-09-28T13:00:00+00:00"
                ),
            },
        },
    )

    lifecycle_events = []

    class FakeRestaurantRepository:
        def __init__(self, session):
            pass

        async def list_by_owner(self, owner_id):
            return [restaurant]

    class FakeReservationRepository:
        def __init__(self, session):
            pass

        async def get_by_id_for_restaurants(
            self,
            *,
            reservation_id,
            restaurant_ids,
        ):
            return reservation

    class FakeAISuggestionRepository:
        def __init__(self, session):
            pass

        async def get_by_id(
            self,
            *,
            suggestion_id,
            restaurant_ids=None,
        ):
            return suggestion

    class FakeOrchestrator:
        def __init__(self, *, intelligence_service):
            pass

        async def apply_reoptimization(self, **kwargs):
            lifecycle_events.append("apply")
            raise ValidationError(
                "Original reservation state has changed"
            )

    class FakeEmailService:
        async def send_reservation_confirmation(
            self,
            **kwargs,
        ):
            lifecycle_events.append("email")

    session = SimpleNamespace()

    async def commit():
        lifecycle_events.append("commit")

    session.commit = commit

    monkeypatch.setattr(
        "app.intelligence.router.RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.AISuggestionRepository",
        FakeAISuggestionRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "app.intelligence.router.EmailService",
        FakeEmailService,
    )

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=suggestion_id,
        new_reservation_id=reservation_id,
        new_reservation_table_ids=[table_id],
        new_reservation_primary_table_id=table_id,
        moves=[],
    )

    with pytest.raises(
        ValidationError,
        match="Original reservation state",
    ):
        await apply_reoptimization(
            payload=payload,
            current_user=SimpleNamespace(id=user_id),
            session=session,
        )

    assert lifecycle_events == [
        "apply",
    ]

@pytest.mark.asyncio
async def test_commit_failure_does_not_send_modification_confirmation(
    monkeypatch,
):
    restaurant_id = uuid4()
    reservation_id = uuid4()
    suggestion_id = uuid4()
    table_id = uuid4()
    user_id = uuid4()

    requested_time = datetime(
        2026,
        9,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    restaurant = SimpleNamespace(
        id=restaurant_id,
        subscription_status="active",
        timezone="UTC",
        preferred_language="en",
        name="Alias Test Restaurant",
    )

    previous_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=6,
        reservation_time=requested_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    confirmed_reservation = SimpleNamespace(
        id=reservation_id,
        restaurant_id=restaurant_id,
        status=ReservationStatus.CONFIRMED,
        party_size=10,
        reservation_time=requested_time,
        customer_email="guest@example.com",
        customer_name="Lifecycle Guest",
    )

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        payload={
            "requested_modification": {
                "party_size": 10,
                "reservation_time": requested_time.isoformat(),
            },
        },
    )

    lifecycle_events = []

    class FakeRestaurantRepository:
        def __init__(self, session):
            pass

        async def list_by_owner(self, owner_id):
            return [restaurant]

        async def get_by_id(self, requested_restaurant_id):
            return restaurant

    class FakeReservationRepository:
        def __init__(self, session):
            self.calls = 0

        async def get_by_id_for_restaurants(
            self,
            *,
            reservation_id,
            restaurant_ids,
        ):
            self.calls += 1
            if self.calls == 1:
                return previous_reservation
            return confirmed_reservation

    class FakeAISuggestionRepository:
        def __init__(self, session):
            pass

        async def get_by_id(
            self,
            *,
            suggestion_id,
            restaurant_ids=None,
        ):
            return suggestion

    class FakeOrchestrator:
        def __init__(self, *, intelligence_service):
            pass

        async def apply_reoptimization(self, **kwargs):
            lifecycle_events.append("apply")
            return SimpleNamespace()

    class FakeEmailService:
        async def send_reservation_confirmation(
            self,
            **kwargs,
        ):
            lifecycle_events.append("email")

    session = SimpleNamespace()

    async def commit():
        lifecycle_events.append("commit")
        raise RuntimeError("database commit failed")

    session.commit = commit

    monkeypatch.setattr(
        "app.intelligence.router.RestaurantRepository",
        FakeRestaurantRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.ReservationRepository",
        FakeReservationRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.AISuggestionRepository",
        FakeAISuggestionRepository,
    )
    monkeypatch.setattr(
        "app.intelligence.router.IntelligenceExecutionOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "app.intelligence.router.EmailService",
        FakeEmailService,
    )

    payload = IntelligenceApplyReoptimizationRequest(
        suggestion_id=suggestion_id,
        new_reservation_id=reservation_id,
        new_reservation_table_ids=[table_id],
        new_reservation_primary_table_id=table_id,
        moves=[],
    )

    with pytest.raises(
        RuntimeError,
        match="database commit failed",
    ):
        await apply_reoptimization(
            payload=payload,
            current_user=SimpleNamespace(id=user_id),
            session=session,
        )

    assert lifecycle_events == [
        "apply",
        "commit",
    ]