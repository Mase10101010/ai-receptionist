from datetime import datetime, timedelta, timezone

import pytest

from app.providers.contract.errors import ProviderValidationError
from app.providers.thefork.mapper import _parse_datetime as parse_thefork
from app.providers.sevenrooms.mapper import _parse_datetime as parse_sevenrooms


@pytest.mark.parametrize("parser", [parse_thefork, parse_sevenrooms])
def test_accepts_explicit_utc_timestamp(parser):
    result = parser("2026-07-01T19:30:00Z", "start")

    assert result == datetime(2026, 7, 1, 19, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("parser", [parse_thefork, parse_sevenrooms])
def test_preserves_explicit_timezone_offset(parser):
    result = parser("2026-07-01T19:30:00+08:00", "start")

    assert result.utcoffset() == timedelta(hours=8)
    assert result.astimezone(timezone.utc) == datetime(
        2026, 7, 1, 11, 30, tzinfo=timezone.utc
    )


@pytest.mark.parametrize("parser", [parse_thefork, parse_sevenrooms])
@pytest.mark.parametrize(
    "value",
    [
        "2026-07-01T19:30:00",
        datetime(2026, 7, 1, 19, 30),
    ],
)
def test_rejects_datetime_without_timezone(parser, value):
    with pytest.raises(ProviderValidationError):
        parser(value, "start")
