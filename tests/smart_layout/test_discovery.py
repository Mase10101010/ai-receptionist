import uuid

from app.services.smart_layout.discovery import (
    MAX_COMBINATION_SIZE,
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


def test_adjacent_pair_is_discovered():
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


def test_linear_three_table_layout_discovers_connected_sets():
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
        frozenset(
            {
                first,
                second,
                third,
            }
        ),
    }


def test_disconnected_pair_is_never_invented():
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


def test_linear_four_table_set_is_rejected_as_insufficiently_cohesive():
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

    assert frozenset(
        tables
    ) not in discovered


def test_cohesive_four_table_set_is_discovered():
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

    assert frozenset(
        tables
    ) in discovered


def test_default_discovery_never_exceeds_maximum_combination_size():
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
        len(table_set)
        <= MAX_COMBINATION_SIZE
        for table_set in discovered
    )

    assert frozenset(
        tables
    ) not in discovered


def test_custom_max_size_is_respected():
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

    discovered = (
        discover_connected_table_sets(
            graph,
            max_size=2,
        )
    )

    assert discovered
    assert all(
        len(table_set) == 2
        for table_set in discovered
    )


def test_invalid_max_size_discovers_nothing():
    first = table_id()
    second = table_id()

    graph = {
        first: {second},
        second: {first},
    }

    assert discover_connected_table_sets(
        graph,
        max_size=1,
    ) == []