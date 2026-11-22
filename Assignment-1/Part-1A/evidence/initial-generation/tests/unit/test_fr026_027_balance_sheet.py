"""FR-026, FR-027: Balance Sheet items, both sides of every boundary (SC-002)."""

import pytest

from gis_scorer.rules import score_current_ratio, score_debt_to_equity
from gis_scorer.snapshot import validate


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(2.01, 5, "> 2.0", id="fr026_gt2_above"),
        pytest.param(2.0, 3, ">= 1.5", id="fr026_gt2_strict_at"),
        pytest.param(1.5, 3, ">= 1.5", id="fr026_ge1_5_at"),
        pytest.param(1.49, 1, ">= 1.0", id="fr026_ge1_5_below"),
        pytest.param(1.0, 1, ">= 1.0", id="fr026_ge1_0_at"),
        pytest.param(0.99, 0, "otherwise", id="fr026_ge1_0_below"),
        pytest.param(0, 0, "otherwise", id="fr026_zero"),
    ],
)
def test_fr026_current_ratio_ladder(value, points, reason):
    """FR-026: current ratio >2.0 -> 5 (strict); >=1.5 -> 3; >=1.0 -> 1; otherwise 0 (of 5)."""
    item = score_current_ratio(validate({"current_ratio": value}))
    assert item.name == "Current Ratio"
    assert item.requirement == "FR-026"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(0.49, 5, "< 0.5", id="fr027_lt0_5_below"),
        pytest.param(0.5, 3, "<= 1.0", id="fr027_lt0_5_strict_at"),
        pytest.param(1.0, 3, "<= 1.0", id="fr027_le1_0_at"),
        pytest.param(1.01, 1, "<= 2.0", id="fr027_le1_0_above"),
        pytest.param(2.0, 1, "<= 2.0", id="fr027_le2_0_at"),
        pytest.param(2.01, 0, "otherwise", id="fr027_le2_0_above"),
        pytest.param(-0.2, 5, "< 0.5", id="fr027_negative_scored_as_given"),
    ],
)
def test_fr027_debt_to_equity_ladder(value, points, reason):
    """FR-027: D/E <0.5 -> 5; <=1.0 -> 3; <=2.0 -> 1; otherwise 0 (of 5); negatives as given."""
    item = score_debt_to_equity(validate({"debt_to_equity": value}))
    assert item.name == "Debt to Equity"
    assert item.requirement == "FR-027"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)
