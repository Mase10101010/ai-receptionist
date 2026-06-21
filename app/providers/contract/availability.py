"""Availability domain DTOs for the provider contract.

These types describe an availability *question* (:class:`AvailabilityQuery`)
and a provider's *answer* (:class:`AvailabilityResult` /
:class:`AvailabilitySlot`). ``SlotToken`` is an opaque availability binding:
the core carries it from a slot into a create request without ever parsing
it, so provider-specific booking mechanics never leak.

All datetimes are timezone-aware by construction. No provider-specific logic,
FastAPI, or I/O. Depends on ``refs`` only.
"""

from datetime import timedelta
from enum import StrEnum
from typing import NewType, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    PositiveInt,
    model_validator,
)

from .refs import NonEmptyStr

__all__ = [
    "AliasVenueId",
    "Channel",
    "TimeRange",
    "SlotToken",
    "AvailabilitySlot",
    "AvailabilityResult",
    "AvailabilityQuery",
]

# Alias-internal venue identifier, shared by availability and reservation
# requests. Swap the base type (UUID -> int) to match your primary-key type.
AliasVenueId = NewType("AliasVenueId", UUID)


class Channel(StrEnum):
    """Origin of a booking interaction, for routing and analytics."""

    CONCIERGE_VOICE = "concierge_voice"
    CONCIERGE_CHAT = "concierge_chat"
    DASHBOARD = "dashboard"
    PUBLIC_WIDGET = "public_widget"
    API = "api"


class TimeRange(BaseModel):
    """An inclusive window of timezone-aware datetimes (start <= end)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.end < self.start:
            raise ValueError("TimeRange.end must not be before TimeRange.start")
        return self


class SlotToken(BaseModel):
    """Opaque availability binding round-tripped from a slot into a booking.

    The core never parses ``value``; only the originating provider's adapter
    understands it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: NonEmptyStr

    def __str__(self) -> str:
        return self.value


class AvailabilitySlot(BaseModel):
    """A single bookable opening returned by a provider."""

    model_config = ConfigDict(extra="forbid")

    start: AwareDatetime
    duration: timedelta | None = None
    area: str | None = None
    party_size_max: PositiveInt | None = None
    slot_token: SlotToken | None = None
    is_request_only: bool = False


class AvailabilityResult(BaseModel):
    """A provider's answer to an availability query.

    An empty ``slots`` list is a valid business answer ("no availability"),
    distinct from an error.
    """

    model_config = ConfigDict(extra="forbid")

    slots: list[AvailabilitySlot] = []
    queried_at: AwareDatetime


class AvailabilityQuery(BaseModel):
    """A request for live availability at a venue."""

    model_config = ConfigDict(extra="forbid")

    venue_id: AliasVenueId
    party_size: PositiveInt
    window: TimeRange
    seating_preference: str | None = None
    channel: Channel