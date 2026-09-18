from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.intelligence_temporal.learning import (
    TemporalDaypart,
    TemporalSampleState,
)
from app.intelligence_temporal.observations import (
    TemporalTurnObservation,
)
from app.intelligence_temporal.snapshot import (
    TemporalLearningSnapshotService,
)


class FakeCollector:
    def __init__(self, observations):
        self.observations = observations
        self.calls = []

    async def collect(
        self,
        *,
        session,
        restaurant_id,
        completed_since=None,
        limit=1000,
    ):
        self.calls.append(
            {
                "session": session,
                "restaurant_id": restaurant_id,
                "completed_since": completed_since,
                "limit": limit,
            }
        )

        return list(
            self.observations
        )


def _observation(
    *,
    restaurant_id,
    party_size,
    reservation_time,
    actual_minutes,
    service_area_id=None,
):
    seated_at = (
        reservation_time
        + timedelta(minutes=5)
    )

    return TemporalTurnObservation(
        reservation_id=uuid4(),
        restaurant_id=restaurant_id,
        table_id=uuid4(),
        service_area_id=service_area_id,
        party_size=party_size,
        reservation_time=reservation_time,
        seated_at=seated_at,
        completed_at=(
            seated_at
            + timedelta(
                minutes=actual_minutes,
            )
        ),
        planned_duration_minutes=90,
        actual_dining_minutes=actual_minutes,
        duration_delta_minutes=(
            actual_minutes - 90
        ),
    )


@pytest.mark.asyncio
async def test_builds_complete_temporal_learning_snapshot():
    restaurant_id = uuid4()

    indoor_id = uuid4()
    terrace_id = uuid4()

    observations = [
        _observation(
            restaurant_id=restaurant_id,
            party_size=2,
            reservation_time=datetime(
                2026,
                9,
                7,
                12,
                0,
            ),
            actual_minutes=60,
            service_area_id=indoor_id,
        ),
        _observation(
            restaurant_id=restaurant_id,
            party_size=2,
            reservation_time=datetime(
                2026,
                9,
                7,
                13,
                0,
            ),
            actual_minutes=70,
            service_area_id=indoor_id,
        ),
        _observation(
            restaurant_id=restaurant_id,
            party_size=4,
            reservation_time=datetime(
                2026,
                9,
                11,
                19,
                0,
            ),
            actual_minutes=100,
            service_area_id=terrace_id,
        ),
    ]

    collector = FakeCollector(
        observations
    )

    service = (
        TemporalLearningSnapshotService(
            collector=collector,
        )
    )

    snapshot = await service.build(
        session=object(),
        restaurant_id=restaurant_id,
    )

    assert (
        snapshot.restaurant_id
        == restaurant_id
    )

    assert (
        snapshot.generated_from_sample_count
        == 3
    )

    assert (
        snapshot.restaurant_profile
        is not None
    )

    assert (
        snapshot.restaurant_profile
        .sample_count
        == 3
    )

    assert (
        snapshot.restaurant_profile
        .sample_state
        == TemporalSampleState.DEVELOPING
    )

    assert len(
        snapshot.party_size_profiles
    ) == 2

    assert {
        profile.party_size
        for profile
        in snapshot.party_size_profiles
    } == {
        2,
        4,
    }

    assert len(
        snapshot.day_of_week_profiles
    ) == 2

    assert {
        profile.day_of_week
        for profile
        in snapshot.day_of_week_profiles
    } == {
        0,
        4,
    }

    assert len(
        snapshot.daypart_profiles
    ) == 2

    assert {
        profile.daypart
        for profile
        in snapshot.daypart_profiles
    } == {
        TemporalDaypart.LUNCH,
        TemporalDaypart.DINNER,
    }

    assert len(
        snapshot.service_area_profiles
    ) == 2

    assert {
        profile.service_area_id
        for profile
        in snapshot.service_area_profiles
    } == {
        indoor_id,
        terrace_id,
    }


@pytest.mark.asyncio
async def test_empty_collection_builds_empty_snapshot():
    restaurant_id = uuid4()

    service = (
        TemporalLearningSnapshotService(
            collector=FakeCollector([]),
        )
    )

    snapshot = await service.build(
        session=object(),
        restaurant_id=restaurant_id,
    )

    assert (
        snapshot.generated_from_sample_count
        == 0
    )

    assert (
        snapshot.restaurant_profile
        is None
    )

    assert (
        snapshot.party_size_profiles
        == []
    )

    assert (
        snapshot.day_of_week_profiles
        == []
    )

    assert (
        snapshot.daypart_profiles
        == []
    )

    assert (
        snapshot.service_area_profiles
        == []
    )


@pytest.mark.asyncio
async def test_snapshot_forwards_collection_window():
    restaurant_id = uuid4()

    completed_since = datetime(
        2026,
        8,
        1,
        0,
        0,
    )

    collector = FakeCollector([])

    service = (
        TemporalLearningSnapshotService(
            collector=collector,
        )
    )

    session = object()

    await service.build(
        session=session,
        restaurant_id=restaurant_id,
        completed_since=completed_since,
        limit=250,
    )

    assert collector.calls == [
        {
            "session": session,
            "restaurant_id": (
                restaurant_id
            ),
            "completed_since": (
                completed_since
            ),
            "limit": 250,
        }
    ]