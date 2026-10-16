from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.intelligence.schemas import (
    IntelligenceOptimizeRequest,
    IntelligenceReoptimizeRequest,
)


@pytest.mark.parametrize(
    "request_class",
    [IntelligenceOptimizeRequest, IntelligenceReoptimizeRequest],
)
@pytest.mark.parametrize(
    ("requested_start", "expected_utc"),
    [
        (
            datetime.fromisoformat("2026-10-26T20:00:00+08:00"),
            datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
        ),
        (
            datetime.fromisoformat("2026-07-15T20:00:00+02:00"),
            datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 10, 26, 12, 0),
            datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_intelligence_requested_start_is_utc(
    request_class,
    requested_start,
    expected_utc,
):
    payload = request_class(
        restaurant_id=uuid4(),
        requested_start=requested_start,
        party_size=2,
    )

    assert payload.requested_start == expected_utc
    assert payload.requested_start.tzinfo == timezone.utc
