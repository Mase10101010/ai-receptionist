"""Guest domain DTOs that flow through the provider contract.

``GuestInput`` is the write-side payload the Concierge collects when making a
booking. ``GuestProfile`` is the read-side representation a provider returns;
its recognition fields (visit history, returning-guest signals) are populated
only by providers that declare ``guest_recognition`` and are ``None``
otherwise.

No provider-specific logic, FastAPI, or I/O. Depends on ``refs`` only.
"""

from typing import NewType
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from .refs import NonEmptyStr

__all__ = [
    "AliasGuestId",
    "GuestInput",
    "GuestProfile",
]

# Alias-internal guest identifier. Swap the base type (UUID -> int) to match
# your actual primary-key type if it differs.
AliasGuestId = NewType("AliasGuestId", UUID)


class GuestInput(BaseModel):
    """Guest details supplied when creating or updating a reservation."""

    model_config = ConfigDict(extra="forbid")

    full_name: NonEmptyStr
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class GuestProfile(BaseModel):
    """Normalized guest representation returned by a provider.

    Recognition fields are ``None`` unless the provider declares
    ``guest_recognition`` and resolved a matching profile.
    """

    model_config = ConfigDict(extra="forbid")

    alias_guest_id: AliasGuestId | None = None
    full_name: NonEmptyStr
    phone: str | None = None
    email: str | None = None
    tags: list[str] = []
    notes: str | None = None

    # --- Recognition data (populated only when guest_recognition is true) ---
    is_returning: bool | None = None
    visit_count: int | None = None
    last_visit: AwareDatetime | None = None