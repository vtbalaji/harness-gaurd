"""FR-010, FR-011, FR-012: Forensic Quality items, both sides of every boundary (SC-002)."""

import pytest

from gis_scorer.rules import score_altman_z, score_beneish_m, score_piotroski
from gis_scorer.snapshot import validate


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(9, 10, ">= 8", id="fr010_ge8_at_9"),
        pytest.param(8, 10, ">= 8", id="fr010_ge8_at_8"),
        pytest.param(7, 7, ">= 6", id="fr010_ge6_below_8"),
        pytest.param(6, 7, ">= 6", id="fr010_ge6_at_6"),
        pytest.param(5, 4, ">= 4", id="fr010_ge4_below_6"),
        pytest.param(4, 4, ">= 4", id="fr010_ge4_at_4"),
        pytest.param(3, 2, ">= 2", id="fr010_ge2_below_4"),
        pytest.param(2, 2, ">= 2", id="fr010_ge2_at_2"),
        pytest.param(1, 0, "otherwise", id="fr010_otherwise_below_2"),
        pytest.param(0, 0, "otherwise", id="fr010_otherwise_at_0"),
    ],
)
def test_fr010_piotroski_ladder(value, points, reason):
    """FR-010: Piotroski >=8 -> 10; >=6 -> 7; >=4 -> 4; >=2 -> 2; otherwise 0 (available 10)."""
    item = score_piotroski(validate({"piotroski": value}))
    assert item.name == "Piotroski F-Score"
    assert item.requirement == "FR-010"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 10, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(3.0, 5, "> 2.99", id="fr011_gt299_at_3_0"),
        pytest.param(2.99, 3, ">= 1.81", id="fr011_gt299_strict_at_2_99"),
        pytest.param(1.81, 3, ">= 1.81", id="fr011_ge181_at_1_81"),
        pytest.param(1.80, 0, "otherwise", id="fr011_otherwise_below_1_81"),
        pytest.param(-1.5, 0, "otherwise", id="fr011_otherwise_negative"),
    ],
)
def test_fr011_altman_z_ladder(value, points, reason):
    """FR-011: Altman Z >2.99 -> 5 (strict); >=1.81 -> 3; otherwise 0 (available 5)."""
    item = score_altman_z(validate({"altman_z": value}))
    assert item.name == "Altman Z-Score"
    assert item.requirement == "FR-011"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)


@pytest.mark.parametrize(
    ("value", "points", "reason"),
    [
        pytest.param(-2.23, 5, "< -2.22", id="fr012_lt_neg222_below"),
        pytest.param(-2.22, 2, "<= -1.78", id="fr012_lt_neg222_strict_at"),
        pytest.param(-1.78, 2, "<= -1.78", id="fr012_le_neg178_at"),
        pytest.param(-1.77, 0, "otherwise", id="fr012_otherwise_above_neg178"),
        pytest.param(0, 0, "otherwise", id="fr012_otherwise_zero"),
    ],
)
def test_fr012_beneish_m_ladder(value, points, reason):
    """FR-012: Beneish M <-2.22 -> 5 (strict); <=-1.78 -> 2; otherwise 0 (available 5)."""
    item = score_beneish_m(validate({"beneish_m": value}))
    assert item.name == "Beneish M-Score"
    assert item.requirement == "FR-012"
    assert item.status == "scored"
    assert item.value == value
    assert (item.earned, item.available, item.reason) == (points, 5, reason)
