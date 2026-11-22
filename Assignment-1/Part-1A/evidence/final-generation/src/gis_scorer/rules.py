"""Item scoring rules (research.md R-03).

Every scoring ladder is an immutable module constant named after its requirement (`FRxxx_*`),
so each threshold, operator and point value traces to one FR in spec.md (SC-006).
"""

import math
import operator
from dataclasses import dataclass

from gis_scorer.result import (
    STATUS_CAPPED,
    STATUS_NO_DATA,
    STATUS_NOT_APPLICABLE,
    STATUS_PENALTY,
    STATUS_SCORED,
    ScoreItem,
)

_OPERATOR_SYMBOLS = {
    operator.ge: ">=",
    operator.gt: ">",
    operator.le: "<=",
    operator.lt: "<",
}

REASON_OTHERWISE = "otherwise"
REASON_NO_DATA = "No data"
REASON_OVERFLOW_SUFFIX = " (value outside float range)"  # research.md R-07

GROWTH_VALUE = "value"
GROWTH_CAPPED = "capped"
GROWTH_MISSING = "missing"


@dataclass(frozen=True)
class Ladder:
    """Ordered (operator, threshold, points) steps; first match wins, else `default`."""

    available: int
    steps: tuple
    default: int


def apply_ladder(ladder, value):
    """Return (points, reason) for `value`; the reason is the matched step in ASCII."""
    for op, threshold, points in ladder.steps:
        if op(value, threshold):
            return points, f"{_OPERATOR_SYMBOLS[op]} {threshold}"
    return ladder.default, REASON_OTHERWISE


def ladder_item(name, requirement, ladder, value):
    """A 'scored' ScoreItem for `value` on `ladder`."""
    points, reason = apply_ladder(ladder, value)
    return ScoreItem(
        name=name,
        requirement=requirement,
        value=value,
        earned=points,
        available=ladder.available,
        status=STATUS_SCORED,
        reason=reason,
    )


def no_data_item(name, requirement):
    """A missing-input item: 0 of 0 with reason "No data" (Constitution IV)."""
    return ScoreItem(
        name=name,
        requirement=requirement,
        value=None,
        earned=0,
        available=0,
        status=STATUS_NO_DATA,
        reason=REASON_NO_DATA,
    )


def input_item(name, requirement, ladder, value):
    """ladder_item for a direct input, or no_data_item when the input is missing."""
    if value is None:
        return no_data_item(name, requirement)
    return ladder_item(name, requirement, ladder, value)


def _derived_item(name, requirement, ladder, value):
    """Like ladder_item for a derived value; an overflowed value is reported as None (R-07)."""
    item = ladder_item(name, requirement, ladder, value)
    if math.isfinite(value):
        return item
    return ScoreItem(
        name=name,
        requirement=requirement,
        value=None,
        earned=item.earned,
        available=item.available,
        status=STATUS_SCORED,
        reason=item.reason + REASON_OVERFLOW_SUFFIX,
    )


# --- Forensic Quality: FR-010, FR-011, FR-012 ---------------------------------------------------

FR010_PIOTROSKI = Ladder(
    available=10,
    steps=(
        (operator.ge, 8, 10),
        (operator.ge, 6, 7),
        (operator.ge, 4, 4),
        (operator.ge, 2, 2),
    ),
    default=0,
)

FR011_ALTMAN_Z = Ladder(
    available=5,
    steps=(
        (operator.gt, 2.99, 5),
        (operator.ge, 1.81, 3),
    ),
    default=0,
)

FR012_BENEISH_M = Ladder(
    available=5,
    steps=(
        (operator.lt, -2.22, 5),
        (operator.le, -1.78, 2),
    ),
    default=0,
)


def score_piotroski(snapshot):
    """FR-010 Piotroski F-score."""
    return input_item("Piotroski F-Score", "FR-010", FR010_PIOTROSKI, snapshot.piotroski)


def score_altman_z(snapshot):
    """FR-011 Altman Z-score."""
    return input_item("Altman Z-Score", "FR-011", FR011_ALTMAN_Z, snapshot.altman_z)


def score_beneish_m(snapshot):
    """FR-012 Beneish M-score."""
    return input_item("Beneish M-Score", "FR-012", FR012_BENEISH_M, snapshot.beneish_m)


