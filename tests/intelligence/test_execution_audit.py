from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.intelligence_events.models import (
    IntelligenceEventSource,
    IntelligenceEventType,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()
SUGGESTION_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

TABLE_1_ID = uuid.uuid4()
TABLE_2_ID = uuid.uuid4()
MOVE_RESERVATION_ID = uuid.uuid4()
MOVE_TABLE_ID = uuid.uuid4()


class FakeEventRepository:
    def __init__(self):
        self.created = []

    async def create(
        self,
        event,
    ):
        self.created.append(event)
        return event


@pytest.mark.asyncio
async def test_seating_plan_applied_event_payload():
    from app.intelligence_events.service import (
        IntelligenceEventService,
    )

    repository = FakeEventRepository()

    service = IntelligenceEventService(
        repository=repository,
    )

    result = SimpleNamespace(
        new_reservation_primary_table_id=(
            TABLE_1_ID
        ),
        new_reservation_table_ids=[
            TABLE_1_ID,
            TABLE_2_ID,
        ],
        new_reservation_table_numbers=[
            "1",
            "2",
        ],
        applied_moves=[
            SimpleNamespace(
                reservation_id=(
                    MOVE_RESERVATION_ID
                ),
                primary_table_id=(
                    MOVE_TABLE_ID
                ),
                table_ids=[
                    MOVE_TABLE_ID,
                ],
                table_numbers=[
                    "3",
                ],
            ),
        ],
        mode="assisted_reoptimization",
        applied=True,
    )

    event = await service.record(
        restaurant_id=RESTAURANT_ID,
        event_type=(
            IntelligenceEventType
            .SEATING_PLAN_APPLIED
        ),
        source=(
            IntelligenceEventSource.MANAGER
        ),
        entity_type="reservation",
        entity_id=RESERVATION_ID,
        actor_user_id=USER_ID,
        payload={
            "suggestion_id": str(
                SUGGESTION_ID
            ),
            "new_reservation_primary_table_id": (
                str(
                    result
                    .new_reservation_primary_table_id
                )
            ),
            "new_reservation_table_ids": [
                str(table_id)
                for table_id
                in result
                .new_reservation_table_ids
            ],
            "new_reservation_table_numbers": (
                result
                .new_reservation_table_numbers
            ),
            "moves": [
                {
                    "reservation_id": str(
                        move.reservation_id
                    ),
                    "primary_table_id": str(
                        move.primary_table_id
                    ),
                    "table_ids": [
                        str(table_id)
                        for table_id
                        in move.table_ids
                    ],
                    "table_numbers": (
                        move.table_numbers
                    ),
                }
                for move
                in result.applied_moves
            ],
            "mode": result.mode,
            "applied": result.applied,
        },
    )

    assert len(repository.created) == 1

    assert (
        event.event_type
        == IntelligenceEventType
        .SEATING_PLAN_APPLIED
    )

    assert (
        event.source
        == IntelligenceEventSource.MANAGER
    )

    assert event.restaurant_id == RESTAURANT_ID
    assert event.entity_type == "reservation"
    assert event.entity_id == RESERVATION_ID
    assert event.actor_user_id == USER_ID

    assert (
        event.payload["suggestion_id"]
        == str(SUGGESTION_ID)
    )

    assert (
        event.payload[
            "new_reservation_primary_table_id"
        ]
        == str(TABLE_1_ID)
    )

    assert (
        event.payload[
            "new_reservation_table_ids"
        ]
        == [
            str(TABLE_1_ID),
            str(TABLE_2_ID),
        ]
    )

    assert (
        event.payload[
            "new_reservation_table_numbers"
        ]
        == [
            "1",
            "2",
        ]
    )

    assert (
        event.payload["moves"]
        == [
            {
                "reservation_id": str(
                    MOVE_RESERVATION_ID
                ),
                "primary_table_id": str(
                    MOVE_TABLE_ID
                ),
                "table_ids": [
                    str(MOVE_TABLE_ID),
                ],
                "table_numbers": [
                    "3",
                ],
            },
        ]
    )

    assert (
        event.payload["mode"]
        == "assisted_reoptimization"
    )

    assert event.payload["applied"] is True