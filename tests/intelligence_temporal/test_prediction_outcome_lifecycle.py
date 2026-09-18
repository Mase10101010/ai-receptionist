from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.reservation import ReservationStatus
from app.services.reservation_service import (
    ReservationService,
)


class FakeNestedTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSession:
    def __init__(self):
        self.begin_nested_calls = 0

    def begin_nested(self):
        self.begin_nested_calls += 1
        return FakeNestedTransaction()


def _build_service():
    repository = SimpleNamespace(
        db=FakeSession(),
    )

    service = ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )

    return service, repository


@pytest.mark.asyncio
async def test_completed_reservation_records_temporal_outcome(
    monkeypatch,
):
    service, repository = _build_service()

    coordinator_call = AsyncMock()

    class FakeCoordinator:
        async def record_for_completed_reservation(
            self,
            *,
            session,
            reservation,
        ):
            await coordinator_call(
                session=session,
                reservation=reservation,
            )

    monkeypatch.setattr(
        "app.services.reservation_service."
        "TemporalPredictionOutcomeCoordinator",
        FakeCoordinator,
    )

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        status=ReservationStatus.COMPLETED,
        seated_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            9,
            6,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    )

    await service._try_record_temporal_outcome(
        reservation=reservation,
    )

    assert repository.db.begin_nested_calls == 1

    coordinator_call.assert_awaited_once_with(
        session=repository.db,
        reservation=reservation,
    )


@pytest.mark.asyncio
async def test_non_completed_reservation_records_no_outcome(
    monkeypatch,
):
    service, repository = _build_service()

    coordinator_call = AsyncMock()

    class FakeCoordinator:
        async def record_for_completed_reservation(
            self,
            *,
            session,
            reservation,
        ):
            await coordinator_call(
                session=session,
                reservation=reservation,
            )

    monkeypatch.setattr(
        "app.services.reservation_service."
        "TemporalPredictionOutcomeCoordinator",
        FakeCoordinator,
    )

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        status=ReservationStatus.SEATED,
        seated_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=None,
    )

    await service._try_record_temporal_outcome(
        reservation=reservation,
    )

    assert repository.db.begin_nested_calls == 0
    coordinator_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_temporal_outcome_failure_is_isolated(
    monkeypatch,
):
    service, repository = _build_service()

    class FakeCoordinator:
        async def record_for_completed_reservation(
            self,
            *,
            session,
            reservation,
        ):
            raise RuntimeError(
                "temporal persistence failed"
            )

    monkeypatch.setattr(
        "app.services.reservation_service."
        "TemporalPredictionOutcomeCoordinator",
        FakeCoordinator,
    )

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        status=ReservationStatus.COMPLETED,
        seated_at=datetime(
            2026,
            9,
            6,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            9,
            6,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    )

    await service._try_record_temporal_outcome(
        reservation=reservation,
    )

    assert repository.db.begin_nested_calls == 1