# --- Growth: FR-013 to FR-016 -------------------------------------------------------------------

FR013_ROUND_DIGITS = 6
FR013_CAP_MULTIPLE = 4
FR013_CAP_PRIOR_REASON = "Capped: prior 12M <= 0"
FR013_CAP_MULTIPLE_REASON = "Capped: current 12M > 4x prior 12M"


@dataclass(frozen=True)
class GrowthOutcome:
    """FR-013 growth: `pct` is set only when `state` is 'value'."""

    pct: float | None
    state: str
    cap_reason: str | None


def compute_growth(current, prior):
    """FR-013: growth % with the 6-decimal rounding and the two cap rules (research.md R-07)."""
    if current is None or prior is None:
        return GrowthOutcome(None, GROWTH_MISSING, None)
    current = round(current, FR013_ROUND_DIGITS)
    prior = round(prior, FR013_ROUND_DIGITS)
    if prior <= 0:
        return GrowthOutcome(None, GROWTH_CAPPED, FR013_CAP_PRIOR_REASON)
    if current > 0 and current > FR013_CAP_MULTIPLE * prior:
        return GrowthOutcome(None, GROWTH_CAPPED, FR013_CAP_MULTIPLE_REASON)
    return GrowthOutcome((current - prior) / abs(prior) * 100, GROWTH_VALUE, None)


FR014_EBITDA_GROWTH = Ladder(
    available=8,
    steps=(
        (operator.ge, 20, 8),
        (operator.ge, 15, 6),
        (operator.ge, 10, 4),
        (operator.ge, 5, 2),
    ),
    default=0,
)
FR014_CAPPED_POINTS = 4

FR015_EARNINGS_GROWTH = Ladder(
    available=7,
    steps=(
        (operator.ge, 20, 7),
        (operator.ge, 10, 5),
        (operator.ge, 5, 3),
        (operator.ge, 0, 2),
    ),
    default=0,
)
FR015_CAPPED_POINTS = 3

FR016_REVENUE_GROWTH = Ladder(
    available=10,
    steps=(
        (operator.ge, 25, 10),
        (operator.ge, 15, 7),
        (operator.ge, 10, 5),
        (operator.ge, 0, 3),
    ),
    default=0,
)
FR016_CAPPED_POINTS = 5


def _growth_item(name, requirement, ladder, capped_points, outcome):
    if outcome.state == GROWTH_MISSING:
        return no_data_item(name, requirement)
    if outcome.state == GROWTH_CAPPED:
        return ScoreItem(
            name=name,
            requirement=requirement,
            value=None,
            earned=capped_points,
            available=ladder.available,
            status=STATUS_CAPPED,
            reason=outcome.cap_reason,
        )
    return _derived_item(name, requirement, ladder, outcome.pct)


def ebitda_growth(snapshot):
    """FR-013 growth of EBITDA (used by FR-014 and FR-042)."""
    return compute_growth(snapshot.ebitda_12m, snapshot.ebitda_prior_12m)


def earnings_growth(snapshot):
    """FR-013 growth of net profit (used by FR-015 and FR-041)."""
    return compute_growth(snapshot.net_profit_12m, snapshot.net_profit_prior_12m)


def revenue_growth(snapshot):
    """FR-013 growth of revenue (used by FR-016 and FR-040)."""
    return compute_growth(snapshot.revenue_12m, snapshot.revenue_prior_12m)


def score_ebitda_growth(snapshot):
    """FR-014 EBITDA growth."""
    return _growth_item(
        "EBITDA Growth",
        "FR-014",
        FR014_EBITDA_GROWTH,
        FR014_CAPPED_POINTS,
        ebitda_growth(snapshot),
    )


def score_earnings_growth(snapshot):
    """FR-015 earnings (net profit) growth."""
    return _growth_item(
        "Earnings Growth",
        "FR-015",
        FR015_EARNINGS_GROWTH,
        FR015_CAPPED_POINTS,
        earnings_growth(snapshot),
    )


def score_revenue_growth(snapshot):
    """FR-016 revenue growth."""
    return _growth_item(
        "Revenue Growth",
        "FR-016",
        FR016_REVENUE_GROWTH,
        FR016_CAPPED_POINTS,
        revenue_growth(snapshot),
    )


