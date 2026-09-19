import uuid

from app.services.smart_layout.discovery import (
    discover_connected_table_sets,
)


def table_id() -> uuid.UUID:
    return uuid.uuid4()


def test_empty_graph_discovers_nothing():
    assert discover_connected_table_sets(
        {}
    ) == []


def test_isolated_table_discovers_nothing():
    first = table_id()

    graph = {
        first: set(),
    }

    assert discover_connected_table_sets(
        graph
    ) == []


def test_adjacent_pair_is_discovered_as_physical_join():
    first = table_id()
    second = table_id()

    graph = {
        first: {second},
        second: {first},
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered == {
        frozenset(
            {first, second}
        ),
    }


def test_linear_three_table_layout_discovers_only_physical_join_edges():
    first = table_id()
    second = table_id()
    third = table_id()

    graph = {
        first: {second},
        second: {
            first,
            third,
        },
        third: {second},
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered == {
        frozenset(
            {first, second}
        ),
        frozenset(
            {second, third}
        ),
    }


def test_transitive_pair_is_never_invented():
    first = table_id()
    second = table_id()
    third = table_id()

    graph = {
        first: {second},
        second: {
            first,
            third,
        },
        third: {second},
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert frozenset(
        {first, third}
    ) not in discovered


def test_separate_clusters_remain_separate():
    first = table_id()
    second = table_id()

    third = table_id()
    fourth = table_id()

    graph = {
        first: {second},
        second: {first},
        third: {fourth},
        fourth: {third},
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered == {
        frozenset(
            {first, second}
        ),
        frozenset(
            {third, fourth}
        ),
    }


def test_linear_four_table_layout_discovers_only_three_join_edges():
    tables = [
        table_id()
        for _ in range(4)
    ]

    graph = {
        tables[0]: {
            tables[1],
        },
        tables[1]: {
            tables[0],
            tables[2],
        },
        tables[2]: {
            tables[1],
            tables[3],
        },
        tables[3]: {
            tables[2],
        },
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered == {
        frozenset(
            {
                tables[0],
                tables[1],
            }
        ),
        frozenset(
            {
                tables[1],
                tables[2],
            }
        ),
        frozenset(
            {
                tables[2],
                tables[3],
            }
        ),
    }


def test_dense_layout_discovers_edges_not_multi_table_combinations():
    tables = [
        table_id()
        for _ in range(4)
    ]

    graph = {
        tables[0]: {
            tables[1],
            tables[2],
        },
        tables[1]: {
            tables[0],
            tables[3],
        },
        tables[2]: {
            tables[0],
            tables[3],
        },
        tables[3]: {
            tables[1],
            tables[2],
        },
    }

    discovered = set(
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered == {
        frozenset(
            {
                tables[0],
                tables[1],
            }
        ),
        frozenset(
            {
                tables[0],
                tables[2],
            }
        ),
        frozenset(
            {
                tables[1],
                tables[3],
            }
        ),
        frozenset(
            {
                tables[2],
                tables[3],
            }
        ),
    }

    assert all(
        len(join) == 2
        for join in discovered
    )


def test_duplicate_bidirectional_edges_are_returned_once():
    first = table_id()
    second = table_id()

    graph = {
        first: {second},
        second: {first},
    }

    discovered = (
        discover_connected_table_sets(
            graph
        )
    )

    assert len(discovered) == 1
    assert discovered[0] == frozenset(
        {
            first,
            second,
        }
    )


def test_every_discovered_item_is_a_physical_join_pair():
    tables = [
        table_id()
        for _ in range(5)
    ]

    graph = {
        tables[0]: {
            tables[1],
        },
        tables[1]: {
            tables[0],
            tables[2],
        },
        tables[2]: {
            tables[1],
            tables[3],
        },
        tables[3]: {
            tables[2],
            tables[4],
        },
        tables[4]: {
            tables[3],
        },
    }

    discovered = (
        discover_connected_table_sets(
            graph
        )
    )

    assert discovered
    assert all(
        len(join) == 2
        for join in discovered
    )