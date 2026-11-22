"""FR-022, FR-023, FR-024, FR-025: Turnaround items, both sides of every boundary (SC-002)."""

import pytest

from gis_scorer.rules import (
    FR025_NOT_APPLICABLE_BELOW,
    score_debt_reduction,
    score_loss_to_profit,
    score_profitability_sustainability,
    score_working_capital,
)
from gis_scorer.snapshot import validate

# --- FR-022 Loss -> Profit -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "previous", "points"),
    [
        pytest.param(0.01, 0, 5, id="fr022_cur_pos_prev_zero"),
        pytest.param(0.01, -1, 5, id="fr022_cur_pos_prev_neg"),
        pytest.param(0, -1, 0, id="fr022_cur_zero_is_not_profit"),
        pytest.param(5, 0.01, 0, id="fr022_prev_pos_is_not_a_transition"),
    ],
)
def test_fr022_loss_to_profit(current, previous, points):
    """FR-022: 5 when current NPM > 0 and previous <= 0, otherwise 0 (of 5)."""
    snap = validate({"net_profit_margin": current, "previous_net_profit_margin": previous})
    item = score_loss_to_profit(snap)
    assert item.name == "Loss to Profit"
    assert item.requirement == "FR-022"
    assert item.status == "scored"
    assert (item.earned, item.available) == (points, 5)
    expected_reason = "current > 0 and previous <= 0" if points else "otherwise"
    assert item.reason == expected_reason
    assert item.to_dict()["value"] == {
        "net_profit_margin": current,
        "previous_net_profit_margin": previous,
    }


# --- FR-023 Profitability sustainability ------------------------------------------------------


@pytest.mark.parametrize(
    ("margins", "run", "points", "reason"),
    [
        pytest.param([1, 1, 1, 1], 4, 2, ">= 4", id="fr023_ge4_at"),
        pytest.param([8, 7, 6, 5, 4, 3, 2, 1], 8, 2, ">= 4", id="fr023_ge4_eight"),
        pytest.param([3, 2, 1], 3, 1, ">= 2", id="fr023_ge4_below"),
        pytest.param([2, 1], 2, 1, ">= 2", id="fr023_ge2_at"),
        pytest.param([5], 1, 0, "otherwise", id="fr023_ge2_below_single_quarter"),
        pytest.param([0, 5, 5], 0, 0, "otherwise", id="fr023_zero_stops_run"),
        pytest.param([5, -1, 5, 5], 1, 0, "otherwise", id="fr023_negative_stops_run"),
    ],
)
def test_fr023_profitability_sustainability(margins, run, points, reason):
    """FR-023: consecutive quarters (newest first) with NPM > 0: >=4 -> 2; >=2 -> 1; else 0."""
    item = score_profitability_sustainability(validate({"recent_net_profit_margins": margins}))
    assert item.name == "Profitability Sustainability"
    assert item.requirement == "FR-023"
    assert item.status == "scored"
    assert item.value == run
    assert (item.earned, item.available, item.reason) == (points, 2, reason)


# --- FR-024 Working-capital efficiency --------------------------------------------------------


def _wc(ccc_change, dso_change):
    """Snapshot with both changes computable (prior 0, so the change equals the current)."""
    snap = validate(
        {"ccc_days": ccc_change, "ccc_days_prior": 0, "dso_days": dso_change, "dso_days_prior": 0}
    )
    assert snap.ccc_days - snap.ccc_days_prior == ccc_change  # precondition
    assert snap.dso_days - snap.dso_days_prior == dso_change  # precondition
    return snap


