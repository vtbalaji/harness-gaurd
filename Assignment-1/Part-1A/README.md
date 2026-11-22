# Part 1A: GIS Scorer

Author: Balakrishnan, student ID 2026ns93087 (2026ns93087@wilp.bits-pilani.ac.in)

A small, deterministic re-implementation of the General Investor Score (GIS) method from
myportfolio-web. It was built spec-first with GitHub Spec Kit and checked by a test harness.

You give it one company's pre-computed metrics. It returns:
- a 0–100 quality score, with every scoring item and the reason for its points
- a recommendation label (STRONG BUY … STRONG SELL, SUSPICIOUS, INSUFFICIENT DATA)
- a separate 0–10 valuation score

Where things are:
- Specification: [`specs/001-gis-scorer/spec.md`](specs/001-gis-scorer/spec.md)
- Constitution: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- Reference method: [`../GIS_REFERENCE.md`](../GIS_REFERENCE.md)
- Harness evidence and log: [`evidence/harness-log.md`](evidence/harness-log.md)

## Setup

The commands need Python 3.12 or newer (it was developed on 3.14.7). Run everything from this
folder.

```bash
python3 -m venv .venv
```

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

```bash
.venv/bin/python -m pip install -e .
```

The package itself has no runtime dependencies. `requirements-dev.txt` pins the harness tools:
`ruff`, `bandit`, `pytest` and `pytest-cov`.

## Run the scorer

Score a snapshot file:

```bash
.venv/bin/python -m gis_scorer tests/fixtures/snapshots/full_max.json
```

The editable install also provides a console script that does the same:

```bash
.venv/bin/gis-scorer tests/fixtures/snapshots/sparse.json
```

The input is a JSON object whose fields are listed in the spec (Key Entities). Every field is
optional. A field that is absent or `null` is missing, and is excluded from the points rather than
scored as zero. The output is the result as indented JSON.

| Exit code | Meaning |
|---|---|
| 0 | scored |
| 1 | invalid snapshot or invalid JSON. stderr names each bad field. |
| 2 | file not readable, or wrong arguments |

From Python:

```python
from gis_scorer import score_snapshot
result = score_snapshot({"piotroski": 6, "altman_z": 2.5, "beneish_m": -2.5, "net_profit_margin": 5})
print(result.total, result.label.final)
print(result.to_json())
```

## Run the tests

```bash
.venv/bin/pytest
```

## Run the harness

```bash
.harness/run_harness.sh
```

The harness runs every gate, even when an earlier one fails:
1. Lint: `ruff check` and `ruff format --check`.
2. Security: `bandit -r src`, with no medium or high findings allowed.
3. Tests: `pytest` with coverage of at least 90% on `src`.

It writes each gate's log, `environment.txt` and `summary.md` to
`evidence/harness-results/<UTC timestamp>/`. It exits 0 only when every gate passes.

## Layout

```text
src/gis_scorer/    library: snapshot (validation), rules (FR ladders), scoring, valuation, result, cli
tests/             unit (per FR), acceptance (per user-story scenario), CLI, determinism,
                   performance and traceability tests
.harness/          run_harness.sh
specs/001-gis-scorer/   spec, plan, research, data model, contracts, tasks, task log
evidence/          Spec Kit transcripts, initial and final generation snapshots,
                   harness results, harness self-test, harness log
```
