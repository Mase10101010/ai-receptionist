from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql import operators

from app.models.reservation import Reservation
from app.repositories.reservation_repository import ReservationRepository


@pytest.mark.asyncio
async def test_find_upcoming_by_customer_uses_utc_aware_cutoff():
    db = MagicMock()
    db.execute = AsyncMock()

    result = MagicMock()
    result.scalars.return_value.unique.return_value.all.return_value = []
    db.execute.return_value = result

    repository = ReservationRepository(db)

    before = datetime.now(timezone.utc)

    reservations = await repository.find_upcoming_by_customer(
        customer_phone="0400000000",
    )

    after = datetime.now(timezone.utc)

    assert reservations == []
    db.execute.assert_awaited_once()

    statement = db.execute.await_args.args[0]

    cutoff_values = []

    for criterion in statement._where_criteria:
        for expression in criterion.get_children():
            if (
                getattr(expression, "operator", None) is operators.ge
                and getattr(expression.left, "name", None)
                == Reservation.reservation_time.key
            ):
                cutoff_values.append(expression.right.value)

        if (
            getattr(criterion, "operator", None) is operators.ge
            and getattr(criterion.left, "name", None)
            == Reservation.reservation_time.key
        ):
            cutoff_values.append(criterion.right.value)

    assert len(cutoff_values) == 1

    cutoff = cutoff_values[0]

    assert isinstance(cutoff, datetime)
    assert cutoff.tzinfo is not None
    assert cutoff.utcoffset() == timedelta(0)
    assert before <= cutoff <= after
