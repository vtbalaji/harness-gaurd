# Data Model: GIS Scorer

**Feature**: `001-gis-scorer` | **Date**: 2026-11-22 | **Plan**: [plan.md](plan.md)

All entities are immutable: frozen dataclasses, with tuples for sequences. The JSON form of each
output entity is fixed by [contracts/result.schema.json](contracts/result.schema.json), and the
input form by [contracts/snapshot.schema.json](contracts/snapshot.schema.json).

## 1. Company Snapshot (input) — FR-001, FR-002

Every field is optional. Missing means the key is absent or, provisionally under
[research.md](research.md) R-01, the value is `null`. Zero and negative values are real values.

| Field | Type | Range / rule | Unit | Used by |
|---|---|---|---|---|
| `piotroski` | integer (R-02: integral float accepted) | 0–9 | score | FR-010, FR-051, FR-054 |
| `altman_z` | number | finite | score | FR-011, FR-051 |
| `beneish_m` | number | finite | score | FR-012, FR-051 |
| `revenue_12m`, `revenue_prior_12m` | number | finite | ₹ crore | FR-013, FR-016, FR-040 |
| `ebitda_12m`, `ebitda_prior_12m` | number | finite | ₹ crore | FR-013, FR-014, FR-042 |
| `net_profit_12m`, `net_profit_prior_12m` | number | finite | ₹ crore | FR-013, FR-015, FR-041; `net_profit_12m` also FR-018 (TTM sign) |
| `equity`, `equity_prior` | number | finite | ₹ crore | FR-017 |
| `debt_to_equity` | number | finite | ratio | FR-025, FR-027 |
| `debt_to_equity_prior` | number | finite | ratio | FR-025 |
| `current_ratio` | number | finite, ≥ 0 | ratio | FR-026 |
| `ocf_to_net_profit` | number | finite | ratio | FR-018 |
| `net_profit_margin` | number | finite | % | FR-019, FR-022, FR-043, FR-051 |
| `operating_margin` | number | finite | % | FR-020, FR-043 |
| `net_profit_margin_year_ago` | number | finite | % | FR-043 |
| `operating_margin_year_ago` | number | finite | % | FR-043 |
| `previous_net_profit_margin` | number | finite | % | FR-022 |
| `roe` | number | finite | % | FR-021, FR-054 |
| `roce` | number | finite | % | FR-021 |
| `recent_net_profit_margins` | list of (number \| null) | ≤ 8 elements, newest first; elements finite or `null` (R-01) | % | FR-023 |
| `ccc_days`, `ccc_days_prior` | number | finite | days | FR-024 |
| `dso_days`, `dso_days_prior` | number | finite | days | FR-024 |
| `pe` | number | finite | ratio | FR-060 |
| `pb` | number | finite | ratio | FR-060 |
| `peg` | number | finite | ratio | FR-060 |

That is 30 fields.

### Validation rules (R-05)

Validation does not stop at the first problem. Every problem is collected, and then a single
`SnapshotValidationError` is raised. No result is produced.

| # | Condition | Field named in error | Message (fixed text) |
|---|---|---|---|
| V1 | Snapshot is not a mapping, or has a non-`str` key | `<snapshot>` | `must be an object with string keys` |
| V2 | Key not in the table above | the key | `unknown field` |
| V3 | Value is `bool`, `str`, a container (except the list field) or another non-number | the field | `must be a number` |
| V4 | Number is NaN or ±infinity | the field | `must be finite` |
| V5 | `piotroski` not integral (R-02) or outside 0–9 | `piotroski` | `must be an integer from 0 to 9` |
| V6 | `current_ratio` < 0 | `current_ratio` | `must be >= 0` |
| V7 | `recent_net_profit_margins` not a list/tuple | `recent_net_profit_margins` | `must be a list of numbers` |
| V8 | List longer than 8 | `recent_net_profit_margins` | `must have at most 8 elements` |
| V9 | List element fails V3 or V4 | `recent_net_profit_margins[i]` | as V3 or V4 |

Error order is V1, then unknown keys sorted by name, then the known fields in table order.
`recent_net_profit_margins` errors sit at that field's own table position, between `roce` and
`ccc_days`, and are not moved after the scalar fields. An error on the field itself (V7 or V8) comes
first, then its element errors (V9, `recent_net_profit_margins[i]`) in index order.

### Snapshot (validated, internal)

This is a frozen dataclass with one attribute per field. Each attribute is `int | float | None`;
`piotroski` is `int | None` and `recent_net_profit_margins` is `tuple[float | int | None, ...] | None`.
`None` means missing.

