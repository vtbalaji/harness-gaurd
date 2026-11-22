# Implementation Plan: GIS Scorer (deterministic General Investor Score)

**Branch**: `001-gis-scorer` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-gis-scorer/spec.md`

**Note**: This plan was produced by `/speckit-plan` in a non-interactive run. The technical context
was fixed by the owner in the command input. Two validation details are adopted as **provisional**
(see [research.md](research.md) R-01 and R-02). They are not part of the spec's Clarifications.

## Summary

Build a small, pure Python library, `gis_scorer`. It takes one company's metric snapshot (a plain
mapping or JSON object), validates it strictly, and returns an immutable, JSON-serialisable result:

- a 0–100 quality total, normalised over the points available;
- 9 dimensions holding 18 scoring items and up to 4 penalties;
- a label before gating, a final label after gating, and the reasons for both;
- a separate 0–10 valuation score.

A thin CLI (`python -m gis_scorer <snapshot.json>`) reads a file and prints the result as JSON.

The technical approach:

- Every ladder from FR-010 to FR-060 is a module constant named after its FR id.
- The total is computed with exact rational arithmetic (`fractions.Fraction`), so ties-to-even
  rounding is exact.
- JSON is emitted with fixed insertion-ordered keys.

A harness script runs three gates (ruff, bandit, pytest with coverage) and keeps the evidence from
each run.

## Technical Context

**Language/Version**: Python ≥ 3.12. The development venv at `Part-1A/.venv` runs Python 3.14.7.

**Primary Dependencies**: Runtime uses the standard library only (`dataclasses`, `fractions`,
`math`, `json`, `argparse`, `enum`). Dev tools are pinned exactly in `requirements-dev.txt`: ruff,
bandit, pytest and pytest-cov. The pins are in [research.md](research.md) R-09.

**Storage**: N/A. There is no persistence. The CLI reads one input file.

**Testing**: pytest with pytest-cov (branch coverage, `--cov-fail-under=90` on `src`). The test
suite has:

- unit tests per FR;
- acceptance tests per user-story scenario (`USn-ASm`);
- the SC-004 worked examples;
- a determinism test (FR-003, SC-003);
- a CLI test (FR-072);
- a traceability test (Constitution III).

**Target Platform**: Any OS with CPython ≥ 3.12. Development and CI run on macOS (darwin).

**Project Type**: A single-project Python library with a thin CLI entry point. It uses a src layout
with `pyproject.toml`, so `pip install -e .` works.

**Performance Goals**: SC-005, 10,000 snapshots scored in under 5 s on a laptop. One score is a few
dozen comparisons, so this is expected to be met by a wide margin.

**Constraints**:

- FR-003 and Constitution I: byte-identical output for identical input, with no clock, environment,
  file, network or randomness in the library.
- The result must serialise to JSON with stable key order.
- Strict input validation (FR-002).

**Scale/Scope**: 30 input fields, 18 scoring items, 4 penalties, 3 valuation parts and 9
dimensions. The source is expected to be well under 1,000 lines.

There are no NEEDS CLARIFICATION markers. The two open validation questions from `/speckit-clarify`
are resolved provisionally in research.md (R-01, R-02) and flagged for owner confirmation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0.

| Principle / constraint | How the plan satisfies it | Pre-research | Post-design |
|---|---|---|---|
| **I. Deterministic Pure Scoring** | `score_snapshot()` is a pure function with no I/O, clock, environment or randomness. The total uses exact `Fraction` arithmetic (R-04). The result is frozen dataclasses with a fixed key order (R-06). Only `cli.py` touches a file, and it sits outside the scorer. The determinism test runs 1,000 in-process calls and compares the CLI's bytes across different `PYTHONHASHSEED` values (R-11). | PASS | PASS |
| **II. Spec-Traceable Rules** | Every threshold, operator and point value lives in a constant named `FRxxx_*` in `rules.py` / `valuation.py` (R-03). Each item's output carries its `requirement` id. There are no constants beyond the spec. The validation decisions R-01/R-02 are not scoring constants; the owner confirmed them on 2026-11-22 and they are recorded in spec.md Clarifications. Their tests are tagged `R-01` / `R-02`. | PASS | PASS |
| **III. Test-First With a Harness** | The task order will put the failing acceptance and unit tests before each behaviour. Every boundary is tested on both sides (SC-002). The test-to-FR traceability check is automated (R-12). `.harness/run_harness.sh` runs all gates (R-10). The 90% coverage gate is the owner's floor. SC-002's 100% line and branch coverage on the scoring modules is checked from the same coverage report (R-10). | PASS | PASS |
| **IV. Explicit Missing-Data Semantics** | Absent and (provisionally) `null` mean missing, and an item with missing input is 0 of 0 with status `no_data`, reason "No data". Zero and negative values are scored. Bad types, non-finite values and out-of-range values raise `SnapshotValidationError` naming every bad field, and no partial result is returned (R-05). | PASS | PASS |
| **V. Simplicity and Isolation** | Runtime is stdlib only, in 8 small modules (one of them is the CLI). Nothing out of scope is built: no sectors, lenders, capital deployment or red flags. Nothing is imported from myportfolio-web. | PASS | PASS |
| Tech constraints | Python ≥ 3.12; all commands run in `Part-1A/.venv`; pytest and ruff (plus bandit and pytest-cov) are dev-only; output is JSON with stable key order; no secrets are written. | PASS | PASS |
| Workflow | The plan is produced after specify and clarify. Nothing is committed. The owner reviews it before `/speckit-tasks`. | PASS | PASS |

**Gate result**: PASS. There are no unjustified violations, so Complexity Tracking is empty. The
one condition is owner confirmation of R-01/R-02 before implementation is accepted.

## Project Structure

### Documentation (this feature)

```text
specs/001-gis-scorer/
├── plan.md              # This file
├── research.md          # Phase 0: decisions, incl. R-01/R-02
├── data-model.md        # Phase 1: snapshot fields, result entities, validation rules
├── quickstart.md        # Phase 1: setup, run and validation scenarios
├── contracts/
│   ├── library-api.md        # Python public API contract
│   ├── cli.md                # Command-line contract (args, streams, exit codes)
│   ├── harness.md            # .harness/run_harness.sh contract and evidence layout
│   ├── snapshot.schema.json  # Input contract (JSON Schema 2020-12, documentation only)
│   └── result.schema.json    # Output contract (JSON Schema 2020-12, documentation only)
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (Part-1A root)

