import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.intelligence.sqlalchemy_adapter import (
    reservation_to_intelligence,
    table_to_intelligence,
)
from app.models.reservation import ReservationStatus


def test_table_adapter_maps_alias_table() -> None:
    table = SimpleNamespace(
        id=uuid.uuid4(),
        table_number="12",
        seats=4,
        service_area_id=uuid.uuid4(),
        is_active=True,
    )
    converted = table_to_intelligence(table)
    assert converted.id == str(table.id)
    assert converted.max_capacity == 4
    assert converted.area_id == str(table.service_area_id)


def test_reservation_adapter_builds_end_time() -> None:
    start_at = datetime(2026, 8, 1, 19, 30, tzinfo=timezone.utc)
    reservation = SimpleNamespace(
        id=uuid.uuid4(),
        table_id=uuid.uuid4(),
        reservation_time=start_at,
        duration_minutes=60,
        party_size=2,
        status=ReservationStatus.CONFIRMED,
    )
    converted = reservation_to_intelligence(reservation)
    assert converted is not None
    assert converted.end_at == start_at + timedelta(minutes=60)
    assert converted.status == "confirmed"


def test_unassigned_reservation_does_not_block_table() -> None:
    reservation = SimpleNamespace(
        id=uuid.uuid4(),
        table_id=None,
        reservation_time=datetime.now(timezone.utc),
        duration_minutes=90,
        party_size=2,
        status=ReservationStatus.PENDING,
    )
    assert reservation_to_intelligence(reservation) is None
