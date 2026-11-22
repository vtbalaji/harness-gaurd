"""User Story 5 - Separate valuation score (US5-AS1 ... US5-AS3)."""

from gis_scorer import score_snapshot


def test_us5_as1_cheapest_bands_give_10():
    """US5-AS1: P/E 11, P/B 1.4, PEG 0.9 -> valuation 10 (FR-060)."""
    valuation = score_snapshot({"pe": 11, "pb": 1.4, "peg": 0.9}).valuation
    assert valuation.score == 10


def test_us5_as2_dearest_bands_give_0():
    """US5-AS2: P/E 60, P/B 4, PEG 2 -> valuation 0 (FR-060)."""
    valuation = score_snapshot({"pe": 60, "pb": 4, "peg": 2}).valuation
    assert valuation.score == 0


def test_us5_as3_no_valuation_inputs_leaves_quality_unchanged(max_snapshot):
    """US5-AS3: no P/E, P/B or PEG -> valuation 0; total, dimensions and label unchanged."""
    with_valuation = score_snapshot(max_snapshot())
    without = score_snapshot(max_snapshot("pe", "pb", "peg"))
    assert with_valuation.valuation.score == 10
    assert without.valuation.score == 0
    assert without.total == with_valuation.total  # FR-060: never affects the quality total
    assert without.dimensions == with_valuation.dimensions
    assert without.label == with_valuation.label
