"""The ReservationProvider contract.

Defines the async Protocol every reservation provider implements and the
small ``ProviderHealth`` DTO returned by ``health_check``. The Alias core and
Concierge depend only on this Protocol and the contract DTOs -- never on a
concrete provider.

No provider-specific logic, FastAPI, or I/O.
"""

from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict

from .availability import AvailabilityQuery, AvailabilityResult
from .capabilities import ProviderCapabilities, SourceOfTruth
from .refs import ProviderRef, ProviderType
from .reservation import (
    CancelReservationRequest,
    CreateReservationRequest,
    Reservation,
    UpdateReservationRequest,
)

__all__ = [
    "ProviderHealth",
    "ReservationProvider",
]


class ProviderHealth(BaseModel):
    """Result of a provider connectivity / credential check."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderType
    healthy: bool
    checked_at: AwareDatetime
    detail: str | None = None


@runtime_checkable
class ReservationProvider(Protocol):
    """Async contract every reservation provider must satisfy.

    Implementations are resolved already bound to a venue context. They
    declare their abilities via ``capabilities`` and where authoritative state
    lives via ``source_of_truth``; the orchestration layer reads these to
    select fallbacks. All failures are raised as the typed exceptions defined
    in ``contract.errors`` -- raw transport/provider exceptions must never
    escape an implementation.
    """

    capabilities: ProviderCapabilities
    source_of_truth: SourceOfTruth

    async def get_availability(
        self, query: AvailabilityQuery
    ) -> AvailabilityResult: ...

    async def create_reservation(
        self, request: CreateReservationRequest
    ) -> Reservation: ...

    async def update_reservation(
        self, request: UpdateReservationRequest
    ) -> Reservation: ...

    async def cancel_reservation(
        self, request: CancelReservationRequest
    ) -> Reservation: ...

    async def get_reservation(self, ref: ProviderRef) -> Reservation | None: ...

    async def health_check(self) -> ProviderHealth: ...

    # --- Reserved for later phases (declared as intent, do not implement) ---
    # async def find_guest(self, query: GuestQuery) -> GuestProfile | None: ...
    # async def list_reservations(
    #     self, query: ReservationQuery
    # ) -> list[Reservation]: ...