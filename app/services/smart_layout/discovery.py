from __future__ import annotations

import uuid

from app.services.smart_layout.adjacency import (
    AdjacencyGraph,
)


MAX_COMBINATION_SIZE = 4


TableSet = frozenset[uuid.UUID]


def discover_connected_table_sets(
    graph: AdjacencyGraph,
    *,
    max_size: int = MAX_COMBINATION_SIZE,
) -> list[TableSet]:
    """
    Discover unique connected table sets from an adjacency graph.

    Only combinations containing at least two tables are returned.
    Discovery is bounded by max_size and never generates arbitrary
    disconnected subsets.
    """
    if max_size < 2:
        return []

    discovered: set[TableSet] = set()

    for start_table_id in sorted(
        graph,
        key=str,
    ):
        _expand_connected_set(
            graph=graph,
            current=frozenset(
                {start_table_id}
            ),
            discovered=discovered,
            max_size=max_size,
        )

    return sorted(
        discovered,
        key=_table_set_sort_key,
    )


def _expand_connected_set(
    *,
    graph: AdjacencyGraph,
    current: TableSet,
    discovered: set[TableSet],
    max_size: int,
) -> None:
    if len(current) >= 2:
        discovered.add(current)

    if len(current) >= max_size:
        return

    frontier: set[uuid.UUID] = set()

    for table_id in current:
        frontier.update(
            graph.get(
                table_id,
                set(),
            )
        )

    frontier.difference_update(current)

    for neighbour_id in sorted(
        frontier,
        key=str,
    ):
        expanded = frozenset(
            {
                *current,
                neighbour_id,
            }
        )

        if (
            len(expanded) >= 2
            and expanded in discovered
        ):
            continue

        _expand_connected_set(
            graph=graph,
            current=expanded,
            discovered=discovered,
            max_size=max_size,
        )


def _table_set_sort_key(
    table_set: TableSet,
) -> tuple[int, tuple[str, ...]]:
    return (
        len(table_set),
        tuple(
            sorted(
                str(table_id)
                for table_id in table_set
            )
        ),
    )