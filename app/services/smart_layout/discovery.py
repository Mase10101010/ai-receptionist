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
    Discover unique plausible table combinations from an adjacency graph.

    Every returned combination must be connected.

    Four-table combinations must also be sufficiently cohesive:
    simple linear chains are not automatically considered plausible
    physical joins.

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
    if (
        len(current) >= 2
        and _is_cohesive_table_set(
            graph,
            current,
        )
    ):
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

        _expand_connected_set(
            graph=graph,
            current=expanded,
            discovered=discovered,
            max_size=max_size,
        )


def _is_cohesive_table_set(
    graph: AdjacencyGraph,
    table_set: TableSet,
) -> bool:
    """
    Decide whether a connected table set is cohesive enough to be
    proposed automatically as a physical table combination.

    Pairs and triples keep the existing connected-set behaviour.

    Four-table combinations require at least four internal adjacency
    edges. This rejects simple chains while preserving compact layouts
    such as 2x2 arrangements.

    Manager-confirmed rules remain authoritative elsewhere in the
    Smart Layout reconciliation layer.
    """
    size = len(table_set)

    if size <= 3:
        return True

    internal_edges = sum(
        1
        for table_id in table_set
        for neighbour_id in graph.get(
            table_id,
            set(),
        )
        if (
            neighbour_id in table_set
            and str(table_id)
            < str(neighbour_id)
        )
    )

    return internal_edges >= 4


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