## 2. Derived values

| Name | Rule | Result |
|---|---|---|
| Growth (FR-013), for revenue, EBITDA and net profit | Round both values to 6 decimals. If either is missing → **missing**. If prior ≤ 0, or current > 0 and current > 4 × prior → **capped**. Otherwise (c − p) ÷ \|p\| × 100. | `GrowthOutcome`: `pct: float \| None`, `state: "value" \| "capped" \| "missing"`, `cap_reason` |
| Equity growth (FR-017) | Missing if either value is missing or prior = 0. Otherwise (c − p) ÷ \|p\| × 100. No rounding and no cap. | `float \| None` |
| ΔCCC, ΔDSO (FR-024) | current − prior when both are present, otherwise not computable | `float \| None` each |
| ΔD/E (FR-025) | `debt_to_equity − debt_to_equity_prior` when both are present | `float \| None` |
| Consecutive profitable quarters (FR-023) | Count from index 0 while the element is not `None` and > 0 | `int`. The item is missing only if the list is missing or `[]` (R-01) |

## 3. Score Item — FR-070

| Attribute | Type | Notes |
|---|---|---|
| `name` | str | A fixed display name (catalogue below) |
| `requirement` | str | FR id, e.g. `"FR-014"` |
| `value` | number \| object \| null | The value the rule was applied to (catalogue below). It is `null` when missing or capped, and when an overflowed derived value occurs (R-07). |
| `earned` | int | It can be negative: −3 for FR-018, and for penalties |
| `available` | int | 0 when the status is `no_data` or `not_applicable`, and for penalties |
| `status` | enum | `scored` \| `no_data` \| `capped` \| `not_applicable` \| `penalty` |
| `reason` | str | `"No data"` when the status is `no_data`. Otherwise the rule that matched, in ASCII form (`">= 6"`, `"> 2.99"`, `"< -2.22"`, `"otherwise"`, `"Capped: prior 12M <= 0"`, `"Capped: current 12M > 4x prior 12M"`, `"Not applicable: D/E < 0.5 in both years"`, `"< 0 with TTM net profit > 0"`, …). |

Invariants:

- If the status is `no_data` or `not_applicable`, then `earned == available == 0`.
- If the status is `penalty`, then `available == 0` and `earned < 0`.
- Otherwise `available` is the item's maximum, and `earned ≤ available`.
- A `capped` item keeps its full `available` (8, 7 or 10) and earns the fixed capped points (4, 3
  or 5). `available` never drops when growth is capped.

### Item catalogue (FR-030 order)

| Dimension | Item `name` | FR | `value` reported | Available | Missing when |
|---|---|---|---|---|---|
| Forensic Quality | Piotroski F-Score | FR-010 | `piotroski` (int) | 10 | absent |
| | Altman Z-Score | FR-011 | `altman_z` | 5 | absent |
| | Beneish M-Score | FR-012 | `beneish_m` | 5 | absent |
| Growth | EBITDA Growth | FR-014 | growth % (`null` if capped) | 8 (capped: earns 4) | growth missing |
| | Earnings Growth | FR-015 | growth % | 7 (capped: earns 3) | growth missing |
| Revenue Quality | Revenue Growth | FR-016 | growth % | 10 (capped: earns 5) | growth missing |
| Financial Health | Equity Growth | FR-017 | equity growth % | 5 | either missing, or prior = 0 |
| | Cash Flow Quality | FR-018 | `ocf_to_net_profit` | 5 (earned may be −3) | ratio absent |
| Profitability | Net Profit Margin | FR-019 | `net_profit_margin` | 3 | absent |
| | Operating Margin | FR-020 | `operating_margin` | 4 | absent |
| Competitive Moat | ROE | FR-021 | `roe` | 5 | absent |
| | ROCE | FR-021 | `roce` | 5 | absent |
| Turnaround | Loss to Profit | FR-022 | `{"net_profit_margin", "previous_net_profit_margin"}` | 5 | either absent |
| | Profitability Sustainability | FR-023 | consecutive count (int) | 2 | list absent or `[]` |
| | Working Capital Efficiency | FR-024 | `{"ccc_change", "dso_change"}` (each number or `null`) | 5 | neither change computable |
| | Debt Reduction | FR-025 | ΔD/E | 3, or 0 if not applicable | either D/E absent |
| Balance Sheet | Current Ratio | FR-026 | `current_ratio` | 5 | absent |
| | Debt to Equity | FR-027 | `debt_to_equity` | 5 | absent |
| Penalties | Revenue Declining | FR-040 | revenue growth % | 0 (earned −5) | — (listed only if triggered) |
| | Earnings Declining | FR-041 | earnings growth % | 0 (−5) | — |
| | EBITDA Declining | FR-042 | EBITDA growth % | 0 (−5) | — |
| | Margin Compression | FR-043 | `{"net_profit_margin", "net_profit_margin_year_ago", "operating_margin", "operating_margin_year_ago"}` | 0 (−3) | — (needs all four values) |

