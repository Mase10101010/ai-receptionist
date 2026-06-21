"""Opaque reference and identity value objects for the provider contract.

These types form the stable boundary between the Alias core and any
reservation provider. The core passes them around and persists them, but
never inspects or parses their opaque contents (``ProviderRef.external_id``,
``IdempotencyKey.value``). Provider-specific meaning lives only inside the
relevant adapter.

This module must remain free of provider-specific logic, FastAPI, and any
I/O. It is the lowest layer of the contract: other contract modules may
import from here, never the reverse.
"""

from enum import StrEnum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, StringConstraints

__all__ = [
    "ProviderType",
    "ProviderRef",
    "IdempotencyKey",
    "NonEmptyStr",
]


class ProviderType(StrEnum):
    """Stable identifier for a reservation provider implementation.

    These values are persisted (e.g. ``reservations.source``,
    ``restaurant_integrations.provider_type``) and must never be renamed
    once shipped. Add new providers by appending members only.
    """

    ALIAS_NATIVE = "alias_native"
    SEVENROOMS = "sevenrooms"
    OPENTABLE = "opentable"
    RESDIARY = "resdiary"
    THEFORK = "thefork"


# Reusable constrained string: non-empty, surrounding whitespace stripped.
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class ProviderRef(BaseModel):
    """Opaque external identity of a reservation in a provider's system.

    The Alias core treats ``external_id`` as a black box: store it, pass it
    back to the originating provider, and never parse it. Frozen so it can
    be used as a value object (hashable, immutable); equality is by
    ``(provider, external_id)``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: ProviderType
    external_id: NonEmptyStr

    def __str__(self) -> str:
        return f"{self.provider.value}:{self.external_id}"


class IdempotencyKey(BaseModel):
    """Caller-generated key that makes a write operation safely retryable.

    Minted once by the orchestration layer at the moment a logical write
    intent is formed, persisted before the provider call, and reused
    verbatim on every retry of that same intent. Two distinct intents must
    never share a key; one intent must never use two keys.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: NonEmptyStr

    @classmethod
    def generate(cls) -> Self:
        """Mint a fresh, globally-unique idempotency key."""
        return cls(value=uuid4().hex)

    def __str__(self) -> str:
        return self.value