```text
pyproject.toml               # setuptools src layout; [project.scripts] gis-scorer; ruff/pytest/coverage config
requirements-dev.txt         # exact pins: ruff, bandit, pytest, pytest-cov
src/gis_scorer/
├── __init__.py              # public API re-exports: score_snapshot, ScoreResult, SnapshotValidationError, FieldError
├── __main__.py              # `python -m gis_scorer` → cli.main()
├── cli.py                   # argparse, read file, strict JSON parse, print result / errors, exit codes (FR-072)
├── snapshot.py              # field schema, validate() → Snapshot (FR-001, FR-002, R-01, R-02)
├── rules.py                 # FR-013 growth + FR-010…FR-027 item scorers + FR-040…FR-044 penalties; FRxxx_* constants
├── scoring.py               # FR-030 dimensions, FR-050 total, FR-051…FR-055 labels; score_snapshot()
├── valuation.py             # FR-060
└── result.py                # frozen dataclasses + to_dict()/to_json() (FR-070, FR-071)
tests/
├── conftest.py              # snapshot builders (max snapshot, empty snapshot, helpers)
├── fixtures/snapshots/      # sample JSON files used by CLI tests and quickstart
├── unit/                    # one module per FR group; test_frNNN_* names
├── acceptance/              # test_us1_*.py … test_us6_*.py (docstrings cite USn-ASm); test_worked_examples.py (SC-004)
├── test_determinism.py      # FR-003, FR-071, SC-003
├── test_cli.py              # FR-072 edge cases (missing file, bad JSON, duplicate keys, exit codes)
├── test_performance.py      # SC-005
└── test_traceability.py     # every FR-0xx in spec.md is cited by ≥1 test
.harness/
└── run_harness.sh           # runs all gates, writes evidence, non-zero exit if any gate fails
evidence/harness-results/<UTC timestamp>/   # written by the harness (not by the library)
```

**Structure Decision**: The project is a single library with a src layout under `Part-1A/`. The
scoring logic is split by concern:

- input: `snapshot.py`
- per-item rules: `rules.py`
- assembly and labels: `scoring.py`
- valuation: `valuation.py`
- output shape: `result.py`

I/O is confined to `cli.py`. Tests mirror the spec's structure (FR, user story, success criterion),
so the traceability check can be automated.

## Complexity Tracking

No Constitution Check violations, so nothing needs justifying.