When every input is present and scorable, the available total is 97 (spec Assumptions).

Penalty trigger notes:

- FR-044: a growth that is `capped` or `missing` never triggers FR-040 to FR-042.
- FR-043 triggers only when all four margins are present and both strict `<` comparisons hold.

## 4. Dimension — FR-030

| Attribute | Type | Notes |
|---|---|---|
| `name` | str | One of the 9 names, in this order: Forensic Quality, Growth, Revenue Quality, Financial Health, Profitability, Competitive Moat, Turnaround, Balance Sheet, Penalties |
| `earned` | int | Σ item.earned |
| `available` | int | Σ item.available |
| `items` | tuple[ScoreItem, …] | All the catalogue items for the dimension, in catalogue order, including `no_data` items. Penalties lists triggered penalties only. |

The attribute order above is also the serialised key order.

## 5. Label Decision — FR-051 to FR-055

| Attribute | Type | Notes |
|---|---|---|
| `pre_gate` | enum | The label after FR-051/FR-052 and before FR-053/FR-054 |
| `final` | enum | The label after the gates |
| `reasons` | tuple[str, …] | Ordered, with fixed wording (research R-14) |

The label enum is `STRONG BUY`, `BUY`, `HOLD`, `SELL`, `STRONG SELL`, `INSUFFICIENT DATA` and
`SUSPICIOUS`.

### Label transitions

```text
                ┌─ net_profit_margin missing  OR  piotroski, altman_z, beneish_m all missing
start ──────────┤        → pre_gate = final = SUSPICIOUS                       (FR-051)
                └─ else band(total): ≥70 STRONG BUY │ ≥55 BUY │ ≥40 HOLD │ ≥25 SELL │ else STRONG SELL (FR-052)
                         │
       pre_gate ∈ {STRONG BUY, BUY}? ── no ──▶ final = pre_gate   (gates never touch HOLD/SELL/STRONG SELL)
                         │ yes
   any of Forensic Quality, Growth, Revenue Quality, Competitive Moat has available = 0?
                         ├─ yes ─▶ final = INSUFFICIENT DATA                    (FR-053)
                         └─ no ──▶ gate fails (ROE missing │ ROE < 12 │ piotroski < 4)?
                                       ├─ yes ─▶ final = HOLD                  (FR-054)
                                       └─ no ──▶ final = pre_gate
```

The total never depends on the label (FR-055).

## 6. Valuation — FR-060

| Entity | Attributes |
|---|---|
| `ValuationPart` | `name` (`"P/E"`, `"P/B"`, `"PEG"`), `requirement` (`"FR-060"`), `value` (number \| null), `points` (int), `available` (5 / 3 / 2), `reason` (`"No data"` or the matched band, e.g. `"< 12"`, `"otherwise"`) |
| `Valuation` | `score` (int 0–10 = Σ points), `max` (10), `parts` (tuple of 3 `ValuationPart`, in P/E, P/B, PEG order) |

A missing part scores 0 points. The valuation never feeds into the total or the labels.

## 7. Score Result — FR-070, FR-071

| Attribute | Type | Notes |
|---|---|---|
| `total` | int | 0–100 (FR-050, exact half-even rounding per R-04) |
| `max` | int | Always 100 |
| `raw_earned` | int | Σ over all items, penalties included. It can be negative. |
| `raw_available` | int | Σ over all items (penalties add 0) |
| `dimensions` | tuple[Dimension, …] | Always all 9, in FR-030 order |
| `label` | LabelDecision | |
| `valuation` | Valuation | |

Methods:

- `to_dict()` returns plain dicts and lists in the key order of the result schema.
- `to_json()` returns the deterministic JSON text described in R-06.

## 8. Errors

| Entity | Attributes |
|---|---|
| `FieldError` | `field: str`, `message: str` |
| `SnapshotValidationError(ValueError)` | `errors: tuple[FieldError, …]`, which is never empty. `str()` gives one `field: message` line per error. |
