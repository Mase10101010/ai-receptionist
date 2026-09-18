from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.intelligence_events.repository import (
    IntelligenceEventRepository,
)


class FakeScalarResult:
    def all(self):
        return []


class FakeExecuteResult:
    def scalars(self):
        return FakeScalarResult()


class FakeSession:
    def __init__(self):
        self.execute = AsyncMock(
            return_value=FakeExecuteResult(),
        )


@pytest.mark.asyncio
async def test_list_after_cursor_uses_created_at_and_event_id():
    session = FakeSession()
    repository = IntelligenceEventRepository(
        session,
    )

    restaurant_id = uuid.uuid4()
    last_event_id = uuid.uuid4()
    cursor_time = datetime(
        2026,
        9,
        3,
        8,
        0,
        0,
        tzinfo=timezone.utc,
    )

    await repository.list_after_cursor(
        restaurant_id=restaurant_id,
        created_after=cursor_time,
        last_event_id=last_event_id,
        limit=500,
    )

    session.execute.assert_awaited_once()

    statement = session.execute.await_args.args[0]
    sql = str(statement)

    normalized_sql = " ".join(
        sql.lower().split()
    )

    assert "intelligence_events.created_at >" in normalized_sql

    assert (
        "intelligence_events.created_at ="
        in normalized_sql
    )

    assert "intelligence_events.id >" in normalized_sql

    assert " or " in normalized_sql

    assert (
        "order by intelligence_events.created_at asc, "
        "intelligence_events.id asc"
        in normalized_sql
    )


@pytest.mark.asyncio
async def test_list_after_cursor_without_event_id_uses_time_only():
    session = FakeSession()
    repository = IntelligenceEventRepository(
        session,
    )

    cursor_time = datetime(
        2026,
        9,
        3,
        8,
        0,
        0,
        tzinfo=timezone.utc,
    )

    await repository.list_after_cursor(
        restaurant_id=uuid.uuid4(),
        created_after=cursor_time,
        last_event_id=None,
        limit=500,
    )

    session.execute.assert_awaited_once()

    statement = session.execute.await_args.args[0]
    sql = str(statement)

    normalized_sql = " ".join(
        sql.lower().split()
    )

    assert "intelligence_events.created_at >" in normalized_sql

    assert (
        "intelligence_events.created_at ="
        not in normalized_sql
    )

    assert "intelligence_events.id >" not in normalized_sql
