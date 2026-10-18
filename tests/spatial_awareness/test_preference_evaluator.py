"""Tests for read-only spatial preference evaluation."""

import uuid

import pytest

from app.models.floor_feature import FloorFeature
from app.models.table_placement import TablePlacement
from app.services.spatial_intelligence.preference_evaluator import (
    SpatialPreference,
    SpatialPreferenceEvaluator,
)


def make_placement(*, floor_plan_id=None, x=0, visible=True):
    return TablePlacement(
        floor_plan_id=floor_plan_id or uuid.uuid4(),
        table_id=uuid.uuid4(),
        x=x,
        y=0,
        width=80,
        height=80,
        rotation=0,
        is_visible=visible,
    )


def make_feature(
    *,
    floor_plan_id,
    x=100,
    feature_type="window",
    visible=True,
):
    return FloorFeature(
        id=uuid.uuid4(),
        floor_plan_id=floor_plan_id,
        feature_type=feature_type,
        x=x,
        y=0,
        width=40,
        height=40,
        rotation=0,
        is_visible=visible,
    )


def evaluate(placements, features):
    return SpatialPreferenceEvaluator.evaluate(
        preference=SpatialPreference.NEAR_WINDOW,
        placements=placements,
        features=features,
    )


def test_nearest_window_is_selected():
    placement = make_placement()
    near = make_feature(
        floor_plan_id=placement.floor_plan_id,
        x=100,
    )
    far = make_feature(
        floor_plan_id=placement.floor_plan_id,
        x=300,
    )

    result = evaluate([placement], [far, near])

    assert len(result) == 1
    assert result[0].evaluable is True
    assert result[0].nearest_feature_id == near.id
    assert result[0].separation == pytest.approx(20.0)


def test_different_tables_have_different_distances():
    floor_id = uuid.uuid4()
    near_table = make_placement(floor_plan_id=floor_id, x=0)
    far_table = make_placement(floor_plan_id=floor_id, x=300)
    window = make_feature(floor_plan_id=floor_id, x=100)

    results = evaluate([near_table, far_table], [window])
    by_id = {result.table_id: result for result in results}

    assert by_id[near_table.table_id].separation == pytest.approx(20.0)
    assert by_id[far_table.table_id].separation == pytest.approx(160.0)


def test_hidden_window_is_ignored():
    placement = make_placement()
    window = make_feature(
        floor_plan_id=placement.floor_plan_id,
        visible=False,
    )

    result = evaluate([placement], [window])[0]

    assert result.evaluable is False
    assert result.nearest_feature_id is None
    assert result.separation is None


def test_other_floor_plan_is_ignored():
    placement = make_placement()
    window = make_feature(floor_plan_id=uuid.uuid4())

    result = evaluate([placement], [window])[0]

    assert result.evaluable is False
    assert result.separation is None


def test_hidden_table_is_not_evaluated():
    placement = make_placement(visible=False)
    window = make_feature(floor_plan_id=placement.floor_plan_id)

    result = evaluate([placement], [window])[0]

    assert result.evaluable is False
    assert result.separation is None


def test_non_window_features_are_ignored():
    placement = make_placement()
    wall = make_feature(
        floor_plan_id=placement.floor_plan_id,
        feature_type="wall",
    )

    result = evaluate([placement], [wall])[0]

    assert result.evaluable is False


def test_tie_break_is_deterministic():
    placement = make_placement()
    first = make_feature(
        floor_plan_id=placement.floor_plan_id,
        x=100,
    )
    second = make_feature(
        floor_plan_id=placement.floor_plan_id,
        x=100,
    )

    expected = min((first.id, second.id), key=str)

    result_a = evaluate([placement], [first, second])[0]
    result_b = evaluate([placement], [second, first])[0]

    assert result_a.nearest_feature_id == expected
    assert result_b.nearest_feature_id == expected
    assert result_a.separation == result_b.separation
