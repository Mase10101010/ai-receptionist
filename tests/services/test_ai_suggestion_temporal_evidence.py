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

@pytest.mark.asyncio
async def test_modification_reoptimization_uses_requested_state_without_mutating_reservation():
    original_table_id = uuid4()
    target_table_id = uuid4()

    reservation = SimpleNamespace(
        id=uuid4(),
        restaurant_id=uuid4(),
        status=ReservationStatus.CONFIRMED,
        customer_name="Modification Guest",
        customer_phone="+390000000001",
        customer_email="modification@example.com",
        party_size=6,
        reservation_time=NOW,
        duration_minutes=90,
        table_id=original_table_id,
        assigned_table_ids=[original_table_id],
    )

    requested_time = datetime(
        2026,
        9,
        8,
        20,
        0,
        tzinfo=timezone.utc,
    )

    assignment = SimpleNamespace(
        table_ids=[target_table_id],
        table_numbers=["20"],
    )

    plan = SimpleNamespace(
        moved_reservations_count=1,
        score=95.0,
        new_reservation_assignment=assignment,
        temporal_autopilot_safety=None,
    )

    def model_dump(
        *,
        mode,
        exclude=None,
    ):
        payload = {
            "new_reservation_assignment": {
                "table_ids": [
                    str(target_table_id),
                ],
                "primary_table_id": str(
                    target_table_id
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
            "score": 95.0,
            "moved_reservations_count": 1,
            "temporal_autopilot_safety": None,
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

    service, repository = _service(
        result=_result(
            plan=plan,
        )
    )

    service.expire_for_reservation = AsyncMock(
        return_value=1,
    )

    suggestion = (
        await service
        .analyze_reservation_modification(
            reservation,
            requested_party_size=10,
            requested_reservation_time=(
                requested_time
            ),
        )
    )

    assert suggestion is not None
    assert len(repository.created) == 1

    reoptimize_call = (
        service.intelligence_service
        .reoptimize.await_args
    )

    request = reoptimize_call.kwargs[
        "payload"
    ]

    assert request.reservation_id == reservation.id
    assert request.party_size == 10
    assert request.requested_start == requested_time
    assert request.duration_minutes == 90

    payload = suggestion.payload

    assert payload["reservation"]["id"] == str(
        reservation.id
    )
    assert payload["reservation"]["party_size"] == 6
    assert (
        payload["reservation"]["reservation_time"]
        == NOW.isoformat()
    )
    assert (
        payload["reservation"]["status"]
        == ReservationStatus.CONFIRMED.value
    )
    assert (
        payload["reservation"]["primary_table_id"]
        == str(original_table_id)
    )
    assert payload["reservation"]["table_ids"] == [
        str(original_table_id)
    ]

    assert (
        payload["requested_modification"][
            "party_size"
        ]
        == 10
    )
    assert (
        payload["requested_modification"][
            "reservation_time"
        ]
        == requested_time.isoformat()
    )

    assert (
        payload["plan"][
            "new_reservation_assignment"
        ]["table_ids"]
        == [str(target_table_id)]
    )

    service.expire_for_reservation.assert_awaited_once_with(
        reservation.id
    )

    # Proposal creation must never mutate the live reservation.
    assert reservation.party_size == 6
    assert reservation.reservation_time == NOW
    assert reservation.status == ReservationStatus.CONFIRMED
    assert reservation.table_id == original_table_id
    assert reservation.assigned_table_ids == [
        original_table_id
    ]