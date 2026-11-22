---

description: "Task list for 001-gis-scorer (GIS Scorer, deterministic General Investor Score)"
---

# Tasks: GIS Scorer (deterministic General Investor Score)

**Input**: Design documents from `specs/001-gis-scorer/`: [plan.md](plan.md), [spec.md](spec.md),
[research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/),
[quickstart.md](quickstart.md); constitution `.specify/memory/constitution.md` v1.0.0.

**Tests**: REQUIRED (Constitution III, test-first, NON-NEGOTIABLE). In every phase the test tasks
come before the implementation tasks, and a "confirm red" task records that tests of
not-yet-implemented behaviour fail before that behaviour is written, listing any that pass because
the behaviour already exists. Every test task names the FR / acceptance-scenario (`USn-ASm`) / SC
ids it verifies, and those ids MUST appear in the test function names or docstrings (research
R-12), so the traceability check (written in T011a, completed in T075) can find them.

**Provisional decisions**: research.md R-01 (explicit `null`, null list elements, empty list) and
R-02 (integral-float Piotroski, booleans rejected) stay **PROVISIONAL — not confirmed by Balaji**.
Every test that depends on them carries the literal tag `PROVISIONAL R-01` or `PROVISIONAL R-02`
in its docstring. Do **not** move R-01/R-02 into spec.md as part of these tasks.

**Organization**: Tasks are grouped by user story so each story is an independently testable
increment. All paths are relative to `Assignment-1/Part-1A/`. All Python commands use
`.venv/bin/…` (Constitution, Technical Constraints).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task belongs to (US1…US6)
- **Checking off red-phase tasks (Constitution III)**: test-writing tasks and confirm-red tasks
  end with a deliberately failing suite. They are recorded in the task log when done, but they are
  checked off (`[x]`) only together with their phase's green-run task, once the full suite
  passes: Phase 1 T007 and Phase 2 T008–T012 with T016; US1 T017–T029 with T039; US2 T040–T044 with
  T048; US3 T049–T051 with T053; US4 T054–T056 with T059; US5 T060–T062 with T064; US6 T065–T069
  with T072; Phase 9 T073–T076 with T079.

## Conventions used by the tasks (from plan.md, research.md, data-model.md)

- **Modules** (plan.md Project Structure): `src/gis_scorer/{__init__,__main__,cli,snapshot,rules,scoring,valuation,result}.py`.
- **Internal API the tests call** (contracts/library-api.md allows tests to import internals):
  - `gis_scorer.snapshot`: `FIELDS` (tuple of the 30 field names in data-model.md §1 order),
    `Snapshot`, `validate(raw) -> Snapshot`, `FieldError`, `SnapshotValidationError`.
  - `gis_scorer.rules`: `Ladder`, `apply_ladder(ladder, value)`, `GrowthOutcome`,
    `compute_growth(current, prior) -> GrowthOutcome`, one item scorer per catalogue row
    `score_<item>(snapshot: Snapshot) -> ScoreItem`: `score_piotroski`, `score_altman_z`,
    `score_beneish_m`, `score_ebitda_growth`, `score_earnings_growth`, `score_revenue_growth`,
    `score_equity_growth`, `score_cash_flow_quality`, `score_net_profit_margin`,
    `score_operating_margin`, `score_roe`, `score_roce`, `score_loss_to_profit`,
    `score_profitability_sustainability`, `score_working_capital`, `score_debt_reduction`,
    `score_current_ratio`, `score_debt_to_equity`; and `score_penalties(snapshot) -> tuple[ScoreItem, ...]`.
  - `gis_scorer.scoring`: `compute_total(earned: int, available: int) -> int`,
    `decide_label(total: int, dimensions: tuple[Dimension, ...], snapshot: Snapshot) -> LabelDecision`,
    `score_snapshot(raw) -> ScoreResult`.
  - `gis_scorer.valuation`: `score_valuation(snapshot: Snapshot) -> Valuation`.
- **Constants**: every threshold/points value is a module constant named `FRxxx_*` (research R-03).
- **Test names**: unit `test_frNNN_<behaviour>`, acceptance `test_usN_asM_<behaviour>` with a
  docstring starting `"USn-ASm: …"`, parametrize ids like `fr010_ge8_at_8` / `fr010_ge8_below_7`
  (research R-12). Every test module has a unique basename (pytest default import mode).
- **Float boundaries**: when a boundary test derives its input from a subtraction or a growth
  formula, it first asserts the derived value equals the intended boundary exactly (a precondition
  assert), so floating-point noise can never silently move a case to the wrong side.
- **Staged assembly** (keeps every story independently testable): `decide_label` gains FR-052 in
  US1, FR-051 in US2 and FR-053–FR-055 in US3; `score_valuation` is created in US1 with only the
  FR-060 missing-input path and gains its bands in US5; the Penalties dimension is empty until US4.
- **Traceability scope** (Constitution workflow gate "traceability stays complete"): the environment
  variable `GIS_TRACE_SCOPE` holds comma-separated tokens from the table below. The traceability
  test (T011a) expects the union of their ids. Unset means full scope: every FR and every
  `USn-ASm` in spec.md. Each phase's green-run task sets it to `foundation` plus every story whose
  green run has passed, including its own. The values shown in the green-run tasks assume the order
  US1 → US6; add any story completed out of that order.

  | Token | FR ids | Acceptance scenarios |
  |---|---|---|
  | `foundation` | FR-001, FR-070, FR-071 | — |
  | `US1` | FR-003, FR-010 – FR-027, FR-030, FR-044, FR-050, FR-052 | US1-AS1 … US1-AS5 |
  | `US2` | FR-002, FR-051 | US2-AS1 … US2-AS4 |
  | `US3` | FR-053, FR-054, FR-055 | US3-AS1 … US3-AS5 |
  | `US4` | FR-040, FR-041, FR-042, FR-043 | US4-AS1 … US4-AS4 |
  | `US5` | FR-060 | US5-AS1 … US5-AS3 |
  | `US6` | FR-072 | US6-AS1, US6-AS2 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Packaging, pinned dev tools in `Part-1A/.venv`, and the harness.

