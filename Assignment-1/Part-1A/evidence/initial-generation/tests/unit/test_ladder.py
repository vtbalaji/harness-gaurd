"""Research R-03 ladder primitive (used by FR-010 to FR-060 scoring ladders)."""

import dataclasses
import operator

import pytest

from gis_scorer.rules import Ladder, apply_ladder, ladder_item

LADDER = Ladder(
    available=10,
    steps=(
        (operator.ge, 8, 10),
        (operator.gt, 5, 7),
        (operator.le, -3, 4),
        (operator.lt, 0, 2),
    ),
    default=1,
)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(9, 10, ">= 8", id="ge_above"),
        pytest.param(8, 10, ">= 8", id="ge_at"),
        pytest.param(7.99, 7, "> 5", id="ge_below_falls_to_gt"),
        pytest.param(5.01, 7, "> 5", id="gt_above"),
        pytest.param(5, 1, "otherwise", id="gt_at_is_not_matched"),
        pytest.param(-3, 4, "<= -3", id="le_at"),
        pytest.param(-2.99, 2, "< 0", id="le_above_falls_to_lt"),
        pytest.param(-0.01, 2, "< 0", id="lt_below"),
        pytest.param(0, 1, "otherwise", id="lt_at_is_not_matched"),
    ],
)
def test_ladder_operators_at_and_around_thresholds(value, points, reason):
    """SC-002, R-03: each operator holds exactly at its threshold; first match wins; default."""
    assert apply_ladder(LADDER, value) == (points, reason)


def test_ladder_first_match_wins_top_down():
    """SC-002, R-03: steps are evaluated top-down; an earlier matching step beats a later one."""
    overlapping = Ladder(available=5, steps=((operator.ge, 0, 5), (operator.ge, 10, 3)), default=0)
    assert apply_ladder(overlapping, 20) == (5, ">= 0")


def test_ladder_float_threshold_reason_format():
    """SC-002, R-03: reasons are ASCII with the threshold as written ('> 2.99', '< -2.22')."""
    ladder = Ladder(available=5, steps=((operator.gt, 2.99, 5), (operator.lt, -2.22, 1)), default=0)
    assert apply_ladder(ladder, 3.0) == (5, "> 2.99")
    assert apply_ladder(ladder, -3) == (1, "< -2.22")
    assert apply_ladder(ladder, 0) == (0, "otherwise")


def test_ladder_is_immutable():
    """SC-002, R-03: a Ladder is frozen and its steps are a tuple."""
    assert isinstance(LADDER.steps, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        LADDER.default = 3


def test_ladder_item_builds_a_scored_item():
    """SC-002, R-03: ladder_item applies the ladder and builds a 'scored' ScoreItem."""
    item = ladder_item("Example", "FR-010", LADDER, 8)
    assert item.name == "Example"
    assert item.requirement == "FR-010"
    assert item.value == 8
    assert item.earned == 10
    assert item.available == 10
    assert item.status == "scored"
    assert item.reason == ">= 8"
