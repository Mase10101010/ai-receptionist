"""Tests for read-only floor-plan spatial analysis."""

import uuid

import pytest

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.analysis import (
    analyze_floor_plan_spatially,
)


def make_scene():
    floor_id = uuid.uuid4()

    first = TablePlacement(
        floor_plan_id=floor_id,
        table_id=uuid.uuid4(),
        x=0, y=0, width=40, height=40,
        rotation=0, is_visible=True,
    )

    second = TablePlacement(
        floor_plan_id=floor_id,
        table_id=uuid.uuid4(),
        x=200, y=0, width=40, height=40,
        rotation=0, is_visible=True,
    )

    wall = FloorFeature(
        id=uuid.uuid4(),
        floor_plan_id=floor_id,
        feature_type="wall",
        x=110, y=0, width=10, height=40,
        rotation=0, is_visible=True,
    )

    return floor_id, first, second, wall


def test_analysis_combines_relationships_and_obstacles():
    floor_id, first, second, wall = make_scene()

    result = analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[first, second],
        features=[wall],
    )

    assert result.floor_plan_id == floor_id
    assert len(result.table_feature_relationships) == 2
    assert len(result.table_pair_obstacles) == 1
    assert result.table_pair_obstacles[0].has_potential_obstacles
    assert result.table_pair_obstacles[0].obstacle_feature_ids == (
        wall.id,
    )


def test_invisible_objects_are_excluded():
    floor_id, first, second, wall = make_scene()
    second.is_visible = False
    wall.is_visible = False

    result = analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[first, second],
        features=[wall],
    )

    assert result.table_feature_relationships == ()
    assert result.table_pair_obstacles == ()


def test_other_floor_plan_table_rejected():
    floor_id, first, second, wall = make_scene()
    second.floor_plan_id = uuid.uuid4()

    with pytest.raises(ValueError, match="another floor plan"):
        analyze_floor_plan_spatially(
            floor_plan_id=floor_id,
            placements=[first, second],
            features=[wall],
        )


def test_other_floor_plan_feature_rejected():
    floor_id, first, second, wall = make_scene()
    wall.floor_plan_id = uuid.uuid4()

    with pytest.raises(ValueError, match="another floor plan"):
        analyze_floor_plan_spatially(
            floor_plan_id=floor_id,
            placements=[first, second],
            features=[wall],
        )


def test_results_independent_of_input_order():
    floor_id, first, second, wall = make_scene()

    forward = analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[first, second],
        features=[wall],
    )

    reversed_input = analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[second, first],
        features=[wall],
    )

    assert forward == reversed_input


def test_empty_floor_plan():
    floor_id = uuid.uuid4()

    result = analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[],
        features=[],
    )

    assert result.table_feature_relationships == ()
    assert result.table_pair_obstacles == ()


def test_analysis_does_not_modify_placements_or_features():
    floor_id, first, second, wall = make_scene()

    original_coordinates = (
        first.x, first.y,
        second.x, second.y,
        wall.x, wall.y,
    )

    analyze_floor_plan_spatially(
        floor_plan_id=floor_id,
        placements=[first, second],
        features=[wall],
    )

    assert original_coordinates == (
        first.x, first.y,
        second.x, second.y,
        wall.x, wall.y,
    )
