"""Separate 0-10 valuation score (FR-060). It never affects the quality total or label."""

import operator

from gis_scorer.result import Valuation, ValuationPart
from gis_scorer.rules import REASON_NO_DATA, Ladder, apply_ladder

FR060_PE = Ladder(
    available=5,
    steps=(
        (operator.lt, 12, 5),
        (operator.lt, 18, 3),
        (operator.lt, 25, 2),
        (operator.lt, 50, 1),
    ),
    default=0,
)

FR060_PB = Ladder(
    available=3,
    steps=(
        (operator.lt, 1.5, 3),
        (operator.lt, 3.0, 2),
    ),
    default=0,
)

FR060_PEG = Ladder(
    available=2,
    steps=(
        (operator.lt, 1, 2),
        (operator.lt, 1.5, 1),
    ),
    default=0,
)

FR060_MAX = 10


def _part(name, ladder, value):
    if value is None:
        points, reason = 0, REASON_NO_DATA
    else:
        points, reason = apply_ladder(ladder, value)
    return ValuationPart(
        name=name,
        requirement="FR-060",
        value=value,
        points=points,
        available=ladder.available,
        reason=reason,
    )


def score_valuation(snapshot):
    """FR-060: P/E + P/B + PEG points (each 0 when missing), reported in that order."""
    parts = (
        _part("P/E", FR060_PE, snapshot.pe),
        _part("P/B", FR060_PB, snapshot.pb),
        _part("PEG", FR060_PEG, snapshot.peg),
    )
    return Valuation(score=sum(p.points for p in parts), max=FR060_MAX, parts=parts)
