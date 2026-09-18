from app.intelligence_temporal.autopilot_evidence import (
    TemporalAutopilotSafetyEvidenceService,
)
from app.intelligence_temporal.autopilot_guard import (
    TemporalAutopilotSafetyContext,
)
from app.intelligence_temporal.calibration_state import (
    TemporalCalibrationState,
)
from app.intelligence_temporal.prediction import (
    ExpectedTurnConfidence,
)


def _context():
    return TemporalAutopilotSafetyContext(
        calibration_state=(
            TemporalCalibrationState.WELL_CALIBRATED
        ),
        expected_turn_confidence=(
            ExpectedTurnConfidence.HIGH
        ),
        marginal_capacity_loss_ratio=0.0,
        lost_future_available_slots=0,
    )


def test_build_payload_round_trips_context():
    context = _context()

    stored = (
        TemporalAutopilotSafetyEvidenceService
        .build_payload(
            context=context,
        )
    )

    suggestion_payload = {
        "plan": {
            "example": True,
        },
        (
            TemporalAutopilotSafetyEvidenceService
            .PAYLOAD_KEY
        ): stored,
    }

    restored = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload=suggestion_payload,
        )
    )

    assert restored == context


def test_serialized_evidence_has_explicit_version():
    stored = (
        TemporalAutopilotSafetyEvidenceService
        .build_payload(
            context=_context(),
        )
    )

    assert (
        stored["schema_version"]
        == "temporal_autopilot_safety.v1"
    )


def test_missing_payload_fails_closed():
    result = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload=None,
        )
    )

    assert result is None


def test_missing_evidence_fails_closed():
    result = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload={
                "plan": {},
            },
        )
    )

    assert result is None


def test_non_dict_evidence_fails_closed():
    result = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload={
                (
                    TemporalAutopilotSafetyEvidenceService
                    .PAYLOAD_KEY
                ): "invalid",
            },
        )
    )

    assert result is None


def test_malformed_context_fails_closed():
    result = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload={
                (
                    TemporalAutopilotSafetyEvidenceService
                    .PAYLOAD_KEY
                ): {
                    "schema_version": (
                        "temporal_autopilot_safety.v1"
                    ),
                    "context": {
                        "calibration_state": (
                            "not-a-real-state"
                        ),
                    },
                },
            },
        )
    )

    assert result is None


def test_unknown_schema_version_fails_closed():
    stored = (
        TemporalAutopilotSafetyEvidenceService
        .build_payload(
            context=_context(),
        )
    )

    stored["schema_version"] = (
        "temporal_autopilot_safety.v999"
    )

    result = (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload={
                (
                    TemporalAutopilotSafetyEvidenceService
                    .PAYLOAD_KEY
                ): stored,
            },
        )
    )

    assert result is None


def test_read_does_not_modify_original_payload():
    stored = (
        TemporalAutopilotSafetyEvidenceService
        .build_payload(
            context=_context(),
        )
    )

    payload = {
        (
            TemporalAutopilotSafetyEvidenceService
            .PAYLOAD_KEY
        ): stored,
        "plan": {
            "score": 90.0,
        },
    }

    original = {
        key: (
            value.copy()
            if isinstance(value, dict)
            else value
        )
        for key, value in payload.items()
    }

    (
        TemporalAutopilotSafetyEvidenceService
        .context_from_payload(
            payload=payload,
        )
    )

    assert payload == original