from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.intelligence_execution.gate import (
    IntelligenceExecutionGate,
)
from app.models.ai_suggestion import (
    AISuggestionStatus,
    AISuggestionType,
)


RESTAURANT_ID = uuid.uuid4()
RESERVATION_ID = uuid.uuid4()
SUGGESTION_ID = uuid.uuid4()

TABLE_1_ID = uuid.uuid4()
TABLE_2_ID = uuid.uuid4()

MOVED_RESERVATION_ID = uuid.uuid4()
MOVE_TABLE_ID = uuid.uuid4()


class FakeSuggestionRepository:
    def __init__(self, suggestion):
        self.suggestion = suggestion

    async def get_by_id(
        self,
        suggestion_id,
        restaurant_ids=None,
    ):
        if self.suggestion is None:
            return None

        if suggestion_id != self.suggestion.id:
            return None

        if (
            restaurant_ids is not None
            and self.suggestion.restaurant_id
            not in restaurant_ids
        ):
            return None

        return self.suggestion


def build_suggestion(
    *,
    status=AISuggestionStatus.PENDING,
    suggestion_type=(
        AISuggestionType.REOPTIMIZATION
    ),
    reservation_id=RESERVATION_ID,
    expires_at=None,
):
    if expires_at is None:
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(hours=1)
        )

    return SimpleNamespace(
        id=SUGGESTION_ID,
        restaurant_id=RESTAURANT_ID,
        reservation_id=reservation_id,
        suggestion_type=suggestion_type,
        status=status,
        expires_at=expires_at,
        payload={
            "plan": {
                "new_reservation_assignment": {
                    "table_ids": [
                        str(TABLE_1_ID),
                        str(TABLE_2_ID),
                    ],
                },
                "moves": [
                    {
                        "reservation_id": str(
                            MOVED_RESERVATION_ID
                        ),
                        "to_table_ids": [
                            str(MOVE_TABLE_ID),
                        ],
                    },
                ],
            },
        },
    )


def build_gate(
    suggestion,
):
    return IntelligenceExecutionGate(
        repository=FakeSuggestionRepository(
            suggestion,
        ),
    )


async def validate(
    gate,
    *,
    new_reservation_id=RESERVATION_ID,
    new_reservation_table_ids=None,
    new_reservation_primary_table_id=TABLE_1_ID,
    moves=None,
):
    if new_reservation_table_ids is None:
        new_reservation_table_ids = [
            TABLE_1_ID,
            TABLE_2_ID,
        ]

    if moves is None:
        moves = [
            {
                "reservation_id": (
                    MOVED_RESERVATION_ID
                ),
                "to_table_ids": [
                    MOVE_TABLE_ID,
                ],
                "primary_table_id": (
                    MOVE_TABLE_ID
                ),
            },
        ]

    await gate.validate_reoptimization(
        suggestion_id=SUGGESTION_ID,
        allowed_restaurant_ids=[
            RESTAURANT_ID,
        ],
        new_reservation_id=(
            new_reservation_id
        ),
        new_reservation_table_ids=(
            new_reservation_table_ids
        ),
        new_reservation_primary_table_id=(
            new_reservation_primary_table_id
        ),
        moves=moves,
    )


@pytest.mark.asyncio
async def test_valid_reoptimization_is_allowed():
    gate = build_gate(
        build_suggestion(),
    )

    await validate(gate)


@pytest.mark.asyncio
async def test_missing_suggestion_is_rejected():
    gate = build_gate(None)

    with pytest.raises(
        NotFoundError,
    ):
        await validate(gate)


@pytest.mark.asyncio
async def test_non_pending_suggestion_is_rejected():
    gate = build_gate(
        build_suggestion(
            status=(
                AISuggestionStatus.ACCEPTED
            ),
        ),
    )

    with pytest.raises(
        ValidationError,
        match="no longer pending",
    ):
        await validate(gate)


@pytest.mark.asyncio
async def test_expired_suggestion_is_rejected():
    gate = build_gate(
        build_suggestion(
            expires_at=(
                datetime.now(timezone.utc)
                - timedelta(minutes=1)
            ),
        ),
    )

    with pytest.raises(
        ValidationError,
        match="expired",
    ):
        await validate(gate)


@pytest.mark.asyncio
async def test_reservation_mismatch_is_rejected():
    gate = build_gate(
        build_suggestion(),
    )

    with pytest.raises(
        ValidationError,
        match="does not match the reservation",
    ):
        await validate(
            gate,
            new_reservation_id=(
                uuid.uuid4()
            ),
        )


@pytest.mark.asyncio
async def test_table_mismatch_is_rejected():
    gate = build_gate(
        build_suggestion(),
    )

    with pytest.raises(
        ValidationError,
        match="Requested tables",
    ):
        await validate(
            gate,
            new_reservation_table_ids=[
                TABLE_1_ID,
            ],
        )


@pytest.mark.asyncio
async def test_primary_table_mismatch_is_rejected():
    gate = build_gate(
        build_suggestion(),
    )

    with pytest.raises(
        ValidationError,
        match="Primary table",
    ):
        await validate(
            gate,
            new_reservation_primary_table_id=(
                TABLE_2_ID
            ),
        )


@pytest.mark.asyncio
async def test_move_mismatch_is_rejected():
    gate = build_gate(
        build_suggestion(),
    )

    wrong_table_id = uuid.uuid4()

    with pytest.raises(
        ValidationError,
        match="Requested reservation moves",
    ):
        await validate(
            gate,
            moves=[
                {
                    "reservation_id": (
                        MOVED_RESERVATION_ID
                    ),
                    "to_table_ids": [
                        wrong_table_id,
                    ],
                    "primary_table_id": (
                        wrong_table_id
                    ),
                },
            ],
        )


@pytest.mark.asyncio
async def test_move_primary_table_mismatch_is_rejected():
    gate = build_gate(
        build_suggestion(),
    )

    with pytest.raises(
        ValidationError,
        match="Move primary tables",
    ):
        await validate(
            gate,
            moves=[
                {
                    "reservation_id": (
                        MOVED_RESERVATION_ID
                    ),
                    "to_table_ids": [
                        MOVE_TABLE_ID,
                    ],
                    "primary_table_id": (
                        uuid.uuid4()
                    ),
                },
            ],
        )