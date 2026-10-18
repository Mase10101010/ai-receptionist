"""Read-only, restaurant-scoped spatial geometry loader."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_feature import FloorFeature
from app.models.floor_plan import FloorPlan
from app.models.service_area import ServiceArea
from app.models.table import Table
from app.models.table_placement import TablePlacement


@dataclass(frozen=True)
class RestaurantSpatialGeometry:
    placements: tuple[TablePlacement, ...]
    features: tuple[FloorFeature, ...]


class SpatialGeometryLoader:
    """Load visible geometry from active restaurant floor plans."""

    @staticmethod
    async def load(
        *,
        session: AsyncSession,
        restaurant_id: uuid.UUID,
    ) -> RestaurantSpatialGeometry:
        placements_result = await session.execute(
            select(TablePlacement)
            .join(
                FloorPlan,
                TablePlacement.floor_plan_id == FloorPlan.id,
            )
            .join(
                ServiceArea,
                FloorPlan.service_area_id == ServiceArea.id,
            )
            .join(
                Table,
                TablePlacement.table_id == Table.id,
            )
            .where(
                ServiceArea.restaurant_id == restaurant_id,
                ServiceArea.is_active.is_(True),
                FloorPlan.is_active.is_(True),
                Table.restaurant_id == restaurant_id,
                Table.service_area_id == ServiceArea.id,
                Table.is_active.is_(True),
                TablePlacement.is_visible.is_(True),
            )
            .order_by(
                TablePlacement.floor_plan_id,
                TablePlacement.table_id,
            )
        )

        features_result = await session.execute(
            select(FloorFeature)
            .join(
                FloorPlan,
                FloorFeature.floor_plan_id == FloorPlan.id,
            )
            .join(
                ServiceArea,
                FloorPlan.service_area_id == ServiceArea.id,
            )
            .where(
                ServiceArea.restaurant_id == restaurant_id,
                ServiceArea.is_active.is_(True),
                FloorPlan.is_active.is_(True),
                FloorFeature.is_visible.is_(True),
                FloorFeature.feature_type == "window",
            )
            .order_by(
                FloorFeature.floor_plan_id,
                FloorFeature.id,
            )
        )

        return RestaurantSpatialGeometry(
            placements=tuple(
                placements_result.scalars().all()
            ),
            features=tuple(
                features_result.scalars().all()
            ),
        )
