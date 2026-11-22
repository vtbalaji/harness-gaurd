"""FR-051: the SUSPICIOUS label and its reasons (research.md R-14)."""

import pytest

from gis_scorer.scoring import compute_total, decide_label, score_snapshot
from gis_scorer.snapshot import validate

NPM_MISSING = "Net profit margin missing"
FORENSIC_MISSING = "Piotroski, Altman Z and Beneish M all missing"


def _decide(raw, total):
    return decide_label(total, score_snapshot(raw).dimensions, validate(raw))


def test_fr051_npm_missing_is_suspicious(max_snapshot):
    """FR-051: net profit margin missing -> SUSPICIOUS, with that reason only."""
    decision = _decide(max_snapshot("net_profit_margin"), 100)
    assert decision.pre_gate == decision.final == "SUSPICIOUS"
    assert decision.reasons == (NPM_MISSING,)


def test_fr051_all_forensic_missing_is_suspicious(max_snapshot):
    """FR-051: Piotroski, Altman Z and Beneish M all missing -> SUSPICIOUS."""
    decision = _decide(max_snapshot("piotroski", "altman_z", "beneish_m"), 100)
    assert decision.pre_gate == decision.final == "SUSPICIOUS"
    assert decision.reasons == (FORENSIC_MISSING,)


def test_fr051_both_conditions_listed_in_order(max_snapshot):
    """FR-051: when both conditions hold, both reasons are listed in R-14 order."""
    raw = max_snapshot("net_profit_margin", "piotroski", "altman_z", "beneish_m")
    decision = _decide(raw, 50)
    assert decision.final == "SUSPICIOUS"
    assert decision.reasons == (NPM_MISSING, FORENSIC_MISSING)


@pytest.mark.parametrize(
    "drop",
    [
        pytest.param(("piotroski", "altman_z"), id="fr051_two_of_three_missing"),
        pytest.param(("altman_z", "beneish_m"), id="fr051_other_two_missing"),
    ],
)
def test_fr051_two_forensic_inputs_missing_is_not_suspicious(max_snapshot, drop):
    """FR-051: only two of the three forensic inputs missing -> not SUSPICIOUS."""
    decision = _decide(max_snapshot(*drop), 100)
    assert decision.pre_gate != "SUSPICIOUS"
    assert decision.final != "SUSPICIOUS"


@pytest.mark.parametrize("total", [100, 0])
def test_fr051_suspicious_whatever_the_total(max_snapshot, total):
    """FR-051: SUSPICIOUS holds at totals 100 and 0."""
    assert _decide(max_snapshot("net_profit_margin"), total).final == "SUSPICIOUS"


def test_fr051_label_does_not_change_the_total(max_snapshot):
    """FR-051, FR-055: the total is the normalised raw score, unchanged by SUSPICIOUS."""
    result = score_snapshot(max_snapshot("net_profit_margin"))
    assert result.label.final == "SUSPICIOUS"
    assert result.total == compute_total(result.raw_earned, result.raw_available)
    assert (result.raw_earned, result.raw_available) == (89, 89)
    assert result.total == 100
