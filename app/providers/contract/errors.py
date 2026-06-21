"""Normalized provider error taxonomy.

Every reservation provider adapter must translate its backend failures into
exactly one of these typed exceptions. The Alias core catches only these
types; raw provider/transport exceptions (``httpx``, ``asyncpg``, ...) must
never escape an adapter.

Each error carries:
  * ``code``      -- a stable machine code the Concierge localizes from.
                     Never display ``message`` to a guest.
  * ``retryable`` -- whether the same call may be safely retried.
  * ``provider``  -- which provider raised it (for logs/metrics), if known.
  * ``detail``    -- raw provider payload, for logging only.
  * ``message``   -- developer/log-facing description (English is fine).

This module must remain free of provider-specific logic, FastAPI, and any
I/O. It may import from ``refs`` (a lower contract layer) only.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

from .refs import ProviderType

__all__ = [
    "ProviderErrorCode",
    "ProviderError",
    "ProviderUnavailable",
    "ProviderRateLimited",
    "ProviderAuthError",
    "ProviderValidationError",
    "SlotUnavailable",
    "ProviderNotFound",
    "UnsupportedOperation",
    "UnknownProviderError",
]


class ProviderErrorCode(StrEnum):
    """Stable machine codes for normalized provider failures.

    Values are part of the localization contract with the Concierge and
    must not be renamed once shipped.
    """

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTH = "auth"
    VALIDATION = "validation"
    SLOT_UNAVAILABLE = "slot_unavailable"
    NOT_FOUND = "not_found"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """Base class for every normalized provider failure.

    Subclasses fix ``code`` and a sensible ``default_retryable``; callers
    may override ``retryable`` per instance when the concrete situation
    warrants it (the default is otherwise used).
    """

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.UNKNOWN
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        provider: ProviderType | None = None,
        retryable: bool | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.provider: ProviderType | None = provider
        self.retryable: bool = (
            self.default_retryable if retryable is None else retryable
        )
        self.detail: Mapping[str, Any] | None = detail

    def __str__(self) -> str:
        provider = f" provider={self.provider.value}" if self.provider else ""
        return f"[{self.code.value}{provider} retryable={self.retryable}] {self.message}"


class ProviderUnavailable(ProviderError):
    """Backend unreachable, timed out, returned 5xx, or circuit is open."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.PROVIDER_UNAVAILABLE
    default_retryable: ClassVar[bool] = True


class ProviderRateLimited(ProviderError):
    """The provider throttled the request. Honor ``retry_after`` if present."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.RATE_LIMITED
    default_retryable: ClassVar[bool] = True

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        provider: ProviderType | None = None,
        retryable: bool | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message, provider=provider, retryable=retryable, detail=detail
        )
        self.retry_after: float | None = retry_after
        """Seconds to wait before retrying, if the provider supplied a hint."""


class ProviderAuthError(ProviderError):
    """Credentials are missing, invalid, or expired. Not retryable."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.AUTH
    default_retryable: ClassVar[bool] = False


class ProviderValidationError(ProviderError):
    """The request was rejected as invalid (e.g. party size exceeds the max)."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.VALIDATION
    default_retryable: ClassVar[bool] = False


class SlotUnavailable(ProviderError):
    """The requested slot was taken or is no longer bookable. Re-fetch availability."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.SLOT_UNAVAILABLE
    default_retryable: ClassVar[bool] = False


class ProviderNotFound(ProviderError):
    """The referenced reservation does not exist in the provider's system."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.NOT_FOUND
    default_retryable: ClassVar[bool] = False


class UnsupportedOperation(ProviderError):
    """The provider does not support the requested operation (capability is false)."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.UNSUPPORTED_OPERATION
    default_retryable: ClassVar[bool] = False


class UnknownProviderError(ProviderError):
    """An unclassified failure. Adapters should map to a specific type where possible."""

    code: ClassVar[ProviderErrorCode] = ProviderErrorCode.UNKNOWN
    default_retryable: ClassVar[bool] = False