from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.services.smart_layout.geometry import (
    PlacementGeometry,
    evaluate_geometric_adjacency,
)


@dataclass(frozen=True)
class LayoutPlacement:
    table_id: uuid.UUID
    geometry: PlacementGeometry
    is_visible: bool = True


AdjacencyGraph = dict[uuid.UUID, set[uuid.UUID]]


def build_adjacency_graph(
    placements: list[LayoutPlacement],
) -> AdjacencyGraph:
    """
    Build an undirected graph of plausible physical adjacency.

    Only visible placements participate in discovery.

    Every visible table appears in the graph, including isolated
    tables with no adjacent neighbours.
    """
    visible_placements = [
        placement
        for placement in placements
        if placement.is_visible
    ]

    graph: AdjacencyGraph = {
        placement.table_id: set()
        for placement in visible_placements
    }

    for first_index, first in enumerate(
        visible_placements
    ):
        for second in visible_placements[
            first_index + 1:
        ]:
            result = evaluate_geometric_adjacency(
                first.geometry,
                second.geometry,
            )

            if not result.is_adjacent:
                continue

            graph[first.table_id].add(
                second.table_id
            )
            graph[second.table_id].add(
                first.table_id
            )

    return graph