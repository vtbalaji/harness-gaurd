"""Dimensions, total and label (FR-030, FR-050 to FR-055); `score_snapshot` assembles a result."""

from fractions import Fraction

from gis_scorer import rules
from gis_scorer.result import (
    BUY,
    HOLD,
    INSUFFICIENT_DATA,
    SELL,
    STRONG_BUY,
    STRONG_SELL,
    SUSPICIOUS,
    Dimension,
    LabelDecision,
    ScoreResult,
)
from gis_scorer.snapshot import validate
from gis_scorer.valuation import score_valuation

# FR-030: dimensions and their item scorers, in reporting order.
FR030_DIMENSIONS = (
    (
        "Forensic Quality",
        (rules.score_piotroski, rules.score_altman_z, rules.score_beneish_m),
    ),
    ("Growth", (rules.score_ebitda_growth, rules.score_earnings_growth)),
    ("Revenue Quality", (rules.score_revenue_growth,)),
    ("Financial Health", (rules.score_equity_growth, rules.score_cash_flow_quality)),
    ("Profitability", (rules.score_net_profit_margin, rules.score_operating_margin)),
    ("Competitive Moat", (rules.score_roe, rules.score_roce)),
    (
        "Turnaround",
        (
            rules.score_loss_to_profit,
            rules.score_profitability_sustainability,
            rules.score_working_capital,
            rules.score_debt_reduction,
        ),
    ),
    ("Balance Sheet", (rules.score_current_ratio, rules.score_debt_to_equity)),
)
FR030_PENALTIES_DIMENSION = "Penalties"

FR050_PERCENT = 100
FR050_MIN_TOTAL = 0
FR050_MAX_TOTAL = 100

# FR-052: (minimum total, label), highest first; below the last threshold is STRONG SELL.
FR052_BANDS = (
    (70, STRONG_BUY),
    (55, BUY),
    (40, HOLD),
    (25, SELL),
)
FR052_DEFAULT = STRONG_SELL

FR051_NPM_MISSING_REASON = "Net profit margin missing"
FR051_FORENSIC_MISSING_REASON = "Piotroski, Altman Z and Beneish M all missing"

FR053_GATED_LABELS = (STRONG_BUY, BUY)
FR053_CORE_DIMENSIONS = ("Forensic Quality", "Growth", "Revenue Quality", "Competitive Moat")
FR053_MISSING_DIMENSION_PREFIX = "Missing dimension: "

FR054_MIN_ROE = 12
FR054_MIN_PIOTROSKI = 4
FR054_ROE_MISSING_REASON = "ROE missing"
FR054_ROE_LOW_REASON = "ROE below 12%"
FR054_PIOTROSKI_LOW_REASON = "Piotroski below 4"


def _dimension(name, items):
    items = tuple(items)
    return Dimension(
        name=name,
        earned=sum(i.earned for i in items),
        available=sum(i.available for i in items),
        items=items,
    )


def build_dimensions(snapshot):
    """FR-030: the nine dimensions, in order, each with its items and subtotals.

    The ninth, Penalties, holds the triggered FR-040 to FR-043 penalties (0 available).
    """
    dims = [
        _dimension(name, (scorer(snapshot) for scorer in scorers))
        for name, scorers in FR030_DIMENSIONS
    ]
    dims.append(_dimension(FR030_PENALTIES_DIMENSION, rules.score_penalties(snapshot)))
    return tuple(dims)


def compute_total(earned, available):
    """FR-050: earned / available x 100, rounded half to even (exactly), limited to 0-100.

    If nothing is available the total is 0.
    """
    if available == 0:
        return FR050_MIN_TOTAL
    total = round(Fraction(FR050_PERCENT * earned, available))
    return max(FR050_MIN_TOTAL, min(FR050_MAX_TOTAL, total))


def _band(total):
    for threshold, label in FR052_BANDS:
        if total >= threshold:
            return label, f"Total {total} >= {threshold}: {label}"
    lowest = FR052_BANDS[-1][0]
    return FR052_DEFAULT, f"Total {total} < {lowest}: {FR052_DEFAULT}"


def suspicious_reasons(snapshot):
    """FR-051: every SUSPICIOUS condition met, in research.md R-14 order."""
    reasons = []
    if snapshot.net_profit_margin is None:
        reasons.append(FR051_NPM_MISSING_REASON)
    forensic = (snapshot.piotroski, snapshot.altman_z, snapshot.beneish_m)
    if all(value is None for value in forensic):
        reasons.append(FR051_FORENSIC_MISSING_REASON)
    return tuple(reasons)


def missing_core_dimensions(dimensions):
    """FR-053: core dimensions with 0 available points, in FR-030 order."""
    return tuple(d.name for d in dimensions if d.name in FR053_CORE_DIMENSIONS and d.available == 0)


def quality_gate_failures(snapshot):
    """FR-054: every failed quality-gate check, in research.md R-14 order."""
    failures = []
    if snapshot.roe is None:
        failures.append(FR054_ROE_MISSING_REASON)
    elif snapshot.roe < FR054_MIN_ROE:
        failures.append(FR054_ROE_LOW_REASON)
    if snapshot.piotroski is not None and snapshot.piotroski < FR054_MIN_PIOTROSKI:
        failures.append(FR054_PIOTROSKI_LOW_REASON)
    return tuple(failures)


def decide_label(total, dimensions, snapshot):
    """FR-051 to FR-055: the pre-gate and final labels with their reasons (research.md R-14).

    SUSPICIOUS (FR-051) wins outright. Otherwise the FR-052 band is the pre-gate label; a
    STRONG BUY or BUY is downgraded to INSUFFICIENT DATA (FR-053) or, failing that check
    only, to HOLD when the quality gate fails (FR-054).
    """
    reasons = suspicious_reasons(snapshot)
    if reasons:
        return LabelDecision(pre_gate=SUSPICIOUS, final=SUSPICIOUS, reasons=reasons)
    label, band_reason = _band(total)
    if label not in FR053_GATED_LABELS:
        return LabelDecision(pre_gate=label, final=label, reasons=(band_reason,))
    missing = missing_core_dimensions(dimensions)
    if missing:
        downgrade = tuple(f"{FR053_MISSING_DIMENSION_PREFIX}{name}" for name in missing)
        return LabelDecision(
            pre_gate=label, final=INSUFFICIENT_DATA, reasons=(band_reason, *downgrade)
        )
    failures = quality_gate_failures(snapshot)
    if failures:
        return LabelDecision(pre_gate=label, final=HOLD, reasons=(band_reason, *failures))
    return LabelDecision(pre_gate=label, final=label, reasons=(band_reason,))


def score_snapshot(raw):
    """Validate a raw snapshot and score it into a ScoreResult.

    Raises SnapshotValidationError before any scoring when the snapshot is invalid (FR-002).
    """
    snapshot = validate(raw)
    dimensions = build_dimensions(snapshot)
    raw_earned = sum(d.earned for d in dimensions)
    raw_available = sum(d.available for d in dimensions)
    total = compute_total(raw_earned, raw_available)
    return ScoreResult(
        total=total,
        max=FR050_MAX_TOTAL,
        raw_earned=raw_earned,
        raw_available=raw_available,
        dimensions=dimensions,
        label=decide_label(total, dimensions, snapshot),
        valuation=score_valuation(snapshot),
    )
