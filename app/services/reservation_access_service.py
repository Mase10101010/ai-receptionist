"""Secure, reservation-scoped customer access tokens."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.reservation import Reservation
from app.models.reservation_access_token import ReservationAccessToken
from app.services.reservation_access_context import ReservationAccessContext


class ReservationAccessService:
    DEFAULT_TTL = timedelta(days=30)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def issue(
        self,
        reservation_id: uuid.UUID,
        restaurant_id: uuid.UUID,
        ttl: timedelta | None = None,
    ) -> str:
        """Issue a bearer token; return plaintext only to the caller."""
        lifetime = ttl if ttl is not None else self.DEFAULT_TTL
        if lifetime <= timedelta(0):
            raise ValidationError("Token lifetime must be positive")

        result = await self.db.execute(
            select(Reservation.id).where(
                Reservation.id == reservation_id,
                Reservation.restaurant_id == restaurant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ValidationError("Reservation not eligible for access token")

        token = secrets.token_urlsafe(32)
        record = ReservationAccessToken(
            reservation_id=reservation_id,
            restaurant_id=restaurant_id,
            token_hash=self._hash_token(token),
            expires_at=datetime.now(timezone.utc) + lifetime,
        )
        self.db.add(record)
        await self.db.flush()
        return token

    async def resolve(
        self,
        token: str,
        restaurant_id: uuid.UUID,
    ) -> ReservationAccessContext | None:
        """Resolve a valid bearer token into its server-verified reservation scope."""
        if not isinstance(token, str) or not token or len(token) > 512:
            return None

        result = await self.db.execute(
            select(
                ReservationAccessToken.reservation_id,
                ReservationAccessToken.restaurant_id,
            ).where(
                ReservationAccessToken.token_hash == self._hash_token(token),
                ReservationAccessToken.restaurant_id == restaurant_id,
                ReservationAccessToken.revoked_at.is_(None),
                ReservationAccessToken.expires_at > datetime.now(timezone.utc),
            )
        )

        row = result.one_or_none()
        if row is None:
            return None

        return ReservationAccessContext(
            reservation_id=row.reservation_id,
            restaurant_id=row.restaurant_id,
        )

    async def verify(
        self,
        token: str,
        reservation_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> bool:
        """Fail closed unless token matches this exact tenant and booking."""
        if not isinstance(token, str) or not token or len(token) > 512:
            return False

        result = await self.db.execute(
            select(ReservationAccessToken.id).where(
                ReservationAccessToken.token_hash == self._hash_token(token),
                ReservationAccessToken.reservation_id == reservation_id,
                ReservationAccessToken.restaurant_id == restaurant_id,
                ReservationAccessToken.revoked_at.is_(None),
                ReservationAccessToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none() is not None

    async def revoke(
        self,
        token: str,
        reservation_id: uuid.UUID,
        restaurant_id: uuid.UUID,
    ) -> bool:
        """Revoke only a token belonging to the specified reservation."""
        if not isinstance(token, str) or not token or len(token) > 512:
            return False

        result = await self.db.execute(
            update(ReservationAccessToken)
            .where(
                ReservationAccessToken.token_hash == self._hash_token(token),
                ReservationAccessToken.reservation_id == reservation_id,
                ReservationAccessToken.restaurant_id == restaurant_id,
                ReservationAccessToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
            .returning(ReservationAccessToken.id)
        )
        return result.scalar_one_or_none() is not None
