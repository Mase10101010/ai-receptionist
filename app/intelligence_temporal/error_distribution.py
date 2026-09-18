from __future__ import annotations

import math

from pydantic import BaseModel

from .prediction_truth import (
    TemporalTurnPredictionOutcome,
)


class TemporalErrorDistribution(BaseModel):
    sample_count: int

    p10_signed_error_minutes: int | None
    p50_signed_error_minutes: int | None
    p90_signed_error_minutes: int | None


class TemporalErrorDistributionService:
    """
    Builds an empirical distribution of temporal prediction errors.

    signed_error semantics:
        actual_duration - predicted_duration

        positive -> Alias predicted too short
        negative -> Alias predicted too long

    Quantiles use the nearest-rank empirical method.

    No DB access.
    No persistence.
    No probability model.
    No Brain / optimizer / Autopilot integration.
    """

    @staticmethod
    def _nearest_rank(
        values: list[int],
        probability: float,
    ) -> int:
        if not values:
            raise ValueError(
                "Cannot calculate quantile for empty values."
            )

        ordered = sorted(values)

        rank = math.ceil(
            probability * len(ordered)
        )

        index = max(0, rank - 1)

        return ordered[index]

    @classmethod
    def calculate(
        cls,
        outcomes: list[
            TemporalTurnPredictionOutcome
        ],
    ) -> TemporalErrorDistribution:
        if not outcomes:
            return TemporalErrorDistribution(
                sample_count=0,
                p10_signed_error_minutes=None,
                p50_signed_error_minutes=None,
                p90_signed_error_minutes=None,
            )

        errors = [
            outcome.signed_error_minutes
            for outcome in outcomes
        ]

        return TemporalErrorDistribution(
            sample_count=len(errors),
            p10_signed_error_minutes=(
                cls._nearest_rank(
                    errors,
                    0.10,
                )
            ),
            p50_signed_error_minutes=(
                cls._nearest_rank(
                    errors,
                    0.50,
                )
            ),
            p90_signed_error_minutes=(
                cls._nearest_rank(
                    errors,
                    0.90,
                )
            ),
        )