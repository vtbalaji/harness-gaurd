"""FR-019, FR-020, FR-021: Profitability and Competitive Moat items (SC-002)."""

import pytest

from gis_scorer.rules import score_net_profit_margin, score_operating_margin, score_roce, score_roe
from gis_scorer.snapshot import validate


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(15.01, 3, "> 15", id="fr019_gt15_above"),
        pytest.param(15, 2, "> 10", id="fr019_gt15_strict_at"),
        pytest.param(10.01, 2, "> 10", id="fr019_gt10_above"),
        pytest.param(10, 1, "> 0", id="fr019_gt10_strict_at"),
        pytest.param(0.01, 1, "> 0", id="fr019_gt0_above"),
        pytest.param(0, 0, "otherwise", id="fr019_gt0_strict_at"),
        pytest.param(-3, 0, "otherwise", id="fr019_negative"),
    ],
)
def test_fr019_net_profit_margin_ladder(value, points, reason):
    """FR-019: NPM >15 -> 3; >10 -> 2; >0 -> 1; otherwise 0 (of 3)."""
    item = score_net_profit_margin(validate({"net_profit_margin": value}))
    assert item.name == "Net Profit Margin"
    assert item.requirement == "FR-019"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 3, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(20.01, 4, "> 20", id="fr020_gt20_above"),
        pytest.param(20, 3, "> 15", id="fr020_gt20_strict_at"),
        pytest.param(15.01, 3, "> 15", id="fr020_gt15_above"),
        pytest.param(15, 2, "> 10", id="fr020_gt15_strict_at"),
        pytest.param(10.01, 2, "> 10", id="fr020_gt10_above"),
        pytest.param(10, 1, "> 0", id="fr020_gt10_strict_at"),
        pytest.param(0.01, 1, "> 0", id="fr020_gt0_above"),
        pytest.param(0, 0, "otherwise", id="fr020_gt0_strict_at"),
    ],
)
def test_fr020_operating_margin_ladder(value, points, reason):
    """FR-020: OPM >20 -> 4; >15 -> 3; >10 -> 2; >0 -> 1; otherwise 0 (of 4)."""
    item = score_operating_margin(validate({"operating_margin": value}))
    assert item.name == "Operating Margin"
    assert item.requirement == "FR-020"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 4, reason)


RETURNS_CASES = [
    pytest.param(15, 5, ">= 15", id="fr021_ge15_at"),
    pytest.param(14.99, 3, ">= 12", id="fr021_ge15_below"),
    pytest.param(12, 3, ">= 12", id="fr021_ge12_at"),
    pytest.param(11.99, 2, ">= 8", id="fr021_ge12_below"),
    pytest.param(8, 2, ">= 8", id="fr021_ge8_at"),
    pytest.param(7.99, 1, "> 0", id="fr021_ge8_below"),
    pytest.param(0.01, 1, "> 0", id="fr021_gt0_above"),
    pytest.param(0, 0, "otherwise", id="fr021_gt0_strict_at_zero_is_scored"),
    pytest.param(-2, 0, "otherwise", id="fr021_negative"),
]


@pytest.mark.parametrize(("value", "points", "reason"), RETURNS_CASES)
def test_fr021_roe_ladder(value, points, reason):
    """FR-021, FR-001: ROE >=15 -> 5; >=12 -> 3; >=8 -> 2; >0 -> 1; else 0; 0 is scored."""
    item = score_roe(validate({"roe": value}))
    assert item.name == "ROE"
    assert item.requirement == "FR-021"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)


@pytest.mark.parametrize(("value", "points", "reason"), RETURNS_CASES)
def test_fr021_roce_ladder(value, points, reason):
    """FR-021, FR-001: ROCE >=15 -> 5; >=12 -> 3; >=8 -> 2; >0 -> 1; else 0; 0 is scored."""
    item = score_roce(validate({"roce": value}))
    assert item.name == "ROCE"
    assert item.requirement == "FR-021"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)
