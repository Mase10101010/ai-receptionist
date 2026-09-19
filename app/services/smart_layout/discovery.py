from __future__ import annotations

import uuid

from app.services.smart_layout.adjacency import (
    AdjacencyGraph,
)


TableSet = frozenset[uuid.UUID]


def discover_connected_table_sets(
    graph: AdjacencyGraph,
) -> list[TableSet]:
    """
    Discover the elementary physical joins represented by an
    adjacency graph.

    Smart Layout discovery stores physical join topology, not every
    larger table combination that can be derived from that topology.

    Each returned item therefore contains exactly two adjacent tables.

    Larger executable table combinations are derived separately from
    approved physical joins.
    """
    discovered: set[TableSet] = set()

    for table_id in sorted(
        graph,
        key=str,
    ):
        for neighbour_id in sorted(
            graph.get(
                table_id,
                set(),
            ),
            key=str,
        ):
            if neighbour_id == table_id:
                continue

            discovered.add(
                frozenset(
                    {
                        table_id,
                        neighbour_id,
                    }
                )
            )

    return sorted(
        discovered,
        key=_table_set_sort_key,
    )


def _table_set_sort_key(
    table_set: TableSet,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(table_id)
            for table_id in table_set
        )
    )