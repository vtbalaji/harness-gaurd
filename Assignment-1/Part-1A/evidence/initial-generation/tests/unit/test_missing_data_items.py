"""Missing-input path of FR-010 to FR-027 (FR-001, FR-013, FR-050; Constitution IV).

A missing input drops the item out of both earned and available points ("No data", 0 of 0).
"""

import pytest

from gis_scorer import rules
from gis_scorer.scoring import compute_total, score_snapshot
from gis_scorer.snapshot import validate

ITEM_MAX = {
    "Piotroski F-Score": 10,
    "Altman Z-Score": 5,
    "Beneish M-Score": 5,
    "EBITDA Growth": 8,
    "Earnings Growth": 7,
    "Revenue Growth": 10,
    "Equity Growth": 5,
    "Cash Flow Quality": 5,
    "Net Profit Margin": 3,
    "Operating Margin": 4,
    "ROE": 5,
    "ROCE": 5,
    "Loss to Profit": 5,
    "Profitability Sustainability": 2,
    "Working Capital Efficiency": 5,
    "Debt Reduction": 3,
    "Current Ratio": 5,
    "Debt to Equity": 5,
}

# (dropped inputs, items that become no_data). Inputs shared by two items (net_profit_margin,
# debt_to_equity) take both items out, so the expected drop is the sum of both maxima.
MISSING_CASES = [
    pytest.param(("piotroski",), ["Piotroski F-Score"], id="fr010_missing"),
    pytest.param(("altman_z",), ["Altman Z-Score"], id="fr011_missing"),
    pytest.param(("beneish_m",), ["Beneish M-Score"], id="fr012_missing"),
    pytest.param(("ebitda_12m",), ["EBITDA Growth"], id="fr014_current_missing"),
    pytest.param(("ebitda_prior_12m",), ["EBITDA Growth"], id="fr014_prior_missing"),
    pytest.param(("net_profit_prior_12m",), ["Earnings Growth"], id="fr015_missing"),
    pytest.param(("revenue_12m",), ["Revenue Growth"], id="fr016_missing"),
    pytest.param(("equity_prior",), ["Equity Growth"], id="fr017_missing"),
    pytest.param(("ocf_to_net_profit",), ["Cash Flow Quality"], id="fr018_missing"),
    pytest.param(
        ("net_profit_margin",), ["Net Profit Margin", "Loss to Profit"], id="fr019_fr022_missing"
    ),
    pytest.param(("operating_margin",), ["Operating Margin"], id="fr020_missing"),
    pytest.param(("roe",), ["ROE"], id="fr021_roe_missing"),
    pytest.param(("roce",), ["ROCE"], id="fr021_roce_missing"),
    pytest.param(("previous_net_profit_margin",), ["Loss to Profit"], id="fr022_missing"),
    pytest.param(
        ("recent_net_profit_margins",), ["Profitability Sustainability"], id="fr023_missing"
    ),
    pytest.param(
        ("ccc_days", "ccc_days_prior", "dso_days", "dso_days_prior"),
        ["Working Capital Efficiency"],
        id="fr024_missing",
    ),
    pytest.param(("debt_to_equity_prior",), ["Debt Reduction"], id="fr025_missing"),
    pytest.param(("current_ratio",), ["Current Ratio"], id="fr026_missing"),
    pytest.param(
        ("debt_to_equity",), ["Debt to Equity", "Debt Reduction"], id="fr027_fr025_missing"
    ),
]


def _items_by_name(result):
    return {i.name: i for d in result.dimensions for i in d.items}


@pytest.mark.parametrize(("drop", "affected"), MISSING_CASES)
def test_fr010_to_fr027_missing_input_is_no_data(max_snapshot, drop, affected):
    """FR-010..FR-027 (FR-010, FR-011, FR-012, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019,
    FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-027), FR-001: a missing input
    gives status no_data, value None, 0 of 0, "No data", and lowers raw_available by the
    item's maximum.
    """
    full = score_snapshot(max_snapshot())
    result = score_snapshot(max_snapshot(*drop))
    items = _items_by_name(result)
    for name in affected:
        item = items[name]
        assert item.status == "no_data"
        assert item.value is None
        assert (item.earned, item.available) == (0, 0)
        assert item.reason == "No data"
    assert full.raw_available - result.raw_available == sum(ITEM_MAX[n] for n in affected)
    others = [i for n, i in items.items() if n not in affected]
    assert all(i.status != "no_data" for i in others)


def test_fr010_to_fr027_every_catalogue_item_has_a_missing_case():
    """FR-030: the cases above cover all 18 catalogue items."""
    covered = {name for case in MISSING_CASES for name in case.values[1]}
    assert covered == set(ITEM_MAX)


