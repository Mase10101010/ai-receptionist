
from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Protocol

from app.services.smart_layout.geometry import (
    PlacementGeometry,
    placement_corners,
)


class PositionedElement(Protocol):
    x: int
    y: int
    width: int
    height: int
    rotation: int


class LayoutCenteringError(ValueError):
    """The layout cannot fit within the requested floor plan."""


def calculate_centering_offset(
    elements: Iterable[PositionedElement],
    *,
    floor_width: int,
    floor_height: int,
) -> tuple[int, int]:
    """Return a shared integer translation that centers all elements.

    Rotated geometry is included in the occupied bounding box.
    No element is modified.
    """
    items = list(elements)

    if not items:
        return (0, 0)

    if floor_width <= 0 or floor_height <= 0:
        raise LayoutCenteringError("Invalid floor plan dimensions")

    corners = [
        corner
        for element in items
        for corner in placement_corners(
            PlacementGeometry(
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                rotation=element.rotation,
            )
        )
    ]

    min_x = min(point.x for point in corners)
    max_x = max(point.x for point in corners)
    min_y = min(point.y for point in corners)
    max_y = max(point.y for point in corners)

    epsilon = 1e-7

    if (
        max_x - min_x > floor_width + epsilon
        or max_y - min_y > floor_height + epsilon
    ):
        raise LayoutCenteringError(
            "Layout exceeds the requested floor plan dimensions"
        )

    target_dx = (floor_width - min_x - max_x) / 2
    target_dy = (floor_height - min_y - max_y) / 2

    # Coordinates are stored as integers in PostgreSQL.
    dx = math.floor(target_dx + 0.5)
    dy = math.floor(target_dy + 0.5)

    # Account for integer rounding when checking boundaries.
    # Check both rendered geometry and stored coordinates.
    if (
        min_x + dx < -epsilon
        or max_x + dx > floor_width + epsilon
        or min_y + dy < -epsilon
        or max_y + dy > floor_height + epsilon
        or any(element.x + dx < 0 for element in items)
        or any(element.y + dy < 0 for element in items)
    ):
        raise LayoutCenteringError(
            "Cannot center layout within floor plan boundaries"
        )

    return (dx, dy)
