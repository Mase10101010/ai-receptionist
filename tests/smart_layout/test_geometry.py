import math

import pytest

from app.services.smart_layout.geometry import (
    PlacementGeometry,
    are_geometrically_adjacent,
    evaluate_geometric_adjacency,
    minimum_polygon_separation,
    placement_corners,
    polygons_overlap,
)




def test_unrotated_placement_corners():
    geometry = PlacementGeometry(
        x=100,
        y=200,
        width=80,
        height=40,
        rotation=0,
    )

    corners = placement_corners(geometry)

    coordinates = {
        (
            round(point.x, 6),
            round(point.y, 6),
        )
        for point in corners
    }

    assert coordinates == {
        (100.0, 200.0),
        (180.0, 200.0),
        (180.0, 240.0),
        (100.0, 240.0),
    }


def test_rotation_preserves_center():
    geometry = PlacementGeometry(
        x=100,
        y=100,
        width=80,
        height=40,
        rotation=37,
    )

    corners = placement_corners(geometry)

    average_x = sum(
        point.x for point in corners
    ) / 4
    average_y = sum(
        point.y for point in corners
    ) / 4

    assert average_x == pytest.approx(140.0)
    assert average_y == pytest.approx(120.0)


def test_rotation_preserves_corner_radius():
    geometry = PlacementGeometry(
        x=100,
        y=100,
        width=80,
        height=40,
        rotation=73,
    )

    corners = placement_corners(geometry)

    expected_radius = math.hypot(
        geometry.width / 2,
        geometry.height / 2,
    )

    for corner in corners:
        actual_radius = math.hypot(
            corner.x - geometry.center.x,
            corner.y - geometry.center.y,
        )

        assert actual_radius == pytest.approx(
            expected_radius
        )


def test_separated_tables_do_not_overlap():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=100,
            y=0,
            width=80,
            height=80,
        )
    )

    assert not polygons_overlap(
        first,
        second,
    )


def test_overlapping_tables_are_detected():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=40,
            y=0,
            width=80,
            height=80,
        )
    )

    assert polygons_overlap(
        first,
        second,
    )


def test_rotated_overlap_is_detected():
    first = placement_corners(
        PlacementGeometry(
            x=100,
            y=100,
            width=100,
            height=40,
            rotation=45,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=125,
            y=115,
            width=100,
            height=40,
            rotation=315,
        )
    )

    assert polygons_overlap(
        first,
        second,
    )


def test_horizontal_edge_separation():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=100,
            y=0,
            width=80,
            height=80,
        )
    )

    distance = minimum_polygon_separation(
        first,
        second,
    )

    assert distance == pytest.approx(20.0)


def test_vertical_edge_separation():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=0,
            y=95,
            width=80,
            height=80,
        )
    )

    distance = minimum_polygon_separation(
        first,
        second,
    )

    assert distance == pytest.approx(15.0)


def test_diagonal_separation_uses_true_distance():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=100,
            y=100,
            width=80,
            height=80,
        )
    )

    distance = minimum_polygon_separation(
        first,
        second,
    )

    assert distance == pytest.approx(
        math.sqrt(20**2 + 20**2)
    )


def test_overlap_has_zero_separation():
    first = placement_corners(
        PlacementGeometry(
            x=0,
            y=0,
            width=80,
            height=80,
        )
    )
    second = placement_corners(
        PlacementGeometry(
            x=20,
            y=20,
            width=80,
            height=80,
            rotation=25,
        )
    )

    assert minimum_polygon_separation(
        first,
        second,
    ) == pytest.approx(0.0)

def test_side_by_side_tables_are_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=100,
        y=0,
        width=80,
        height=80,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert result.is_adjacent
    assert result.reason == "adjacent"
    assert result.separation == pytest.approx(20.0)


def test_vertically_near_tables_are_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=0,
        y=100,
        width=80,
        height=80,
    )

    assert are_geometrically_adjacent(
        first,
        second,
    )


def test_far_tables_are_not_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=160,
        y=0,
        width=80,
        height=80,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert not result.is_adjacent
    assert result.reason == "too_far"


def test_diagonal_tables_are_not_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=100,
        y=100,
        width=80,
        height=80,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert not result.is_adjacent
    assert result.reason in {
        "too_far",
        "insufficient_alignment",
    }

def test_close_diagonal_tables_fail_alignment():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=100,
        height=100,
    )
    second = PlacementGeometry(
        x=120,
        y=120,
        width=100,
        height=100,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert not result.is_adjacent
    assert result.separation == pytest.approx(
        math.sqrt(20**2 + 20**2)
    )
    assert result.reason == "insufficient_alignment"


def test_overlapping_tables_are_not_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=40,
        y=0,
        width=80,
        height=80,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert not result.is_adjacent
    assert result.reason == "overlapping"


def test_small_relative_gap_is_allowed():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=100,
        height=100,
    )
    second = PlacementGeometry(
        x=130,
        y=0,
        width=100,
        height=100,
    )

    assert are_geometrically_adjacent(
        first,
        second,
    )


def test_gap_beyond_relative_threshold_is_rejected():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=100,
        height=100,
    )
    second = PlacementGeometry(
        x=140,
        y=0,
        width=100,
        height=100,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert not result.is_adjacent
    assert result.reason == "too_far"


def test_partial_side_alignment_can_still_be_adjacent():
    first = PlacementGeometry(
        x=0,
        y=0,
        width=80,
        height=80,
    )
    second = PlacementGeometry(
        x=100,
        y=40,
        width=80,
        height=80,
    )

    assert are_geometrically_adjacent(
        first,
        second,
    )


def test_rotated_nearby_tables_can_be_adjacent():
    first = PlacementGeometry(
        x=100,
        y=100,
        width=80,
        height=80,
        rotation=15,
    )
    second = PlacementGeometry(
        x=205,
        y=100,
        width=80,
        height=80,
        rotation=345,
    )

    result = evaluate_geometric_adjacency(
        first,
        second,
    )

    assert result.is_adjacent