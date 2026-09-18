from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)
from app.models.reservation import ReservationStatus
from app.services.ai_suggestion_service import (
    AISuggestionService,
)


NOW = datetime(
    2026,
    9,
    8,
    19,
    0,
    tzinfo=timezone.utc,
)


class FakeSuggestionRepository:
    def __init__(self) -> None:
        self.db = object()
        self.created = []

    async def find_pending_for_reservation(
        self,
        reservation_id,
    ):
        return None

    async def create(
        self,
        suggestion,
    ):
        self.created.append(suggestion)
        return suggestion


class FakeReservationRepository:
    pass


def _reservation():
    return SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        status=ReservationStatus.PENDING,
        customer_name="Temporal Guest",
        customer_phone="+390000000000",
        customer_email="guest@example.com",
        party_size=4,
        reservation_time=NOW,
        duration_minutes=90,
    )


def _plan(
    *,
    temporal_safety,
):
    plan = SimpleNamespace(
        moved_reservations_count=1,
        score=90.0,
        new_reservation_assignment=SimpleNamespace(
            table_numbers=["12"],
        ),
        temporal_autopilot_safety=temporal_safety,
    )

    def model_dump(
        *,
        mode,
        exclude=None,
    ):
        payload = {
            "new_reservation_assignment": {
                "table_ids": [
                    str(uuid4()),
                ],
                "primary_table_id": str(
                    uuid4()
                ),
            },
            "moves": [
                {
                    "reservation_id": str(
                        uuid4()
                    ),
                    "to_table_ids": [
                        str(uuid4()),
                    ],
                    "primary_table_id": str(
                        uuid4()
                    ),
                },
            ],
            "score": 90.0,
            "base_score": 90.0,
            "personalized_score": 90.0,
            "personalization_applied": False,
            "personalization_reasons": [],
            "total_seat_waste": 0,
            "moved_reservations_count": 1,
            "explanation": "Plan.",
            "temporal_autopilot_safety": (
                temporal_safety.model_dump(
                    mode="json"
                )
                if temporal_safety
                is not None
                else None
            ),
        }

        if (
            exclude
            and "temporal_autopilot_safety"
            in exclude
        ):
            payload.pop(
                "temporal_autopilot_safety",
                None,
            )

        return payload

    plan.model_dump = model_dump

    return plan


def _result(
    *,
    plan,
):
    return SimpleNamespace(
        available=True,
        recommended=plan,
        engine_version="aie-reoptimizer-v1",
        mode="read_only",
    )


def _service(
    *,
    result,
):
    repository = FakeSuggestionRepository()

    intelligence_service = SimpleNamespace(
        reoptimize=AsyncMock(
            return_value=result
        )
    )

    service = AISuggestionService(
        repository=repository,
        reservation_repository=(
            FakeReservationRepository()
        ),
        intelligence_service=(
            intelligence_service
        ),
    )

    service._record_ai_suggestion_event = (
        AsyncMock()
    )

    service._refresh_learning_profile = (
        AsyncMock()
    )

    return service, repository


@pytest.mark.asyncio
async def test_temporal_autopilot_safety_is_persisted_top_level():
    temporal_safety = (
        TemporalAutopilotSafetyContext(
            calibration_state=(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
            expected_turn_confidence=(
                ExpectedTurnConfidence.HIGH
            ),
            marginal_capacity_loss_ratio=0.0,
            lost_future_available_slots=0,
        )
    )

    plan = _plan(
        temporal_safety=temporal_safety,
    )

    service, repository = _service(
        result=_result(
            plan=plan,
        )
    )

    await service.analyze_reservation(
        _reservation()
    )

    assert len(repository.created) == 1

    payload = repository.created[0].payload

    assert (
        "temporal_autopilot_safety"
        in payload
    )

    evidence = payload[
        "temporal_autopilot_safety"
    ]

    assert (
        evidence["schema_version"]
        == "temporal_autopilot_safety.v1"
    )

    assert (
        evidence["context"][
            "calibration_state"
        ]
        == "well_calibrated"
    )

    assert (
        evidence["context"][
            "expected_turn_confidence"
        ]
        == "high"
    )


@pytest.mark.asyncio
async def test_temporal_autopilot_safety_is_not_persisted_inside_plan():
    temporal_safety = (
        TemporalAutopilotSafetyContext(
            calibration_state=(
                TemporalCalibrationState
                .WELL_CALIBRATED
            ),
            expected_turn_confidence=(
                ExpectedTurnConfidence.HIGH
            ),
            marginal_capacity_loss_ratio=0.0,
            lost_future_available_slots=0,
        )
    )

    plan = _plan(
        temporal_safety=temporal_safety,
    )

    service, repository = _service(
        result=_result(
            plan=plan,
        )
    )

    await service.analyze_reservation(
        _reservation()
    )

    payload = repository.created[0].payload

    assert (
        "temporal_autopilot_safety"
        not in payload["plan"]
    )


@pytest.mark.asyncio
async def test_missing_temporal_safety_does_not_fabricate_evidence():
    plan = _plan(
        temporal_safety=None,
    )

    service, repository = _service(
        result=_result(
            plan=plan,
        )
    )

    await service.analyze_reservation(
        _reservation()
    )

    payload = repository.created[0].payload

    assert (
        "temporal_autopilot_safety"
        not in payload
    )

    assert (
        "temporal_autopilot_safety"
        not in payload["plan"]
    )