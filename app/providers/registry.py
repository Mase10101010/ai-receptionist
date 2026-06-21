"""Provider registry: maps a ProviderType to a factory that builds it.

Providers register themselves into a registry (typically the module-level
``default_registry``) so the resolver can construct them by type without
importing concrete provider classes. This keeps the resolver and the contract
free of any dependency on specific adapters.

Only ``AliasNativeProvider`` is expected to be registered for now; future
adapters (SevenRooms, OpenTable, ...) register the same way. Registration is a
side effect of importing the provider's module, so the application must ensure
that module is imported during startup. No FastAPI, no provider-specific
logic.
"""

from collections.abc import Callable

from .context import ProviderContext, ProviderDependencies
from .contract.base import ReservationProvider
from .contract.refs import ProviderType

__all__ = [
    "ProviderFactory",
    "ProviderNotRegistered",
    "ProviderRegistry",
    "default_registry",
]

type ProviderFactory = Callable[
    [ProviderContext, ProviderDependencies], ReservationProvider
]


class ProviderNotRegistered(LookupError):
    """Raised when no factory is registered for a requested ProviderType."""

    def __init__(self, provider_type: ProviderType) -> None:
        super().__init__(f"No provider registered for {provider_type!r}")
        self.provider_type = provider_type


class ProviderRegistry:
    """A mutable mapping of ProviderType -> factory.

    Registration typically happens at import time via :meth:`register` or the
    :meth:`provider` decorator. Duplicate registration raises unless
    ``override=True`` is passed, to surface accidental double-registration.
    """

    def __init__(self) -> None:
        self._factories: dict[ProviderType, ProviderFactory] = {}

    def register(
        self,
        provider_type: ProviderType,
        factory: ProviderFactory,
        *,
        override: bool = False,
    ) -> None:
        if not override and provider_type in self._factories:
            raise ValueError(f"Provider {provider_type!r} is already registered")
        self._factories[provider_type] = factory

    def provider(
        self, provider_type: ProviderType, *, override: bool = False
    ) -> Callable[[ProviderFactory], ProviderFactory]:
        """Decorator form of :meth:`register`."""

        def decorator(factory: ProviderFactory) -> ProviderFactory:
            self.register(provider_type, factory, override=override)
            return factory

        return decorator

    def is_registered(self, provider_type: ProviderType) -> bool:
        return provider_type in self._factories

    def registered_types(self) -> frozenset[ProviderType]:
        return frozenset(self._factories)

    def create(
        self,
        provider_type: ProviderType,
        context: ProviderContext,
        deps: ProviderDependencies,
    ) -> ReservationProvider:
        try:
            factory = self._factories[provider_type]
        except KeyError:
            raise ProviderNotRegistered(provider_type) from None
        return factory(context, deps)


# Application-wide default. Provider modules register into this at import time.
default_registry = ProviderRegistry()