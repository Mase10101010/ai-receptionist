"""
Custom application exceptions.

We define domain-specific exceptions so the service layer can raise meaningful
errors that the API layer translates into proper HTTP responses. This keeps
HTTP concerns out of the business logic.
"""


class AppException(Exception):
    """Base class for all application-specific exceptions."""

    status_code: int = 500
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail


class NotFoundError(AppException):
    """Raised when a requested resource doesn't exist."""
    status_code = 404
    detail = "Resource not found"


class ValidationError(AppException):
    """Raised when domain-level validation fails (beyond Pydantic schema checks)."""
    status_code = 422
    detail = "Validation failed"


class ConflictError(AppException):
    """Raised on resource conflicts (e.g. double-booking, capacity exceeded)."""
    status_code = 409
    detail = "Resource conflict"


class AIServiceError(AppException):
    """Raised when the upstream AI service (OpenAI) fails."""
    status_code = 502
    detail = "AI service is currently unavailable"
