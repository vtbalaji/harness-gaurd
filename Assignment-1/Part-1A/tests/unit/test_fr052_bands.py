"""FR-052: label bands for complete data that passes the quality gate (research.md R-14)."""

import pytest

from gis_scorer.scoring import decide_label, score_snapshot
from gis_scorer.snapshot import validate


@pytest.mark.parametrize(
    ("total", "label", "reason"),
    [
        pytest.param(100, "STRONG BUY", "Total 100 >= 70: STRONG BUY", id="fr052_ge70_at_100"),
        pytest.param(70, "STRONG BUY", "Total 70 >= 70: STRONG BUY", id="fr052_ge70_at"),
        pytest.param(69, "BUY", "Total 69 >= 55: BUY", id="fr052_ge70_below"),
        pytest.param(55, "BUY", "Total 55 >= 55: BUY", id="fr052_ge55_at"),
        pytest.param(54, "HOLD", "Total 54 >= 40: HOLD", id="fr052_ge55_below"),
        pytest.param(40, "HOLD", "Total 40 >= 40: HOLD", id="fr052_ge40_at"),
        pytest.param(39, "SELL", "Total 39 >= 25: SELL", id="fr052_ge40_below"),
        pytest.param(25, "SELL", "Total 25 >= 25: SELL", id="fr052_ge25_at"),
        pytest.param(24, "STRONG SELL", "Total 24 < 25: STRONG SELL", id="fr052_ge25_below"),
        pytest.param(0, "STRONG SELL", "Total 0 < 25: STRONG SELL", id="fr052_otherwise_at_0"),
    ],
)
def test_fr052_bands(max_snapshot, total, label, reason):
    """FR-052: >=70 STRONG BUY; >=55 BUY; >=40 HOLD; >=25 SELL; otherwise STRONG SELL."""
    raw = max_snapshot()
    dims = score_snapshot(raw).dimensions
    decision = decide_label(total, dims, validate(raw))
    assert decision.pre_gate == label
    assert decision.final == label
    assert decision.reasons[0] == reason
    assert decision.reasons == (reason,)
