import uuid
from enum import Enum

from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IntegrationMode(str, Enum):
    STANDALONE = "standalone"
    CONNECT = "connect"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    DISABLED = "disabled"
    ERROR = "error"


class ProviderType(str, Enum):
    ALIAS_NATIVE = "alias_native"
    SEVENROOMS = "sevenrooms"
    OPENTABLE = "opentable"
    RESDIARY = "resdiary"
    THEFORK = "thefork"


class OperationType(str, Enum):
    CREATE_RESERVATION = "create_reservation"
    UPDATE_RESERVATION = "update_reservation"
    CANCEL_RESERVATION = "cancel_reservation"


class OperationStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    IN_DOUBT = "in_doubt"


class RestaurantIntegration(Base):
    __tablename__ = "restaurant_integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    provider_type: Mapped[ProviderType] = mapped_column(
        SQLEnum(
            ProviderType,
            name="integration_provider_type",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    mode: Mapped[IntegrationMode] = mapped_column(
        SQLEnum(
            IntegrationMode,
            name="integration_mode",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=IntegrationMode.STANDALONE,
    )

    status: Mapped[IntegrationStatus] = mapped_column(
        SQLEnum(
            IntegrationStatus,
            name="integration_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=IntegrationStatus.PENDING,
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
    )

    locale: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    encrypted_credentials: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    restaurant = relationship("Restaurant")


class IntegrationOperation(Base):
    __tablename__ = "integration_operations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider_type: Mapped[ProviderType] = mapped_column(
        SQLEnum(
            ProviderType,
            name="integration_provider_type",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    operation_type: Mapped[OperationType] = mapped_column(
        SQLEnum(
            OperationType,
            name="integration_operation_type",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    status: Mapped[OperationStatus] = mapped_column(
        SQLEnum(
            OperationStatus,
            name="integration_operation_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=OperationStatus.PENDING,
    )

    external_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    request_fingerprint: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    error_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    restaurant = relationship("Restaurant")

    __table_args__ = (
        Index("ix_integration_operations_restaurant_status", "restaurant_id", "status"),
        Index("ix_integration_operations_provider_status", "provider_type", "status"),
    )