from __future__ import annotations

import uuid
from collections.abc import Iterable


DEFAULT_MAX_COMBINATION_SIZE = 4

TableSet = frozenset[uuid.UUID]


def derive_table_combinations(
    joins: Iterable[TableSet],
    *,
    max_size: int = DEFAULT_MAX_COMBINATION_SIZE,
) -> list[TableSet]:
    """
    Derive executable table configurations from approved physical joins.

    Physical joins are elementary two-table edges.

    Larger configurations are valid when their tables form a connected
    set in the approved physical-join graph.

    This layer does not decide whether a physical join is AUTO,
    CONFIRMED, or BLOCKED. It receives only joins that have already
    been approved for derivation.
    """
    if max_size < 2:
        return []

    graph = _build_join_graph(
        joins
    )

    if not graph:
        return []

    derived: set[TableSet] = set()

    for start_table_id in sorted(
        graph,
        key=str,
    ):
        _expand_connected_sets(
            graph=graph,
            current=frozenset(
                {
                    start_table_id,
                }
            ),
            derived=derived,
            max_size=max_size,
        )

    return sorted(
        derived,
        key=_table_set_sort_key,
    )


def _build_join_graph(
    joins: Iterable[TableSet],
) -> dict[uuid.UUID, set[uuid.UUID]]:
    graph: dict[
        uuid.UUID,
        set[uuid.UUID],
    ] = {}

    for join in joins:
        if len(join) != 2:
            continue

        first, second = tuple(join)

        if first == second:
            continue

        graph.setdefault(
            first,
            set(),
        ).add(
            second
        )

        graph.setdefault(
            second,
            set(),
        ).add(
            first
        )

    return graph


def _expand_connected_sets(
    *,
    graph: dict[
        uuid.UUID,
        set[uuid.UUID],
    ],
    current: TableSet,
    derived: set[TableSet],
    max_size: int,
) -> None:
    if len(current) >= 2:
        derived.add(
            current
        )

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

    frontier.difference_update(
        current
    )

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

        if expanded in derived:
            continue

        _expand_connected_sets(
            graph=graph,
            current=expanded,
            derived=derived,
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