# --- Financial Health: FR-017, FR-018 -----------------------------------------------------------

FR017_EQUITY_GROWTH = Ladder(
    available=5,
    steps=(
        (operator.gt, 15, 5),
        (operator.ge, 10, 3),
        (operator.ge, 5, 2),
        (operator.gt, 0, 1),
    ),
    default=0,
)

FR018_CASH_FLOW = Ladder(
    available=5,
    steps=(
        (operator.ge, 1.5, 5),
        (operator.ge, 1.0, 4),
        (operator.ge, 0.8, 3),
        (operator.ge, 0.5, 2),
        (operator.gt, 0, 1),
    ),
    default=0,
)
FR018_NEGATIVE_POINTS = -3
FR018_NEGATIVE_REASON = "< 0 with TTM net profit > 0"


def score_equity_growth(snapshot):
    """FR-017 equity growth: (current - prior) / |prior| x 100, unrounded and uncapped."""
    current, prior = snapshot.equity, snapshot.equity_prior
    if current is None or prior is None or prior == 0:
        return no_data_item("Equity Growth", "FR-017")
    growth = (current - prior) / abs(prior) * 100
    return _derived_item("Equity Growth", "FR-017", FR017_EQUITY_GROWTH, growth)


def score_cash_flow_quality(snapshot):
    """FR-018 cash-flow quality, with the -3 branch for a negative ratio and TTM profit > 0.

    When TTM net profit is unknown, a negative ratio falls through to the ladder (0 points).
    """
    ratio = snapshot.ocf_to_net_profit
    if ratio is None:
        return no_data_item("Cash Flow Quality", "FR-018")
    ttm_profit = snapshot.net_profit_12m
    if ratio < 0 and ttm_profit is not None and ttm_profit > 0:
        return ScoreItem(
            name="Cash Flow Quality",
            requirement="FR-018",
            value=ratio,
            earned=FR018_NEGATIVE_POINTS,
            available=FR018_CASH_FLOW.available,
            status=STATUS_SCORED,
            reason=FR018_NEGATIVE_REASON,
        )
    return ladder_item("Cash Flow Quality", "FR-018", FR018_CASH_FLOW, ratio)


# --- Profitability and Competitive Moat: FR-019, FR-020, FR-021 ---------------------------------

FR019_NET_PROFIT_MARGIN = Ladder(
    available=3,
    steps=(
        (operator.gt, 15, 3),
        (operator.gt, 10, 2),
        (operator.gt, 0, 1),
    ),
    default=0,
)

FR020_OPERATING_MARGIN = Ladder(
    available=4,
    steps=(
        (operator.gt, 20, 4),
        (operator.gt, 15, 3),
        (operator.gt, 10, 2),
        (operator.gt, 0, 1),
    ),
    default=0,
)

FR021_RETURNS = Ladder(
    available=5,
    steps=(
        (operator.ge, 15, 5),
        (operator.ge, 12, 3),
        (operator.ge, 8, 2),
        (operator.gt, 0, 1),
    ),
    default=0,
)


def score_net_profit_margin(snapshot):
    """FR-019 net profit margin."""
    return input_item(
        "Net Profit Margin", "FR-019", FR019_NET_PROFIT_MARGIN, snapshot.net_profit_margin
    )


def score_operating_margin(snapshot):
    """FR-020 operating margin."""
    return input_item(
        "Operating Margin", "FR-020", FR020_OPERATING_MARGIN, snapshot.operating_margin
    )


def score_roe(snapshot):
    """FR-021 return on equity."""
    return input_item("ROE", "FR-021", FR021_RETURNS, snapshot.roe)


def score_roce(snapshot):
    """FR-021 return on capital employed."""
    return input_item("ROCE", "FR-021", FR021_RETURNS, snapshot.roce)


# --- Turnaround: FR-022 to FR-025 ---------------------------------------------------------------

FR022_AVAILABLE = 5
FR022_LOSS_TO_PROFIT_POINTS = 5
FR022_LOSS_TO_PROFIT_REASON = "current > 0 and previous <= 0"

FR023_SUSTAINABILITY = Ladder(
    available=2,
    steps=(
        (operator.ge, 4, 2),
        (operator.ge, 2, 1),
    ),
    default=0,
)

