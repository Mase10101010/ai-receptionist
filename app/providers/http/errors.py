class ProviderHttpError(RuntimeError):
    """Base exception for provider HTTP communication errors."""

class ProviderAuthenticationError(ProviderHttpError):
    """Authentication with the external provider failed."""

class ProviderAuthorizationError(ProviderHttpError):
    """Authenticated but not authorized for the requested resource."""

class ProviderRateLimitError(ProviderHttpError):
    """The external provider rate limit has been exceeded."""

class ProviderUnavailableError(ProviderHttpError):
    """The external provider is temporarily unavailable."""

class ProviderTimeoutError(ProviderHttpError):
    """The external provider did not respond in time."""