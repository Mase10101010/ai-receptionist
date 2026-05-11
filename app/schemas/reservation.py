"""
Pydantic schemas for reservations.

These define the shape of API requests/responses, separate from the ORM models.
Keeping them separate is a clean-architecture principle: the database layout
shouldn't leak into the API contract, and vice versa.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.reservation import ReservationStatus


class ReservationBase(BaseModel):
    """Fields shared between create/update/response schemas."""
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_phone: str = Field(..., min_length=7, max_length=32)
    customer_email: EmailStr | None = None
    party_size: int = Field(..., ge=1)
    reservation_time: datetime
    special_requests: str | None = Field(None, max_length=2000)

    @field_validator("party_size")
    @classmethod
    def _validate_party_size(cls, v: int) -> int:
        if v > settings.MAX_PARTY_SIZE:
            raise ValueError(
                f"Party size cannot exceed {settings.MAX_PARTY_SIZE}. "
                f"For larger groups, please call the restaurant directly."
            )
        return v


class ReservationCreate(ReservationBase):
    """Payload for creating a new reservation."""
    duration_minutes: int = Field(
        default=settings.RESERVATION_DURATION_MINUTES, ge=30, le=300
    )
    session_id: str | None = None  # Optional: link back to chat session


class ReservationUpdate(BaseModel):
    """Partial update — all fields optional."""
    customer_name: str | None = Field(None, min_length=1, max_length=120)
    customer_phone: str | None = Field(None, min_length=7, max_length=32)
    customer_email: EmailStr | None = None
    party_size: int | None = Field(None, ge=1)
    reservation_time: datetime | None = None
    duration_minutes: int | None = Field(None, ge=30, le=300)
    special_requests: str | None = Field(None, max_length=2000)
    status: ReservationStatus | None = None


class ReservationResponse(ReservationBase):
    """Reservation as returned by the API."""
    # `from_attributes=True` lets Pydantic build this directly from a SQLAlchemy ORM object.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    duration_minutes: int
    status: ReservationStatus
    session_id: str | None
    created_at: datetime
    updated_at: datetime
