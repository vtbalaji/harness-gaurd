"""User Story 2 - Missing data is excluded, never zeroed (US2-AS1 ... US2-AS4)."""

import math

import pytest

from gis_scorer import SnapshotValidationError, score_snapshot


def _dimension(result, name):
    return next(d for d in result.dimensions if d.name == name)


def _item(result, name):
    return next(i for d in result.dimensions for i in d.items if i.name == name)


def test_us2_as1_missing_altman_drops_out_of_available(max_snapshot):
    """US2-AS1: no Altman Z -> 0 of 0 "No data"; Forensic Quality out of 15 (FR-011, FR-030)."""
    result = score_snapshot(max_snapshot("altman_z"))
    item = _item(result, "Altman Z-Score")
    assert (item.earned, item.available, item.reason) == (0, 0, "No data")
    forensic = _dimension(result, "Forensic Quality")
    assert forensic.available == 15
    assert forensic.earned == 15


def test_us2_as2_zero_roe_is_scored_as_a_value(max_snapshot):
    """US2-AS2: ROE exactly 0 -> scored as a real value, 0 of 5 (FR-001, FR-021)."""
    item = _item(score_snapshot(max_snapshot(roe=0)), "ROE")
    assert item.status == "scored"
    assert (item.value, item.earned, item.available) == (0, 0, 5)


def test_us2_as3_nothing_scorable_is_zero_and_suspicious(empty_snapshot):
    """US2-AS3: nothing scorable -> total 0, all 9 dimensions 0 of 0, SUSPICIOUS (FR-050/051)."""
    result = score_snapshot(empty_snapshot)
    assert result.total == 0
    assert (result.raw_earned, result.raw_available) == (0, 0)
    assert len(result.dimensions) == 9
    assert all((d.earned, d.available) == (0, 0) for d in result.dimensions)
    assert result.label.final == "SUSPICIOUS"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("piotroski", 11, id="us2_as4_out_of_range"),
        pytest.param("roe", "x", id="us2_as4_not_a_number"),
        pytest.param("altman_z", math.inf, id="us2_as4_infinite"),
    ],
)
def test_us2_as4_invalid_input_is_refused_naming_the_field(max_snapshot, field, value):
    """US2-AS4: non-number / infinite / out of range -> refused, field named, no result (FR-002)."""
    outcome = []
    with pytest.raises(SnapshotValidationError) as info:
        outcome.append(score_snapshot(max_snapshot(**{field: value})))
    assert [e.field for e in info.value.errors] == [field]
    assert outcome == []
