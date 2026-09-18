from __future__ import annotations

import math
from dataclasses import dataclass


_EPSILON = 1e-9


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class PlacementGeometry:
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0

    @property
    def center(self) -> Point:
        return Point(
            x=self.x + self.width / 2.0,
            y=self.y + self.height / 2.0,
        )


def placement_corners(
    geometry: PlacementGeometry,
) -> tuple[Point, Point, Point, Point]:
    """
    Return the four corners of a table placement after rotation.

    Rotation is performed around the table centre, matching the
    Floor Map rendering model.
    """
    center = geometry.center

    half_width = geometry.width / 2.0
    half_height = geometry.height / 2.0

    local_corners = (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )

    radians = math.radians(
        geometry.rotation % 360.0
    )
    cosine = math.cos(radians)
    sine = math.sin(radians)

    return tuple(
        Point(
            x=(
                center.x
                + local_x * cosine
                - local_y * sine
            ),
            y=(
                center.y
                + local_x * sine
                + local_y * cosine
            ),
        )
        for local_x, local_y in local_corners
    )


def polygon_axes(
    polygon: tuple[Point, ...],
) -> tuple[Point, ...]:
    """
    Return normalized perpendicular axes for polygon edges.
    """
    axes: list[Point] = []

    for index, point in enumerate(polygon):
        next_point = polygon[
            (index + 1) % len(polygon)
        ]

        edge_x = next_point.x - point.x
        edge_y = next_point.y - point.y

        axis_x = -edge_y
        axis_y = edge_x

        length = math.hypot(axis_x, axis_y)

        if length <= _EPSILON:
            continue

        axes.append(
            Point(
                x=axis_x / length,
                y=axis_y / length,
            )
        )

    return tuple(axes)


def project_polygon(
    polygon: tuple[Point, ...],
    axis: Point,
) -> tuple[float, float]:
    projections = [
        point.x * axis.x + point.y * axis.y
        for point in polygon
    ]

    return min(projections), max(projections)


def polygons_overlap(
    first: tuple[Point, ...],
    second: tuple[Point, ...],
) -> bool:
    """
    Test two convex polygons using the Separating Axis Theorem.

    Touching edges count as overlap for geometry validation.
    """
    for axis in (
        *polygon_axes(first),
        *polygon_axes(second),
    ):
        first_min, first_max = project_polygon(
            first,
            axis,
        )
        second_min, second_max = project_polygon(
            second,
            axis,
        )

        if (
            first_max < second_min - _EPSILON
            or second_max < first_min - _EPSILON
        ):
            return False

    return True


def _distance_between_points(
    first: Point,
    second: Point,
) -> float:
    return math.hypot(
        first.x - second.x,
        first.y - second.y,
    )


def _distance_point_to_segment(
    point: Point,
    start: Point,
    end: Point,
) -> float:
    segment_x = end.x - start.x
    segment_y = end.y - start.y

    length_squared = (
        segment_x * segment_x
        + segment_y * segment_y
    )

    if length_squared <= _EPSILON:
        return _distance_between_points(
            point,
            start,
        )

    projection = (
        (
            (point.x - start.x) * segment_x
            + (point.y - start.y) * segment_y
        )
        / length_squared
    )

    projection = max(
        0.0,
        min(1.0, projection),
    )

    closest = Point(
        x=start.x + projection * segment_x,
        y=start.y + projection * segment_y,
    )

    return _distance_between_points(
        point,
        closest,
    )


