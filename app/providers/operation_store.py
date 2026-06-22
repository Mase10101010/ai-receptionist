from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import (
    IntegrationOperation,
    OperationStatus,
    OperationType,
    ProviderType as DbProviderType,
)
from app.providers.contract.availability import AliasVenueId
from app.providers.contract.refs import ProviderType


class SqlAlchemyOperationStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> IntegrationOperation | None:
        result = await self.session.execute(
            select(IntegrationOperation).where(
                IntegrationOperation.idempotency_key == idempotency_key
            )
        )
        return result.scalar_one_or_none()

    async def create_operation(
        self,
        *,
        idempotency_key: str,
        restaurant_id: AliasVenueId,
        provider_type: ProviderType,
        operation_type: OperationType,
        request_fingerprint: str | None = None,
    ) -> IntegrationOperation:
        operation = IntegrationOperation(
            idempotency_key=idempotency_key,
            restaurant_id=restaurant_id,
            provider_type=DbProviderType(provider_type.value),
            operation_type=operation_type,
            status=OperationStatus.PENDING,
            request_fingerprint=request_fingerprint,
        )

        self.session.add(operation)
        await self.session.flush()
        await self.session.refresh(operation)

        return operation

    async def mark_succeeded(
        self,
        operation: IntegrationOperation,
        *,
        external_ref: str | None = None,
    ) -> IntegrationOperation:
        operation.status = OperationStatus.SUCCEEDED
        operation.external_ref = external_ref

        await self.session.flush()
        await self.session.refresh(operation)

        return operation

    async def mark_failed(
        self,
        operation: IntegrationOperation,
        *,
        error_detail: str | None = None,
    ) -> IntegrationOperation:
        operation.status = OperationStatus.FAILED
        operation.error_detail = error_detail

        await self.session.flush()
        await self.session.refresh(operation)

        return operation

    async def mark_in_doubt(
        self,
        operation: IntegrationOperation,
        *,
        error_detail: str | None = None,
    ) -> IntegrationOperation:
        operation.status = OperationStatus.IN_DOUBT
        operation.error_detail = error_detail

        await self.session.flush()
        await self.session.refresh(operation)

        return operation