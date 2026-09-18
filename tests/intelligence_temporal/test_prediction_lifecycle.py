from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.reservation_service import ReservationService


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
    def begin_nested(self):
        return FakeNestedTransaction()


def _build_service():
    repository = SimpleNamespace(
        db=FakeSession(),
    )

    return ReservationService(
        repository=repository,
        restaurant_repository=SimpleNamespace(),
        table_repository=SimpleNamespace(),
        email_service=SimpleNamespace(),
        intelligence_service=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_temporal_prediction_uses_savepoint(
    monkeypatch,
):
    service = _build_service()

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
    )

    predict_for_reservation = AsyncMock()

    coordinator = SimpleNamespace(
        predict_for_reservation=(
            predict_for_reservation
        ),
    )

    monkeypatch.setattr(
        "app.services.reservation_service."
        "TemporalTurnPredictionCoordinator",
        lambda: coordinator,
    )

    await service._try_record_temporal_prediction(
        reservation=reservation,
    )

    predict_for_reservation.assert_awaited_once_with(
        session=service.repository.db,
        reservation=reservation,
    )


@pytest.mark.asyncio
async def test_temporal_prediction_failure_does_not_escape(
    monkeypatch,
):
    service = _build_service()

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
    )

    predict_for_reservation = AsyncMock(
        side_effect=RuntimeError(
            "temporal persistence failed"
        )
    )

    coordinator = SimpleNamespace(
        predict_for_reservation=(
            predict_for_reservation
        ),
    )

    monkeypatch.setattr(
        "app.services.reservation_service."
        "TemporalTurnPredictionCoordinator",
        lambda: coordinator,
    )

    # Must not raise: reservation lifecycle remains authoritative.
    await service._try_record_temporal_prediction(
        reservation=reservation,
    )

    predict_for_reservation.assert_awaited_once_with(
        session=service.repository.db,
        reservation=reservation,
    )