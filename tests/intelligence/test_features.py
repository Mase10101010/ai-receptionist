from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.intelligence_events.models import (
    IntelligenceEvent,
    IntelligenceEventSource,
    IntelligenceEventType,
)
from app.intelligence_features.repository import (
    IntelligenceFeatureRepository,
)
from app.intelligence_features.service import (
    IntelligenceFeatureService,
)


def build_event(
    *,
    restaurant_id: uuid.UUID,
    event_type: IntelligenceEventType,
    score: float | None = None,
    moved_reservations_count: int | None = None,
    total_seat_waste: int | None = None,
) -> IntelligenceEvent:
    payload: dict[str, object] = {}

    if score is not None:
        payload["score"] = score

    if moved_reservations_count is not None:
        payload[
            "moved_reservations_count"
        ] = moved_reservations_count

    if total_seat_waste is not None:
        payload[
            "total_seat_waste"
        ] = total_seat_waste

    return IntelligenceEvent(
        restaurant_id=restaurant_id,
        event_type=event_type,
        source=IntelligenceEventSource.MANAGER,
        entity_type="ai_suggestion",
        entity_id=uuid.uuid4(),
        actor_user_id=None,
        payload=payload,
        metadata_json={},
        occurred_at=datetime.now(
            timezone.utc,
        ),
    )


@pytest.mark.asyncio
async def test_feature_repository_compares_accepted_and_dismissed(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()

    db_session.add_all(
        [
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_CREATED
                ),
                score=170.0,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_CREATED
                ),
                score=180.0,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_ACCEPTED
                ),
                score=180.0,
                moved_reservations_count=1,
                total_seat_waste=0,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_ACCEPTED
                ),
                score=160.0,
                moved_reservations_count=1,
                total_seat_waste=2,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_DISMISSED
                ),
                score=140.0,
                moved_reservations_count=3,
                total_seat_waste=4,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_DISMISSED
                ),
                score=150.0,
                moved_reservations_count=2,
                total_seat_waste=2,
            ),
        ]
    )

    await db_session.flush()

    repository = IntelligenceFeatureRepository(
        db_session,
    )

    metrics = await (
        repository
        .get_ai_suggestion_metrics(
            restaurant_id=restaurant_id,
        )
    )

    assert metrics[
        "suggestions_created"
    ] == 2

    assert metrics[
        "suggestions_accepted"
    ] == 2

    assert metrics[
        "suggestions_dismissed"
    ] == 2

    assert metrics[
        "average_created_score"
    ] == pytest.approx(175.0)

    assert metrics[
        "average_accepted_score"
    ] == pytest.approx(170.0)

    assert metrics[
        "average_dismissed_score"
    ] == pytest.approx(145.0)

    assert metrics[
        "average_moves_accepted"
    ] == pytest.approx(1.0)

    assert metrics[
        "average_moves_dismissed"
    ] == pytest.approx(2.5)

    assert metrics[
        "average_seat_waste_accepted"
    ] == pytest.approx(1.0)

    assert metrics[
        "average_seat_waste_dismissed"
    ] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_feature_repository_isolates_restaurants(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()
    other_restaurant_id = uuid.uuid4()

    db_session.add_all(
        [
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_ACCEPTED
                ),
                score=180.0,
                moved_reservations_count=1,
                total_seat_waste=0,
            ),
            build_event(
                restaurant_id=other_restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_ACCEPTED
                ),
                score=50.0,
                moved_reservations_count=5,
                total_seat_waste=10,
            ),
        ]
    )

    await db_session.flush()

    repository = IntelligenceFeatureRepository(
        db_session,
    )

    metrics = await (
        repository
        .get_ai_suggestion_metrics(
            restaurant_id=restaurant_id,
        )
    )

    assert metrics[
        "suggestions_accepted"
    ] == 1

    assert metrics[
        "average_accepted_score"
    ] == pytest.approx(180.0)

    assert metrics[
        "average_moves_accepted"
    ] == pytest.approx(1.0)

    assert metrics[
        "average_seat_waste_accepted"
    ] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_feature_repository_returns_none_for_missing_averages(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()

    repository = IntelligenceFeatureRepository(
        db_session,
    )

    metrics = await (
        repository
        .get_ai_suggestion_metrics(
            restaurant_id=restaurant_id,
        )
    )

    assert metrics[
        "suggestions_created"
    ] == 0

    assert metrics[
        "suggestions_accepted"
    ] == 0

    assert metrics[
        "suggestions_dismissed"
    ] == 0

    assert metrics[
        "average_accepted_score"
    ] is None

    assert metrics[
        "average_dismissed_score"
    ] is None

    assert metrics[
        "average_moves_accepted"
    ] is None

    assert metrics[
        "average_moves_dismissed"
    ] is None

    assert metrics[
        "average_seat_waste_accepted"
    ] is None

    assert metrics[
        "average_seat_waste_dismissed"
    ] is None


@pytest.mark.asyncio
async def test_feature_service_exposes_dismissed_metrics(
    db_session,
) -> None:
    restaurant_id = uuid.uuid4()

    db_session.add_all(
        [
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_CREATED
                ),
                score=170.0,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_ACCEPTED
                ),
                score=180.0,
                moved_reservations_count=1,
                total_seat_waste=0,
            ),
            build_event(
                restaurant_id=restaurant_id,
                event_type=(
                    IntelligenceEventType
                    .AI_SUGGESTION_DISMISSED
                ),
                score=150.0,
                moved_reservations_count=3,
                total_seat_waste=4,
            ),
        ]
    )

    await db_session.flush()

    service = IntelligenceFeatureService(
        repository=(
            IntelligenceFeatureRepository(
                db_session,
            )
        ),
    )

    features = await (
        service
        .get_ai_suggestion_features(
            restaurant_id=restaurant_id,
        )
    )

    assert (
        features.average_moves_accepted
        == pytest.approx(1.0)
    )

    assert (
        features.average_moves_dismissed
        == pytest.approx(3.0)
    )

    assert (
        features.average_seat_waste_accepted
        == pytest.approx(0.0)
    )

    assert (
        features.average_seat_waste_dismissed
        == pytest.approx(4.0)
    )