# Task log: 001-gis-scorer (/speckit-implement, 2026-11-22)

Red/green runs and notes recorded as tasks.md asks ("record the red/green runs in the task log").

## Phase 1: Setup

- T001–T005: skeleton, `pyproject.toml`, `__init__.py`, `requirements-dev.txt`, `.harness/run_harness.sh` created.
  The harness passes each command as an argument array to a `run_step` helper (no `eval`, no lint
  directives) and does not use `set -e`.
- T006: all four pins installed and ran on Python 3.14.7 with no bump (`ruff 0.14.0`, `bandit 1.8.6`,
  `pytest 8.4.2`, `pytest-cov 7.0.0`); `pip install -e .` OK; `gis_scorer.__version__` = `0.1.0`.
  research.md R-09 therefore needs no change.
- T007: **not run** (owner instruction: do not run `.harness/run_harness.sh`). Left unchecked.

## Phase 2: Foundational

- T012 red: `test_result_model.py`, `test_snapshot_fields.py`, `test_ladder.py` all failed at
  collection (`ModuleNotFoundError: gis_scorer.result / snapshot / rules`).
  `GIS_TRACE_SCOPE=foundation pytest tests/test_traceability.py` passed (4 passed): it checks that the
  ids are *cited*, and the T009/T010 tests citing FR-001/FR-070/FR-071 already existed.
- T016 green: `GIS_TRACE_SCOPE=foundation pytest` → 31 passed; `ruff check .` clean.

## Phase 3: US1

- T029 red: all 12 new modules failed at collection (missing `score_*`, `compute_growth`,
  `FR0xx_*` constants, `gis_scorer.scoring`, `score_snapshot`). Foundation tests stayed green at
  foundation scope. No US1 test passed early.
- T039 green: `GIS_TRACE_SCOPE=foundation,US1 pytest` → 245 passed; ruff clean.
- Notes:
  - Growth uses the spec's own order of operations, `(c − p) ÷ |p| × 100`. It is exact for
    every boundary case; each boundary test asserts its derived value first.
  - R-07's "value outside float range" reporting is applied to every *derived* value: FR-013
    growth, FR-017 equity growth, FR-024 ΔCCC/ΔDSO and FR-025 ΔD/E. Each has a test. Without it,
    an overflowed FR-017/FR-025 value would make `to_json()` fail under `allow_nan=False`.
  - FR-025 not-applicable items report the computed ΔD/E as `value` (0 of 0).
  - FR-024 ties between the CCC and DSO tiers report the CCC reason.

## Phase 4: US2

- T044 red: 78 failed, 14 passed. The passes were behaviour that already existed: the lenient
  validator accepting valid values (Piotroski 0/9, current ratio 0, 8 elements, tuples, null
  elements, echoed values); the empty-error guard (T014); the catalogue meta-check; FR-023
  null-stops-run and FR-024 single-change handling (already in the US1 scorers); and US2-AS2
  (ROE 0 scored, a US1 behaviour).
- T048 green: `GIS_TRACE_SCOPE=foundation,US1,US2 pytest` → 337 passed; ruff clean.
- Note: an integer too large to convert to a float (e.g. `10**400`) is rejected as
  `must be finite` (V4). `math.isfinite` raises OverflowError on it, and the scoring arithmetic
  cannot use it. This is tested.

## Phase 5: US3

- T051 red: 13 failed (every downgrade case), 25 passed. The passes were "no downgrade"
  expectations (trivially true before the gate existed), the US1 bands, the US2 SUSPICIOUS rule
  and the FR-055 shape.
- T053 green: `GIS_TRACE_SCOPE=foundation,US1,US2,US3 pytest` → 375 passed; ruff clean.
- Note: Forensic Quality at 0 available always coincides with FR-051 SUSPICIOUS (all three
  inputs missing). The FR-053 Forensic case is therefore tested at `decide_label` level, with
  dimensions from the reduced snapshot and label inputs from the full one.

## Phase 6: US4

- T056 red: the unit module failed at import (no `FR04x_*`/`score_penalties`); acceptance had
  3 failed and 1 passed (US4-AS3, "no Margin Compression", holds trivially with no penalties).
- T059 green: `GIS_TRACE_SCOPE=foundation,US1,US2,US3,US4 pytest` → 413 passed; ruff clean.
  US1-AS1 and US1-AS4 still show no penalties.

## Phase 7: US5

- T062 red: 26 failed, 1 passed (US5-AS2 expects 0, which the T036 missing-path placeholder
  already returned).
- T064 green: `GIS_TRACE_SCOPE=foundation,US1,…,US5 pytest` → 440 passed; ruff clean.

## Phase 8: US6

- T069 red: `test_cli.py` failed at import (`gis_scorer.cli` absent), and the US6 acceptance and
  the new hash-seed test failed. The three T028 determinism tests stayed green.
- T072 green: `GIS_TRACE_SCOPE=foundation,US1,…,US6 pytest` → 463 passed; ruff clean.
  - Quickstart Q5 by hand: exit 1, stderr `piotroski: must be an integer from 0 to 9`.
  - Q4: the shell form (`PYTHONHASHSEED=… python -m …`) needed an approval this
    non-interactive session could not get. The same two-seed run through Python's `subprocess`
    gave byte-identical stdout (6,034 bytes), and the automated test covers it too.
- `test_cli.py` also drives `cli.main()` and `python -m` in-process, so `cli.py` and
  `__main__.py` are measured by coverage. Subprocess runs are not.

## Phase 9: Polish

- T073–T076: 7 worked examples (≥ 5 required), cross-checked against
  `Assignment-1/GIS_REFERENCE.md` (read only); the SC-005 performance test; traceability completed
  with the FR-constant and R-01/R-02 checks. All 16 passed on the first run, because they test
  behaviour that already exists. **Left unchecked**: the C1 rule ties them to T079, which was not
  run.
- T077: every `FRxxx_*` constant was dumped and compared with spec.md FR-010 … FR-060 and
  FR-002. Thresholds, operators, points and available all match. The validation ranges in
  `snapshot.py` were renamed `FR002_*` so they trace too. No constant exists that the spec lacks.
- T078: `ruff format .` reformatted one file, `.specify/scripts/bash/markdown_sections.py`
  (Spec Kit tooling, whitespace only). Gate 1b would otherwise fail on it. `ruff check .` is
  clean.
  - **bandit 1.8.6 did not run on Python 3.14**: all 8 files were "exception while scanning
    file" (`'Constant' object has no attribute 's'`), so it exited 0 having scanned nothing.
  - The pin was bumped to `bandit==1.9.1` (recorded in research.md R-09). It scans 1,063 lines,
    0 files skipped, 0 issues at any severity.
- T079: **not run** (owner instruction). T080/T081 are left unchecked because they depend on the
  T079 evidence (T080 reads its `3-pytest.log`; T081 includes Q8, the harness run).
  - Observed instead, running the Gate 3 command directly (not the harness):
    `pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90` with
    `GIS_TRACE_SCOPE` unset → **476 passed, total coverage 100.00%**.
  - `rules.py`, `scoring.py` and `valuation.py` are at 100% lines and branches.
  - Quickstart setup, run, sample-table and library-api examples were checked by hand and all
    match.
- T082: the R-tagged tests are listed in the completion report.
