"""FR-014, FR-015, FR-016: growth items, both sides of every boundary (SC-002).

Inputs are 12M pairs against a prior of 100. Each case first asserts the derived growth sits
exactly on (or strictly below) the intended boundary, so float noise cannot move a case.
"""

import pytest

from gis_scorer.rules import (
    FR014_CAPPED_POINTS,
    FR015_CAPPED_POINTS,
    FR016_CAPPED_POINTS,
    compute_growth,
    score_earnings_growth,
    score_ebitda_growth,
    score_revenue_growth,
)
from gis_scorer.snapshot import validate

PRIOR = 100


def _precondition(current, side, boundary):
    pct = compute_growth(current, PRIOR).pct
    if side == "at":
        assert pct == boundary
    else:
        assert pct < boundary
    return pct


@pytest.mark.parametrize(
    ("current", "side", "boundary", "points", "reason"),
    [
        pytest.param(120, "at", 20, 8, ">= 20", id="fr014_ge20_at"),
        pytest.param(119.99, "below", 20, 6, ">= 15", id="fr014_ge20_below"),
        pytest.param(115, "at", 15, 6, ">= 15", id="fr014_ge15_at"),
        pytest.param(114.99, "below", 15, 4, ">= 10", id="fr014_ge15_below"),
        pytest.param(110, "at", 10, 4, ">= 10", id="fr014_ge10_at"),
        pytest.param(109.99, "below", 10, 2, ">= 5", id="fr014_ge10_below"),
        pytest.param(105, "at", 5, 2, ">= 5", id="fr014_ge5_at"),
        pytest.param(104.99, "below", 5, 0, "otherwise", id="fr014_ge5_below"),
        pytest.param(90, "below", 0, 0, "otherwise", id="fr014_negative"),
    ],
)
def test_fr014_ebitda_growth_ladder(current, side, boundary, points, reason):
    """FR-014: EBITDA growth >=20 -> 8; >=15 -> 6; >=10 -> 4; >=5 -> 2; otherwise 0 (of 8)."""
    pct = _precondition(current, side, boundary)
    item = score_ebitda_growth(validate({"ebitda_12m": current, "ebitda_prior_12m": PRIOR}))
    assert item.name == "EBITDA Growth"
    assert item.requirement == "FR-014"
    assert item.status == "scored"
    assert item.value == pct
    assert (item.earned, item.available, item.reason) == (points, 8, reason)


@pytest.mark.parametrize(
    ("current", "side", "boundary", "points", "reason"),
    [
        pytest.param(120, "at", 20, 7, ">= 20", id="fr015_ge20_at"),
        pytest.param(119.99, "below", 20, 5, ">= 10", id="fr015_ge20_below"),
        pytest.param(110, "at", 10, 5, ">= 10", id="fr015_ge10_at"),
        pytest.param(109.99, "below", 10, 3, ">= 5", id="fr015_ge10_below"),
        pytest.param(105, "at", 5, 3, ">= 5", id="fr015_ge5_at"),
        pytest.param(104.99, "below", 5, 2, ">= 0", id="fr015_ge5_below"),
        pytest.param(100, "at", 0, 2, ">= 0", id="fr015_ge0_at_zero_growth"),
        pytest.param(99.99, "below", 0, 0, "otherwise", id="fr015_ge0_below"),
    ],
)
def test_fr015_earnings_growth_ladder(current, side, boundary, points, reason):
    """FR-015: earnings growth >=20 -> 7; >=10 -> 5; >=5 -> 3; >=0 -> 2; otherwise 0 (of 7)."""
    pct = _precondition(current, side, boundary)
    snap = validate({"net_profit_12m": current, "net_profit_prior_12m": PRIOR})
    item = score_earnings_growth(snap)
    assert item.name == "Earnings Growth"
    assert item.requirement == "FR-015"
    assert item.status == "scored"
    assert item.value == pct
    assert (item.earned, item.available, item.reason) == (points, 7, reason)


@pytest.mark.parametrize(
    ("current", "side", "boundary", "points", "reason"),
    [
        pytest.param(125, "at", 25, 10, ">= 25", id="fr016_ge25_at"),
        pytest.param(124.99, "below", 25, 7, ">= 15", id="fr016_ge25_below"),
        pytest.param(115, "at", 15, 7, ">= 15", id="fr016_ge15_at"),
        pytest.param(114.99, "below", 15, 5, ">= 10", id="fr016_ge15_below"),
        pytest.param(110, "at", 10, 5, ">= 10", id="fr016_ge10_at"),
        pytest.param(109.99, "below", 10, 3, ">= 0", id="fr016_ge10_below"),
        pytest.param(100, "at", 0, 3, ">= 0", id="fr016_ge0_at"),
        pytest.param(99.99, "below", 0, 0, "otherwise", id="fr016_ge0_below"),
    ],
)
def test_fr016_revenue_growth_ladder(current, side, boundary, points, reason):
    """FR-016: revenue growth >=25 -> 10; >=15 -> 7; >=10 -> 5; >=0 -> 3; otherwise 0 (of 10)."""
    pct = _precondition(current, side, boundary)
    item = score_revenue_growth(validate({"revenue_12m": current, "revenue_prior_12m": PRIOR}))
    assert item.name == "Revenue Growth"
    assert item.requirement == "FR-016"
    assert item.status == "scored"
    assert item.value == pct
    assert (item.earned, item.available, item.reason) == (points, 10, reason)


CAP_CASES = [
    pytest.param(50, 0, "Capped: prior 12M <= 0", id="prior_zero"),
    pytest.param(50, -20, "Capped: prior 12M <= 0", id="prior_negative"),
    pytest.param(401, 100, "Capped: current 12M > 4x prior 12M", id="above_4x"),
]


@pytest.mark.parametrize(("current", "prior", "reason"), CAP_CASES)
def test_fr014_capped_ebitda_growth_earns_fixed_4_of_8(current, prior, reason):
    """FR-014, FR-013: capped EBITDA growth -> status capped, value None, 4 of 8."""
    item = score_ebitda_growth(validate({"ebitda_12m": current, "ebitda_prior_12m": prior}))
    assert FR014_CAPPED_POINTS == 4
    assert item.status == "capped"
    assert item.value is None
    assert (item.earned, item.available, item.reason) == (FR014_CAPPED_POINTS, 8, reason)


@pytest.mark.parametrize(("current", "prior", "reason"), CAP_CASES)
def test_fr015_capped_earnings_growth_earns_fixed_3_of_7(current, prior, reason):
    """FR-015, FR-013: capped earnings growth -> status capped, value None, 3 of 7."""
    snap = validate({"net_profit_12m": current, "net_profit_prior_12m": prior})
    item = score_earnings_growth(snap)
    assert FR015_CAPPED_POINTS == 3
    assert item.status == "capped"
    assert item.value is None
    assert (item.earned, item.available, item.reason) == (FR015_CAPPED_POINTS, 7, reason)


@pytest.mark.parametrize(("current", "prior", "reason"), CAP_CASES)
def test_fr016_capped_revenue_growth_earns_fixed_5_of_10(current, prior, reason):
    """FR-016, FR-013: capped revenue growth -> status capped, value None, 5 of 10."""
    item = score_revenue_growth(validate({"revenue_12m": current, "revenue_prior_12m": prior}))
    assert FR016_CAPPED_POINTS == 5
    assert item.status == "capped"
    assert item.value is None
    assert (item.earned, item.available, item.reason) == (FR016_CAPPED_POINTS, 10, reason)
