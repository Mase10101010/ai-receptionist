"""Tests for read-only spatial relationships."""

import uuid

import pytest

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.relationships import (
    evaluate_table_feature_relationship,
)


def make_objects(
    *,
    table_x=0,
    table_y=0,
    feature_x=100,
    feature_y=0,
    feature_rotation=0,
):
    floor_plan_id = uuid.uuid4()

    placement = TablePlacement(
        floor_plan_id=floor_plan_id,
        table_id=uuid.uuid4(),
        x=table_x,
        y=table_y,
        width=80,
        height=80,
        rotation=0,
        is_visible=True,
    )

    feature = FloorFeature(
        id=uuid.uuid4(),
        floor_plan_id=floor_plan_id,
        feature_type="wall",
        x=feature_x,
        y=feature_y,
        width=40,
        height=40,
        rotation=feature_rotation,
        is_visible=True,
    )

    return placement, feature


def test_separated_objects():
    placement, feature = make_objects()

    result = evaluate_table_feature_relationship(
        placement, feature
    )

    assert result.separation == pytest.approx(20.0)
    assert result.overlaps is False
    assert result.table_id == placement.table_id
    assert result.feature_id == feature.id
    assert result.feature_type == "wall"


def test_overlapping_objects():
    placement, feature = make_objects(feature_x=50)

    result = evaluate_table_feature_relationship(
        placement, feature
    )

    assert result.separation == pytest.approx(0.0)
    assert result.overlaps is True


def test_rotation_changes_separation():
    placement, feature = make_objects(
        feature_x=100,
        feature_rotation=45,
    )

    result = evaluate_table_feature_relationship(
        placement, feature
    )

    assert result.separation > 0
    assert result.separation < 20


def test_different_floor_plans_rejected():
    placement, feature = make_objects()
    feature.floor_plan_id = uuid.uuid4()

    with pytest.raises(ValueError, match="same floor plan"):
        evaluate_table_feature_relationship(
            placement, feature
        )


def test_invisible_objects_rejected():
    placement, feature = make_objects()
    feature.is_visible = False

    with pytest.raises(ValueError, match="invisible"):
        evaluate_table_feature_relationship(
            placement, feature
        )
