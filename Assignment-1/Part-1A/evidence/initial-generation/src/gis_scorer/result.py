"""Result model (FR-070, FR-071; research.md R-06).

Every entity is a frozen dataclass. `to_dict()` builds plain dicts and lists with a fixed,
insertion-ordered key order (contracts/result.schema.json); `to_json()` is the one fixed
`json.dumps` form, so equal results always serialise to identical bytes.

An object-valued `ScoreItem.value` (FR-022, FR-024, FR-043) is stored immutably as a tuple of
`(key, value)` pairs and becomes a dict, in that pair order, in `to_dict()`.
"""

import json
from dataclasses import dataclass

STATUS_SCORED = "scored"
STATUS_NO_DATA = "no_data"
STATUS_CAPPED = "capped"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_PENALTY = "penalty"
STATUSES = (
    STATUS_SCORED,
    STATUS_NO_DATA,
    STATUS_CAPPED,
    STATUS_NOT_APPLICABLE,
    STATUS_PENALTY,
)

STRONG_BUY = "STRONG BUY"
BUY = "BUY"
HOLD = "HOLD"
SELL = "SELL"
STRONG_SELL = "STRONG SELL"
INSUFFICIENT_DATA = "INSUFFICIENT DATA"
SUSPICIOUS = "SUSPICIOUS"
LABELS = (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL, INSUFFICIENT_DATA, SUSPICIOUS)


def _plain_value(value):
    if isinstance(value, tuple):
        return {key: inner for key, inner in value}
    return value


@dataclass(frozen=True)
class ScoreItem:
    name: str
    requirement: str
    value: object
    earned: int
    available: int
    status: str
    reason: str

    def to_dict(self):
        return {
            "name": self.name,
            "requirement": self.requirement,
            "value": _plain_value(self.value),
            "earned": self.earned,
            "available": self.available,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Dimension:
    name: str
    earned: int
    available: int
    items: tuple

    def to_dict(self):
        return {
            "name": self.name,
            "earned": self.earned,
            "available": self.available,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class LabelDecision:
    pre_gate: str
    final: str
    reasons: tuple

    def to_dict(self):
        return {
            "pre_gate": self.pre_gate,
            "final": self.final,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ValuationPart:
    name: str
    requirement: str
    value: object
    points: int
    available: int
    reason: str

    def to_dict(self):
        return {
            "name": self.name,
            "requirement": self.requirement,
            "value": self.value,
            "points": self.points,
            "available": self.available,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Valuation:
    score: int
    max: int
    parts: tuple

    def to_dict(self):
        return {
            "score": self.score,
            "max": self.max,
            "parts": [part.to_dict() for part in self.parts],
        }


@dataclass(frozen=True)
class ScoreResult:
    total: int
    max: int
    raw_earned: int
    raw_available: int
    dimensions: tuple
    label: LabelDecision
    valuation: Valuation

    def to_dict(self):
        return {
            "total": self.total,
            "max": self.max,
            "raw_earned": self.raw_earned,
            "raw_available": self.raw_available,
            "dimensions": [dimension.to_dict() for dimension in self.dimensions],
            "label": self.label.to_dict(),
            "valuation": self.valuation.to_dict(),
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
