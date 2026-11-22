"""FR-053, FR-054, FR-055: label downgrades and their reasons (research.md R-14)."""

import pytest

from gis_scorer.scoring import compute_total, decide_label, score_snapshot
from gis_scorer.snapshot import validate

BAND_80 = "Total 80 >= 70: STRONG BUY"
BAND_60 = "Total 60 >= 55: BUY"

# Inputs to drop so that a dimension has 0 available points.
DIMENSION_INPUTS = {
    "Forensic Quality": ("piotroski", "altman_z", "beneish_m"),
    "Growth": ("ebitda_12m", "net_profit_12m"),
    "Revenue Quality": ("revenue_12m",),
    "Financial Health": ("equity", "ocf_to_net_profit"),
    "Profitability": ("net_profit_margin", "operating_margin"),
    "Competitive Moat": ("roe", "roce"),
    "Turnaround": (
        "previous_net_profit_margin",
        "recent_net_profit_margins",
        "ccc_days",
        "dso_days",
        "debt_to_equity_prior",
    ),
    "Balance Sheet": ("current_ratio", "debt_to_equity"),
}


def _dims_without(max_snapshot, *dimension_names):
    drop = [key for name in dimension_names for key in DIMENSION_INPUTS[name]]
    dims = score_snapshot(max_snapshot(*drop)).dimensions
    for name in dimension_names:
        assert next(d for d in dims if d.name == name).available == 0  # precondition
    return dims


@pytest.mark.parametrize(
    "dimension",
    [
        pytest.param("Forensic Quality", id="fr053_forensic_quality"),
        pytest.param("Growth", id="fr053_growth"),
        pytest.param("Revenue Quality", id="fr053_revenue_quality"),
        pytest.param("Competitive Moat", id="fr053_competitive_moat"),
    ],
)
def test_fr053_missing_core_dimension_gives_insufficient_data(max_snapshot, dimension):
    """FR-053: a STRONG BUY with a zero-available core dimension -> INSUFFICIENT DATA.

    The dimensions come from a snapshot missing that dimension's inputs; the label inputs come
    from the complete snapshot, so FR-051 does not fire (all three forensic inputs missing would
    otherwise make the label SUSPICIOUS).
    """
    dims = _dims_without(max_snapshot, dimension)
    decision = decide_label(80, dims, validate(max_snapshot()))
    assert decision.pre_gate == "STRONG BUY"
    assert decision.final == "INSUFFICIENT DATA"
    assert decision.reasons == (BAND_80, f"Missing dimension: {dimension}")


def test_fr053_each_missing_core_dimension_listed_once_in_fr030_order(max_snapshot):
    """FR-053: one 'Missing dimension' reason per zero-available core dimension, FR-030 order."""
    dims = _dims_without(max_snapshot, "Competitive Moat", "Growth", "Revenue Quality")
    decision = decide_label(80, dims, validate(max_snapshot()))
    assert decision.final == "INSUFFICIENT DATA"
    assert decision.reasons == (
        BAND_80,
        "Missing dimension: Growth",
        "Missing dimension: Revenue Quality",
        "Missing dimension: Competitive Moat",
    )


@pytest.mark.parametrize(
    "dimension",
    [
        pytest.param("Financial Health", id="fr053_not_core_financial_health"),
        pytest.param("Profitability", id="fr053_not_core_profitability"),
        pytest.param("Turnaround", id="fr053_not_core_turnaround"),
        pytest.param("Balance Sheet", id="fr053_not_core_balance_sheet"),
    ],
)
def test_fr053_non_core_dimension_missing_does_not_downgrade(max_snapshot, dimension):
    """FR-053: only Forensic Quality, Growth, Revenue Quality and Competitive Moat count."""
    dims = _dims_without(max_snapshot, dimension)
    decision = decide_label(80, dims, validate(max_snapshot()))
    assert decision.final == "STRONG BUY"
    assert decision.reasons == (BAND_80,)


def _gate(raw, total=80):
    return decide_label(total, score_snapshot(raw).dimensions, validate(raw))


