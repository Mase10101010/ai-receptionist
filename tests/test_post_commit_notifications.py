import pytest

from app.services.post_commit_notifications import enqueue, dispatch, discard


class FakeSession:
    def __init__(self):
        self.info = {}


@pytest.mark.asyncio
async def test_notifications_dispatch_only_when_requested():
    session = FakeSession()
    events = []

    async def send_email():
        events.append("email")

    enqueue(session, send_email)
    assert events == []

    await dispatch(session)
    assert events == ["email"]

    await dispatch(session)
    assert events == ["email"]


@pytest.mark.asyncio
async def test_discard_prevents_notification():
    session = FakeSession()
    events = []

    async def send_email():
        events.append("email")

    enqueue(session, send_email)
    discard(session)

    await dispatch(session)
    assert events == []


@pytest.mark.asyncio
async def test_session_commit_dispatches_notification(monkeypatch):
    from app.db.session import AliasAsyncSession
    from sqlalchemy.ext.asyncio import AsyncSession

    events = []

    async def fake_commit(self):
        events.append("commit")

    monkeypatch.setattr(AsyncSession, "commit", fake_commit)

    session = AliasAsyncSession()

    async def send_email():
        events.append("email")

    enqueue(session, send_email)
    await session.commit()

    assert events == ["commit", "email"]
    await session.close()


@pytest.mark.asyncio
async def test_failed_session_commit_does_not_dispatch(monkeypatch):
    from app.db.session import AliasAsyncSession
    from sqlalchemy.ext.asyncio import AsyncSession

    events = []

    async def fake_commit(self):
        events.append("commit")
        raise RuntimeError("database failure")

    monkeypatch.setattr(AsyncSession, "commit", fake_commit)

    session = AliasAsyncSession()

    async def send_email():
        events.append("email")

    enqueue(session, send_email)

    with pytest.raises(RuntimeError, match="database failure"):
        await session.commit()

    assert events == ["commit"]

    await session.rollback()
    await dispatch(session)
    assert events == ["commit"]
    await session.close()
