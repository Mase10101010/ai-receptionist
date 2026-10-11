"""Tests for read-only potential obstacle detection."""

import uuid

import pytest

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.obstacles import (
    detect_obstacles_between_tables,
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
    return first, second, wall


def test_wall_between_tables_detected():
    first, second, wall = make_scene()
    result = detect_obstacles_between_tables(first, second, [wall])

    assert result.has_potential_obstacles
    assert result.obstacle_feature_ids == (wall.id,)


def test_wall_outside_path_not_detected():
    first, second, wall = make_scene()
    wall.y = 100

    result = detect_obstacles_between_tables(first, second, [wall])

    assert not result.has_potential_obstacles


def test_rotated_wall_detected():
    first, second, wall = make_scene()
    wall.x = 100
    wall.y = -10
    wall.width = 80
    wall.height = 10
    wall.rotation = 45

    result = detect_obstacles_between_tables(first, second, [wall])

    assert result.has_potential_obstacles


@pytest.mark.parametrize(
    "feature_type",
    ["window", "door", "entrance", "sofa", "other"],
)
def test_non_blocking_types_ignored(feature_type):
    first, second, feature = make_scene()
    feature.feature_type = feature_type

    result = detect_obstacles_between_tables(first, second, [feature])

    assert not result.has_potential_obstacles


def test_invisible_wall_ignored():
    first, second, wall = make_scene()
    wall.is_visible = False

    result = detect_obstacles_between_tables(first, second, [wall])

    assert not result.has_potential_obstacles


def test_different_floor_plan_rejected():
    first, second, wall = make_scene()
    wall.floor_plan_id = uuid.uuid4()

    with pytest.raises(ValueError, match="different floor plan"):
        detect_obstacles_between_tables(first, second, [wall])


def test_invisible_table_rejected():
    first, second, wall = make_scene()
    first.is_visible = False

    with pytest.raises(ValueError, match="invisible tables"):
        detect_obstacles_between_tables(first, second, [wall])


def test_same_table_rejected():
    first, _, wall = make_scene()

    with pytest.raises(ValueError, match="distinct tables"):
        detect_obstacles_between_tables(first, first, [wall])


def test_detection_is_symmetric():
    first, second, wall = make_scene()

    forward = detect_obstacles_between_tables(first, second, [wall])
    reverse = detect_obstacles_between_tables(second, first, [wall])

    assert forward.obstacle_feature_ids == reverse.obstacle_feature_ids


def test_rotated_wall_outside_path_not_detected():
    first, second, wall = make_scene()
    wall.x = 100
    wall.y = -20
    wall.width = 80
    wall.height = 10
    wall.rotation = 45

    result = detect_obstacles_between_tables(first, second, [wall])

    assert not result.has_potential_obstacles


def test_wall_touching_path_detected():
    first, second, wall = make_scene()
    wall.y = 20

    # The table-centre segment lies exactly on the wall's top edge.
    result = detect_obstacles_between_tables(first, second, [wall])

    assert result.has_potential_obstacles


def test_bar_counter_between_tables_detected():
    first, second, feature = make_scene()
    feature.feature_type = "bar_counter"

    result = detect_obstacles_between_tables(first, second, [feature])

    assert result.obstacle_feature_ids == (feature.id,)


def test_multiple_obstacles_are_deduplicated():
    first, second, wall = make_scene()

    result = detect_obstacles_between_tables(
        first, second, [wall, wall]
    )

    assert result.obstacle_feature_ids == (wall.id,)
