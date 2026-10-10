"""Security tests for customer reservation access tokens."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.exceptions import ValidationError
from app.models.reservation import Reservation
from app.models.reservation_access_token import ReservationAccessToken
from app.services.reservation_access_service import ReservationAccessService


async def make_reservation(db, restaurant_id):
    reservation = Reservation(
        restaurant_id=restaurant_id,
        customer_name="Test Customer",
        customer_phone="+61000000000",
        customer_email="customer@example.com",
        party_size=2,
        reservation_time=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db.add(reservation)
    await db.flush()
    return reservation


@pytest.mark.asyncio
async def test_token_is_hashed_and_booking_scoped(db_session):
    db = db_session
    service = ReservationAccessService(db)
    restaurant_id = uuid.uuid4()

    # SQLite tests do not enforce foreign keys unless explicitly enabled.
    first = await make_reservation(db, restaurant_id)
    second = await make_reservation(db, restaurant_id)

    token = await service.issue(first.id, restaurant_id)

    stored = (
        await db.execute(select(ReservationAccessToken))
    ).scalar_one()

    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored.token_hash != token
    assert await service.verify(token, first.id, restaurant_id)
    assert not await service.verify(token, second.id, restaurant_id)
    assert not await service.verify(token, first.id, uuid.uuid4())
    assert not await service.verify("invalid-token", first.id, restaurant_id)
    assert not await service.verify("", first.id, restaurant_id)


@pytest.mark.asyncio
async def test_expired_token_is_rejected(db_session):
    db = db_session
    service = ReservationAccessService(db)
    restaurant_id = uuid.uuid4()
    reservation = await make_reservation(db, restaurant_id)

    token = await service.issue(reservation.id, restaurant_id)

    await db.execute(
        update(ReservationAccessToken)
        .where(ReservationAccessToken.reservation_id == reservation.id)
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    assert not await service.verify(token, reservation.id, restaurant_id)


@pytest.mark.asyncio
async def test_revocation_blocks_access(db_session):
    db = db_session
    service = ReservationAccessService(db)
    restaurant_id = uuid.uuid4()
    reservation = await make_reservation(db, restaurant_id)

    token = await service.issue(reservation.id, restaurant_id)

    assert await service.revoke(token, reservation.id, restaurant_id)
    assert not await service.verify(token, reservation.id, restaurant_id)
    assert not await service.revoke(token, reservation.id, restaurant_id)


@pytest.mark.asyncio
async def test_invalid_lifetime_and_wrong_restaurant(db_session):
    db = db_session
    service = ReservationAccessService(db)
    restaurant_id = uuid.uuid4()
    reservation = await make_reservation(db, restaurant_id)

    with pytest.raises(ValidationError):
        await service.issue(
            reservation.id,
            restaurant_id,
            ttl=timedelta(seconds=0),
        )

    with pytest.raises(ValidationError):
        await service.issue(reservation.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_token_cannot_access_another_restaurant_booking(db_session):
    db = db_session
    service = ReservationAccessService(db)

    restaurant_a = uuid.uuid4()
    restaurant_b = uuid.uuid4()

    booking_a = await make_reservation(db, restaurant_a)
    booking_b = await make_reservation(db, restaurant_b)

    token_a = await service.issue(booking_a.id, restaurant_a)

    assert await service.verify(token_a, booking_a.id, restaurant_a)
    assert not await service.verify(token_a, booking_b.id, restaurant_b)
    assert not await service.verify(token_a, booking_a.id, restaurant_b)
    assert not await service.verify(token_a, booking_b.id, restaurant_a)
    assert not await service.revoke(token_a, booking_b.id, restaurant_b)

    # A failed cross-restaurant revocation must not invalidate the real token.
    assert await service.verify(token_a, booking_a.id, restaurant_a)
