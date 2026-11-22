"""FR-050: total = earned / available x 100, rounded half to even, limited to 0-100."""

import pytest

from gis_scorer.scoring import compute_total


@pytest.mark.parametrize(
    ("earned", "available", "total"),
    [
        pytest.param(45, 90, 50, id="fr050_half"),
        pytest.param(97, 97, 100, id="fr050_full"),
        pytest.param(29, 40, 72, id="fr050_tie_72_5_to_even_72"),
        pytest.param(147, 200, 74, id="fr050_tie_73_5_to_even_74"),
        pytest.param(1, 3, 33, id="fr050_round_down"),
        pytest.param(2, 3, 67, id="fr050_round_up"),
        pytest.param(-5, 10, 0, id="fr050_clamped_at_0"),
    ],
)
def test_fr050_total(earned, available, total):
    """FR-050, US1-AS5: normalised total with exact half-to-even rounding and a 0 floor."""
    result = compute_total(earned, available)
    assert result == total
    assert type(result) is int


def test_fr050_us1_as5_45_of_90_is_50():
    """US1-AS5 / FR-050: raw 45 of 90 -> total 50."""
    assert compute_total(45, 90) == 50
