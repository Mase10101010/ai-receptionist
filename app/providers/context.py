"""Per-venue provider binding and resolved integration configuration.

This module defines the small, framework-agnostic containers the resolver
builds and hands to a provider factory:

* :class:`ProviderContext`      -- the venue binding a provider operates under
                                   (decrypted credentials live here).
* :class:`ProviderDependencies` -- shared runtime dependencies (the async DB
                                   session today; HTTP client, clock, cache
                                   later).
* :class:`IntegrationConfig`    -- the in-memory image of a
                                   ``restaurant_integrations`` row, decoupled
                                   from any ORM model.

These are plain frozen dataclasses (not Pydantic) because they hold runtime
objects such as an ``AsyncSession`` and decrypted secrets that should be
neither validated/coerced nor serialized. No FastAPI, no provider-specific
logic.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .contract.availability import AliasVenueId
from .contract.refs import ProviderType

__all__ = [
    "IntegrationMode",
    "IntegrationStatus",
    "IntegrationConfig",
    "ProviderContext",
    "ProviderDependencies",
]


class IntegrationMode(StrEnum):
    """How a venue manages reservations."""

    STANDALONE = "standalone"  # Alias owns reservations (native provider)
    CONNECT = "connect"        # an external platform owns reservations


class IntegrationStatus(StrEnum):
    """Lifecycle state of a venue's integration configuration."""

    ACTIVE = "active"
    PENDING = "pending"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass(frozen=True, slots=True, repr=False)
class IntegrationConfig:
    """In-memory image of a venue's integration row.

    ``encrypted_credentials`` is carried verbatim as stored; the resolver
    decrypts it into :attr:`ProviderContext.credentials`. ``settings`` holds
    non-secret, provider-specific configuration (e.g. external venue/group
    identifiers) that only the relevant adapter interprets.
    """

    venue_id: AliasVenueId
    provider_type: ProviderType
    mode: IntegrationMode
    status: IntegrationStatus
    timezone: str = "UTC"
    locale: str | None = None
    currency: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    encrypted_credentials: Mapping[str, str] | None = None

    def __repr__(self) -> str:
        creds = "***" if self.encrypted_credentials else None
        return (
            f"IntegrationConfig(venue_id={self.venue_id!r}, "
            f"provider_type={self.provider_type!r}, mode={self.mode!r}, "
            f"status={self.status!r}, timezone={self.timezone!r}, "
            f"encrypted_credentials={creds})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class ProviderContext:
    """The venue binding a provider instance operates under.

    Resolved once per request. ``credentials`` holds *decrypted* secrets and
    must never be logged; ``__repr__`` redacts them. ``settings`` is opaque
    provider-specific configuration the core does not interpret.
    """

    venue_id: AliasVenueId
    provider_type: ProviderType
    timezone: str = "UTC"
    locale: str | None = None
    currency: str | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    credentials: Mapping[str, str] | None = None

    def __repr__(self) -> str:
        creds = "***" if self.credentials else None
        return (
            f"ProviderContext(venue_id={self.venue_id!r}, "
            f"provider_type={self.provider_type!r}, timezone={self.timezone!r}, "
            f"locale={self.locale!r}, currency={self.currency!r}, "
            f"settings_keys={sorted(self.settings)!r}, credentials={creds})"
        )


@dataclass(frozen=True, slots=True)
class ProviderDependencies:
    """Shared runtime dependencies injected into provider factories.

    Holds the request-scoped async DB session today. Future shared infra
    (HTTP client, clock, cache) is added here as providers require it, so the
    factory signature stays stable.
    """

    session: AsyncSession