@pytest.mark.parametrize(
    ("current", "prior"),
    [
        pytest.param(None, 100, id="fr013_current_missing"),
        pytest.param(100, None, id="fr013_prior_missing"),
        pytest.param(None, None, id="fr013_both_missing"),
    ],
)
def test_fr013_missing_value_gives_missing_growth(current, prior):
    """FR-013: if either value is missing, growth is missing (not capped)."""
    outcome = rules.compute_growth(current, prior)
    assert outcome.state == "missing"
    assert outcome.pct is None
    assert outcome.cap_reason is None


def test_fr017_zero_prior_equity_is_missing():
    """FR-017: equity growth is missing when prior equity is 0."""
    item = rules.score_equity_growth(validate({"equity": 50, "equity_prior": 0}))
    assert (item.status, item.earned, item.available, item.reason) == ("no_data", 0, 0, "No data")


def test_fr018_negative_ratio_with_unknown_ttm_profit_scores_zero():
    """FR-018: ratio < 0 with net_profit_12m missing -> 0 of 5 scored (not -3, not no_data)."""
    item = rules.score_cash_flow_quality(validate({"ocf_to_net_profit": -0.1}))
    assert (item.status, item.earned, item.available) == ("scored", 0, 5)
    assert item.reason == "otherwise"


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param({"net_profit_margin": 5}, id="fr022_previous_missing"),
        pytest.param({"previous_net_profit_margin": -1}, id="fr022_current_missing"),
    ],
)
def test_fr022_either_margin_missing_is_no_data(raw):
    """FR-022: Loss -> Profit needs both margins; either missing -> no_data."""
    item = rules.score_loss_to_profit(validate(raw))
    assert (item.status, item.available, item.reason) == ("no_data", 0, "No data")


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param({}, id="fr023_absent"),
        pytest.param({"recent_net_profit_margins": None}, id="fr023_r01_null"),
        pytest.param({"recent_net_profit_margins": []}, id="fr023_r01_empty_list"),
    ],
)
def test_fr023_no_quarter_supplied_is_no_data(raw):
    """FR-023, R-01: absent, null or [] quarterly margins -> no_data, 0 of 0."""
    item = rules.score_profitability_sustainability(validate(raw))
    assert (item.status, item.earned, item.available) == ("no_data", 0, 0)
    assert item.value is None


@pytest.mark.parametrize(
    ("margins", "run"),
    [
        pytest.param([None, 5], 0, id="fr023_r01_null_first_stops_run"),
        pytest.param([5, None, 5, 5], 1, id="fr023_r01_null_element_stops_run"),
    ],
)
def test_fr023_r01_null_element_stops_the_run(margins, run):
    """FR-023, R-01: a null quarter stops the run; the item is still scored (0 of 2)."""
    item = rules.score_profitability_sustainability(
        validate({"recent_net_profit_margins": margins})
    )
    assert (item.status, item.value, item.earned, item.available) == ("scored", run, 0, 2)


def test_fr024_only_ccc_change_is_scored_with_dso_as_zero():
    """FR-024: only the CCC pair present -> scored; the DSO change counts 0, reported None."""
    item = rules.score_working_capital(validate({"ccc_days": 10, "ccc_days_prior": 100}))
    assert (item.status, item.earned, item.available) == ("scored", 3, 5)
    assert item.to_dict()["value"] == {"ccc_change": -90, "dso_change": None}


def test_fr024_only_dso_change_is_scored_with_ccc_as_zero():
    """FR-024: only the DSO pair present -> scored; the CCC change counts 0, reported None."""
    snap = validate({"dso_days": 30, "dso_days_prior": 35, "ccc_days": 10})
    item = rules.score_working_capital(snap)
    assert (item.status, item.earned, item.available) == ("scored", 2, 5)
    assert item.to_dict()["value"] == {"ccc_change": None, "dso_change": -5}


def test_fr024_neither_change_computable_is_no_data():
    """FR-024: with neither change computable the item is no_data, 0 of 0."""
    item = rules.score_working_capital(validate({"ccc_days": 10, "dso_days_prior": 5}))
    assert (item.status, item.earned, item.available, item.reason) == (
        "no_data",
        0,
        0,
        "No data",
    )


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param({"debt_to_equity": 1.0}, id="fr025_prior_missing"),
        pytest.param({"debt_to_equity_prior": 1.0}, id="fr025_current_missing"),
    ],
)
def test_fr025_either_de_missing_is_no_data(raw):
    """FR-025: Debt Reduction needs both D/E values; either missing -> no_data."""
    item = rules.score_debt_reduction(validate(raw))
    assert (item.status, item.available, item.reason) == ("no_data", 0, "No data")


def test_fr050_nothing_available_gives_total_zero():
    """FR-050: if nothing is available the total is 0."""
    assert compute_total(0, 0) == 0


def test_fr001_r01_null_input_is_no_data():
    """FR-001, R-01: an explicit null input gives the same no_data item as an absent one."""
    assert rules.score_roe(validate({"roe": None})) == rules.score_roe(validate({}))
    assert rules.score_roe(validate({})).status == "no_data"
