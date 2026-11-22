"""FR-040 to FR-044: decline and margin-compression penalties."""

import pytest

from gis_scorer.rules import (
    FR040_REVENUE_DECLINING,
    FR041_EARNINGS_DECLINING,
    FR042_EBITDA_DECLINING,
    FR043_MARGIN_COMPRESSION,
    compute_growth,
    score_penalties,
)
from gis_scorer.scoring import score_snapshot
from gis_scorer.snapshot import validate

# (penalty name, FR id, current field, prior field)
DECLINES = [
    pytest.param("Revenue Declining", "FR-040", "revenue_12m", "revenue_prior_12m", id="fr040"),
    pytest.param(
        "Earnings Declining", "FR-041", "net_profit_12m", "net_profit_prior_12m", id="fr041"
    ),
    pytest.param("EBITDA Declining", "FR-042", "ebitda_12m", "ebitda_prior_12m", id="fr042"),
]


def test_fr040_to_fr043_penalty_points():
    """FR-040, FR-041, FR-042, FR-043: -5, -5, -5 and -3."""
    assert FR040_REVENUE_DECLINING == -5
    assert FR041_EARNINGS_DECLINING == -5
    assert FR042_EBITDA_DECLINING == -5
    assert FR043_MARGIN_COMPRESSION == -3


@pytest.mark.parametrize(("name", "requirement", "current", "prior"), DECLINES)
def test_fr040_fr041_fr042_growth_below_zero_is_penalised(name, requirement, current, prior):
    """FR-040, FR-041, FR-042: growth slightly below 0 -> a -5 decline penalty."""
    pct = compute_growth(99.99, 100).pct
    assert pct < 0  # precondition
    penalties = score_penalties(validate({current: 99.99, prior: 100}))
    assert len(penalties) == 1
    penalty = penalties[0]
    assert penalty.name == name
    assert penalty.requirement == requirement
    assert penalty.status == "penalty"
    assert (penalty.earned, penalty.available) == (-5, 0)
    assert penalty.value == pct
    assert penalty.reason == "growth < 0"


@pytest.mark.parametrize(("name", "requirement", "current", "prior"), DECLINES)
def test_fr040_fr041_fr042_zero_growth_is_not_penalised(name, requirement, current, prior):
    """FR-040, FR-041, FR-042: growth exactly 0 is not < 0, so no penalty."""
    assert compute_growth(100, 100).pct == 0  # precondition
    assert score_penalties(validate({current: 100, prior: 100})) == ()


@pytest.mark.parametrize(("name", "requirement", "current", "prior"), DECLINES)
@pytest.mark.parametrize(
    ("current_value", "prior_value"),
    [
        pytest.param(-50, 0, id="fr044_capped_prior_zero"),
        pytest.param(-50, -10, id="fr044_capped_prior_negative"),
        pytest.param(401, 100, id="fr044_capped_above_4x"),
        pytest.param(None, 100, id="fr044_missing_current"),
        pytest.param(90, None, id="fr044_missing_prior"),
    ],
)
def test_fr044_capped_or_missing_growth_never_penalised(
    name, requirement, current, prior, current_value, prior_value
):
    """FR-044: capped or missing growth never triggers a decline penalty."""
    raw = {current: current_value, prior: prior_value}
    assert score_penalties(validate(raw)) == ()


def test_fr040_fr041_fr042_overflowed_decline_still_penalised():
    """FR-040, R-07: a growth of -inf still triggers its penalty; its value is reported None."""
    penalties = score_penalties(validate({"revenue_12m": -1e308, "revenue_prior_12m": 1e-6}))
    assert [(p.name, p.earned) for p in penalties] == [("Revenue Declining", -5)]
    assert penalties[0].value is None
    assert penalties[0].reason == "growth < 0 (value outside float range)"


MARGINS = {
    "net_profit_margin": 8,
    "net_profit_margin_year_ago": 9,
    "operating_margin": 12,
    "operating_margin_year_ago": 13,
}


def test_fr043_both_margins_below_year_ago_is_compression():
    """FR-043: NPM below year-ago AND OPM below year-ago -> Margin Compression -3."""
    penalties = score_penalties(validate(MARGINS))
    assert len(penalties) == 1
    penalty = penalties[0]
    assert penalty.name == "Margin Compression"
    assert penalty.requirement == "FR-043"
    assert penalty.status == "penalty"
    assert (penalty.earned, penalty.available) == (-3, 0)
    assert penalty.to_dict()["value"] == MARGINS
    assert list(penalty.to_dict()["value"]) == list(MARGINS)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"net_profit_margin": 9}, id="fr043_npm_equal"),
        pytest.param({"operating_margin": 13}, id="fr043_opm_equal"),
        pytest.param({"net_profit_margin": 10}, id="fr043_only_opm_below"),
        pytest.param({"operating_margin": 14}, id="fr043_only_npm_below"),
    ],
)
def test_fr043_equal_or_one_sided_is_not_compression(overrides):
    """FR-043: no penalty when either margin is equal to, or above, its year-ago value."""
    assert score_penalties(validate({**MARGINS, **overrides})) == ()


@pytest.mark.parametrize("missing", list(MARGINS))
def test_fr043_any_margin_missing_is_not_compression(missing):
    """FR-043: no penalty when any of the four margins is missing."""
    raw = {k: v for k, v in MARGINS.items() if k != missing}
    assert score_penalties(validate(raw)) == ()


def test_fr040_to_fr043_penalties_listed_in_fr_order():
    """FR-040, FR-041, FR-042, FR-043: all four penalties are listed in FR order."""
    raw = {
        "ebitda_12m": 90,
        "ebitda_prior_12m": 100,
        "net_profit_12m": 90,
        "net_profit_prior_12m": 100,
        "revenue_12m": 90,
        "revenue_prior_12m": 100,
        **MARGINS,
    }
    names = [p.requirement for p in score_penalties(validate(raw))]
    assert names == ["FR-040", "FR-041", "FR-042", "FR-043"]


def test_fr040_to_fr043_penalties_dimension_and_raw_earned(max_snapshot):
    """FR-030, FR-050, FR-040: penalties sit in the Penalties dimension and count in raw_earned."""
    clean = score_snapshot(max_snapshot())
    raw = max_snapshot(revenue_12m=98, net_profit_margin=14, operating_margin=19)
    result = score_snapshot(raw)
    penalties = result.dimensions[-1]
    assert penalties.name == "Penalties"
    assert [p.name for p in penalties.items] == ["Revenue Declining", "Margin Compression"]
    assert (penalties.earned, penalties.available) == (-8, 0)
    assert result.raw_available == clean.raw_available
    item_earned = sum(i.earned for d in result.dimensions[:-1] for i in d.items)
    assert result.raw_earned == item_earned - 8