FR024_AVAILABLE = 5
FR024_CCC_STEPS = (
    (operator.le, -300, 5),
    (operator.le, -150, 4),
    (operator.le, -75, 3),
    (operator.le, -30, 2),
    (operator.lt, 0, 1),
)
FR024_DSO_STEPS = (
    (operator.le, -40, 5),
    (operator.le, -25, 4),
    (operator.le, -12, 3),
    (operator.le, -5, 2),
    (operator.lt, 0, 1),
)
_FR024_CCC = Ladder(available=FR024_AVAILABLE, steps=FR024_CCC_STEPS, default=0)
_FR024_DSO = Ladder(available=FR024_AVAILABLE, steps=FR024_DSO_STEPS, default=0)

FR025_DEBT_REDUCTION = Ladder(
    available=3,
    steps=(
        (operator.le, -0.5, 3),
        (operator.le, -0.2, 2),
        (operator.lt, 0, 1),
    ),
    default=0,
)
FR025_NOT_APPLICABLE_BELOW = 0.5
FR025_NOT_APPLICABLE_REASON = "Not applicable: D/E < 0.5 in both years"


def score_loss_to_profit(snapshot):
    """FR-022 loss -> profit transition: 5 when current NPM > 0 and previous NPM <= 0."""
    current = snapshot.net_profit_margin
    previous = snapshot.previous_net_profit_margin
    if current is None or previous is None:
        return no_data_item("Loss to Profit", "FR-022")
    if current > 0 and previous <= 0:
        points, reason = FR022_LOSS_TO_PROFIT_POINTS, FR022_LOSS_TO_PROFIT_REASON
    else:
        points, reason = 0, REASON_OTHERWISE
    return ScoreItem(
        name="Loss to Profit",
        requirement="FR-022",
        value=(("net_profit_margin", current), ("previous_net_profit_margin", previous)),
        earned=points,
        available=FR022_AVAILABLE,
        status=STATUS_SCORED,
        reason=reason,
    )


def profitable_run(margins):
    """FR-023: consecutive quarters, newest first, with net margin > 0 (stops at a missing one)."""
    run = 0
    for margin in margins:
        if margin is None or margin <= 0:
            break
        run += 1
    return run


def score_profitability_sustainability(snapshot):
    """FR-023 profitability sustainability; missing only when no quarter is supplied (R-01)."""
    margins = snapshot.recent_net_profit_margins
    if not margins:
        return no_data_item("Profitability Sustainability", "FR-023")
    run = profitable_run(margins)
    return ladder_item("Profitability Sustainability", "FR-023", FR023_SUSTAINABILITY, run)


def _change(current, prior):
    if current is None or prior is None:
        return None
    return current - prior


def score_working_capital(snapshot):
    """FR-024 working-capital efficiency: the better tier of the CCC and DSO changes."""
    ccc_change = _change(snapshot.ccc_days, snapshot.ccc_days_prior)
    dso_change = _change(snapshot.dso_days, snapshot.dso_days_prior)
    if ccc_change is None and dso_change is None:
        return no_data_item("Working Capital Efficiency", "FR-024")
    ccc_points, ccc_reason = apply_ladder(_FR024_CCC, 0 if ccc_change is None else ccc_change)
    dso_points, dso_reason = apply_ladder(_FR024_DSO, 0 if dso_change is None else dso_change)
    if ccc_points == 0 and dso_points == 0:
        points, reason = 0, REASON_OTHERWISE
    elif ccc_points >= dso_points:
        points, reason = ccc_points, f"CCC change {ccc_reason}"
    else:
        points, reason = dso_points, f"DSO change {dso_reason}"
    reported = []
    overflowed = False
    for change in (ccc_change, dso_change):
        if change is not None and not math.isfinite(change):
            overflowed = True
            change = None
        reported.append(change)
    if overflowed:
        reason += REASON_OVERFLOW_SUFFIX
    return ScoreItem(
        name="Working Capital Efficiency",
        requirement="FR-024",
        value=(("ccc_change", reported[0]), ("dso_change", reported[1])),
        earned=points,
        available=FR024_AVAILABLE,
        status=STATUS_SCORED,
        reason=reason,
    )