@pytest.mark.parametrize(
    ("ccc_change", "points", "reason"),
    [
        pytest.param(-300, 5, "CCC change <= -300", id="fr024_ccc_le_neg300_at"),
        pytest.param(-299, 4, "CCC change <= -150", id="fr024_ccc_le_neg300_above"),
        pytest.param(-150, 4, "CCC change <= -150", id="fr024_ccc_le_neg150_at"),
        pytest.param(-149, 3, "CCC change <= -75", id="fr024_ccc_le_neg150_above"),
        pytest.param(-75, 3, "CCC change <= -75", id="fr024_ccc_le_neg75_at"),
        pytest.param(-74, 2, "CCC change <= -30", id="fr024_ccc_le_neg75_above"),
        pytest.param(-30, 2, "CCC change <= -30", id="fr024_ccc_le_neg30_at"),
        pytest.param(-29, 1, "CCC change < 0", id="fr024_ccc_le_neg30_above"),
        pytest.param(-1, 1, "CCC change < 0", id="fr024_ccc_lt0_below"),
        pytest.param(0, 0, "otherwise", id="fr024_ccc_lt0_strict_at"),
    ],
)
def test_fr024_ccc_change_ladder(ccc_change, points, reason):
    """FR-024: dCCC <=-300 -> 5; <=-150 -> 4; <=-75 -> 3; <=-30 -> 2; <0 -> 1; else 0."""
    item = score_working_capital(_wc(ccc_change, 0))
    assert item.name == "Working Capital Efficiency"
    assert item.requirement == "FR-024"
    assert item.status == "scored"
    assert (item.earned, item.available, item.reason) == (points, 5, reason)
    assert item.to_dict()["value"] == {"ccc_change": ccc_change, "dso_change": 0}


@pytest.mark.parametrize(
    ("dso_change", "points", "reason"),
    [
        pytest.param(-40, 5, "DSO change <= -40", id="fr024_dso_le_neg40_at"),
        pytest.param(-39, 4, "DSO change <= -25", id="fr024_dso_le_neg40_above"),
        pytest.param(-25, 4, "DSO change <= -25", id="fr024_dso_le_neg25_at"),
        pytest.param(-24, 3, "DSO change <= -12", id="fr024_dso_le_neg25_above"),
        pytest.param(-12, 3, "DSO change <= -12", id="fr024_dso_le_neg12_at"),
        pytest.param(-11, 2, "DSO change <= -5", id="fr024_dso_le_neg12_above"),
        pytest.param(-5, 2, "DSO change <= -5", id="fr024_dso_le_neg5_at"),
        pytest.param(-4, 1, "DSO change < 0", id="fr024_dso_le_neg5_above"),
        pytest.param(-1, 1, "DSO change < 0", id="fr024_dso_lt0_below"),
        pytest.param(0, 0, "otherwise", id="fr024_dso_lt0_strict_at"),
    ],
)
def test_fr024_dso_change_ladder(dso_change, points, reason):
    """FR-024: dDSO <=-40 -> 5; <=-25 -> 4; <=-12 -> 3; <=-5 -> 2; <0 -> 1; else 0."""
    item = score_working_capital(_wc(0, dso_change))
    assert item.status == "scored"
    assert (item.earned, item.available, item.reason) == (points, 5, reason)
    assert item.to_dict()["value"] == {"ccc_change": 0, "dso_change": dso_change}


@pytest.mark.parametrize(
    ("ccc_change", "dso_change", "points", "reason"),
    [
        pytest.param(-300, 10, 5, "CCC change <= -300", id="fr024_or_ccc_best"),
        pytest.param(10, -40, 5, "DSO change <= -40", id="fr024_or_dso_best"),
        pytest.param(-30, -25, 4, "DSO change <= -25", id="fr024_or_best_tier_of_either"),
        pytest.param(-150, -25, 4, "CCC change <= -150", id="fr024_or_tie_reports_ccc"),
    ],
)
def test_fr024_or_semantics_takes_the_best_tier(ccc_change, dso_change, points, reason):
    """FR-024: tiers are 'dCCC ... or dDSO ...', so the better of the two changes decides."""
    item = score_working_capital(_wc(ccc_change, dso_change))
    assert (item.earned, item.reason) == (points, reason)


