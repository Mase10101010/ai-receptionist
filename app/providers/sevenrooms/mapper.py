from datetime import UTC, datetime, timedelta
from typing import Any

from app.providers.contract.errors import ProviderValidationError
from app.providers.contract.guest import GuestProfile
from app.providers.contract.refs import ProviderRef, ProviderType
from app.providers.contract.reservation import Reservation, ReservationStatus


_STATUS_MAP: dict[str, ReservationStatus] = {
    "requested": ReservationStatus.REQUESTED,
    "pending": ReservationStatus.REQUESTED,
    "confirmed": ReservationStatus.CONFIRMED,
    "booked": ReservationStatus.CONFIRMED,
    "seated": ReservationStatus.SEATED,
    "completed": ReservationStatus.COMPLETED,
    "finished": ReservationStatus.COMPLETED,
    "cancelled": ReservationStatus.CANCELLED,
    "canceled": ReservationStatus.CANCELLED,
    "no_show": ReservationStatus.NO_SHOW,
    "noshow": ReservationStatus.NO_SHOW,
    "waitlisted": ReservationStatus.WAITLISTED,
    "waitlist": ReservationStatus.WAITLISTED,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return _ensure_aware(value)

    if isinstance(value, str) and value.strip():
        try:
            normalized = value.replace("Z", "+00:00")
            return _ensure_aware(datetime.fromisoformat(normalized))
        except ValueError as exc:
            raise ProviderValidationError(
                f"Invalid SevenRooms datetime field: {field_name}",
                provider=ProviderType.SEVENROOMS,
            ) from exc

    raise ProviderValidationError(
        f"Missing SevenRooms datetime field: {field_name}",
        provider=ProviderType.SEVENROOMS,
    )


def _require_str(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)

    if isinstance(value, str) and value.strip():
        return value

    raise ProviderValidationError(
        f"Missing SevenRooms required field: {field_name}",
        provider=ProviderType.SEVENROOMS,
    )


def _require_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)

    if isinstance(value, int) and value > 0:
        return value

    raise ProviderValidationError(
        f"Missing or invalid SevenRooms required field: {field_name}",
        provider=ProviderType.SEVENROOMS,
    )


def _map_status(value: Any) -> ReservationStatus:
    if not isinstance(value, str) or not value.strip():
        raise ProviderValidationError(
            "Missing SevenRooms required field: status",
            provider=ProviderType.SEVENROOMS,
        )

    normalized = value.strip().lower()

    try:
        return _STATUS_MAP[normalized]
    except KeyError as exc:
        raise ProviderValidationError(
            f"Unmapped SevenRooms reservation status: {value}",
            provider=ProviderType.SEVENROOMS,
        ) from exc


def to_guest_profile(payload: dict[str, Any]) -> GuestProfile:
    guest = payload.get("guest")

    if not isinstance(guest, dict):
        raise ProviderValidationError(
            "Missing SevenRooms guest object",
            provider=ProviderType.SEVENROOMS,
        )

    full_name = _require_str(guest, "full_name")

    return GuestProfile(
        full_name=full_name,
        phone=guest.get("phone"),
        email=guest.get("email"),
        tags=guest.get("tags") or [],
        notes=guest.get("notes"),
    )


def to_contract_reservation(payload: dict[str, Any]) -> Reservation:
    external_id = _require_str(payload, "id")
    party_size = _require_int(payload, "party_size")
    start = _parse_datetime(payload.get("start"), "start")
    created_at = (
        _parse_datetime(payload.get("created_at"), "created_at")
        if payload.get("created_at")
        else _now()
    )
    updated_at = (
        _parse_datetime(payload.get("updated_at"), "updated_at")
        if payload.get("updated_at")
        else created_at
    )

    duration_minutes = payload.get("duration_minutes")

    return Reservation(
        ref=ProviderRef(
            provider=ProviderType.SEVENROOMS,
            external_id=external_id,
        ),
        alias_id=None,
        status=_map_status(payload.get("status")),
        guest=to_guest_profile(payload),
        party_size=party_size,
        start=start,
        duration=timedelta(minutes=duration_minutes)
        if isinstance(duration_minutes, int) and duration_minutes > 0
        else None,
        area=payload.get("area"),
        special_requests=payload.get("special_requests"),
        tags=payload.get("tags") or [],
        source=ProviderType.SEVENROOMS,
        created_at=created_at,
        updated_at=updated_at,
    )