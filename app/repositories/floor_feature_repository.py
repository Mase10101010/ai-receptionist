"""Persistence operations for environmental floor-plan features."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floor_feature import FloorFeature


class FloorFeatureRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, feature: FloorFeature) -> FloorFeature:
        self.db.add(feature)
        await self.db.flush()
        await self.db.refresh(feature)
        return feature

    async def get_by_id(
        self,
        feature_id: uuid.UUID,
        floor_plan_id: uuid.UUID,
    ) -> FloorFeature | None:
        result = await self.db.execute(
            select(FloorFeature).where(
                FloorFeature.id == feature_id,
                FloorFeature.floor_plan_id == floor_plan_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_floor_plan(
        self,
        floor_plan_id: uuid.UUID,
    ) -> list[FloorFeature]:
        result = await self.db.execute(
            select(FloorFeature)
            .where(FloorFeature.floor_plan_id == floor_plan_id)
            .order_by(FloorFeature.created_at, FloorFeature.id)
        )
        return list(result.scalars().all())

    async def update(
        self,
        feature: FloorFeature,
        fields: dict,
    ) -> FloorFeature:
        for key, value in fields.items():
            setattr(feature, key, value)

        await self.db.flush()
        await self.db.refresh(feature)
        return feature

    async def copy_floor_plan(
        self,
        source_floor_plan_id: uuid.UUID,
        target_floor_plan_id: uuid.UUID,
    ) -> list[FloorFeature]:
        source_features = await self.list_by_floor_plan(
            source_floor_plan_id
        )

        copied_features: list[FloorFeature] = []

        for source in source_features:
            copied = FloorFeature(
                floor_plan_id=target_floor_plan_id,
                feature_type=source.feature_type,
                label=source.label,
                x=source.x,
                y=source.y,
                width=source.width,
                height=source.height,
                rotation=source.rotation,
                is_visible=source.is_visible,
            )

            self.db.add(copied)
            copied_features.append(copied)

        await self.db.flush()

        return copied_features

    async def delete(self, feature: FloorFeature) -> None:
        await self.db.delete(feature)
        await self.db.flush()
