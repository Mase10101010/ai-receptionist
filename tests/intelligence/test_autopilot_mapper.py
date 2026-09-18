from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.intelligence_execution.autopilot_mapper import (
    AutopilotReoptimizationMapper,
)
from app.models.ai_suggestion import AISuggestionType


def test_autopilot_mapper_builds_exact_apply_request():
    suggestion_id = uuid4()
    restaurant_id = uuid4()
    reservation_id = uuid4()

    table_id_1 = uuid4()
    table_id_2 = uuid4()

    moved_reservation_id = uuid4()
    moved_table_id_1 = uuid4()
    moved_table_id_2 = uuid4()

    suggestion = SimpleNamespace(
        id=suggestion_id,
        restaurant_id=restaurant_id,
        reservation_id=reservation_id,
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        payload={
            "plan": {
                "new_reservation_assignment": {
                    "table_ids": [
                        str(table_id_1),
                        str(table_id_2),
                    ],
                },
                "moves": [
                    {
                        "reservation_id": str(
                            moved_reservation_id
                        ),
                        "to_table_ids": [
                            str(moved_table_id_1),
                            str(moved_table_id_2),
                        ],
                    },
                ],
            },
        },
    )

    result = (
        AutopilotReoptimizationMapper()
        .build_apply_request(
            suggestion=suggestion,
        )
    )

    assert result.suggestion_id == suggestion_id
    assert (
        result.new_reservation_id
        == reservation_id
    )

    assert result.new_reservation_table_ids == [
        table_id_1,
        table_id_2,
    ]

    assert (
        result.new_reservation_primary_table_id
        == table_id_1
    )

    assert len(result.moves) == 1

    move = result.moves[0]

    assert (
        move.reservation_id
        == moved_reservation_id
    )

    assert move.to_table_ids == [
        moved_table_id_1,
        moved_table_id_2,
    ]

    assert (
        move.primary_table_id
        == moved_table_id_1
    )


def test_autopilot_mapper_rejects_missing_assignment():
    suggestion = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        reservation_id=uuid4(),
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        payload={
            "plan": {},
        },
    )

    with pytest.raises(
        ValidationError,
        match="valid table assignment",
    ):
        (
            AutopilotReoptimizationMapper()
            .build_apply_request(
                suggestion=suggestion,
            )
        )


def test_autopilot_mapper_rejects_move_without_destination():
    suggestion = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        reservation_id=uuid4(),
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        payload={
            "plan": {
                "new_reservation_assignment": {
                    "table_ids": [
                        str(uuid4()),
                    ],
                },
                "moves": [
                    {
                        "reservation_id": str(
                            uuid4()
                        ),
                        "to_table_ids": [],
                    },
                ],
            },
        },
    )

    with pytest.raises(
        ValidationError,
        match="without destination tables",
    ):
        (
            AutopilotReoptimizationMapper()
            .build_apply_request(
                suggestion=suggestion,
            )
        )


def test_autopilot_mapper_rejects_missing_reservation():
    suggestion = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        reservation_id=None,
        suggestion_type=AISuggestionType.REOPTIMIZATION,
        payload={},
    )

    with pytest.raises(
        ValidationError,
        match="does not reference a reservation",
    ):
        (
            AutopilotReoptimizationMapper()
            .build_apply_request(
                suggestion=suggestion,
            )
        )