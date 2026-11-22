"""FR-060: the separate 0-10 valuation score, both sides of every band (SC-002)."""

import pytest

from gis_scorer.snapshot import validate
from gis_scorer.valuation import score_valuation


def _part(raw, name):
    return next(p for p in score_valuation(validate(raw)).parts if p.name == name)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(11.99, 5, "< 12", id="fr060_pe_lt12_below"),
        pytest.param(12, 3, "< 18", id="fr060_pe_lt12_strict_at"),
        pytest.param(17.99, 3, "< 18", id="fr060_pe_lt18_below"),
        pytest.param(18, 2, "< 25", id="fr060_pe_lt18_strict_at"),
        pytest.param(24.99, 2, "< 25", id="fr060_pe_lt25_below"),
        pytest.param(25, 1, "< 50", id="fr060_pe_lt25_strict_at"),
        pytest.param(49.99, 1, "< 50", id="fr060_pe_lt50_below"),
        pytest.param(50, 0, "otherwise", id="fr060_pe_lt50_strict_at"),
        pytest.param(0, 5, "< 12", id="fr060_pe_zero_is_a_value"),
        pytest.param(-8, 5, "< 12", id="fr060_pe_negative_scored_as_given"),
    ],
)
def test_fr060_pe_bands(value, points, reason):
    """FR-060: P/E <12 -> 5; <18 -> 3; <25 -> 2; <50 -> 1; else 0 (zero/negative as given)."""
    part = _part({"pe": value}, "P/E")
    assert part.requirement == "FR-060"
    assert (part.value, part.points, part.available, part.reason) == (value, points, 5, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(1.49, 3, "< 1.5", id="fr060_pb_lt1_5_below"),
        pytest.param(1.5, 2, "< 3.0", id="fr060_pb_lt1_5_strict_at"),
        pytest.param(2.99, 2, "< 3.0", id="fr060_pb_lt3_below"),
        pytest.param(3.0, 0, "otherwise", id="fr060_pb_lt3_strict_at"),
        pytest.param(0, 3, "< 1.5", id="fr060_pb_zero_is_a_value"),
    ],
)
def test_fr060_pb_bands(value, points, reason):
    """FR-060: P/B <1.5 -> 3; <3.0 -> 2; else 0 (zero is a value)."""
    part = _part({"pb": value}, "P/B")
    assert (part.value, part.points, part.available, part.reason) == (value, points, 3, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(0.99, 2, "< 1", id="fr060_peg_lt1_below"),
        pytest.param(1.0, 1, "< 1.5", id="fr060_peg_lt1_strict_at"),
        pytest.param(1.49, 1, "< 1.5", id="fr060_peg_lt1_5_below"),
        pytest.param(1.5, 0, "otherwise", id="fr060_peg_lt1_5_strict_at"),
        pytest.param(0, 2, "< 1", id="fr060_peg_zero_is_a_value"),
    ],
)
def test_fr060_peg_bands(value, points, reason):
    """FR-060: PEG <1 -> 2; <1.5 -> 1; else 0 (zero is a value)."""
    part = _part({"peg": value}, "PEG")
    assert (part.value, part.points, part.available, part.reason) == (value, points, 2, reason)


@pytest.mark.parametrize("missing", ["pe", "pb", "peg"])
def test_fr060_missing_part_scores_zero(missing):
    """FR-060: a missing part scores 0 points with value None and reason "No data"."""
    raw = {k: v for k, v in {"pe": 11, "pb": 1.4, "peg": 0.9}.items() if k != missing}
    valuation = score_valuation(validate(raw))
    part = next(
        p for p in valuation.parts if p.name == {"pe": "P/E", "pb": "P/B", "peg": "PEG"}[missing]
    )
    assert (part.value, part.points, part.reason) == (None, 0, "No data")
    assert valuation.score == 10 - part.available


def test_fr060_parts_order_sum_and_max():
    """FR-060: parts are P/E, P/B, PEG (available 5/3/2); score is their sum; max is 10."""
    valuation = score_valuation(validate({"pe": 20, "pb": 2, "peg": 1.2}))
    assert [(p.name, p.available) for p in valuation.parts] == [("P/E", 5), ("P/B", 3), ("PEG", 2)]
    assert [p.points for p in valuation.parts] == [2, 2, 1]
    assert valuation.score == 5
    assert valuation.max == 10
