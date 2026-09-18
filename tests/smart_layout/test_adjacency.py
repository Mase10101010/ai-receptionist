import uuid

from app.services.smart_layout.adjacency import (
    LayoutPlacement,
    build_adjacency_graph,
)
from app.services.smart_layout.geometry import (
    PlacementGeometry,
)


def make_placement(
    *,
    x: int,
    y: int,
    visible: bool = True,
) -> LayoutPlacement:
    return LayoutPlacement(
        table_id=uuid.uuid4(),
        geometry=PlacementGeometry(
            x=x,
            y=y,
            width=80,
            height=80,
        ),
        is_visible=visible,
    )


def test_empty_layout_produces_empty_graph():
    assert build_adjacency_graph([]) == {}


def test_single_table_is_preserved_as_isolated_node():
    table = make_placement(
        x=0,
        y=0,
    )

    graph = build_adjacency_graph(
        [table]
    )

    assert graph == {
        table.table_id: set(),
    }


def test_adjacent_pair_creates_bidirectional_edge():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=100,
        y=0,
    )

    graph = build_adjacency_graph(
        [first, second]
    )

    assert graph[first.table_id] == {
        second.table_id
    }
    assert graph[second.table_id] == {
        first.table_id
    }


def test_far_tables_remain_isolated():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=300,
        y=0,
    )

    graph = build_adjacency_graph(
        [first, second]
    )

    assert graph[first.table_id] == set()
    assert graph[second.table_id] == set()


def test_linear_layout_builds_expected_graph():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=100,
        y=0,
    )
    third = make_placement(
        x=200,
        y=0,
    )

    graph = build_adjacency_graph(
        [first, second, third]
    )

    assert graph[first.table_id] == {
        second.table_id
    }
    assert graph[second.table_id] == {
        first.table_id,
        third.table_id,
    }
    assert graph[third.table_id] == {
        second.table_id
    }


def test_separate_clusters_do_not_connect():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=100,
        y=0,
    )

    third = make_placement(
        x=500,
        y=0,
    )
    fourth = make_placement(
        x=600,
        y=0,
    )

    graph = build_adjacency_graph(
        [
            first,
            second,
            third,
            fourth,
        ]
    )

    assert graph[first.table_id] == {
        second.table_id
    }
    assert graph[second.table_id] == {
        first.table_id
    }

    assert graph[third.table_id] == {
        fourth.table_id
    }
    assert graph[fourth.table_id] == {
        third.table_id
    }


def test_invisible_table_is_excluded():
    first = make_placement(
        x=0,
        y=0,
    )
    hidden = make_placement(
        x=100,
        y=0,
        visible=False,
    )
    third = make_placement(
        x=200,
        y=0,
    )

    graph = build_adjacency_graph(
        [
            first,
            hidden,
            third,
        ]
    )

    assert hidden.table_id not in graph
    assert graph[first.table_id] == set()
    assert graph[third.table_id] == set()


def test_diagonal_tables_do_not_create_edge():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=100,
        y=100,
    )

    graph = build_adjacency_graph(
        [first, second]
    )

    assert graph[first.table_id] == set()
    assert graph[second.table_id] == set()


def test_graph_does_not_create_transitive_edge():
    first = make_placement(
        x=0,
        y=0,
    )
    second = make_placement(
        x=100,
        y=0,
    )
    third = make_placement(
        x=200,
        y=0,
    )

    graph = build_adjacency_graph(
        [first, second, third]
    )

    assert second.table_id in graph[
        first.table_id
    ]
    assert third.table_id in graph[
        second.table_id
    ]

    assert third.table_id not in graph[
        first.table_id
    ]
    assert first.table_id not in graph[
        third.table_id
    ]