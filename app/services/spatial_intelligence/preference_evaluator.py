"""Read-only spatial preference evaluation for Alias Concierge."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.relationships import (
    evaluate_table_feature_relationship,
)


class SpatialPreference(str, Enum):
    NEAR_WINDOW = "near_window"


@dataclass(frozen=True)
class SpatialPreferenceEvaluation:
    table_id: uuid.UUID
    preference: SpatialPreference
    evaluable: bool
    nearest_feature_id: uuid.UUID | None
    separation: float | None


class SpatialPreferenceEvaluator:
    """Evaluate geometry without changing assignments or ranking."""

    FEATURE_TYPES = {
        SpatialPreference.NEAR_WINDOW: "window",
    }

    @classmethod
    def evaluate(
        cls,
        *,
        preference: SpatialPreference,
        placements: Sequence[TablePlacement],
        features: Sequence[FloorFeature],
    ) -> list[SpatialPreferenceEvaluation]:
        target_type = cls.FEATURE_TYPES[preference]

        eligible_features = [
            feature
            for feature in features
            if feature.is_visible
            and feature.feature_type == target_type
        ]

        results: list[SpatialPreferenceEvaluation] = []

        for placement in placements:
            relationships = [
                evaluate_table_feature_relationship(
                    placement,
                    feature,
                )
                for feature in eligible_features
                if placement.is_visible
                and feature.floor_plan_id == placement.floor_plan_id
            ]

            if not relationships:
                results.append(
                    SpatialPreferenceEvaluation(
                        table_id=placement.table_id,
                        preference=preference,
                        evaluable=False,
                        nearest_feature_id=None,
                        separation=None,
                    )
                )
                continue

            nearest = min(
                relationships,
                key=lambda item: (
                    item.separation,
                    str(item.feature_id),
                ),
            )

            results.append(
                SpatialPreferenceEvaluation(
                    table_id=placement.table_id,
                    preference=preference,
                    evaluable=True,
                    nearest_feature_id=nearest.feature_id,
                    separation=nearest.separation,
                )
            )

        return results
