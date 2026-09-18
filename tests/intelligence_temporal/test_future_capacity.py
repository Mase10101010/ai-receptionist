from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence.schemas import (
    IntelligenceAssignmentResponse,
    IntelligenceOptimizeResponse,
)
from app.intelligence_temporal.schemas import (
    FutureCapacityRequest,
)
from app.intelligence_temporal.service import (
    TemporalCapacityService,
)


RESTAURANT_ID = uuid4()
TABLE_ID = uuid4()


def _available_result(
    *,
    start_at: datetime,
) -> IntelligenceOptimizeResponse:
    return IntelligenceOptimizeResponse(
        available=True,
        recommended=IntelligenceAssignmentResponse(
            table_ids=[TABLE_ID],
            table_numbers=["12"],
            start_at=start_at,
            end_at=start_at,
            capacity=4,
            score=10.0,
            seat_waste=2,
            fragmentation_minutes=0,
            explanation="Direct assignment available.",
        ),
        alternatives=[],
        rejected_candidates=0,
    )


def _unavailable_result() -> IntelligenceOptimizeResponse:
    return IntelligenceOptimizeResponse(
        available=False,
        recommended=None,
        alternatives=[],
        rejected_candidates=1,
    )


@pytest.mark.asyncio
async def test_profile_builds_deterministic_slots_from_optimizer():
    start_at = datetime(
        2026,
        9,
        10,
        18,
        0,
        tzinfo=timezone.utc,
    )

    optimization_service = SimpleNamespace(
        optimize=AsyncMock(
            side_effect=[
                _available_result(
                    start_at=start_at,
                ),
                _unavailable_result(),
                _available_result(
                    start_at=start_at,
                ),
                _available_result(
                    start_at=start_at,
                ),
            ]
        )
    )

    service = TemporalCapacityService(
        optimization_service=optimization_service,
    )

    result = await service.profile(
        session=SimpleNamespace(),
        request=FutureCapacityRequest(
            restaurant_id=RESTAURANT_ID,
            start_at=start_at,
            party_size=2,
            duration_minutes=90,
            horizon_minutes=90,
            slot_minutes=30,
        ),
    )

    assert len(result.slots) == 4

    assert result.slots[0].start_at == start_at
    assert result.slots[0].directly_available is True
    assert result.slots[0].table_ids == [TABLE_ID]
    assert result.slots[0].assignment_capacity == 4
    assert result.slots[0].seat_waste == 2

    assert result.slots[1].start_at == start_at.replace(
        minute=30,
    )
    assert result.slots[1].directly_available is False
    assert result.slots[1].table_ids == []
    assert result.slots[1].assignment_capacity is None

    assert result.slots[2].start_at == start_at.replace(
        hour=19,
    )
    assert result.slots[3].start_at == start_at.replace(
        hour=19,
        minute=30,
    )

    assert optimization_service.optimize.await_count == 4

    for call in optimization_service.optimize.await_args_list:
        payload = call.kwargs["payload"]

        assert payload.restaurant_id == RESTAURANT_ID
        assert payload.party_size == 2
        assert payload.duration_minutes == 90
        assert payload.max_alternatives == 1


@pytest.mark.asyncio
async def test_profile_never_uses_reoptimization():
    start_at = datetime(
        2026,
        9,
        10,
        18,
        0,
        tzinfo=timezone.utc,
    )

    optimization_service = SimpleNamespace(
        optimize=AsyncMock(
            return_value=_unavailable_result(),
        ),
        reoptimize=AsyncMock(),
    )

    service = TemporalCapacityService(
        optimization_service=optimization_service,
    )

    result = await service.profile(
        session=SimpleNamespace(),
        request=FutureCapacityRequest(
            restaurant_id=RESTAURANT_ID,
            start_at=start_at,
            party_size=4,
            duration_minutes=90,
            horizon_minutes=60,
            slot_minutes=30,
        ),
    )

    assert len(result.slots) == 3
    assert all(
        slot.directly_available is False
        for slot in result.slots
    )

    optimization_service.reoptimize.assert_not_awaited()

@pytest.mark.asyncio
async def test_profile_summarizes_future_direct_capacity():
    start_at = datetime(
        2026,
        9,
        10,
        18,
        0,
        tzinfo=timezone.utc,
    )

    optimization_service = SimpleNamespace(
        optimize=AsyncMock(
            side_effect=[
                _unavailable_result(),
                _available_result(
                    start_at=start_at,
                ),
                _available_result(
                    start_at=start_at,
                ),
                _unavailable_result(),
                _available_result(
                    start_at=start_at,
                ),
            ]
        )
    )

    service = TemporalCapacityService(
        optimization_service=optimization_service,
    )

    result = await service.profile(
        session=SimpleNamespace(),
        request=FutureCapacityRequest(
            restaurant_id=RESTAURANT_ID,
            start_at=start_at,
            party_size=2,
            duration_minutes=90,
            horizon_minutes=120,
            slot_minutes=30,
        ),
    )

    assert result.summary.total_slots == 5
    assert (
        result.summary.directly_available_slots
        == 3
    )
    assert result.summary.unavailable_slots == 2
    assert result.summary.availability_ratio == 0.6

    assert (
        result.summary.first_directly_available_at
        == start_at.replace(minute=30)
    )

    assert (
        result.summary.longest_directly_available_run
        == 2
    )