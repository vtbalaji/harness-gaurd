"""User Story 1 - Score a company and get its total (US1-AS1 ... US1-AS5)."""

from gis_scorer import score_snapshot
from gis_scorer.scoring import compute_total


def _dimension(result, name):
    return next(d for d in result.dimensions if d.name == name)


def _item(result, name):
    return next(i for d in result.dimensions for i in d.items if i.name == name)


def test_us1_as1_all_maximum_scores_100_with_no_penalty(max_snapshot):
    """US1-AS1: every input present at its maximum -> total 100, no penalty (FR-050, FR-030)."""
    result = score_snapshot(max_snapshot())
    assert result.total == 100
    assert (result.raw_earned, result.raw_available) == (97, 97)
    assert _dimension(result, "Penalties").items == ()


def test_us1_as2_forensic_quality_breakdown(max_snapshot):
    """US1-AS2: Piotroski 6, Altman Z 2.5, Beneish M -2.5 -> 7/10, 3/5, 5/5 = 15 of 20."""
    result = score_snapshot(max_snapshot(piotroski=6, altman_z=2.5, beneish_m=-2.5))
    forensic = _dimension(result, "Forensic Quality")
    points = [(i.earned, i.available) for i in forensic.items]
    assert points == [(7, 10), (3, 5), (5, 5)]  # FR-010, FR-011, FR-012
    assert (forensic.earned, forensic.available) == (15, 20)


def test_us1_as3_revenue_growth_15_percent_earns_7(max_snapshot):
    """US1-AS3: revenue 115 vs 100 -> growth 15% and 7 of 10 (FR-013, FR-016)."""
    result = score_snapshot(max_snapshot(revenue_12m=115, revenue_prior_12m=100))
    item = _item(result, "Revenue Growth")
    assert item.value == 15.0
    assert (item.earned, item.available) == (7, 10)


def test_us1_as4_zero_prior_ebitda_is_capped_without_penalty(max_snapshot):
    """US1-AS4: prior EBITDA 0 -> capped, 4 of 8, no EBITDA decline penalty (FR-014, FR-044)."""
    result = score_snapshot(max_snapshot(ebitda_prior_12m=0))
    item = _item(result, "EBITDA Growth")
    assert item.status == "capped"
    assert (item.earned, item.available) == (4, 8)
    penalties = _dimension(result, "Penalties").items
    assert "EBITDA Declining" not in [p.name for p in penalties]


def test_us1_as5_45_of_90_gives_total_50():
    """US1-AS5: raw 45 earned of 90 available -> total 50 (FR-050)."""
    assert compute_total(45, 90) == 50
