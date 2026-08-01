from datetime import datetime

from app.intelligence.interval_engine import intervals_overlap


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 1, hour, minute)


def test_back_to_back_reservations_do_not_overlap() -> None:
    assert not intervals_overlap(
        dt(18),
        dt(19, 30),
        dt(19, 30),
        dt(21),
    )


def test_crossing_intervals_overlap() -> None:
    assert intervals_overlap(
        dt(18),
        dt(19, 30),
        dt(19),
        dt(20),
    )
