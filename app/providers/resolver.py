"""Resolve the ReservationProvider for a venue.

The resolver loads a venue's integration configuration through an abstract
:class:`IntegrationConfigStore` (so this layer needs no ORM model or
migration), then asks the registry to build the matching provider.

Resolution rules:
  * No configuration row              -> AliasNativeProvider (the venue is native).
  * Configuration present and ACTIVE  -> the configured provider.
  * Configuration present, not ACTIVE -> raise IntegrationUnavailable.

The last rule is deliberate: a venue in Connect mode has an *external* source
of truth, so silently falling back to the native (Alias DB) provider when its
integration is disabled or unhealthy would risk split-brain and double
bookings. Such venues fail loudly instead.

No FastAPI, no provider-specific logic.
"""

from collections.abc import Mapping
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from .context import (
    IntegrationConfig,
    IntegrationStatus,
    ProviderContext,
    ProviderDependencies,
)
from .contract.availability import AliasVenueId
from .contract.base import ReservationProvider
from .contract.refs import ProviderType
from .registry import ProviderRegistry, default_registry

__all__ = [
    "IntegrationConfigStore",
    "NullIntegrationConfigStore",
    "CredentialDecryptor",
    "IntegrationUnavailable",
    "ProviderResolver",
]


class IntegrationConfigStore(Protocol):
    """Loads a venue's integration configuration.

    The real implementation (backed by the ``restaurant_integrations`` table)
    arrives with the Phase 1 migration. Until then, use
    :class:`NullIntegrationConfigStore`, which keeps every venue native.
    """

    async def get_for_venue(
        self, session: AsyncSession, venue_id: AliasVenueId
    ) -> IntegrationConfig | None: ...


class NullIntegrationConfigStore:
    """A store that reports no integrations -> every venue resolves to native.

    This is the correct default before the integration table exists.
    """

    async def get_for_venue(
        self, session: AsyncSession, venue_id: AliasVenueId
    ) -> IntegrationConfig | None:
        return None


class CredentialDecryptor(Protocol):
    """Decrypts stored credentials into plaintext for use by an adapter."""

    async def decrypt(self, encrypted: Mapping[str, str]) -> Mapping[str, str]: ...


class IntegrationUnavailable(RuntimeError):
    """A venue's configured integration is present but not usable."""

    def __init__(self, venue_id: AliasVenueId, status: IntegrationStatus) -> None:
        super().__init__(
            f"Integration for venue {venue_id!r} is not active "
            f"(status={status.value})"
        )
        self.venue_id = venue_id
        self.status = status


class ProviderResolver:
    """Builds the ReservationProvider bound to a given venue."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        config_store: IntegrationConfigStore | None = None,
        *,
        credential_decryptor: CredentialDecryptor | None = None,
        default_timezone: str = "UTC",
    ) -> None:
        self._registry = registry if registry is not None else default_registry
        self._config_store = (
            config_store
            if config_store is not None
            else NullIntegrationConfigStore()
        )
        self._decryptor = credential_decryptor
        self._default_timezone = default_timezone

    async def resolve(
        self, session: AsyncSession, venue_id: AliasVenueId
    ) -> ReservationProvider:
        config = await self._config_store.get_for_venue(session, venue_id)
        deps = ProviderDependencies(session=session)

        if config is None:
            return self._registry.create(
                ProviderType.ALIAS_NATIVE, self._native_context(venue_id), deps
            )

        if config.status is not IntegrationStatus.ACTIVE:
            raise IntegrationUnavailable(venue_id, config.status)

        context = await self._build_context(config)
        return self._registry.create(config.provider_type, context, deps)

    def _native_context(self, venue_id: AliasVenueId) -> ProviderContext:
        return ProviderContext(
            venue_id=venue_id,
            provider_type=ProviderType.ALIAS_NATIVE,
            timezone=self._default_timezone,
        )

    async def _build_context(self, config: IntegrationConfig) -> ProviderContext:
        credentials: Mapping[str, str] | None = None
        if config.encrypted_credentials is not None:
            if self._decryptor is None:
                raise RuntimeError(
                    f"No credential decryptor configured to decrypt credentials "
                    f"for venue {config.venue_id!r}"
                )
            credentials = await self._decryptor.decrypt(config.encrypted_credentials)
        return ProviderContext(
            venue_id=config.venue_id,
            provider_type=config.provider_type,
            timezone=config.timezone,
            locale=config.locale,
            currency=config.currency,
            settings=config.settings,
            credentials=credentials,
        )