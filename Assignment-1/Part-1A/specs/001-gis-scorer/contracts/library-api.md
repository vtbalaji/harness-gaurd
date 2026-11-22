# Contract: Python library API (`gis_scorer`)

**Requirements**: FR-001–FR-003, FR-070, FR-071 | **Entities**: [../data-model.md](../data-model.md)

## Public surface

The public API consists of the names below, all exported from `gis_scorer/__init__.py`. Everything
else is internal and may change. Tests may still import internals such as `gis_scorer.rules` and
`gis_scorer.scoring` for unit-level boundary checks.

```python
def score_snapshot(snapshot: Mapping[str, object]) -> ScoreResult: ...

class ScoreResult:            # frozen dataclass
    total: int
    max: int                  # always 100
    raw_earned: int
    raw_available: int
    dimensions: tuple[Dimension, ...]
    label: LabelDecision
    valuation: Valuation
    def to_dict(self) -> dict[str, object]: ...
    def to_json(self) -> str: ...

class SnapshotValidationError(ValueError):
    errors: tuple[FieldError, ...]

class FieldError:             # frozen dataclass
    field: str
    message: str

__version__: str
```

`Dimension`, `ScoreItem`, `LabelDecision`, `Valuation` and `ValuationPart` are importable from
`gis_scorer.result` for type hints.

## Behaviour

| # | Guarantee | Source |
|---|---|---|
| L1 | `score_snapshot` validates first. On any invalid input it raises `SnapshotValidationError`, listing every bad field, and returns nothing. | FR-002, R-05 |
| L2 | A key that is absent (or, provisionally, `None`) is missing. `0` and negative numbers are scored as values. | FR-001, R-01 |
| L3 | `score_snapshot` is pure: no I/O, no clock, no environment, no randomness, and no mutation of the argument. | FR-003, Constitution I |
| L4 | Equal inputs produce `ScoreResult`s that compare equal, with byte-identical `to_json()`. | FR-003, FR-071 |
| L5 | `to_dict()` returns only `dict`, `list`, `str`, `int`, `float` and `None` values, in the key order of [result.schema.json](result.schema.json). | FR-070, FR-071 |
| L6 | `to_json()` equals `json.dumps(to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"`. | R-06 |
| L7 | `total` is in 0–100. `valuation.score` is in 0–10, and the valuation never changes `total` or `label`. | FR-050, FR-060 |
| L8 | `dimensions` always has 9 entries, in FR-030 order, even when every item is `no_data`. | FR-030 |

## Example

```python
>>> from gis_scorer import score_snapshot, SnapshotValidationError
>>> r = score_snapshot({"piotroski": 6, "altman_z": 2.5, "beneish_m": -2.5})
>>> r.dimensions[0].earned, r.dimensions[0].available
(15, 20)
>>> r.label.final              # net profit margin missing (FR-051)
'SUSPICIOUS'
>>> try:
...     score_snapshot({"piotroski": 11})
... except SnapshotValidationError as e:
...     print(e)
piotroski: must be an integer from 0 to 9
```
