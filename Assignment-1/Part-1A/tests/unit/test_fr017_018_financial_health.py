"""FR-017, FR-018: Financial Health items, both sides of every boundary (SC-002)."""

import pytest

from gis_scorer.rules import FR018_NEGATIVE_POINTS, score_cash_flow_quality, score_equity_growth
from gis_scorer.snapshot import validate


@pytest.mark.parametrize(
    ("current", "growth", "points", "reason"),
    [
        pytest.param(116, 16.0, 5, "> 15", id="fr017_gt15_above"),
        pytest.param(115, 15.0, 3, ">= 10", id="fr017_gt15_strict_at"),
        pytest.param(110, 10.0, 3, ">= 10", id="fr017_ge10_at"),
        pytest.param(109, 9.0, 2, ">= 5", id="fr017_ge10_below"),
        pytest.param(105, 5.0, 2, ">= 5", id="fr017_ge5_at"),
        pytest.param(104, 4.0, 1, "> 0", id="fr017_ge5_below"),
        pytest.param(100.5, 0.5, 1, "> 0", id="fr017_gt0_above"),
        pytest.param(100, 0.0, 0, "otherwise", id="fr017_gt0_strict_at"),
        pytest.param(90, -10.0, 0, "otherwise", id="fr017_negative"),
    ],
)
def test_fr017_equity_growth_ladder(current, growth, points, reason):
    """FR-017: equity growth >15 -> 5; >=10 -> 3; >=5 -> 2; >0 -> 1; otherwise 0 (of 5)."""
    item = score_equity_growth(validate({"equity": current, "equity_prior": 100}))
    assert item.value == growth  # precondition: the derived growth is exactly as intended
    assert item.name == "Equity Growth"
    assert item.requirement == "FR-017"
    assert item.status == "scored"
    assert (item.earned, item.available, item.reason) == (points, 5, reason)


def test_fr017_negative_prior_uses_absolute_value():
    """FR-017: growth divides by |prior|; -80 vs -100 -> +20% -> 5."""
    item = score_equity_growth(validate({"equity": -80, "equity_prior": -100}))
    assert item.value == 20.0
    assert (item.earned, item.available) == (5, 5)


def test_fr017_overflowed_growth_reports_null_value():
    """FR-017, R-07: an equity growth that overflows to +inf scores 5 and reports value None."""
    item = score_equity_growth(validate({"equity": 1e308, "equity_prior": 1e-300}))
    assert item.value is None
    assert item.earned == 5
    assert item.reason == "> 15 (value outside float range)"


@pytest.mark.parametrize(
    ("ratio", "points", "reason"),
    [
        pytest.param(1.5, 5, ">= 1.5", id="fr018_ge1_5_at"),
        pytest.param(1.49, 4, ">= 1.0", id="fr018_ge1_5_below"),
        pytest.param(1.0, 4, ">= 1.0", id="fr018_ge1_0_at"),
        pytest.param(0.99, 3, ">= 0.8", id="fr018_ge1_0_below"),
        pytest.param(0.8, 3, ">= 0.8", id="fr018_ge0_8_at"),
        pytest.param(0.79, 2, ">= 0.5", id="fr018_ge0_8_below"),
        pytest.param(0.5, 2, ">= 0.5", id="fr018_ge0_5_at"),
        pytest.param(0.49, 1, "> 0", id="fr018_ge0_5_below"),
        pytest.param(0.01, 1, "> 0", id="fr018_gt0_above"),
        pytest.param(0, 0, "otherwise", id="fr018_gt0_strict_at"),
    ],
)
def test_fr018_cash_flow_quality_ladder(ratio, points, reason):
    """FR-018: OCF/net profit >=1.5 -> 5; >=1.0 -> 4; >=0.8 -> 3; >=0.5 -> 2; >0 -> 1; else 0."""
    item = score_cash_flow_quality(validate({"ocf_to_net_profit": ratio, "net_profit_12m": 10}))
    assert item.name == "Cash Flow Quality"
    assert item.requirement == "FR-018"
    assert item.status == "scored"
    assert item.value == ratio
    assert (item.earned, item.available, item.reason) == (points, 5, reason)


def test_fr018_negative_ratio_with_ttm_profit_is_minus_3():
    """FR-018: ratio < 0 with TTM net profit > 0 -> -3 (worse than 0)."""
    item = score_cash_flow_quality(validate({"ocf_to_net_profit": -0.1, "net_profit_12m": 10}))
    assert FR018_NEGATIVE_POINTS == -3
    assert item.status == "scored"
    assert (item.earned, item.available) == (-3, 5)
    assert item.reason == "< 0 with TTM net profit > 0"


@pytest.mark.parametrize(
    "net_profit",
    [pytest.param(0, id="fr018_ttm_zero"), pytest.param(-5, id="fr018_ttm_loss")],
)
def test_fr018_negative_ratio_without_ttm_profit_is_zero(net_profit):
    """FR-018: ratio < 0 when TTM net profit is not > 0 -> 0, not -3."""
    snap = validate({"ocf_to_net_profit": -0.1, "net_profit_12m": net_profit})
    item = score_cash_flow_quality(snap)
    assert (item.earned, item.available, item.reason) == (0, 5, "otherwise")
