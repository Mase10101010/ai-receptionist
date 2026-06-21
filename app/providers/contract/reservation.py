"""Reservation domain DTOs for the provider contract.

Covers the write requests (create / update / cancel), the normalized
``Reservation`` a provider returns, and the normalized ``ReservationStatus``
enum every provider maps its native states onto.

All datetimes are timezone-aware. No provider-specific logic, FastAPI, or
I/O. Depends on ``refs``, ``availability`` and ``guest``.
"""

from datetime import timedelta
from enum import StrEnum
from typing import NewType
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, PositiveInt

from .availability import AliasVenueId, Channel, SlotToken
from .guest import GuestInput, GuestProfile
from .refs import IdempotencyKey, ProviderRef, ProviderType

__all__ = [
    "AliasReservationId",
    "ReservationStatus",
    "ReservationChanges",
    "CreateReservationRequest",
    "UpdateReservationRequest",
    "CancelReservationRequest",
    "Reservation",
]

# Alias-internal reservation identifier. Swap the base type (UUID -> int) to
# match your primary-key type.
AliasReservationId = NewType("AliasReservationId", UUID)


class ReservationStatus(StrEnum):
    """Normalized reservation lifecycle states.

    Every provider maps its native statuses onto these; the core never sees a
    raw provider status string.
    """

    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    WAITLISTED = "waitlisted"


class ReservationChanges(BaseModel):
    """Mutable fields for an update. ``None`` means "leave unchanged".

    To move a reservation to a slot that requires a fresh availability
    binding, set both ``start`` and ``slot_token``.
    """

    model_config = ConfigDict(extra="forbid")

    start: AwareDatetime | None = None
    party_size: PositiveInt | None = None
    duration: timedelta | None = None
    special_requests: str | None = None
    tags: list[str] | None = None
    slot_token: SlotToken | None = None


class CreateReservationRequest(BaseModel):
    """Request to create a reservation through a provider."""

    model_config = ConfigDict(extra="forbid")

    venue_id: AliasVenueId
    guest: GuestInput
    party_size: PositiveInt
    start: AwareDatetime
    # Ignored by providers that do not declare ``custom_duration``.
    duration: timedelta | None = None
    slot_token: SlotToken | None = None
    special_requests: str | None = None
    tags: list[str] = []
    channel: Channel
    client_token: IdempotencyKey


class UpdateReservationRequest(BaseModel):
    """Request to modify an existing reservation."""

    model_config = ConfigDict(extra="forbid")

    ref: ProviderRef
    changes: ReservationChanges
    client_token: IdempotencyKey


class CancelReservationRequest(BaseModel):
    """Request to cancel an existing reservation."""

    model_config = ConfigDict(extra="forbid")

    ref: ProviderRef
    reason: str | None = None
    client_token: IdempotencyKey


class Reservation(BaseModel):
    """Normalized reservation returned by a provider.

    ``alias_id`` is populated once the reservation has been projected into
    the Alias DB; it may be ``None`` immediately after a create against an
    external provider.
    """

    model_config = ConfigDict(extra="forbid")

    ref: ProviderRef
    alias_id: AliasReservationId | None = None
    status: ReservationStatus
    guest: GuestProfile
    party_size: PositiveInt
    start: AwareDatetime
    duration: timedelta | None = None
    area: str | None = None
    special_requests: str | None = None
    tags: list[str] = []
    source: ProviderType
    created_at: AwareDatetime
    updated_at: AwareDatetime