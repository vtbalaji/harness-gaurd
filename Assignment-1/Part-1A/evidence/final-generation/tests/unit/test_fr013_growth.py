"""FR-013: growth calculation, the cap rules and 6-decimal rounding (research.md R-07)."""

import math

import pytest

from gis_scorer.rules import compute_growth, score_ebitda_growth
from gis_scorer.snapshot import validate

CAP_PRIOR = "Capped: prior 12M <= 0"
CAP_4X = "Capped: current 12M > 4x prior 12M"


def test_fr013_growth_formula():
    """FR-013: growth % = (current - prior) / |prior| x 100; 115 vs 100 -> 15.0."""
    outcome = compute_growth(115, 100)
    assert outcome.state == "value"
    assert outcome.pct == 15.0
    assert outcome.cap_reason is None


@pytest.mark.parametrize(
    "prior",
    [pytest.param(0, id="fr013_cap_prior_zero"), pytest.param(-10, id="fr013_cap_prior_negative")],
)
def test_fr013_prior_not_positive_is_capped(prior):
    """FR-013: a prior 12M <= 0 is 'capped' and no percentage is reported."""
    outcome = compute_growth(50, prior)
    assert outcome.state == "capped"
    assert outcome.pct is None
    assert outcome.cap_reason == CAP_PRIOR


def test_fr013_current_above_4x_prior_is_capped():
    """FR-013: current > 0 and > 4 x prior is 'capped' (401 vs 100)."""
    outcome = compute_growth(401, 100)
    assert outcome.state == "capped"
    assert outcome.pct is None
    assert outcome.cap_reason == CAP_4X


def test_fr013_exactly_4x_prior_is_not_capped():
    """FR-013: exactly 4 x prior is not capped (the test is strictly greater); 400 vs 100 -> 300."""
    outcome = compute_growth(400, 100)
    assert outcome.state == "value"
    assert outcome.pct == 300.0


def test_fr013_rounding_to_6_decimals_before_cap_test():
    """FR-013, R-07: 400.0000004 rounds to 400.0 first, so it is not capped."""
    outcome = compute_growth(400.0000004, 100)
    assert outcome.state == "value"
    assert outcome.pct == 300.0


def test_fr013_just_above_4x_after_rounding_is_capped():
    """FR-013, R-07: 400.000001 survives 6-decimal rounding and is > 4x, so it is capped."""
    outcome = compute_growth(400.000001, 100)
    assert outcome.state == "capped"
    assert outcome.cap_reason == CAP_4X


def test_fr013_negative_current_against_positive_prior_is_normal_growth():
    """FR-013: negative current vs positive prior is ordinary negative growth (-50 vs 100)."""
    outcome = compute_growth(-50, 100)
    assert outcome.state == "value"
    assert outcome.pct == -150.0


def test_fr013_current_zero_is_minus_100():
    """FR-013: current 0 vs prior 100 -> -100.0, not capped."""
    outcome = compute_growth(0, 100)
    assert outcome.state == "value"
    assert outcome.pct == -100.0


def test_fr013_overflow_to_minus_infinity():
    """FR-013, R-07: -1e308 vs 1e-6 overflows to -inf; the growth is still a value."""
    outcome = compute_growth(-1e308, 1e-6)
    assert outcome.state == "value"
    assert outcome.pct == -math.inf


def test_fr013_fr014_overflowed_growth_item_reports_null_value():
    """FR-013, FR-014, R-07: an overflowed growth scores 0 and reports value None with a suffix."""
    item = score_ebitda_growth(validate({"ebitda_12m": -1e308, "ebitda_prior_12m": 1e-6}))
    assert item.status == "scored"
    assert item.value is None
    assert item.earned == 0
    assert item.available == 8
    assert item.reason.endswith("(value outside float range)")
