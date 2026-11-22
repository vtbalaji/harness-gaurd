# Quickstart & Validation Guide: GIS Scorer

**Feature**: `001-gis-scorer` | **Plan**: [plan.md](plan.md)

This guide shows how to set up, run and check the feature end to end once it is implemented. It
does not describe how the code works; for that see [data-model.md](data-model.md) and
[contracts/](contracts/).

The sample files under `tests/fixtures/snapshots/` are created during implementation. Their
contents are given below so the expected results can be checked by hand.

## Prerequisites

- `Part-1A/.venv` exists and runs Python ≥ 3.12. The development venv has Python 3.14.7.
- Every command below is run from `Assignment-1/Part-1A/`, using the venv's binaries.

## Setup

```bash
.venv/bin/python -m pip install -r requirements-dev.txt   # ruff, bandit, pytest, pytest-cov (exact pins, research R-09)
.venv/bin/python -m pip install -e .                      # src-layout editable install
.venv/bin/ruff --version && .venv/bin/bandit --version && .venv/bin/pytest --version
```

## Run the scorer

```bash
.venv/bin/python -m gis_scorer tests/fixtures/snapshots/full_max.json
.venv/bin/gis-scorer           tests/fixtures/snapshots/full_max.json   # same output
```

From Python:

```python
from gis_scorer import score_snapshot
print(score_snapshot({"roe": 18, "net_profit_margin": 16}).to_json())
```

## Sample snapshots and expected outcomes

| File | Content | Expected |
|---|---|---|
| `full_max.json` | see below | exit 0; `total` 100; `raw_earned`/`raw_available` 97/97; label `STRONG BUY` → `STRONG BUY`; no Penalties items; valuation 10 (US1-AS1, US5-AS1) |
| `sparse.json` | `{"net_profit_margin": 12, "roe": 0}` | exit 0; `total` 25 (2 of 8: NPM 2/3, ROE 0/5 scored as a real value); final label `SUSPICIOUS` (all three forensic inputs missing); valuation 0 (US2-AS2, FR-051) |
| `empty.json` | `{}` | exit 0; `total` 0; `raw_available` 0; label `SUSPICIOUS` with both reasons; 9 dimensions all 0 of 0 (US2-AS3) |
| `invalid_piotroski.json` | `{"piotroski": 11}` | exit 1; stdout empty; stderr names `piotroski` (US2-AS4, US6-AS2) |

`full_max.json`, with every item at its maximum. The comments are for reading only and are not
part of the JSON:

```text
piotroski 9 · altman_z 3.5 · beneish_m -2.5                                   → Forensic 20/20
ebitda_12m 125 / ebitda_prior_12m 100 (25%) · net_profit_12m 125 / net_profit_prior_12m 100 (25%) → Growth 15/15
revenue_12m 130 / revenue_prior_12m 100 (30%)                                  → Revenue Quality 10/10
equity 120 / equity_prior 100 (20%) · ocf_to_net_profit 1.6                    → Financial Health 10/10
net_profit_margin 16 · operating_margin 21                                     → Profitability 7/7
roe 18 · roce 20                                                               → Competitive Moat 10/10
previous_net_profit_margin -2 · recent_net_profit_margins [16, 15, 14, 13]
  · ccc_days 40 / ccc_days_prior 400 · dso_days 30 / dso_days_prior 75
  · debt_to_equity 0.3 / debt_to_equity_prior 0.9                              → Turnaround 15/15
current_ratio 2.5 · (debt_to_equity 0.3)                                       → Balance Sheet 10/10
net_profit_margin_year_ago 15 · operating_margin_year_ago 20                   → no Margin Compression
pe 11 · pb 1.4 · peg 0.9                                                       → valuation 10
```

Quick check of the headline fields:

```bash
.venv/bin/python -m gis_scorer tests/fixtures/snapshots/full_max.json \
  | .venv/bin/python -c "import json,sys; r=json.load(sys.stdin); print(r['total'], r['label']['final'], r['valuation']['score'])"
# expected: 100 STRONG BUY 10
```

## Validation scenarios

| # | What it proves | How | Expected |
|---|---|---|---|
| Q1 | Every acceptance scenario (SC-001) | `.venv/bin/pytest tests/acceptance -q` | all pass; each test docstring cites `USn-ASm` |
| Q2 | FR boundaries on both sides (SC-002) | `.venv/bin/pytest tests/unit -q` | all pass |
| Q3 | Worked examples (SC-004) | `.venv/bin/pytest tests/acceptance/test_worked_examples.py -q` | ≥ 5 examples match the hand-computed total, label and valuation |
| Q4 | Determinism (FR-003, SC-003) | `.venv/bin/pytest tests/test_determinism.py -q`, then by hand: `PYTHONHASHSEED=0 .venv/bin/python -m gis_scorer tests/fixtures/snapshots/full_max.json > /tmp/a.json; PYTHONHASHSEED=12345 .venv/bin/python -m gis_scorer tests/fixtures/snapshots/full_max.json > /tmp/b.json; cmp /tmp/a.json /tmp/b.json` | pass; `cmp` prints nothing |
| Q5 | CLI contract (FR-072) | `.venv/bin/pytest tests/test_cli.py -q`; also run the CLI on `invalid_piotroski.json` and `echo $?` | pass; exit 1 with `piotroski` named on stderr |
| Q6 | Performance (SC-005) | `.venv/bin/pytest tests/test_performance.py -q` | 10,000 scores in < 5 s |
| Q7 | Traceability (Constitution III, SC-006) | `.venv/bin/pytest tests/test_traceability.py -q` | every `FR-0xx` and user-story scenario in spec.md is cited by at least one test |
| Q8 | All gates plus evidence | `.harness/run_harness.sh; echo $?` | exit 0; a new `evidence/harness-results/<UTC>/` holds the 4 step logs, `environment.txt` and `summary.md` with `OVERALL: PASS` ([contracts/harness.md](contracts/harness.md)) |
| Q9 | SC-002 100% on the scoring rules | read the coverage table in `3-pytest.log` | `rules.py`, `scoring.py` and `valuation.py` show 100% with no missing branches |

## Provisional behaviour to re-check after owner confirmation

The tests tagged `R-01` (null, null element, empty list) and `R-02`
(integral float, booleans) encode decisions that are **not yet confirmed by Balakrishnan**. List them
with:

```bash
grep -rn "R-0" tests/
```
