"""User Story 3 - Get a recommendation label I can trust (US3-AS1 ... US3-AS5)."""

import pytest

from gis_scorer import score_snapshot
from gis_scorer.scoring import decide_label
from gis_scorer.snapshot import validate


def _label(raw, total):
    return decide_label(total, score_snapshot(raw).dimensions, validate(raw))


@pytest.mark.parametrize(
    ("total", "label"),
    [
        (70, "STRONG BUY"),
        (69, "BUY"),
        (55, "BUY"),
        (54, "HOLD"),
        (40, "HOLD"),
        (39, "SELL"),
        (25, "SELL"),
        (24, "STRONG SELL"),
    ],
)
def test_us3_as1_band_labels_for_complete_data(max_snapshot, total, label):
    """US3-AS1: totals 70, 69, 55, 54, 40, 39, 25, 24 with complete data -> bands (FR-052)."""
    decision = _label(max_snapshot(), total)
    assert decision.final == label


def test_us3_as2_no_roe_or_roce_gives_insufficient_data(max_snapshot):
    """US3-AS2: total 80 with no ROE and no ROCE -> INSUFFICIENT DATA naming the dimension."""
    decision = _label(max_snapshot("roe", "roce"), 80)
    assert decision.final == "INSUFFICIENT DATA"  # FR-053
    assert any("Competitive Moat" in reason for reason in decision.reasons)


def test_us3_as3_roe_10_fails_the_gate(max_snapshot):
    """US3-AS3: total 80, complete data, ROE 10% -> HOLD, reason ROE below 12% (FR-054)."""
    decision = _label(max_snapshot(roe=10), 80)
    assert decision.final == "HOLD"
    assert "ROE below 12%" in decision.reasons


@pytest.mark.parametrize("total", [100, 10])
def test_us3_as4_no_net_profit_margin_is_suspicious(max_snapshot, total):
    """US3-AS4: no net profit margin -> SUSPICIOUS whatever the total (FR-051)."""
    raw = max_snapshot("net_profit_margin")
    assert score_snapshot(raw).label.final == "SUSPICIOUS"
    assert _label(raw, total).final == "SUSPICIOUS"


def test_us3_as5_gates_never_touch_a_sell(max_snapshot):
    """US3-AS5: total 30 with ROE and ROCE missing stays SELL (FR-053 only downgrades BUYs)."""
    decision = _label(max_snapshot("roe", "roce"), 30)
    assert decision.pre_gate == decision.final == "SELL"