@pytest.mark.parametrize(
    ("overrides", "drop", "final", "gate_reasons"),
    [
        pytest.param({}, ("roe",), "HOLD", ("ROE missing",), id="fr054_roe_missing"),
        pytest.param({"roe": 11.99}, (), "HOLD", ("ROE below 12%",), id="fr054_roe_below_12"),
        pytest.param({"roe": 12}, (), "STRONG BUY", (), id="fr054_roe_at_12_passes"),
        pytest.param(
            {"piotroski": 3}, (), "HOLD", ("Piotroski below 4",), id="fr054_piotroski_below_4"
        ),
        pytest.param({"piotroski": 4}, (), "STRONG BUY", (), id="fr054_piotroski_at_4_passes"),
        pytest.param({}, ("piotroski",), "STRONG BUY", (), id="fr054_piotroski_missing_passes"),
        pytest.param(
            {"roe": 10, "piotroski": 3},
            (),
            "HOLD",
            ("ROE below 12%", "Piotroski below 4"),
            id="fr054_both_reasons_in_order",
        ),
    ],
)
def test_fr054_quality_gate(max_snapshot, overrides, drop, final, gate_reasons):
    """FR-054: the gate fails only on ROE missing, ROE < 12 or Piotroski < 4 -> HOLD."""
    decision = _gate(max_snapshot(*drop, **overrides))
    assert decision.pre_gate == "STRONG BUY"
    assert decision.final == final
    assert decision.reasons == (BAND_80, *gate_reasons)


def test_fr054_gate_not_evaluated_when_fr053_fired(max_snapshot):
    """FR-054 ('Otherwise'): when INSUFFICIENT DATA fires, gate reasons are not added."""
    raw = max_snapshot("roe", "roce", piotroski=3)
    decision = _gate(raw)
    assert decision.final == "INSUFFICIENT DATA"
    assert decision.reasons == (BAND_80, "Missing dimension: Competitive Moat")


def test_fr053_fr054_buy_is_downgraded_the_same_way(max_snapshot):
    """FR-053, FR-054: a BUY (total 60) is downgraded exactly like a STRONG BUY."""
    insufficient = _gate(max_snapshot("roe", "roce"), total=60)
    assert (insufficient.pre_gate, insufficient.final) == ("BUY", "INSUFFICIENT DATA")
    assert insufficient.reasons == (BAND_60, "Missing dimension: Competitive Moat")
    held = _gate(max_snapshot(roe=10), total=60)
    assert (held.pre_gate, held.final) == ("BUY", "HOLD")
    assert held.reasons == (BAND_60, "ROE below 12%")


@pytest.mark.parametrize(
    ("total", "label"),
    [
        pytest.param(50, "HOLD", id="fr053_fr054_hold_unchanged"),
        pytest.param(30, "SELL", id="fr053_fr054_sell_unchanged"),
        pytest.param(10, "STRONG SELL", id="fr053_fr054_strong_sell_unchanged"),
    ],
)
def test_fr053_fr054_non_positive_labels_never_change(max_snapshot, total, label):
    """FR-053, FR-054: HOLD, SELL and STRONG SELL are never downgraded."""
    for raw in (max_snapshot("roe", "roce"), max_snapshot(roe=10, piotroski=3)):
        decision = _gate(raw, total=total)
        assert decision.pre_gate == decision.final == label
        assert len(decision.reasons) == 1


@pytest.mark.parametrize(
    "raw_args",
    [
        pytest.param(((), {}), id="fr055_strong_buy"),
        pytest.param((("roe", "roce"), {}), id="fr055_insufficient_data"),
        pytest.param(((), {"roe": 10}), id="fr055_hold_by_gate"),
        pytest.param((("net_profit_margin",), {}), id="fr055_suspicious"),
    ],
)
def test_fr055_labels_reported_and_total_independent_of_label(max_snapshot, raw_args):
    """FR-055: pre-gate label, final label and reasons are reported; the total never changes."""
    drop, overrides = raw_args
    result = score_snapshot(max_snapshot(*drop, **overrides))
    label = result.label.to_dict()
    assert list(label) == ["pre_gate", "final", "reasons"]
    assert label["reasons"]
    assert result.total == compute_total(result.raw_earned, result.raw_available)
