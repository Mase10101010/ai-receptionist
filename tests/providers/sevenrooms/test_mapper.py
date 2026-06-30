from datetime import datetime

import pytest

from app.providers.contract.errors import ProviderValidationError
from app.providers.contract.refs import ProviderType
from app.providers.contract.reservation import ReservationStatus
from app.providers.sevenrooms.mapper import to_contract_reservation


def test_maps_sevenrooms_reservation_payload_to_contract_reservation():
    payload = {
        "id": "sr-res-123",
        "status": "confirmed",
        "party_size": 4,
        "start": "2026-07-01T19:30:00Z",
        "duration_minutes": 90,
        "area": "Main Dining Room",
        "special_requests": "Window table if possible",
        "tags": ["vip"],
        "created_at": "2026-06-30T10:00:00Z",
        "updated_at": "2026-06-30T11:00:00Z",
        "guest": {
            "full_name": "Alessandro Masiero",
            "phone": "+61400000000",
            "email": "ale@example.com",
            "tags": ["returning"],
            "notes": "Prefers quiet table",
        },
    }

    reservation = to_contract_reservation(payload)

    assert reservation.ref.provider == ProviderType.SEVENROOMS
    assert reservation.ref.external_id == "sr-res-123"
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.party_size == 4
    assert reservation.start == datetime.fromisoformat("2026-07-01T19:30:00+00:00")
    assert reservation.duration.total_seconds() == 90 * 60
    assert reservation.area == "Main Dining Room"
    assert reservation.special_requests == "Window table if possible"
    assert reservation.tags == ["vip"]
    assert reservation.guest.full_name == "Alessandro Masiero"
    assert reservation.guest.email == "ale@example.com"


def test_raises_validation_error_when_required_field_is_missing():
    payload = {
        "status": "confirmed",
        "party_size": 2,
        "start": "2026-07-01T19:30:00Z",
        "guest": {
            "full_name": "Test Guest",
        },
    }

    with pytest.raises(ProviderValidationError):
        to_contract_reservation(payload)


def test_raises_validation_error_for_unknown_status():
    payload = {
        "id": "sr-res-123",
        "status": "strange_status",
        "party_size": 2,
        "start": "2026-07-01T19:30:00Z",
        "guest": {
            "full_name": "Test Guest",
        },
    }

    with pytest.raises(ProviderValidationError):
        to_contract_reservation(payload)