def score_debt_reduction(snapshot):
    """FR-025 debt reduction; not applicable when D/E < 0.5 in both years."""
    current, prior = snapshot.debt_to_equity, snapshot.debt_to_equity_prior
    if current is None or prior is None:
        return no_data_item("Debt Reduction", "FR-025")
    change = current - prior
    if current < FR025_NOT_APPLICABLE_BELOW and prior < FR025_NOT_APPLICABLE_BELOW:
        return ScoreItem(
            name="Debt Reduction",
            requirement="FR-025",
            value=change,
            earned=0,
            available=0,
            status=STATUS_NOT_APPLICABLE,
            reason=FR025_NOT_APPLICABLE_REASON,
        )
    return _derived_item("Debt Reduction", "FR-025", FR025_DEBT_REDUCTION, change)


# --- Balance Sheet: FR-026, FR-027 --------------------------------------------------------------

FR026_CURRENT_RATIO = Ladder(
    available=5,
    steps=(
        (operator.gt, 2.0, 5),
        (operator.ge, 1.5, 3),
        (operator.ge, 1.0, 1),
    ),
    default=0,
)

FR027_DEBT_TO_EQUITY = Ladder(
    available=5,
    steps=(
        (operator.lt, 0.5, 5),
        (operator.le, 1.0, 3),
        (operator.le, 2.0, 1),
    ),
    default=0,
)


def score_current_ratio(snapshot):
    """FR-026 current ratio."""
    return input_item("Current Ratio", "FR-026", FR026_CURRENT_RATIO, snapshot.current_ratio)


def score_debt_to_equity(snapshot):
    """FR-027 debt-to-equity level."""
    return input_item("Debt to Equity", "FR-027", FR027_DEBT_TO_EQUITY, snapshot.debt_to_equity)


# --- Penalties: FR-040 to FR-044 ----------------------------------------------------------------

FR040_REVENUE_DECLINING = -5
FR041_EARNINGS_DECLINING = -5
FR042_EBITDA_DECLINING = -5
FR043_MARGIN_COMPRESSION = -3
FR040_FR042_DECLINE_REASON = "growth < 0"
FR043_MARGIN_COMPRESSION_REASON = "net and operating margins both below year-ago"


def _penalty(name, requirement, value, points, reason):
    return ScoreItem(
        name=name,
        requirement=requirement,
        value=value,
        earned=points,
        available=0,
        status=STATUS_PENALTY,
        reason=reason,
    )


def _decline_penalty(name, requirement, points, outcome):
    """FR-040..FR-042 with FR-044: only a computed growth below 0 is penalised."""
    if outcome.state != GROWTH_VALUE or not outcome.pct < 0:
        return None
    value, reason = outcome.pct, FR040_FR042_DECLINE_REASON
    if not math.isfinite(value):
        value, reason = None, reason + REASON_OVERFLOW_SUFFIX
    return _penalty(name, requirement, value, points, reason)


def _margin_compression(snapshot):
    """FR-043: both margins strictly below their year-ago values (all four present)."""
    margins = (
        ("net_profit_margin", snapshot.net_profit_margin),
        ("net_profit_margin_year_ago", snapshot.net_profit_margin_year_ago),
        ("operating_margin", snapshot.operating_margin),
        ("operating_margin_year_ago", snapshot.operating_margin_year_ago),
    )
    if any(value is None for _, value in margins):
        return None
    npm, npm_year_ago, opm, opm_year_ago = (value for _, value in margins)
    if not (npm < npm_year_ago and opm < opm_year_ago):
        return None
    return _penalty(
        "Margin Compression",
        "FR-043",
        margins,
        FR043_MARGIN_COMPRESSION,
        FR043_MARGIN_COMPRESSION_REASON,
    )


def score_penalties(snapshot):
    """FR-040 to FR-044: the triggered penalties only, in FR order."""
    candidates = (
        _decline_penalty(
            "Revenue Declining", "FR-040", FR040_REVENUE_DECLINING, revenue_growth(snapshot)
        ),
        _decline_penalty(
            "Earnings Declining", "FR-041", FR041_EARNINGS_DECLINING, earnings_growth(snapshot)
        ),
        _decline_penalty(
            "EBITDA Declining", "FR-042", FR042_EBITDA_DECLINING, ebitda_growth(snapshot)
        ),
        _margin_compression(snapshot),
    )
    return tuple(p for p in candidates if p is not None)
