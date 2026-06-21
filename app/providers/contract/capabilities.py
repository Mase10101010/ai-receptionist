"""Provider capability declarations and source-of-truth classification.

A provider advertises what it can do via :class:`ProviderCapabilities` and
where authoritative state lives via :class:`SourceOfTruth`. The orchestration
layer is the *only* component that reads these; it uses them to select
fallbacks so that provider-specific limitations never leak into the Alias
core or the Concierge.

Capabilities default to the most conservative (least-capable) value: a
provider must explicitly opt in to each ability, and the compliance suite
verifies that every declared capability is truthful. See the capability
matrix for the meaning, gated compliance tests, and required fallback of
each flag.

This module must remain free of provider-specific logic, FastAPI, and any
I/O.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "SourceOfTruth",
    "ProviderCapabilities",
]


class SourceOfTruth(StrEnum):
    """Which system owns authoritative reservation and availability state."""

    ALIAS = "alias"
    """Alias DB is authoritative (e.g. AliasNativeProvider)."""

    EXTERNAL = "external"
    """The provider is authoritative; the Alias DB holds a projection/cache."""


class ProviderCapabilities(BaseModel):
    """Truthful, immutable declaration of what a provider supports.

    All flags default to ``False`` (fail-closed): an undeclared capability
    is treated as unavailable and the orchestration layer applies the
    corresponding fallback. Frozen so a provider's advertised capabilities
    cannot drift at runtime.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- Core reservation lifecycle ---
    real_time_availability: bool = False
    create: bool = False
    modify: bool = False
    cancel: bool = False

    # --- Booking semantics ---
    request_to_book: bool = False
    custom_duration: bool = False
    waitlist: bool = False
    deposits: bool = False

    # --- Guest / CRM ---
    guest_recognition: bool = False

    # --- Operational / sync ---
    webhooks: bool = False
    idempotency_keys: bool = False