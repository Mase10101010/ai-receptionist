from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.intelligence_temporal.collector import (
    TemporalObservationCollector,
)
from app.models.reservation import ReservationStatus


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.executed_statement = None

    async def execute(self, statement):
        self.executed_statement = statement

        return FakeResult(
            self.rows
        )


def _completed_reservation(
    *,
    restaurant_id,
    table_id=None,
    actual_minutes=80,
    planned_minutes=90,
):
    seated_at = datetime(
        2026,
        9,
        10,
        18,
        5,
    )

    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=restaurant_id,
        table_id=table_id,
        party_size=4,
        reservation_time=datetime(
            2026,
            9,
            10,
            18,
            0,
        ),
        duration_minutes=planned_minutes,
        status=ReservationStatus.COMPLETED,
        seated_at=seated_at,
        completed_at=(
            seated_at
            + timedelta(
                minutes=actual_minutes,
            )
        ),
    )


@pytest.mark.asyncio
async def test_collects_completed_temporal_observations():
    restaurant_id = uuid4()
    table_id = uuid4()
    service_area_id = uuid4()

    reservation = _completed_reservation(
        restaurant_id=restaurant_id,
        table_id=table_id,
        actual_minutes=82,
    )

    session = FakeSession(
        [
            (
                reservation,
                service_area_id,
            ),
        ]
    )

    collector = (
        TemporalObservationCollector()
    )

    result = await collector.collect(
        session=session,
        restaurant_id=restaurant_id,
    )

    assert len(result) == 1

    observation = result[0]

    assert (
        observation.reservation_id
        == reservation.id
    )

    assert (
        observation.restaurant_id
        == restaurant_id
    )

    assert observation.table_id == table_id

    assert (
        observation.service_area_id
        == service_area_id
    )

    assert (
        observation.actual_dining_minutes
        == 82
    )

    assert (
        observation.planned_duration_minutes
        == 90
    )

    assert (
        observation.duration_delta_minutes
        == -8
    )

    assert (
        session.executed_statement
        is not None
    )


@pytest.mark.asyncio
async def test_collects_observation_without_table_context():
    restaurant_id = uuid4()

    reservation = _completed_reservation(
        restaurant_id=restaurant_id,
        table_id=None,
    )

    session = FakeSession(
        [
            (
                reservation,
                None,
            ),
        ]
    )

    result = await (
        TemporalObservationCollector()
        .collect(
            session=session,
            restaurant_id=restaurant_id,
        )
    )

    assert len(result) == 1

    assert result[0].table_id is None

    assert (
        result[0].service_area_id
        is None
    )


@pytest.mark.asyncio
async def test_invalid_lifecycle_row_is_defensively_ignored():
    restaurant_id = uuid4()

    reservation = _completed_reservation(
        restaurant_id=restaurant_id,
    )

    reservation.completed_at = (
        reservation.seated_at
    )

    session = FakeSession(
        [
            (
                reservation,
                uuid4(),
            ),
        ]
    )

    result = await (
        TemporalObservationCollector()
        .collect(
            session=session,
            restaurant_id=restaurant_id,
        )
    )

    assert result == []


@pytest.mark.asyncio
async def test_collector_rejects_invalid_limit():
    collector = (
        TemporalObservationCollector()
    )

    session = FakeSession([])

    with pytest.raises(
        ValueError,
        match="positive",
    ):
        await collector.collect(
            session=session,
            restaurant_id=uuid4(),
            limit=0,
        )

    with pytest.raises(
        ValueError,
        match="cannot exceed",
    ):
        await collector.collect(
            session=session,
            restaurant_id=uuid4(),
            limit=5001,
        )