def _segments_intersect(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> bool:
    def orientation(
        first: Point,
        second: Point,
        third: Point,
    ) -> float:
        return (
            (second.x - first.x)
            * (third.y - first.y)
            - (second.y - first.y)
            * (third.x - first.x)
        )

    o1 = orientation(
        first_start,
        first_end,
        second_start,
    )
    o2 = orientation(
        first_start,
        first_end,
        second_end,
    )
    o3 = orientation(
        second_start,
        second_end,
        first_start,
    )
    o4 = orientation(
        second_start,
        second_end,
        first_end,
    )

    return (
        (
            o1 > _EPSILON
            and o2 < -_EPSILON
            or o1 < -_EPSILON
            and o2 > _EPSILON
        )
        and (
            o3 > _EPSILON
            and o4 < -_EPSILON
            or o3 < -_EPSILON
            and o4 > _EPSILON
        )
    )


def _segment_distance(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> float:
    if _segments_intersect(
        first_start,
        first_end,
        second_start,
        second_end,
    ):
        return 0.0

    return min(
        _distance_point_to_segment(
            first_start,
            second_start,
            second_end,
        ),
        _distance_point_to_segment(
            first_end,
            second_start,
            second_end,
        ),
        _distance_point_to_segment(
            second_start,
            first_start,
            first_end,
        ),
        _distance_point_to_segment(
            second_end,
            first_start,
            first_end,
        ),
    )


def minimum_polygon_separation(
    first: tuple[Point, ...],
    second: tuple[Point, ...],
) -> float:
    """
    Return the minimum edge-to-edge distance between two polygons.

    Overlapping or touching polygons return 0.
    """
    if polygons_overlap(first, second):
        return 0.0

    minimum_distance = math.inf

    for first_index, first_start in enumerate(first):
        first_end = first[
            (first_index + 1) % len(first)
        ]

        for second_index, second_start in enumerate(
            second
        ):
            second_end = second[
                (second_index + 1) % len(second)
            ]

            minimum_distance = min(
                minimum_distance,
                _segment_distance(
                    first_start,
                    first_end,
                    second_start,
                    second_end,
                ),
            )

    return minimum_distance

@dataclass(frozen=True)
class AdjacencyResult:
    is_adjacent: bool
    separation: float
    reason: str


def _projection_overlap_ratio(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    """
    Return how much two 1D intervals overlap relative to the
    smaller interval.

    1.0 means full overlap of the smaller interval.
    0.0 means no overlap.
    """
    first_min, first_max = first
    second_min, second_max = second

    overlap = max(
        0.0,
        min(first_max, second_max)
        - max(first_min, second_min),
    )

    smaller_length = min(
        first_max - first_min,
        second_max - second_min,
    )

    if smaller_length <= _EPSILON:
        return 0.0

    return overlap / smaller_length


def _axis_aligned_bounds(
    polygon: tuple[Point, ...],
) -> tuple[float, float, float, float]:
    return (
        min(point.x for point in polygon),
        max(point.x for point in polygon),
        min(point.y for point in polygon),
        max(point.y for point in polygon),
    )


def evaluate_geometric_adjacency(
    first_geometry: PlacementGeometry,
    second_geometry: PlacementGeometry,
) -> AdjacencyResult:
    """
    Conservatively decide whether two placements are plausible
    physical neighbours.

    Geometry proposes adjacency. It does not establish physical
    combinability; manager authority remains above this heuristic.
    """
    first = placement_corners(first_geometry)
    second = placement_corners(second_geometry)

    if polygons_overlap(first, second):
        return AdjacencyResult(
            is_adjacent=False,
            separation=0.0,
            reason="overlapping",
        )

    separation = minimum_polygon_separation(
        first,
        second,
    )

    smaller_dimension = min(
        first_geometry.width,
        first_geometry.height,
        second_geometry.width,
        second_geometry.height,
    )

    max_separation = smaller_dimension * 0.35

    if separation > max_separation + _EPSILON:
        return AdjacencyResult(
            is_adjacent=False,
            separation=separation,
            reason="too_far",
        )

    (
        first_left,
        first_right,
        first_top,
        first_bottom,
    ) = _axis_aligned_bounds(first)

    (
        second_left,
        second_right,
        second_top,
        second_bottom,
    ) = _axis_aligned_bounds(second)

    horizontal_overlap = _projection_overlap_ratio(
        (first_left, first_right),
        (second_left, second_right),
    )

    vertical_overlap = _projection_overlap_ratio(
        (first_top, first_bottom),
        (second_top, second_bottom),
    )

    minimum_alignment = 0.35

    if (
        horizontal_overlap < minimum_alignment
        and vertical_overlap < minimum_alignment
    ):
        return AdjacencyResult(
            is_adjacent=False,
            separation=separation,
            reason="insufficient_alignment",
        )

    return AdjacencyResult(
        is_adjacent=True,
        separation=separation,
        reason="adjacent",
    )


def are_geometrically_adjacent(
    first_geometry: PlacementGeometry,
    second_geometry: PlacementGeometry,
) -> bool:
    return evaluate_geometric_adjacency(
        first_geometry,
        second_geometry,
    ).is_adjacent