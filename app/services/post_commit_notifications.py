"""Request-scoped notifications dispatched only after a successful DB commit."""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_QUEUE_KEY = "alias_post_commit_notifications"

Notification = Callable[[], Awaitable[None]]


def enqueue(session: AsyncSession, notification: Notification) -> None:
    """Queue a notification without committing or sending it."""
    session.info.setdefault(_QUEUE_KEY, []).append(notification)


async def dispatch(session: AsyncSession) -> None:
    """Send queued notifications after the transaction has committed."""
    notifications = session.info.pop(_QUEUE_KEY, [])

    for notification in notifications:
        try:
            await notification()
        except Exception:
            logger.exception("Post-commit notification delivery failed")


def discard(session: AsyncSession) -> None:
    """Discard notifications when the transaction fails."""
    session.info.pop(_QUEUE_KEY, None)
