import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from app.models.reservation import Reservation as OrmReservation
from app.models.reservation import ReservationStatus as OrmReservationStatus
from app.schemas.reservation import ReservationCreate, ReservationUpdate

from ..contract.availability import AvailabilityResult, AvailabilitySlot, TimeRange
from ..contract.errors import UnknownProviderError
from ..contract.guest import GuestProfile
from ..contract.refs import ProviderRef, ProviderType
from ..contract.reservation import (
    AliasReservationId,
    CreateReservationRequest,
    Reservation,
    ReservationChanges,
    ReservationStatus,
)


_STATUS_MAP = {
    OrmReservationStatus.PENDING: ReservationStatus.REQUESTED,
    OrmReservationStatus.CONFIRMED: ReservationStatus.CONFIRMED,
    OrmReservationStatus.SEATED: ReservationStatus.SEATED,
    OrmReservationStatus.COMPLETED: ReservationStatus.COMPLETED,
    OrmReservationStatus.CANCELLED: ReservationStatus.CANCELLED,
    OrmReservationStatus.NO_SHOW: ReservationStatus.NO_SHOW,
}


def _ensure_aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_minutes(duration: timedelta) -> int:
    return int(duration.total_seconds() // 60)


def to_contract_status(status: OrmReservationStatus) -> ReservationStatus:
    try:
        return _STATUS_MAP[status]
    except KeyError as exc:
        raise UnknownProviderError(
            f"Unmapped native reservation status: {status!r}",
            provider=ProviderType.ALIAS_NATIVE,
        ) from exc


def to_guest_profile(orm: OrmReservation) -> GuestProfile:
    return GuestProfile(
        full_name=orm.customer_name,
        phone=orm.customer_phone,
        email=orm.customer_email,
        notes=None,
    )


def to_contract_reservation(orm: OrmReservation) -> Reservation:
    reservation_time = _ensure_aware(orm.reservation_time)

    return Reservation(
        ref=ProviderRef(
            provider=ProviderType.ALIAS_NATIVE,
            external_id=str(orm.id),
        ),
        alias_id=AliasReservationId(orm.id),
        status=to_contract_status(orm.status),
        guest=to_guest_profile(orm),
        party_size=orm.party_size,
        start=reservation_time,
        duration=timedelta(minutes=orm.duration_minutes)
        if orm.duration_minutes
        else None,
        area=None,
        special_requests=orm.special_requests,
        tags=[],
        source=ProviderType.ALIAS_NATIVE,
        created_at=reservation_time,
        updated_at=reservation_time,
    )


def to_reservation_create(request: CreateReservationRequest) -> ReservationCreate:
    return ReservationCreate(
        restaurant_id=request.venue_id,
        table_id=None,
        customer_name=request.guest.full_name,
        customer_phone=request.guest.phone or "",
        customer_email=request.guest.email,
        party_size=request.party_size,
        reservation_time=request.start,
        duration_minutes=_to_minutes(request.duration)
        if request.duration
        else 90,
        special_requests=request.special_requests,
        session_id=None,
    )


def to_reservation_update(changes: ReservationChanges) -> ReservationUpdate:
    data: dict = {}

    if changes.start is not None:
        data["reservation_time"] = changes.start
    if changes.party_size is not None:
        data["party_size"] = changes.party_size
    if changes.duration is not None:
        data["duration_minutes"] = _to_minutes(changes.duration)
    if changes.special_requests is not None:
        data["special_requests"] = changes.special_requests

    return ReservationUpdate(**data)


def build_availability_result(
    window: TimeRange,
    requested_available: bool,
    alternatives: Iterable[datetime] | None,
) -> AvailabilityResult:
    slots: list[AvailabilitySlot] = []
    seen: set[datetime] = set()

    def add_slot(value: datetime) -> None:
        when = _ensure_aware(value)
        if window.start <= when <= window.end and when not in seen:
            seen.add(when)
            slots.append(AvailabilitySlot(start=when))

    if requested_available:
        add_slot(window.start)

    for alternative in alternatives or []:
        add_slot(alternative)

    slots.sort(key=lambda slot: slot.start)

    return AvailabilityResult(
        slots=slots,
        queried_at=datetime.now(UTC),
    )