- [ ] T001 Create the directory skeleton from plan.md Project Structure: `src/gis_scorer/`, `tests/unit/`, `tests/acceptance/`, `tests/fixtures/snapshots/`, `.harness/` (empty directories only; no `__init__.py` under `tests/`)
- [ ] T002 Create `pyproject.toml` per research.md R-08: `[build-system] requires = ["setuptools>=77"]`, `build-backend = "setuptools.build_meta"`; `[project] name = "gis-scorer"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, `dependencies = []`; `[project.scripts] gis-scorer = "gis_scorer.cli:main"`; `[tool.setuptools.packages.find] where = ["src"]`; `[tool.ruff] target-version = "py312"`, `line-length = 100`; `[tool.ruff.lint] select = ["E","F","W","I","B","UP","SIM"]`; `[tool.pytest.ini_options] testpaths = ["tests"]`; `[tool.coverage.run] source = ["gis_scorer"]`, `branch = true`; `[tool.coverage.report] show_missing = true`. (`python -m gis_scorer` is provided by `src/gis_scorer/__main__.py` in T071.)
- [ ] T003 [P] Create minimal `src/gis_scorer/__init__.py` containing only `__version__ = "0.1.0"` and a module docstring, so the editable install in T006 succeeds (public re-exports are added in T038)
- [ ] T004 [P] Create `requirements-dev.txt` with the exact pins from research.md R-09, one per line: `ruff==0.14.0`, `bandit==1.8.6`, `pytest==8.4.2`, `pytest-cov==7.0.0` (no ranges)
- [ ] T005 [P] Create `.harness/run_harness.sh` exactly per contracts/harness.md and research.md R-10: bash, `set -u` and `set -o pipefail` but **not** `set -e`; `cd` to `Part-1A` from the script's own location; call tools only via `.venv/bin/`; create `evidence/harness-results/$(date -u +%Y%m%dT%H%M%SZ)/`; run steps `1a-ruff-check` (`ruff check .`), `1b-ruff-format` (`ruff format --check .`), `2-bandit` (`bandit -r src -ll`), `3-pytest` (`pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90`), each to its own `<step-id>.log` (stdout+stderr) with its exit code captured; write `environment.txt` (`python --version`, `pip freeze`, `git rev-parse HEAD` or `no commit`) and `summary.md` (table: step id | command | exit code | PASS/FAIL; then Gate 1/2/3 results, Gate 1 = 1a AND 1b; then `OVERALL: PASS|FAIL`); last output line prints the evidence directory and the overall result; exit 0 only if all gates pass, else 1. `chmod +x` the script.
- [ ] T006 Install into `Part-1A/.venv` (depends on T002–T004): `.venv/bin/python -m pip install -r requirements-dev.txt` then `.venv/bin/python -m pip install -e .`; verify with `.venv/bin/ruff --version`, `.venv/bin/bandit --version`, `.venv/bin/pytest --version`, `.venv/bin/python -m pip show pytest-cov`, `.venv/bin/python -c "import gis_scorer; print(gis_scorer.__version__)"`. If a pin fails to install or run on Python 3.14, bump it to the nearest later working release in `requirements-dev.txt` and record the change under R-09 in `specs/001-gis-scorer/research.md`
- [ ] T007 Smoke-run `.harness/run_harness.sh` (depends on T005, T006) and check the no-fail-fast contract: expected exit 1 with steps 1a, 1b and 2 PASS and step 3 FAIL (no tests collected yet); the evidence directory contains all six files from contracts/harness.md and `summary.md` ends with `OVERALL: FAIL`. Fix the script (not the gates) if any of this differs

**Checkpoint**: Tooling installed, harness proven to run every gate and keep evidence.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Result model, snapshot field schema and the ladder primitive that every story uses.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

### Tests for the foundation (write first, confirm red)

- [ ] T008 [P] Create `tests/conftest.py` with fixtures: `full_max_values` (a dict of the `full_max.json` values from quickstart.md: every item at its maximum, 97/97 available, valuation 10, no Margin Compression); `max_snapshot` (factory fixture `max_snapshot(*drop, **overrides) -> dict` returning a fresh copy of `full_max_values` with the keys named in `drop` removed and `overrides` applied); `empty_snapshot` (returns `{}`). No production code imports
- [ ] T009 [P] Write `tests/unit/test_result_model.py` verifying **FR-070, FR-071**: build `ScoreItem`, `Dimension`, `LabelDecision`, `ValuationPart`, `Valuation`, `ScoreResult` directly; assert they are frozen; `to_dict()` key order equals contracts/result.schema.json property order at every level (result, dimension, item, label, valuation, part); `to_dict()` contains only `dict`/`list`/`str`/`int`/`float`/`None` (tuples become lists); `to_json() == json.dumps(to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"` (contracts/library-api.md L5, L6)
- [ ] T010 [P] Write `tests/unit/test_snapshot_fields.py` verifying **FR-001**: `snapshot.FIELDS` equals the 30 field names in data-model.md §1 table order (same order as contracts/snapshot.schema.json); `validate({})` gives a `Snapshot` whose every attribute is `None`; `validate({"roe": 0, "pe": 0, "altman_z": -1.5})` keeps `0`, `0`, `-1.5` (zero and negatives are real values); `Snapshot` is frozen
- [ ] T011 [P] Write `tests/unit/test_ladder.py` verifying the research.md R-03 ladder primitive: steps are evaluated top-down and the first match wins; each of `operator.ge`, `gt`, `le`, `lt` is honoured exactly at its threshold (both sides); no match returns the ladder default; `Ladder` is immutable
- [ ] T011a [P] Write `tests/test_traceability.py` (research R-12, Constitution III): read `specs/001-gis-scorer/spec.md`, extract every `FR-\d{3}` and every acceptance scenario as `USn-ASm` (numbered list items under each "User Story n" heading), and assert that each id in the current scope appears in at least one test function name (`frNNN` / `usN_asM`) or docstring in `tests/**/*.py`, **excluding `tests/test_traceability.py` itself**. The scope comes from `GIS_TRACE_SCOPE` per the Traceability scope table in Conventions (encoded in the test as a constant); unset means every FR and scenario in spec.md, and an unknown token fails the test. At every scope it also asserts that the union of the table's FR ids equals the set of FR ids in spec.md, so the table cannot drift. The SC-006 checks are added in T075
- [ ] T012 Run `.venv/bin/pytest tests/unit/test_result_model.py tests/unit/test_snapshot_fields.py tests/unit/test_ladder.py` and `GIS_TRACE_SCOPE=foundation .venv/bin/pytest tests/test_traceability.py`; confirm that tests of not-yet-implemented behaviour fail (ImportError counts as red), and list any that pass because the behaviour already exists; note the result in the task log

### Implementation for the foundation

- [ ] T013 [P] Implement `src/gis_scorer/result.py`: frozen dataclasses `ScoreItem`, `Dimension`, `LabelDecision`, `ValuationPart`, `Valuation`, `ScoreResult` with `to_dict()`/`to_json()` per research.md R-06. Fields, types and key order per data-model.md §3 `ScoreItem.name`, `ScoreItem.requirement`, `ScoreItem.value`, `ScoreItem.earned`, `ScoreItem.available`, `ScoreItem.status` (enum), `ScoreItem.reason`; §4 `Dimension.name`, `Dimension.earned`, `Dimension.available`, `Dimension.items`; §5 `LabelDecision.pre_gate`, `LabelDecision.final` (label enum), `LabelDecision.reasons`; §6 `ValuationPart.name`, `ValuationPart.requirement`, `ValuationPart.value`, `ValuationPart.points`, `ValuationPart.available`, `ValuationPart.reason`, `Valuation.score`, `Valuation.max`, `Valuation.parts`; §7 `ScoreResult.total`, `ScoreResult.max`, `ScoreResult.raw_earned`, `ScoreResult.raw_available`, `ScoreResult.dimensions`, `ScoreResult.label`, `ScoreResult.valuation`. Define the status and label value sets as module constants (no `sort_keys`)
- [ ] T014 [P] Implement `src/gis_scorer/snapshot.py` foundation: `FIELDS` (30 names, data-model.md §1 order), frozen `Snapshot` dataclass with the attribute types of data-model.md §1 "Snapshot (validated, internal)" (`Snapshot.piotroski` `int | None`, `Snapshot.recent_net_profit_margins` `tuple | None`, all others `int | float | None`), `FieldError` (data-model.md §8 `FieldError.field`, `FieldError.message`), `SnapshotValidationError(ValueError)` (data-model.md §8 `SnapshotValidationError.errors`, never empty; `str()` = one `field: message` line per error), and a **lenient** `validate(raw)` that copies known keys into `Snapshot` (absent → `None`, lists → tuples). Strict V1–V9 checks are added in T045
- [ ] T015 [P] Implement the ladder primitive in `src/gis_scorer/rules.py`: immutable `Ladder(available, steps, default)` where `steps` is a tuple of `(operator, threshold, points)` using `operator.ge/gt/le/lt`, `apply_ladder(ladder, value) -> (points, reason)` with ASCII reasons such as `">= 6"`, `"> 2.99"`, `"< -2.22"`, `"otherwise"` (data-model.md §3 `ScoreItem.reason`), and a small helper that builds a `ScoreItem`. No FR constants yet
- [ ] T016 Run `GIS_TRACE_SCOPE=foundation .venv/bin/pytest` and `.venv/bin/ruff check .`; all foundation tests pass, including the traceability test scoped to the foundation, and lint is clean

**Checkpoint**: Foundation ready; user-story phases can begin.

---

## Phase 3: User Story 1 - Score a company and get its total (Priority: P1) 🎯 MVP

**Goal**: A complete snapshot yields every item's earned/available/reason, nine dimension subtotals
in FR-030 order and a normalised 0–100 total, plus a band label.

**Independent Test**: Score `max_snapshot()` and variants with known values; check every item's
points, each dimension subtotal and the total against hand-computed figures (US1-AS1…AS5).

### Tests for User Story 1 (write first, confirm red) ⚠️

- [ ] T017 [P] [US1] Write `tests/unit/test_fr010_012_forensic.py` verifying **FR-010, FR-011, FR-012** on both sides of every boundary via `rules.score_piotroski/score_altman_z/score_beneish_m(validate({...}))`: Piotroski 9/8→10, 7/6→7, 5/4→4, 3/2→2, 1/0→0; Altman 3.0→5, 2.99→3 (strict `>`), 1.81→3, 1.80→0; Beneish −2.23→5, −2.22→2 (strict `<`), −1.78→2, −1.77→0; each item has `requirement` set to its FR id, `status` `scored`, available 10/5/5 and the matched ASCII reason
- [ ] T018 [P] [US1] Write `tests/unit/test_fr013_growth.py` verifying **FR-013** (`rules.compute_growth`): 115 vs 100 → 15.0 (state `value`); prior 0 and prior −10 → `capped` with cap reason `"Capped: prior 12M <= 0"`; 401 vs 100 → `capped` with `"Capped: current 12M > 4x prior 12M"`; exactly 400 vs 100 → not capped, 300.0; 400.0000004 vs 100 → rounded to 6 decimals first, so not capped (research R-07); 400.000001 vs 100 → capped; negative current vs positive base (−50 vs 100) → −150.0, not capped; current 0 vs 100 → −100.0; R-07 overflow: −1e308 vs 1e-6 → pct is −inf and, at item level via `score_ebitda_growth`, the item `value` is `None` and its reason ends with `"(value outside float range)"` while points are still 0
- [ ] T019 [P] [US1] Write `tests/unit/test_fr014_016_growth_items.py` verifying **FR-014, FR-015, FR-016** on both sides of every boundary (inputs as 12M pairs against a prior of 100, with a precondition assert on `compute_growth(...).pct`): EBITDA ≥20→8, ≥15→6, ≥10→4, ≥5→2, else 0, capped → status `capped`, value `None`, 4 of 8; Earnings ≥20→7, ≥10→5, ≥5→3, ≥0→2 (growth 0.0 → 2), below 0 → 0, capped → 3 of 7; Revenue ≥25→10, ≥15→7, ≥10→5, ≥0→3, below 0 → 0, capped → 5 of 10; capped points come from `FR014_CAPPED_POINTS`/`FR015_CAPPED_POINTS`/`FR016_CAPPED_POINTS`
- [ ] T020 [P] [US1] Write `tests/unit/test_fr017_018_financial_health.py` verifying **FR-017** (equity vs prior 100: 115→3 because `>15` is strict, 116→5, 110→3, 109→2, 105→2, 104→1, 100.5→1, 100→0, 90→0; negative prior uses |prior|: −80 vs −100 → +20% → 5; no rounding) and **FR-018** (`ocf_to_net_profit` 1.5→5, 1.49→4, 1.0→4, 0.99→3, 0.8→3, 0.79→2, 0.5→2, 0.49→1, 0.01→1, exactly 0→0; −0.1 with `net_profit_12m` 10 → −3 with reason `"< 0 with TTM net profit > 0"`; −0.1 with `net_profit_12m` 0 or −5 → 0)
- [ ] T021 [P] [US1] Write `tests/unit/test_fr019_021_profitability_moat.py` verifying **FR-019** (NPM 15.01→3, 15→2, 10.01→2, 10→1, 0.01→1, 0→0, −3→0), **FR-020** (OPM 20.01→4, 20→3, 15.01→3, 15→2, 10.01→2, 10→1, 0.01→1, 0→0) and **FR-021** for both ROE and ROCE (15→5, 14.99→3, 12→3, 11.99→2, 8→2, 7.99→1, 0.01→1, exactly 0 → 0 of 5 with status `scored`, per **FR-001**; −2→0)
- [ ] T022 [P] [US1] Write `tests/unit/test_fr022_025_turnaround.py` verifying **FR-022** (cur 0.01/prev 0 → 5; cur 0.01/prev −1 → 5; cur 0/prev −1 → 0; cur 5/prev 0.01 → 0; value is `{"net_profit_margin", "previous_net_profit_margin"}`), **FR-023** (runs newest first: `[1,1,1,1]` and 8 positives → 2; 3 and 2 → 1; `[5]` → 0 of 2 status `scored`; `[0,5,5]` → 0 of 2; `[5,-1,5,5]` → run 1 → 0; value is the run count), **FR-024** with both changes computable (ΔCCC −300→5, −299→4, −150→4, −149→3, −75→3, −74→2, −30→2, −29→1, −1→1, 0→0; ΔDSO −40→5, −39→4, −25→4, −24→3, −12→3, −11→2, −5→2, −4→1, −1→1, 0→0; OR semantics, e.g. ΔCCC −300 with ΔDSO +10 → 5 and ΔCCC +10 with ΔDSO −40 → 5; value `{"ccc_change", "dso_change"}`; R-07 overflow ΔCCC = +inf (1e308 vs −1e308) → 0 points, `value` `None`, reason suffix `"(value outside float range)"`) and **FR-025** (D/E 0.4 and 0.3 → status `not_applicable`, 0 of 0, reason `"Not applicable: D/E < 0.5 in both years"`; prior 0.5 → scored; ΔD/E exactly −0.5→3, −0.49→2, exactly −0.2→2, just above −0.2→1, −0.01→1, 0→0, +0.3→0; precondition-assert every Δ before use)
- [ ] T023 [P] [US1] Write `tests/unit/test_fr026_027_balance_sheet.py` verifying **FR-026** (current ratio 2.01→5, 2.0→3 (strict `>`), 1.5→3, 1.49→1, 1.0→1, 0.99→0, 0→0) and **FR-027** (D/E 0.49→5, 0.5→3, 1.0→3, 1.01→1, 2.0→1, 2.01→0, −0.2→5 as given)
- [ ] T024 [P] [US1] Write `tests/unit/test_fr030_dimensions.py` verifying **FR-030, FR-070**: `score_snapshot(max_snapshot())` has exactly 9 dimensions named, in order, Forensic Quality, Growth, Revenue Quality, Financial Health, Profitability, Competitive Moat, Turnaround, Balance Sheet, Penalties; item names and `requirement` ids follow the data-model.md §3 catalogue order; each dimension's earned/available equals the sum of its items; subtotals are 20, 15, 10, 10, 7, 10, 15, 10 and Penalties has no items (0 of 0); the result carries `max` 100, `raw_earned`, `raw_available`, `label` and `valuation`
- [ ] T025 [P] [US1] Write `tests/unit/test_fr050_total.py` verifying **FR-050** via `scoring.compute_total`: 45/90 → 50 (also cites **US1-AS5**); 97/97 → 100; ties to even 29/40 (72.5) → 72 and 147/200 (73.5) → 74; clamp −5/10 → 0; result is an `int`. (The zero-available case is tested in T041.)
- [ ] T026 [P] [US1] Write `tests/unit/test_fr052_bands.py` verifying **FR-052** via `scoring.decide_label(total, dims, snapshot)` using the dimensions and snapshot of `max_snapshot()` (complete data, passes the gate): 100, 70 → STRONG BUY; 69, 55 → BUY; 54, 40 → HOLD; 39, 25 → SELL; 24, 0 → STRONG SELL; `pre_gate == final`; `reasons[0]` uses the research.md R-14 band wording `"Total {t} >= {threshold}: {label}"` and, for STRONG SELL, the R-14 wording `"Total {t} < 25: STRONG SELL"`
- [ ] T027 [P] [US1] Write `tests/acceptance/test_us1_score_total.py` with one test per scenario: **US1-AS1** `max_snapshot()` → total 100, raw 97/97, Penalties items empty (FR-050, FR-030); **US1-AS2** `max_snapshot(piotroski=6, altman_z=2.5, beneish_m=-2.5)` → Forensic items 7/10, 3/5, 5/5 and dimension 15/20 (FR-010–FR-012); **US1-AS3** `revenue_12m=115, revenue_prior_12m=100` → Revenue Growth value 15.0, 7 of 10 (FR-013, FR-016); **US1-AS4** `ebitda_prior_12m=0` → EBITDA Growth status `capped`, 4 of 8, and no `EBITDA Declining` item in Penalties (FR-014, FR-044); **US1-AS5** `compute_total(45, 90) == 50` (FR-050)
- [ ] T028 [P] [US1] Write `tests/test_determinism.py` verifying **FR-003, FR-071, SC-003** (research R-11 a and c): scoring `max_snapshot()` 1,000 times yields exactly one distinct `to_json()` string and equal `ScoreResult`s; the input mapping is unchanged after scoring (deep-copy compare, contracts/library-api.md L3); an AST walk of the library modules `src/gis_scorer/{__init__,result,snapshot,rules,scoring,valuation}.py` finds no import of `time`, `datetime`, `random`, `os`, `pathlib`, `socket`, `uuid`, `sys` or `importlib` (both `import x` and `from x import y`, matched on the top-level module name, so `os.path` and `importlib.util` count) and no call to the builtins `open(...)` or `__import__(...)`; `cli.py` and `__main__.py` are exempt (the CLI module may use `sys`)
- [ ] T029 [US1] Run `.venv/bin/pytest tests/unit tests/acceptance/test_us1_score_total.py tests/test_determinism.py` and confirm that the T017–T028 tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; the foundation tests still pass

### Implementation for User Story 1

- [ ] T030 [US1] Implement FR-010, FR-011, FR-012 in `src/gis_scorer/rules.py`: constants `FR010_PIOTROSKI`, `FR011_ALTMAN_Z`, `FR012_BENEISH_M` as `Ladder`s and `score_piotroski`, `score_altman_z`, `score_beneish_m` for present inputs (missing-input path comes in T046)
- [ ] T031 [US1] Implement FR-013 and FR-014–FR-016 in `src/gis_scorer/rules.py`: `GrowthOutcome` (data-model.md §2: `pct`, `state` `value|capped|missing`, `cap_reason`), `compute_growth` with `round(x, 6)` on both inputs before the cap test `prior <= 0 or (current > 0 and current > 4 * prior)` and the formula (research R-07), constants `FR014_EBITDA_GROWTH`, `FR015_EARNINGS_GROWTH`, `FR016_REVENUE_GROWTH`, `FR014_CAPPED_POINTS = 4`, `FR015_CAPPED_POINTS = 3`, `FR016_CAPPED_POINTS = 5`, scorers `score_ebitda_growth`, `score_earnings_growth`, `score_revenue_growth` (capped → status `capped`, value `None`; non-finite derived pct → value `None` and reason suffix per R-07)
- [ ] T032 [US1] Implement FR-017 and FR-018 in `src/gis_scorer/rules.py`: `FR017_EQUITY_GROWTH` (unrounded growth, |prior|), `FR018_CASH_FLOW` ladder plus `FR018_NEGATIVE_POINTS = -3` special case keyed on `Snapshot.net_profit_12m > 0`; `score_equity_growth`, `score_cash_flow_quality`
- [ ] T033 [US1] Implement FR-019, FR-020, FR-021 in `src/gis_scorer/rules.py`: `FR019_NET_PROFIT_MARGIN`, `FR020_OPERATING_MARGIN`, `FR021_RETURNS` (shared by ROE and ROCE); `score_net_profit_margin`, `score_operating_margin`, `score_roe`, `score_roce`
- [ ] T034 [US1] Implement FR-022–FR-025 in `src/gis_scorer/rules.py`: `FR022_LOSS_TO_PROFIT_POINTS = 5`; `FR023_SUSTAINABILITY` (run count newest first while element > 0); `FR024_CCC_STEPS`/`FR024_DSO_STEPS` with best-tier-of-either logic and R-07 overflow reporting; `FR025_DEBT_REDUCTION` with `FR025_NOT_APPLICABLE_BELOW = 0.5` (status `not_applicable`, 0 of 0); scorers `score_loss_to_profit`, `score_profitability_sustainability`, `score_working_capital`, `score_debt_reduction` for present inputs
- [ ] T035 [US1] Implement FR-026 and FR-027 in `src/gis_scorer/rules.py`: `FR026_CURRENT_RATIO`, `FR027_DEBT_TO_EQUITY`; `score_current_ratio`, `score_debt_to_equity`
- [ ] T036 [P] [US1] Create `src/gis_scorer/valuation.py` with `score_valuation(snapshot) -> Valuation` returning the three parts `P/E`, `P/B`, `PEG` in that order with `requirement` `"FR-060"` and the data-model.md §6 `ValuationPart.available` values 5/3/2, implementing only the FR-060 missing-input path for now (value `None`, 0 points, reason `"No data"`); bands are added in T063
- [ ] T037 [US1] Implement `src/gis_scorer/scoring.py`: FR-030 dimension assembly in catalogue order (Penalties dimension present with no items until T058); `compute_total` per FR-050 and research R-04 (`round(Fraction(100 * earned, available))`, clamped to 0–100; zero-available guard comes in T047); `decide_label` with the FR-052 bands and R-14 band reason (`pre_gate == final`); `score_snapshot(raw)` = `validate` → items → dimensions → total → label → `score_valuation`, producing `ScoreResult` (data-model.md §7 `ScoreResult.total` 0–100, `ScoreResult.max` = 100, `ScoreResult.dimensions` always 9)
- [ ] T038 [US1] Update `src/gis_scorer/__init__.py` to re-export `score_snapshot`, `ScoreResult`, `SnapshotValidationError`, `FieldError` and keep `__version__` (contracts/library-api.md Public surface)
- [ ] T039 [US1] Run `GIS_TRACE_SCOPE=foundation,US1 .venv/bin/pytest` and `.venv/bin/ruff check .`; all US1 and foundation tests pass (green), including the traceability test scoped to the foundation and US1, and lint is clean

**Checkpoint**: MVP: a complete snapshot scores correctly with a full breakdown and total.

---

## Phase 4: User Story 2 - Missing data is excluded, never zeroed (Priority: P1)

**Goal**: Missing inputs drop out of earned and available points with reason "No data"; invalid
input is refused with an error naming every bad field; nothing-scorable gives total 0 and
SUSPICIOUS.

**Independent Test**: Score the same snapshot with and without one input; the item becomes 0 of 0
"No data" and the total is re-normalised. Invalid inputs raise `SnapshotValidationError`.

### Tests for User Story 2 (write first, confirm red) ⚠️

- [ ] T040 [P] [US2] Write `tests/unit/test_fr001_fr002_validation.py` verifying **FR-001, FR-002** and data-model.md validation rules V1–V9 (research R-05): V1 non-mapping (`[]`, `"x"`) and a non-`str` key → field `<snapshot>`, `must be an object with string keys`; V2 unknown fields reported sorted by name, `unknown field`; V3 `"12"`, `{}`, `[1]` in a scalar field → `must be a number`; V4 NaN, +inf, −inf → `must be finite`; V5 `piotroski` 10, −1, 6.5 → `must be an integer from 0 to 9`; V6 `current_ratio` −0.01 rejected and 0 accepted; V7 `recent_net_profit_margins` = 5 → `must be a list of numbers`; V8 nine elements → `must have at most 8 elements`; V9 element `"a"`/NaN at index 2 → field `recent_net_profit_margins[2]`; every problem collected in one error, ordered V1 → unknown keys → schema order → list index; `str(err)` is one `field: message` line each; `SnapshotValidationError` is a `ValueError` with non-empty `.errors`; `score_snapshot` raises and returns nothing. PROVISIONAL R-01 tests: `{"roe": None}` equals absent; PROVISIONAL R-02 tests: `piotroski` 6.0 accepted and reported as int `6`; `True`/`False` rejected as `must be a number` in a scalar field, in `piotroski` and inside the list
- [ ] T041 [P] [US2] Write `tests/unit/test_missing_data_items.py` verifying the missing-input path of **FR-010–FR-027** plus **FR-001, FR-013, FR-050**: parametrised over all 18 catalogue items, removing the item's input(s) from `max_snapshot()` gives status `no_data`, `value` `None`, 0 of 0, reason `"No data"` and lowers `raw_available` by exactly that item's maximum; FR-013 either value missing → state `missing`; FR-017 prior equity 0 → `no_data`; FR-018 ratio −0.1 with `net_profit_12m` missing → 0 of 5 scored (not `no_data`); FR-022 either margin missing → `no_data`; FR-023 list absent → `no_data`; PROVISIONAL R-01: `[]` → `no_data` 0 of 0, `[None, 5]` → 0 of 2 scored, `[5, None, 5, 5]` → run 1 → 0 of 2; FR-024 only CCC pair or only DSO pair → scored with the missing change counted as 0 and reported as `None`, neither → `no_data`; FR-025 either D/E missing → `no_data`; FR-050 `compute_total(0, 0) == 0`
- [ ] T042 [P] [US2] Write `tests/unit/test_fr051_suspicious.py` verifying **FR-051** via `decide_label` and `score_snapshot`: NPM missing → `pre_gate == final == "SUSPICIOUS"`, reasons `["Net profit margin missing"]`; all of Piotroski, Altman Z, Beneish M missing → `["Piotroski, Altman Z and Beneish M all missing"]`; both conditions → both reasons in that order (research R-14); only two of the three forensic inputs missing → not SUSPICIOUS; SUSPICIOUS holds at totals 100 and 0; the total is unchanged by the label
- [ ] T043 [P] [US2] Write `tests/acceptance/test_us2_missing_data.py`: **US2-AS1** `max_snapshot("altman_z")` → Altman item 0 of 0, reason `"No data"`, Forensic Quality available 15 (FR-011, FR-030); **US2-AS2** `max_snapshot(roe=0)` → ROE 0 of 5 status `scored` (FR-001, FR-021); **US2-AS3** `{}` → total 0, all 9 dimensions 0 of 0, label SUSPICIOUS (FR-050, FR-051); **US2-AS4** `piotroski` 11, `roe` "x", `altman_z` inf, each → `SnapshotValidationError` naming the field and no result returned (FR-002)
- [ ] T044 [US2] Run `.venv/bin/pytest tests/unit/test_fr001_fr002_validation.py tests/unit/test_missing_data_items.py tests/unit/test_fr051_suspicious.py tests/acceptance/test_us2_missing_data.py` and confirm that the new tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; all US1 tests stay green

### Implementation for User Story 2

- [ ] T045 [US2] Make `validate()` in `src/gis_scorer/snapshot.py` strict per data-model.md §1 "Validation rules" V1–V9 and research R-05 (collect all errors, fixed messages, fixed order, no partial result), applying the range/type constraints of data-model.md §1 `Snapshot.piotroski`, `Snapshot.current_ratio`, `Snapshot.recent_net_profit_margins` and the finite-number rule for `Snapshot.altman_z`, `Snapshot.beneish_m`, `Snapshot.revenue_12m`, `Snapshot.revenue_prior_12m`, `Snapshot.ebitda_12m`, `Snapshot.ebitda_prior_12m`, `Snapshot.net_profit_12m`, `Snapshot.net_profit_prior_12m`, `Snapshot.equity`, `Snapshot.equity_prior`, `Snapshot.debt_to_equity`, `Snapshot.debt_to_equity_prior`, `Snapshot.ocf_to_net_profit`, `Snapshot.net_profit_margin`, `Snapshot.operating_margin`, `Snapshot.net_profit_margin_year_ago`, `Snapshot.operating_margin_year_ago`, `Snapshot.previous_net_profit_margin`, `Snapshot.roe`, `Snapshot.roce`, `Snapshot.ccc_days`, `Snapshot.ccc_days_prior`, `Snapshot.dso_days`, `Snapshot.dso_days_prior`, `Snapshot.pe`, `Snapshot.pb`, `Snapshot.peg`; `None` = missing and null list elements kept (PROVISIONAL R-01); integral-float Piotroski normalised to `int`, `bool` rejected everywhere (PROVISIONAL R-02)
- [ ] T046 [US2] Add the missing-input path to every scorer in `src/gis_scorer/rules.py` (data-model.md §3 "Missing when" column and §2 derived values): `no_data` items are 0 of 0 with reason `"No data"` and `value` `None`; `compute_growth` returns state `missing`; FR-017 prior 0 → missing; FR-018 unknown TTM profit with non-positive ratio → 0 points scored; FR-023 null element stops the run and `[]` is missing (PROVISIONAL R-01); FR-024 one computable change counts the other as 0
- [ ] T047 [US2] Update `src/gis_scorer/scoring.py`: `compute_total` returns 0 when available is 0 (FR-050); `decide_label` applies FR-051 before the FR-052 band with the R-14 SUSPICIOUS reasons (`pre_gate = final = SUSPICIOUS`); `score_snapshot` lets `SnapshotValidationError` propagate before any scoring
- [ ] T048 [US2] Run `GIS_TRACE_SCOPE=foundation,US1,US2 .venv/bin/pytest` and `.venv/bin/ruff check .`; all US1 and US2 tests pass, including the traceability test scoped to the completed stories

**Checkpoint**: US1 and US2 both work; missing and invalid data are handled per Constitution IV.

---

## Phase 5: User Story 3 - Get a recommendation label I can trust (Priority: P2)

**Goal**: Positive labels are downgraded to INSUFFICIENT DATA when a core dimension has no data, or
to HOLD when the quality gate fails, and the result shows both labels and the reasons.

**Independent Test**: Feed totals either side of every band boundary, then positive-band inputs
missing a core dimension or failing the gate (US3-AS1…AS5). Depends on US1 (bands) and US2 (FR-051).

### Tests for User Story 3 (write first, confirm red) ⚠️

- [ ] T049 [P] [US3] Write `tests/unit/test_fr053_fr055_gates.py` verifying **FR-053, FR-054, FR-055** via `decide_label` with dimensions from scored snapshots: for each of Forensic Quality, Growth, Revenue Quality, Competitive Moat at 0 available, total 80 → final INSUFFICIENT DATA, `pre_gate` STRONG BUY, reason `"Missing dimension: <name>"` once per missing core dimension in FR-030 order; Financial Health, Profitability, Turnaround or Balance Sheet at 0 available → no downgrade; gate: ROE missing (ROCE present) → HOLD with `"ROE missing"`, ROE 11.99 → `"ROE below 12%"`, ROE 12 → passes, Piotroski 3 → `"Piotroski below 4"`, Piotroski 4 → passes, Piotroski missing → does not fail the gate (research R-14 open item 3), ROE 10 and Piotroski 3 → both reasons in R-14 order; gate reasons absent when INSUFFICIENT DATA fired; BUY at total 60 is downgraded the same way; HOLD/SELL/STRONG SELL never change; FR-055: `pre_gate`, `final` and `reasons` are all reported and `score_snapshot(...).total == compute_total(raw_earned, raw_available)` whichever label results
- [ ] T050 [P] [US3] Write `tests/acceptance/test_us3_labels.py`: **US3-AS1** totals 70, 69, 55, 54, 40, 39, 25, 24 with `max_snapshot()` dimensions → STRONG BUY, BUY, BUY, HOLD, HOLD, SELL, SELL, STRONG SELL (FR-052); **US3-AS2** total 80 with `max_snapshot("roe", "roce")` dimensions → INSUFFICIENT DATA, reason names `Competitive Moat` (FR-053); **US3-AS3** total 80 with `max_snapshot(roe=10)` → HOLD, reason `"ROE below 12%"` (FR-054); **US3-AS4** `score_snapshot(max_snapshot("net_profit_margin"))` and `decide_label` at totals 100 and 10 → SUSPICIOUS (FR-051); **US3-AS5** total 30 with `max_snapshot("roe", "roce")` → stays SELL (FR-053)
- [ ] T051 [US3] Run `.venv/bin/pytest tests/unit/test_fr053_fr055_gates.py tests/acceptance/test_us3_labels.py` and confirm that the gate tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; US1/US2 tests stay green

### Implementation for User Story 3

- [ ] T052 [US3] Extend `decide_label` in `src/gis_scorer/scoring.py` with FR-053 (core dimensions `FR053_CORE_DIMENSIONS` = Forensic Quality, Growth, Revenue Quality, Competitive Moat) and, only when FR-053 did not fire, FR-054 (`FR054_MIN_ROE = 12`, `FR054_MIN_PIOTROSKI = 4`), applied only to STRONG BUY/BUY, with R-14 reason wording and order; keep `pre_gate` per FR-055 (data-model.md §5 `LabelDecision.pre_gate`, `LabelDecision.final`, `LabelDecision.reasons`)
- [ ] T053 [US3] Run `GIS_TRACE_SCOPE=foundation,US1,US2,US3 .venv/bin/pytest` and `.venv/bin/ruff check .`; all tests pass, including the traceability test scoped to the completed stories

**Checkpoint**: Labels are gated and explained.

---

## Phase 6: User Story 4 - Penalties for a deteriorating business (Priority: P2)

**Goal**: Declining revenue, earnings or EBITDA and two-sided margin compression cost points and
are listed in the Penalties dimension.

**Independent Test**: Score snapshots with declining figures and check each penalty line and the
effect on the total (US4-AS1…AS4). Depends on US1 (growth, total).

### Tests for User Story 4 (write first, confirm red) ⚠️

- [ ] T054 [P] [US4] Write `tests/unit/test_fr040_044_penalties.py` verifying **FR-040, FR-041, FR-042, FR-043, FR-044** via `rules.score_penalties` and `score_snapshot`: revenue/earnings/EBITDA growth slightly below 0 → `Revenue Declining`/`Earnings Declining`/`EBITDA Declining` −5 each, growth exactly 0 → no penalty; penalty items have status `penalty`, available 0, `requirement` FR-040/041/042, value = growth %; Margin Compression −3 (FR-043) only when NPM < year-ago NPM **and** OPM < year-ago OPM, not when either is equal or only one is below, not when any of the four margins is missing; FR-044: capped growth (prior ≤ 0, and > 4× prior) and missing growth never trigger a decline penalty; penalty order FR-040, FR-041, FR-042, FR-043; R-07: a −inf growth still triggers its penalty with `value` `None`; Penalties dimension earned = sum of penalties, available 0, and `raw_earned` includes them
- [ ] T055 [P] [US4] Write `tests/acceptance/test_us4_penalties.py`: **US4-AS1** `max_snapshot(revenue_12m=98, revenue_prior_12m=100)` → `Revenue Declining` −5 listed and Revenue Growth 0 of 10 (FR-016, FR-040); **US4-AS2** `max_snapshot(net_profit_margin=8, net_profit_margin_year_ago=9, operating_margin=12, operating_margin_year_ago=13)` → `Margin Compression` −3 (FR-043); **US4-AS3** only NPM below year-ago → no Margin Compression (FR-043); **US4-AS4** `{"revenue_12m": 90, "revenue_prior_12m": 100, "ebitda_12m": 90, "ebitda_prior_12m": 100, "net_profit_12m": 90, "net_profit_prior_12m": 100}` → raw −15 of 25, total 0 (FR-050, FR-040–FR-042)
- [ ] T056 [US4] Run `.venv/bin/pytest tests/unit/test_fr040_044_penalties.py tests/acceptance/test_us4_penalties.py` and confirm that the penalty tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; earlier tests stay green

### Implementation for User Story 4

- [ ] T057 [US4] Implement `score_penalties` in `src/gis_scorer/rules.py`: `FR040_REVENUE_DECLINING = -5`, `FR041_EARNINGS_DECLINING = -5`, `FR042_EBITDA_DECLINING = -5`, `FR043_MARGIN_COMPRESSION = -3`; triggers only for growth state `value` with pct < 0 (FR-044) and for FR-043 only with all four margins present; only triggered penalties are returned, in FR order, as data-model.md §3 `ScoreItem` with `ScoreItem.status` `penalty` and `ScoreItem.available` 0
- [ ] T058 [US4] Wire the Penalties dimension in `src/gis_scorer/scoring.py` so it holds `score_penalties(snapshot)` and its earned points flow into `raw_earned` and the FR-050 total (clamped at 0)
- [ ] T059 [US4] Run `GIS_TRACE_SCOPE=foundation,US1,US2,US3,US4 .venv/bin/pytest` and `.venv/bin/ruff check .`; all tests pass, including the traceability test scoped to the completed stories (US1-AS1 still shows no penalties; US1-AS4 still shows no EBITDA penalty)

**Checkpoint**: Penalties are scored and listed.

---

## Phase 7: User Story 5 - Separate valuation score (Priority: P3)

**Goal**: A 0–10 valuation from P/E, P/B and PEG, reported separately and never affecting the
quality total or label.

**Independent Test**: Score P/E, P/B and PEG either side of each band and check the sum
(US5-AS1…AS3). Depends only on the Foundation and the US1 assembly.

### Tests for User Story 5 (write first, confirm red) ⚠️

- [ ] T060 [P] [US5] Write `tests/unit/test_fr060_valuation.py` verifying **FR-060** via `valuation.score_valuation(validate({...}))`: P/E 11.99→5, 12→3, 17.99→3, 18→2, 24.99→2, 25→1, 49.99→1, 50→0; P/E 0 → 5 and P/E −8 → 5 (scored as given, spec Edge Cases); P/B 1.49→3, 1.5→2, 2.99→2, 3.0→0, 0→3; PEG 0.99→2, 1.0→1, 1.49→1, 1.5→0, 0→2; each missing part → 0 points, `value` `None`, reason `"No data"`; parts are in P/E, P/B, PEG order with available 5/3/2; `score` = sum, `max` 10
- [ ] T061 [P] [US5] Write `tests/acceptance/test_us5_valuation.py`: **US5-AS1** P/E 11, P/B 1.4, PEG 0.9 → 10; **US5-AS2** P/E 60, P/B 4, PEG 2 → 0; **US5-AS3** `max_snapshot("pe", "pb", "peg")` → valuation 0 and the total, dimensions and label equal those of `max_snapshot()` (FR-060: valuation never affects the quality total or label)
- [ ] T062 [US5] Run `.venv/bin/pytest tests/unit/test_fr060_valuation.py tests/acceptance/test_us5_valuation.py` and confirm that the band tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; earlier tests stay green

### Implementation for User Story 5

- [ ] T063 [US5] Implement the FR-060 bands in `src/gis_scorer/valuation.py`: `FR060_PE`, `FR060_PB`, `FR060_PEG` as `Ladder`s (strict `<` steps, default 0) used by `score_valuation`, populating data-model.md §6 `ValuationPart.value`, `ValuationPart.points`, `ValuationPart.reason` and `Valuation.score` (0–10); `score_snapshot` must not read the valuation when computing total or label
- [ ] T064 [US5] Run `GIS_TRACE_SCOPE=foundation,US1,US2,US3,US4,US5 .venv/bin/pytest` and `.venv/bin/ruff check .`; all tests pass, including the traceability test scoped to the completed stories

**Checkpoint**: Valuation reported alongside the quality score.

---

## Phase 8: User Story 6 - Run it from the command line (Priority: P3)

**Goal**: `python -m gis_scorer <snapshot.json>` (and `gis-scorer`) prints the result JSON or a
validation error with the exit codes in contracts/cli.md.

**Independent Test**: Run the command on sample snapshot files and compare stdout with the
library's `to_json()` for the same input (US6-AS1, US6-AS2). Depends on US1 and US2.

### Tests for User Story 6 (write first, confirm red) ⚠️

- [ ] T065 [P] [US6] Create fixtures in `tests/fixtures/snapshots/`: `full_max.json` (quickstart.md values), `sparse.json` (`{"net_profit_margin": 12, "roe": 0}`), `empty.json` (`{}`), `invalid_piotroski.json` (`{"piotroski": 11}`), `multi_error.json` (`{"zzz": 1, "piotroski": 6.5, "current_ratio": -1}`), `malformed.json` (truncated object), `duplicate_key.json` (`{"roe": 10, "roe": 12}`), `top_level_array.json` (`[1, 2]`), `nan_value.json` (`{"roe": NaN}`)
- [ ] T066 [P] [US6] Write `tests/test_cli.py` verifying **FR-072** against every row of contracts/cli.md using `subprocess.run([sys.executable, "-m", "gis_scorer", path])`: valid → exit 0, stdout ends with a newline, stderr empty; `multi_error.json` → exit 1, stderr `gis_scorer: invalid snapshot` then one `  <field>: <message>` line per error in R-05 order; `malformed.json` → exit 1, `gis_scorer: invalid JSON: …`; `duplicate_key.json` → exit 1, `gis_scorer: invalid JSON: duplicate key 'roe'`; `top_level_array.json` → exit 1, `  <snapshot>: must be an object with string keys`; `nan_value.json` → exit 1 naming `roe` / `must be finite`; missing path and a non-UTF-8 file written to `tmp_path` → exit 2, `gis_scorer: cannot read <path>: …`; no argument and two arguments → exit 2; stdout is empty on every non-zero exit; the `gis-scorer` console script next to `sys.executable` produces the same stdout as `-m`
- [ ] T067 [P] [US6] Write `tests/acceptance/test_us6_cli.py`: **US6-AS1** `full_max.json` → exit 0 and stdout byte-identical to `score_snapshot(json.loads(file_text)).to_json()` (FR-071, FR-072); **US6-AS2** `invalid_piotroski.json` → exit 1, stdout empty, stderr contains `piotroski: must be an integer from 0 to 9` (FR-002, FR-072)
- [ ] T068 [P] [US6] Extend `tests/test_determinism.py` with the research R-11(b) cross-process check for **FR-003, FR-071, SC-003**: run the CLI on `full_max.json` with `PYTHONHASHSEED=0` and `PYTHONHASHSEED=12345` and assert byte-identical stdout
- [ ] T069 [US6] Run `.venv/bin/pytest tests/test_cli.py tests/acceptance/test_us6_cli.py tests/test_determinism.py` and confirm that the CLI tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists; the T028 determinism tests stay green

### Implementation for User Story 6

- [ ] T070 [US6] Implement `src/gis_scorer/cli.py` per contracts/cli.md and research R-13: argparse with one positional path; read UTF-8 (read/decode failure → stderr `gis_scorer: cannot read <path>: <reason>`, exit 2); `json.loads` with an `object_pairs_hook` that rejects duplicate keys; malformed JSON / duplicate key → `gis_scorer: invalid JSON: …`, exit 1; `SnapshotValidationError` → `gis_scorer: invalid snapshot` plus `  <field>: <message>` lines, exit 1; success → `sys.stdout.write(result.to_json())`, exit 0; nothing on stdout when exiting non-zero; `main(argv=None) -> int`
- [ ] T071 [US6] Implement `src/gis_scorer/__main__.py` so `python -m gis_scorer` calls `cli.main()` and exits with its return code
- [ ] T072 [US6] Run `GIS_TRACE_SCOPE=foundation,US1,US2,US3,US4,US5,US6 .venv/bin/pytest` and `.venv/bin/ruff check .`; all tests pass, including the traceability test scoped to the completed stories; run quickstart.md Q4 and Q5 by hand (`cmp` prints nothing; `invalid_piotroski.json` exits 1)

**Checkpoint**: All six user stories work independently through library and CLI.

---

## Phase 9: Polish & Cross-Cutting Concerns (harness green + traceability)

**Purpose**: Success criteria, traceability and the final all-gates-green harness run.

- [ ] T073 [P] Write `tests/acceptance/test_worked_examples.py` for **SC-004**: at least 5 snapshots, each with a docstring showing the item-by-item hand computation from spec.md FRs cross-checked against `Assignment-1/GIS_REFERENCE.md`, asserting exact total, final label and valuation: (1) `full_max.json` → 100, STRONG BUY, 10; (2) `sparse.json` → 25, SUSPICIOUS, 0; (3) `empty.json` → 0, SUSPICIOUS, 0; (4) a BUY/STRONG BUY-band company with ROE 10 → HOLD; (5) a declining company with penalties → STRONG SELL or SELL; (6, optional) a turnaround with capped growth in the HOLD band
- [ ] T074 [P] Write `tests/test_performance.py` for **SC-005**: score 10,000 snapshots (varied deterministically from `max_snapshot()`) and assert elapsed `time.perf_counter()` < 5 s (timing lives only in the test, never in `src/`)
- [ ] T075 [P] Complete `tests/test_traceability.py` (written in T011a; research R-12, Constitution III, **SC-006**): with `GIS_TRACE_SCOPE` unset, the T011a check expects every `FR-\d{3}` and every `USn-ASm` in spec.md; add assertions that every `FR\d{3}_*` constant name in `src/gis_scorer/*.py` refers to an FR id present in spec.md; assert at least one test docstring contains `PROVISIONAL R-01` and at least one contains `PROVISIONAL R-02`
- [ ] T076 Run `.venv/bin/pytest tests/acceptance/test_worked_examples.py tests/test_performance.py tests/test_traceability.py`; if the traceability check reports an uncovered FR or scenario, add the missing test to the owning story's test file (never a stub that only mentions the id) and re-run until green
- [ ] T077 SC-006 constant review: compare every `FRxxx_*` constant in `src/gis_scorer/rules.py`, `scoring.py` and `valuation.py` against its FR text in spec.md (threshold, operator `>`/`>=`/`<`/`<=`, points, available); confirm no scoring constant exists that the spec lacks (Constitution II) and fix any mismatch test-first
- [ ] T078 Run `.venv/bin/ruff format .`, `.venv/bin/ruff check .` and `.venv/bin/bandit -r src -ll`; fix every finding in source (no blanket `noqa`/`nosec`)
- [ ] T079 Run `.harness/run_harness.sh` with `GIS_TRACE_SCOPE` unset, so the gated pytest step runs the traceability test at full scope, and require **all gates green**: exit 0, steps 1a, 1b, 2 and 3 PASS, `summary.md` ends `OVERALL: PASS`, coverage ≥ 90%; record the evidence directory path `evidence/harness-results/<UTC>/` in the task log. If any gate fails, fix the cause and re-run (do not edit the gate commands)
- [ ] T080 SC-002 check from `3-pytest.log` of the T079 run: `rules.py`, `scoring.py` and `valuation.py` show 100% line coverage with no missing branches; if not, add the missing boundary tests in the owning story's test file and repeat T079
- [ ] T081 Walk through quickstart.md: Setup commands, "Run the scorer", the sample-snapshot table and validation scenarios Q1–Q9; every expected outcome matches
- [ ] T082 Run `grep -rn "PROVISIONAL R-0" tests/` and list the tagged tests in the final report for owner confirmation of research.md R-01/R-02 (and open items R-07, R-14); leave R-01/R-02 PROVISIONAL and out of spec.md; do not commit or push (owner instruction)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T006 needs T002–T004; T007 needs T005 and T006.
- **Foundational (Phase 2)**: needs Setup; BLOCKS every user story.
- **US1 (Phase 3)**: needs Foundational.
- **US2 (Phase 4)**: needs US1 (adds missing-data paths to the US1 scorers and `decide_label`).
- **US3 (Phase 5)**: needs US1 (bands) and US2 (FR-051 precedence).
- **US4 (Phase 6)**: needs US1 (growth, total); independent of US2/US3.
- **US5 (Phase 7)**: needs US1 (valuation module created in T036); independent of US2–US4.
- **US6 (Phase 8)**: needs US1 and US2 (validation errors for US6-AS2).
- **Polish (Phase 9)**: needs every story; T079 needs T073–T078.

### User Story Dependency Graph

```text
Setup ─▶ Foundational ─▶ US1 (P1, MVP) ─┬─▶ US2 (P1) ─┬─▶ US3 (P2)
                                         │             └─▶ US6 (P3)
                                         ├─▶ US4 (P2)
                                         └─▶ US5 (P3)
                         all stories ─▶ Polish (harness green, traceability)
```

### Within Each User Story

- Test tasks first, then the "confirm red" task, then implementation, then the green run.
- `rules.py` tasks within a story are sequential (same file); `valuation.py`, `snapshot.py`,
  `scoring.py` and `cli.py` tasks can overlap only where marked [P].
- A story is complete only when the full suite (`.venv/bin/pytest`) passes (Constitution III).

### Parallel Opportunities

- Setup: T003, T004, T005 in parallel.
- Foundational: T008–T011a in parallel; then T013, T014, T015 in parallel.
- US1: T017–T028 (12 test files) in parallel; T036 in parallel with T030–T035.
- US2: T040–T043 in parallel. US3: T049–T050. US4: T054–T055. US5: T060–T061.
- US6: T065–T068 in parallel.
- After US1 is green: US4 and US5 can proceed in parallel with US2; after US2, US3 and US6 in parallel.
- Polish: T073, T074, T075 in parallel.

---

## Parallel Example: User Story 1

```bash
# All US1 test files at once (different files, no shared state):
Task: "T017 tests/unit/test_fr010_012_forensic.py (FR-010, FR-011, FR-012)"
Task: "T018 tests/unit/test_fr013_growth.py (FR-013)"
Task: "T019 tests/unit/test_fr014_016_growth_items.py (FR-014, FR-015, FR-016)"
Task: "T020 tests/unit/test_fr017_018_financial_health.py (FR-017, FR-018)"
Task: "T021 tests/unit/test_fr019_021_profitability_moat.py (FR-019, FR-020, FR-021)"
Task: "T022 tests/unit/test_fr022_025_turnaround.py (FR-022 … FR-025)"
Task: "T023 tests/unit/test_fr026_027_balance_sheet.py (FR-026, FR-027)"
Task: "T024 tests/unit/test_fr030_dimensions.py (FR-030, FR-070)"
Task: "T025 tests/unit/test_fr050_total.py (FR-050)"
Task: "T026 tests/unit/test_fr052_bands.py (FR-052)"
Task: "T027 tests/acceptance/test_us1_score_total.py (US1-AS1 … US1-AS5)"
Task: "T028 tests/test_determinism.py (FR-003, FR-071, SC-003)"

# Then, alongside the sequential rules.py work (T030–T035):
Task: "T036 src/gis_scorer/valuation.py (FR-060 missing path)"
```

## Parallel Example: User Story 2

```bash
Task: "T040 tests/unit/test_fr001_fr002_validation.py (FR-001, FR-002, PROVISIONAL R-01/R-02)"
Task: "T041 tests/unit/test_missing_data_items.py (FR-010–FR-027 missing path, FR-013, FR-050)"
Task: "T042 tests/unit/test_fr051_suspicious.py (FR-051)"
Task: "T043 tests/acceptance/test_us2_missing_data.py (US2-AS1 … US2-AS4)"
```

## Parallel Example: User Stories 4 and 5 after US1

```bash
Task: "T054 tests/unit/test_fr040_044_penalties.py"   # US4
Task: "T060 tests/unit/test_fr060_valuation.py"       # US5
```

---

## Requirement → Test Coverage Matrix

| Requirement | Test task(s) |
|---|---|
| FR-001 | T010, T021, T040, T041, T043 |
| FR-002 | T040, T043, T067 |
| FR-003 | T028, T068 |
| FR-010, FR-011, FR-012 | T017, T027, T041, T043 |
| FR-013 | T018, T019, T027, T041 |
| FR-014, FR-015, FR-016 | T019, T027, T041, T055 |
| FR-017, FR-018 | T020, T041 |
| FR-019, FR-020, FR-021 | T021, T041, T043 |
| FR-022, FR-023, FR-024, FR-025 | T022, T041 |
| FR-026, FR-027 | T023, T041 |
| FR-030 | T024, T027, T043 |
| FR-040, FR-041, FR-042, FR-043 | T054, T055 |
| FR-044 | T027, T054 |
| FR-050 | T025, T027, T041, T043, T055 |
| FR-051 | T042, T043, T050 |
| FR-052 | T026, T050 |
| FR-053 | T049, T050 |
| FR-054 | T049, T050 |
| FR-055 | T049 |
| FR-060 | T036 (missing path), T060, T061 |
| FR-070 | T009, T024 |
| FR-071 | T009, T028, T067, T068 |
| FR-072 | T066, T067 |
| SC-001 | T027, T043, T050, T055, T061, T067 |
| SC-002 | T017–T023, T025, T026, T054, T060, T080 |
| SC-003 | T028, T068 |
| SC-004 | T073 |
| SC-005 | T074 |
| SC-006 | T011a, T075, T077 |

| Acceptance scenarios | Test task |
|---|---|
| US1-AS1 … US1-AS5 | T027 (AS5 also T025) |
| US2-AS1 … US2-AS4 | T043 |
| US3-AS1 … US3-AS5 | T050 |
| US4-AS1 … US4-AS4 | T055 |
| US5-AS1 … US5-AS3 | T061 |
| US6-AS1, US6-AS2 | T067 |

The automated check of this matrix is the traceability test (T011a, completed in T075). Each
phase's green run executes it scoped to the completed stories, and T079 runs it at full scope and
requires every harness gate green.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1: tests red (T029) → implementation → green (T039).
3. **STOP and VALIDATE**: `max_snapshot()` scores 100 with a full breakdown; US1-AS1…AS5 pass.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → complete snapshots score correctly (MVP).
3. US2 → missing and invalid data handled (completes the P1 scope).
4. US3 and US4 (P2) → trustworthy labels and penalties.
5. US5 and US6 (P3) → valuation and CLI.
6. Polish → worked examples, performance, traceability, harness all green.

### Parallel Team Strategy

After US1: one developer on US2 → US3/US6, another on US4, a third on US5. Stories touching
`rules.py` (US2, US4) or `scoring.py` (US2, US3, US4) must merge carefully because they share files.

---

## Notes

- [P] = different files and no dependency on an incomplete task.
- Every test task cites the ids it verifies; the traceability test (T011a/T075) enforces it, scoped
  to the completed stories in each green run and at full scope in T079.
- Confirm red before green in every phase; record the red/green runs in the task log.
- Test-writing and confirm-red tasks are logged when done but checked off only together with
  their phase's green-run task (see Format), so no task is marked complete on a red suite
  (Constitution III).
- R-01/R-02 stay PROVISIONAL; their tests keep the `PROVISIONAL R-01` / `PROVISIONAL R-02` tags.
- Do not commit or push without the owner's say-so.
