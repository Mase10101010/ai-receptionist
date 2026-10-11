"""Read-only detection of potential obstacles between tables."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.smart_layout.geometry import (
    PlacementGeometry,
    Point,
    placement_corners,
)

POTENTIAL_OBSTACLE_TYPES = frozenset({
    "wall",
    "bar_counter",
})

_EPSILON = 1e-9


@dataclass(frozen=True)
class ObstacleDetectionResult:
    first_table_id: uuid.UUID
    second_table_id: uuid.UUID
    obstacle_feature_ids: tuple[uuid.UUID, ...]

    @property
    def has_potential_obstacles(self) -> bool:
        return bool(self.obstacle_feature_ids)


def _cross(a: Point, b: Point, c: Point) -> float:
    return (
        (b.x - a.x) * (c.y - a.y)
        - (b.y - a.y) * (c.x - a.x)
    )


def _point_inside_convex_polygon(
    point: Point,
    polygon: tuple[Point, ...],
) -> bool:
    values = [
        _cross(polygon[i], polygon[(i + 1) % len(polygon)], point)
        for i in range(len(polygon))
    ]
    return (
        all(value >= -_EPSILON for value in values)
        or all(value <= _EPSILON for value in values)
    )


def _segments_touch_or_intersect(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
) -> bool:
    ab_c = _cross(a, b, c)
    ab_d = _cross(a, b, d)
    cd_a = _cross(c, d, a)
    cd_b = _cross(c, d, b)

    if (
        ((ab_c > _EPSILON and ab_d < -_EPSILON)
         or (ab_c < -_EPSILON and ab_d > _EPSILON))
        and
        ((cd_a > _EPSILON and cd_b < -_EPSILON)
         or (cd_a < -_EPSILON and cd_b > _EPSILON))
    ):
        return True

    def on_segment(p: Point, q: Point, r: Point) -> bool:
        return (
            min(p.x, r.x) - _EPSILON <= q.x <= max(p.x, r.x) + _EPSILON
            and min(p.y, r.y) - _EPSILON <= q.y <= max(p.y, r.y) + _EPSILON
        )

    return (
        (abs(ab_c) <= _EPSILON and on_segment(a, c, b))
        or (abs(ab_d) <= _EPSILON and on_segment(a, d, b))
        or (abs(cd_a) <= _EPSILON and on_segment(c, a, d))
        or (abs(cd_b) <= _EPSILON and on_segment(c, b, d))
    )


def _segment_intersects_polygon(
    start: Point,
    end: Point,
    polygon: tuple[Point, ...],
) -> bool:
    if (
        _point_inside_convex_polygon(start, polygon)
        or _point_inside_convex_polygon(end, polygon)
    ):
        return True

    return any(
        _segments_touch_or_intersect(
            start,
            end,
            polygon[index],
            polygon[(index + 1) % len(polygon)],
        )
        for index in range(len(polygon))
    )


def detect_obstacles_between_tables(
    first: TablePlacement,
    second: TablePlacement,
    features: Iterable[FloorFeature],
) -> ObstacleDetectionResult:
    """Detect potential blockers along the table-centre segment.

    Geometry uses floor-plan coordinate units.
    Results are informational and must not automatically block joins.
    """
    if first.floor_plan_id != second.floor_plan_id:
        raise ValueError("Tables must belong to the same floor plan")

    if first.table_id == second.table_id:
        raise ValueError("Two distinct tables are required")

    if not first.is_visible or not second.is_visible:
        raise ValueError("Cannot analyze invisible tables")

    first_center = PlacementGeometry(
        first.x, first.y, first.width, first.height, first.rotation
    ).center
    second_center = PlacementGeometry(
        second.x, second.y, second.width, second.height, second.rotation
    ).center

    detected: set[uuid.UUID] = set()

    for feature in features:
        if feature.floor_plan_id != first.floor_plan_id:
            raise ValueError("Feature belongs to a different floor plan")

        if (
            not feature.is_visible
            or feature.feature_type not in POTENTIAL_OBSTACLE_TYPES
        ):
            continue

        polygon = placement_corners(
            PlacementGeometry(
                feature.x,
                feature.y,
                feature.width,
                feature.height,
                feature.rotation,
            )
        )

        if _segment_intersects_polygon(
            first_center,
            second_center,
            polygon,
        ):
            detected.add(feature.id)

    return ObstacleDetectionResult(
        first_table_id=first.table_id,
        second_table_id=second.table_id,
        obstacle_feature_ids=tuple(sorted(detected)),
    )
