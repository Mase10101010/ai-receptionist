import uuid

from app.services.smart_layout.derivation import (
    derive_table_combinations,
)


def table_id() -> uuid.UUID:
    return uuid.uuid4()


def test_empty_join_set_derives_nothing():
    assert derive_table_combinations(
        []
    ) == []


def test_single_join_derives_pair():
    first = table_id()
    second = table_id()

    joins = [
        frozenset(
            {
                first,
                second,
            }
        )
    ]

    assert set(
        derive_table_combinations(
            joins
        )
    ) == {
        frozenset(
            {
                first,
                second,
            }
        )
    }


def test_linear_three_table_topology_derives_connected_combinations():
    first = table_id()
    second = table_id()
    third = table_id()

    joins = [
        frozenset(
            {
                first,
                second,
            }
        ),
        frozenset(
            {
                second,
                third,
            }
        ),
    ]

    assert set(
        derive_table_combinations(
            joins
        )
    ) == {
        frozenset(
            {
                first,
                second,
            }
        ),
        frozenset(
            {
                second,
                third,
            }
        ),
        frozenset(
            {
                first,
                second,
                third,
            }
        ),
    }


def test_disconnected_tables_are_never_combined():
    first = table_id()
    second = table_id()
    third = table_id()
    fourth = table_id()

    joins = [
        frozenset(
            {
                first,
                second,
            }
        ),
        frozenset(
            {
                third,
                fourth,
            }
        ),
    ]

    derived = set(
        derive_table_combinations(
            joins
        )
    )

    assert frozenset(
        {
            first,
            third,
        }
    ) not in derived

    assert frozenset(
        {
            first,
            second,
            third,
        }
    ) not in derived


def test_blocked_missing_edge_breaks_derivation_path():
    first = table_id()
    second = table_id()
    third = table_id()
    fourth = table_id()

    # T3 <-> T4 is intentionally absent from the approved joins.
    joins = [
        frozenset(
            {
                first,
                second,
            }
        ),
        frozenset(
            {
                second,
                third,
            }
        ),
    ]

    derived = set(
        derive_table_combinations(
            joins
        )
    )

    assert frozenset(
        {
            first,
            second,
            third,
        }
    ) in derived

    assert all(
        fourth not in combination
        for combination in derived
    )


def test_derivation_respects_maximum_size():
    tables = [
        table_id()
        for _ in range(5)
    ]

    joins = [
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
        frozenset(
            {
                tables[3],
                tables[4],
            }
        ),
    ]

    derived = derive_table_combinations(
        joins,
        max_size=4,
    )

    assert derived

    assert all(
        2 <= len(combination) <= 4
        for combination in derived
    )

    assert frozenset(
        tables
    ) not in derived


def test_duplicate_joins_do_not_duplicate_combinations():
    first = table_id()
    second = table_id()

    join = frozenset(
        {
            first,
            second,
        }
    )

    derived = derive_table_combinations(
        [
            join,
            join,
        ]
    )

    assert derived == [
        join
    ]


def test_invalid_join_shape_is_ignored():
    first = table_id()
    second = table_id()
    third = table_id()

    joins = [
        frozenset(
            {
                first,
            }
        ),
        frozenset(
            {
                first,
                second,
                third,
            }
        ),
    ]

    assert derive_table_combinations(
        joins
    ) == []


def test_invalid_maximum_size_derives_nothing():
    first = table_id()
    second = table_id()

    assert derive_table_combinations(
        [
            frozenset(
                {
                    first,
                    second,
                }
            )
        ],
        max_size=1,
    ) == []