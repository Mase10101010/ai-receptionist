from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from .autopilot_guard import (
    TemporalAutopilotSafetyContext,
)


class TemporalAutopilotSafetyEvidence(BaseModel):
    """
    Persistable temporal safety evidence attached to an exact
    autonomous-action candidate.

    This is evidence only.
    It is not execution authority.
    """

    schema_version: str = "temporal_autopilot_safety.v1"

    context: TemporalAutopilotSafetyContext


class TemporalAutopilotSafetyEvidenceService:
    """
    Serialization boundary for stored Temporal Autopilot evidence.

    Missing or malformed stored evidence fails closed by returning None.

    Invariants:
    - no temporal calculation
    - no prediction
    - no calibration calculation
    - no ranking
    - no DB
    - no execution
    - no Autopilot authority
    - no mutation
    - no Brain
    - no ML
    """

    PAYLOAD_KEY = "temporal_autopilot_safety"

    @classmethod
    def build_payload(
        cls,
        *,
        context: TemporalAutopilotSafetyContext,
    ) -> dict[str, Any]:
        evidence = TemporalAutopilotSafetyEvidence(
            context=context,
        )

        return evidence.model_dump(
            mode="json",
        )

    @classmethod
    def read_from_payload(
        cls,
        *,
        payload: dict[str, Any] | None,
    ) -> TemporalAutopilotSafetyEvidence | None:
        if not isinstance(payload, dict):
            return None

        raw_evidence = payload.get(
            cls.PAYLOAD_KEY,
        )

        if not isinstance(raw_evidence, dict):
            return None

        try:
            evidence = (
                TemporalAutopilotSafetyEvidence
                .model_validate(raw_evidence)
            )
        except (ValidationError, TypeError, ValueError):
            return None

        if (
            evidence.schema_version
            != "temporal_autopilot_safety.v1"
        ):
            return None

        return evidence

    @classmethod
    def context_from_payload(
        cls,
        *,
        payload: dict[str, Any] | None,
    ) -> TemporalAutopilotSafetyContext | None:
        evidence = cls.read_from_payload(
            payload=payload,
        )

        if evidence is None:
            return None

        return evidence.context