def test_fr024_overflowed_change_reports_null_value():
    """FR-024, R-07: dCCC = +inf (1e308 vs -1e308) scores 0 and reports ccc_change None."""
    snap = validate(
        {"ccc_days": 1e308, "ccc_days_prior": -1e308, "dso_days": 10, "dso_days_prior": 10}
    )
    item = score_working_capital(snap)
    assert (item.earned, item.available) == (0, 5)
    assert item.to_dict()["value"] == {"ccc_change": None, "dso_change": 0}
    assert item.reason == "otherwise (value outside float range)"


# --- FR-025 Debt reduction --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "prior"),
    [
        pytest.param(0.4, 0.3, id="fr025_both_below_half_rising"),
        pytest.param(0.3, 0.4, id="fr025_both_below_half_falling"),
    ],
)
def test_fr025_not_applicable_when_both_below_half(current, prior):
    """FR-025: D/E < 0.5 in both years -> not applicable, 0 of 0."""
    assert FR025_NOT_APPLICABLE_BELOW == 0.5
    item = score_debt_reduction(
        validate({"debt_to_equity": current, "debt_to_equity_prior": prior})
    )
    assert item.name == "Debt Reduction"
    assert item.requirement == "FR-025"
    assert item.status == "not_applicable"
    assert (item.earned, item.available) == (0, 0)
    assert item.reason == "Not applicable: D/E < 0.5 in both years"


def test_fr025_prior_at_half_is_applicable():
    """FR-025: a prior D/E of exactly 0.5 is not < 0.5, so the item is scored."""
    item = score_debt_reduction(validate({"debt_to_equity": 0.4, "debt_to_equity_prior": 0.5}))
    assert item.status == "scored"
    assert item.available == 3


@pytest.mark.parametrize(
    ("current", "prior", "delta", "points", "reason"),
    [
        pytest.param(0.5, 1.0, -0.5, 3, "<= -0.5", id="fr025_le_neg0_5_at"),
        pytest.param(0.51, 1.0, -0.49, 2, "<= -0.2", id="fr025_le_neg0_5_above"),
        pytest.param(0.3, 0.5, -0.2, 2, "<= -0.2", id="fr025_le_neg0_2_at"),
        pytest.param(0.31, 0.5, -0.19, 1, "< 0", id="fr025_le_neg0_2_above"),
        pytest.param(0.99, 1.0, 0.99 - 1.0, 1, "< 0", id="fr025_lt0_below"),
        pytest.param(1.0, 1.0, 0.0, 0, "otherwise", id="fr025_lt0_strict_at"),
        pytest.param(1.3, 1.0, 1.3 - 1.0, 0, "otherwise", id="fr025_rising"),
    ],
)
def test_fr025_debt_reduction_ladder(current, prior, delta, points, reason):
    """FR-025: dD/E <=-0.5 -> 3; <=-0.2 -> 2; <0 -> 1; otherwise 0 (of 3)."""
    assert current - prior == delta  # precondition: the derived change is exactly as intended
    if reason == "< 0":
        assert -0.2 < delta < 0
    if reason == "otherwise" and delta:
        assert delta > 0
    item = score_debt_reduction(
        validate({"debt_to_equity": current, "debt_to_equity_prior": prior})
    )
    assert item.status == "scored"
    assert item.value == delta
    assert (item.earned, item.available, item.reason) == (points, 3, reason)


def test_fr025_overflowed_change_reports_null_value():
    """FR-025, R-07: dD/E = +inf (1e308 vs -1e308) scores 0 and reports value None."""
    snap = validate({"debt_to_equity": 1e308, "debt_to_equity_prior": -1e308})
    item = score_debt_reduction(snap)
    assert (item.earned, item.available, item.status) == (0, 3, "scored")
    assert item.value is None
    assert item.reason == "otherwise (value outside float range)"
