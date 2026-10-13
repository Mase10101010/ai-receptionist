
from dataclasses import dataclass

import pytest

from app.services.floor_plan_centering import (
    LayoutCenteringError,
    calculate_centering_offset,
)
from app.services.smart_layout.geometry import (
    PlacementGeometry,
    placement_corners,
)


@dataclass
class Element:
    x: int
    y: int
    width: int
    height: int
    rotation: int = 0


def test_empty_layout_requires_no_translation():
    assert calculate_centering_offset(
        [],
        floor_width=2400,
        floor_height=1800,
    ) == (0, 0)


def test_single_table_is_centered():
    table = Element(100, 100, 80, 80)

    dx, dy = calculate_centering_offset(
        [table],
        floor_width=1000,
        floor_height=800,
    )

    assert (table.x + dx, table.y + dy) == (460, 360)


def test_multiple_elements_keep_relative_positions():
    first = Element(100, 100, 80, 80)
    second = Element(300, 200, 120, 60)

    dx, dy = calculate_centering_offset(
        [first, second],
        floor_width=1200,
        floor_height=900,
    )

    assert (second.x + dx) - (first.x + dx) == 200
    assert (second.y + dy) - (first.y + dy) == 100


def test_rotated_wall_is_centered_within_bounds():
    wall = Element(100, 100, 200, 20, 45)

    dx, dy = calculate_centering_offset(
        [wall],
        floor_width=1000,
        floor_height=800,
    )

    corners = placement_corners(
        PlacementGeometry(
            x=wall.x + dx,
            y=wall.y + dy,
            width=wall.width,
            height=wall.height,
            rotation=wall.rotation,
        )
    )

    assert min(point.x for point in corners) >= -1e-7
    assert max(point.x for point in corners) <= 1000 + 1e-7
    assert min(point.y for point in corners) >= -1e-7
    assert max(point.y for point in corners) <= 800 + 1e-7


def test_layout_larger_than_floor_is_rejected():
    table = Element(0, 0, 1200, 100)

    with pytest.raises(LayoutCenteringError):
        calculate_centering_offset(
            [table],
            floor_width=1000,
            floor_height=800,
        )


def test_translation_uses_integer_coordinates():
    table = Element(13, 27, 80, 80)

    dx, dy = calculate_centering_offset(
        [table],
        floor_width=1001,
        floor_height=801,
    )

    assert isinstance(dx, int)
    assert isinstance(dy, int)


def test_rotated_element_with_negative_origin_is_rejected():
    # Its rendered corners fit, but centering would produce
    # a negative stored x coordinate.
    wall = Element(
        x=100,
        y=100,
        width=200,
        height=20,
        rotation=90,
    )

    with pytest.raises(LayoutCenteringError):
        calculate_centering_offset(
            [wall],
            floor_width=40,
            floor_height=400,
        )


def test_rotated_feature_can_be_centered_safely():
    wall = Element(
        x=100,
        y=100,
        width=200,
        height=20,
        rotation=90,
    )

    dx, dy = calculate_centering_offset(
        [wall],
        floor_width=500,
        floor_height=500,
    )

    assert wall.x + dx >= 0
    assert wall.y + dy >= 0


def test_centering_does_not_modify_original_elements():
    table = Element(100, 150, 80, 80)
    wall = Element(250, 150, 200, 20)

    original = (
        table.x,
        table.y,
        wall.x,
        wall.y,
    )

    calculate_centering_offset(
        [table, wall],
        floor_width=2400,
        floor_height=1800,
    )

    assert (
        table.x,
        table.y,
        wall.x,
        wall.y,
    ) == original
