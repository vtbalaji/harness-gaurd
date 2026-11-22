"""Company snapshot schema and validation (FR-001, FR-002; data-model.md §1, research.md R-05).

`validate(raw)` checks every field, collects every problem and either raises one
`SnapshotValidationError` or returns a frozen `Snapshot`, where `None` means missing.

- Explicit `None` equals an absent field; `None` elements of the quarterly list are kept as
  missing quarters (R-01).
- Booleans are never numbers; an integral float Piotroski is normalised to `int` (R-02).
- An integer too large to convert to a float is reported as not finite: it lies outside the
  float range the scoring arithmetic works in.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Snapshot:
    """A validated company snapshot. Every attribute is optional; None means missing."""

    piotroski: int | None = None
    altman_z: int | float | None = None
    beneish_m: int | float | None = None
    revenue_12m: int | float | None = None
    revenue_prior_12m: int | float | None = None
    ebitda_12m: int | float | None = None
    ebitda_prior_12m: int | float | None = None
    net_profit_12m: int | float | None = None
    net_profit_prior_12m: int | float | None = None
    equity: int | float | None = None
    equity_prior: int | float | None = None
    debt_to_equity: int | float | None = None
    debt_to_equity_prior: int | float | None = None
    current_ratio: int | float | None = None
    ocf_to_net_profit: int | float | None = None
    net_profit_margin: int | float | None = None
    operating_margin: int | float | None = None
    net_profit_margin_year_ago: int | float | None = None
    operating_margin_year_ago: int | float | None = None
    previous_net_profit_margin: int | float | None = None
    roe: int | float | None = None
    roce: int | float | None = None
    recent_net_profit_margins: tuple | None = None
    ccc_days: int | float | None = None
    ccc_days_prior: int | float | None = None
    dso_days: int | float | None = None
    dso_days_prior: int | float | None = None
    pe: int | float | None = None
    pb: int | float | None = None
    peg: int | float | None = None


FIELDS = tuple(f.name for f in fields(Snapshot))

SNAPSHOT_FIELD = "<snapshot>"
PIOTROSKI_FIELD = "piotroski"
CURRENT_RATIO_FIELD = "current_ratio"
MARGINS_FIELD = "recent_net_profit_margins"

# FR-002 / Key Entities ranges.
FR002_PIOTROSKI_MIN = 0
FR002_PIOTROSKI_MAX = 9
FR002_CURRENT_RATIO_MIN = 0
FR002_MARGINS_MAX_LENGTH = 8

MSG_NOT_OBJECT = "must be an object with string keys"
MSG_UNKNOWN = "unknown field"
MSG_NOT_NUMBER = "must be a number"
MSG_NOT_FINITE = "must be finite"
MSG_PIOTROSKI = "must be an integer from 0 to 9"
MSG_CURRENT_RATIO = "must be >= 0"
MSG_NOT_LIST = "must be a list of numbers"
MSG_TOO_LONG = "must have at most 8 elements"


@dataclass(frozen=True)
class FieldError:
    """One validation problem: the field it concerns and a fixed message."""

    field: str
    message: str


class SnapshotValidationError(ValueError):
    """Raised when a snapshot is invalid (FR-002). `errors` is never empty."""

    def __init__(self, errors):
        errors = tuple(errors)
        if not errors:
            raise ValueError("SnapshotValidationError needs at least one FieldError")
        self.errors = errors
        super().__init__("\n".join(f"{e.field}: {e.message}" for e in errors))


def _number_problem(value):
    """V3/V4: the message for a value that is not a finite number, or None if it is one."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return MSG_NOT_NUMBER
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    return None if finite else MSG_NOT_FINITE


def _check_piotroski(value, errors):
    if (problem := _number_problem(value)) is not None:
        errors.append(FieldError(PIOTROSKI_FIELD, problem))
        return None
    if value != int(value) or not FR002_PIOTROSKI_MIN <= value <= FR002_PIOTROSKI_MAX:
        errors.append(FieldError(PIOTROSKI_FIELD, MSG_PIOTROSKI))
        return None
    return int(value)


def _check_margins(value, errors):
    if not isinstance(value, list | tuple):
        errors.append(FieldError(MARGINS_FIELD, MSG_NOT_LIST))
        return None
    if len(value) > FR002_MARGINS_MAX_LENGTH:
        errors.append(FieldError(MARGINS_FIELD, MSG_TOO_LONG))
    for index, element in enumerate(value):
        if element is None:
            continue
        if (problem := _number_problem(element)) is not None:
            errors.append(FieldError(f"{MARGINS_FIELD}[{index}]", problem))
    return tuple(value)


def _check_scalar(name, value, errors):
    if (problem := _number_problem(value)) is not None:
        errors.append(FieldError(name, problem))
        return None
    if name == CURRENT_RATIO_FIELD and value < FR002_CURRENT_RATIO_MIN:
        errors.append(FieldError(name, MSG_CURRENT_RATIO))
        return None
    return value


def validate(raw):
    """Validate `raw` (data-model.md V1-V9): return a Snapshot or raise SnapshotValidationError."""
    if not isinstance(raw, Mapping):
        raise SnapshotValidationError([FieldError(SNAPSHOT_FIELD, MSG_NOT_OBJECT)])
    errors = []
    if any(not isinstance(key, str) for key in raw):
        errors.append(FieldError(SNAPSHOT_FIELD, MSG_NOT_OBJECT))
    known = set(FIELDS)
    unknown = sorted(key for key in raw if isinstance(key, str) and key not in known)
    errors.extend(FieldError(key, MSG_UNKNOWN) for key in unknown)

    values = {}
    for name in FIELDS:
        value = raw.get(name)
        if value is None:
            values[name] = None
        elif name == PIOTROSKI_FIELD:
            values[name] = _check_piotroski(value, errors)
        elif name == MARGINS_FIELD:
            values[name] = _check_margins(value, errors)
        else:
            values[name] = _check_scalar(name, value, errors)
    if errors:
        raise SnapshotValidationError(errors)
    return Snapshot(**values)
