# Research & Decisions: GIS Scorer

**Feature**: `001-gis-scorer` | **Date**: 2026-11-22 | **Plan**: [plan.md](plan.md)

The technical context below was fixed by the owner. That covers the language, the layout, the
gates and the tool list. This file records the design decisions made inside that context.

R-01 and R-02 are **provisional**. They answer the two open questions from `/speckit-clarify`, and
on the owner's instruction they are *not* recorded in the spec's Clarifications.

---

## R-01 — Explicit `null`, null list elements, empty list

> **CONFIRMED by Balaji, 2026-11-22** (project thread; recorded in spec.md Clarifications)

- **Decision**:
  - An explicit `null` (Python `None`) for any field means the same as an absent field: the value
    is missing.
  - A `null` element inside `recent_net_profit_margins` counts as a missing quarter. Per FR-023 it
    **stops** the run of consecutive profitable quarters, newest first.
  - An empty list `[]` counts as "no quarter supplied". Profitability Sustainability is then
    **0 of 0** with status `no_data`.
  - A list whose first element is `null` (for example `[null, 5]`) has a run of 0. It is scored
    **0 of 2**, not missing, because at least one quarter was supplied.
- **Rationale**:
  - JSON producers routinely emit `null` for unknown values. Rejecting `null` would force every
    caller to strip keys. Treating it as zero would break Constitution IV.
  - FR-023 already talks about a quarter that "is missing", which assumes a list element can be
    missing.
  - "Missing only when no quarterly margin is supplied" maps naturally onto `[]`.
- **Alternatives considered**:
  - (i) Reject `null` as non-numeric. This is stricter, but hostile to JSON input, and FR-023's
    wording would then have no case to cover.
  - (ii) Treat `[]` as 0 of 2. This contradicts "missing only when no quarterly margin is
    supplied".
  - (iii) Skip null elements instead of stopping. This contradicts FR-023's "stopping at the first
    that is not, or is missing".
- **Tests**: Tests that depend on this decision carry `R-01` in their docstring.

## R-02 — Integral floats for Piotroski; booleans

> **CONFIRMED by Balaji, 2026-11-22** (project thread; recorded in spec.md Clarifications)

- **Decision**:
  - `piotroski` accepts an `int`, or a `float` with no fractional part. `6.0` is normalised to the
    `int` 6, and the result reports `6`.
  - A non-integral float (`6.5`) is rejected with a field error, as is anything outside 0–9.
  - `bool` (`true`/`false`) is rejected as non-numeric in **every** numeric field, including inside
    `recent_net_profit_margins`. Python's `bool` is a subclass of `int`, so the check must be
    explicit.
- **Rationale**:
  - JSON has a single number type, and many producers write `6.0` for an integer. JSON Schema
    2020-12 also treats `6.0` as a valid `"integer"`.
  - Booleans are never a meaningful metric. Silently scoring `true` as 1 would be exactly the
    "guessing" Constitution IV forbids.
- **Alternatives considered**:
  - Accept only `int`. This would break on JSON written by floating-point tools.
  - Round non-integral values. That is guessing.
  - Accept booleans as 0/1. That is a silent coercion.
- **Tests**: Tests that depend on this decision carry `R-02` in their docstring.

---

## R-03 — Encoding the scoring rules so every constant traces to an FR

- **Decision**:
  - Each ladder is an immutable module-level constant named after its requirement. Examples:
    `FR010_PIOTROSKI`, `FR014_EBITDA_GROWTH`, `FR060_PE`.
  - A ladder holds `available`, an ordered tuple of `(operator, threshold, points)` steps, and a
    `default` value. The operator is one of `operator.ge`, `gt`, `le` or `lt`, so `>` vs `≥` is
    explicit data and not buried in an `if`.
  - Steps are evaluated top-down, and the first match wins.
  - The special cases get their own small functions, each with its FR id in the docstring and its
    constants named the same way:
    - FR-013 capped growth;
    - FR-018 −3 branch;
    - FR-022, FR-023, FR-024 and FR-025;
    - FR-040…FR-043 penalties.
  - Capped points are named constants, for example `FR014_CAPPED_POINTS = 4`.
- **Rationale**: SC-006 requires that a reviewer can trace each constant to one FR. Data-driven
  ladders also make the boundary tests systematic: there is one parametrised table per ladder.
- **Alternatives considered**:
  - `if/elif` chains. These are harder to audit and easier to get an operator wrong in.
  - A config file (JSON/TOML). That would be runtime I/O, which breaks Constitution I and V.

## R-04 — Exact total arithmetic and rounding

- **Decision**:
  - All item points are integers.
  - `total = round(Fraction(100 * earned, available))`, then clamped to `[0, 100]`.
  - If `available == 0`, the total is 0.
  - `round()` on a `Fraction` rounds half to even exactly. For example 72.5 → 72 and 73.5 → 74
    (FR-050).
  - `raw_earned` and `raw_available` are reported as integers.
- **Rationale**: Float division can land a hair either side of `.5`. For example `x/y*100` may come
  out as `72.49999999999999`, which would flip the tie rule. Integer points make the ratio exactly
  rational, so `Fraction` gives the mathematically exact half-even result with no tolerance fudge.
- **Alternatives considered**:
  - `round(earned / available * 100)`. This can mis-round ties.
  - `decimal.Decimal` with `ROUND_HALF_EVEN`. It is exact too, but needs context and quantise
    plumbing. `Fraction` is simpler.

## R-05 — Validation and error model

- **Decision**:
  - `validate(raw)` accepts any `collections.abc.Mapping` with `str` keys.
  - It checks **all** fields and collects every problem, then raises a single
    `SnapshotValidationError` (a subclass of `ValueError`). The error has an `.errors` tuple of
    `FieldError(field, message)`.
  - Error order is deterministic:
    1. a non-mapping or non-string-key error, which uses the field name `<snapshot>`;
    2. unknown fields, sorted by name;
    3. known fields, in schema order. Errors for `recent_net_profit_margins` stay at that
       field's own schema position: an error on the field itself first, then its element errors,
       reported as `recent_net_profit_margins[i]`, in index order (data-model.md §1).
  - `str(error)` is one line per field, in the form `field: message`.
  - No partial result is ever returned.
  - A valid snapshot is turned into a frozen `Snapshot` dataclass. In it, `None` means missing and
    Piotroski is an `int`.
- **Accepted value types**:
  - `int` or `float`, never `bool`;
  - the value must be finite (`math.isfinite`);
  - field ranges are in [data-model.md](data-model.md).
  - `recent_net_profit_margins` must be a `list` or `tuple` of at most 8 elements, each a finite
    number or `null` (R-01).
- **Rationale**:
  - FR-002 asks for an error naming the field. Reporting every bad field at once is more useful,
    and it is just as deterministic.
  - A `ValueError` subclass lets callers catch it idiomatically.
- **Alternatives considered**:
  - Fail on the first error. This is simpler but makes the user fix errors one at a time.
  - Return error objects instead of raising. That mixes success and failure shapes in the result.

## R-06 — Result model and deterministic serialisation

- **Decision**:
  - The result is a tree of frozen dataclasses: `ScoreResult`, `Dimension`, `ScoreItem`,
    `LabelDecision`, `Valuation` and `ValuationPart`.
  - `to_dict()` builds plain `dict`/`list` values in a fixed, documented key order (see
    [contracts/result.schema.json](contracts/result.schema.json)).
  - `to_json()` returns
    `json.dumps(self.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"`.
  - Key order is semantic and comes from insertion order. `sort_keys` is not used.
  - Each item carries a `status` that says how it was scored: `scored`, `no_data`, `capped`,
    `not_applicable` or `penalty`. It also carries `requirement`, its FR id.
  - Input values are echoed exactly as validated. Piotroski is normalised to `int`.
  - Penalties are the items of the ninth dimension, **Penalties**. Only triggered penalties are
    listed, so a clean company shows an empty list (US1-AS1).
- **Rationale**:
  - FR-070 and FR-071 require structured data that always serialises the same way.
  - The constitution requires stable key order.
  - CPython's float `repr` (shortest round-trip) is deterministic across runs and platforms.
- **Alternatives considered**:
  - `dataclasses.asdict()`. Its key order follows field order, which is fine, but it cannot rename
    keys or handle the composite working-capital value cleanly.
  - `sort_keys=True`. This loses the dimension and item order that FR-030 specifies.

## R-07 — Floating-point details

- **Decision**:
  - FR-013 rounds both growth inputs with `round(x, 6)` before both the cap test and the growth
    formula.
  - The cap test is `prior <= 0 or (current > 0 and current > 4 * prior)`.
  - Ladder comparisons use the float values directly. Exact boundary values such as 15.0 or 2.99
    are therefore tested exactly.
  - FR-017 equity growth is not rounded, because the spec gives no rounding rule for it.
- **Plan-level decision (output only; owner may revisit)**:
  - With finite but extreme inputs, a *derived* value can overflow to ±infinity. Examples are
    growth against a tiny base, or a ΔCCC between ±1e308.
  - Points are still computed from the comparison, which is mathematically correct: −inf is < 0,
    so it scores 0 and triggers the decline penalty.
  - The item's reported `value` is `null`, and its reason ends with
    `"(value outside float range)"`, so `allow_nan=False` serialisation never fails.
  - This changes no points or labels. Only the echoed number is affected.
- **Rationale**:
  - Python's `round(float, n)` is correctly rounded and deterministic.
  - The overflow case cannot be ruled out by the spec's ranges ("any finite number"), and a crash
    while serialising would break FR-071.
- **Alternatives considered**:
  - Range-limit every input. That adds limits the spec does not contain (Constitution II).
  - Emit `Infinity`. That is not valid JSON.

## R-08 — Packaging

- **Decision**:
  - The project uses `pyproject.toml` with the `setuptools` build backend
    (`requires = ["setuptools>=77"]`) and a src layout (`[tool.setuptools.packages.find]
    where = ["src"]`).
  - It sets `requires-python = ">=3.12"` and `dependencies = []`.
  - `[project.scripts] gis-scorer = "gis_scorer.cli:main"` adds a console script next to
    `python -m gis_scorer`.
  - The ruff, pytest and coverage configuration also lives in `pyproject.toml`:
    - ruff: `target-version = "py312"`, `line-length = 100`, `select = ["E","F","W","I","B","UP","SIM"]`;
    - pytest: `testpaths = ["tests"]`;
    - coverage: `[tool.coverage.run] source = ["gis_scorer"]`, `branch = true`.
- **Rationale**: This is the standard, dependency-free path that makes `pip install -e .` work. One
  config file keeps the tools consistent between the harness and local runs.
- **Alternatives considered**:
  - hatchling or flit. Both are fine, but neither offers anything here over setuptools.
  - A flat layout. It risks tests importing the working tree rather than the installed package.

## R-09 — Dev tool pins (`requirements-dev.txt`)

- **Decision**: Pin these exact versions:

  | Tool | Pin |
  |---|---|
  | ruff | `ruff==0.14.0` |
  | bandit | `bandit==1.9.1` (bumped from `1.8.6`, see the change note below) |
  | pytest | `pytest==8.4.2` |
  | pytest-cov | `pytest-cov==7.0.0` |

  **Change (2026-11-22, `/speckit-implement` T006/T078)**: `bandit==1.8.6` installs on Python
  3.14.7 and `bandit --version` works, but it does not *run*. Every file is reported as
  "exception while scanning file" (`AttributeError: 'Constant' object has no attribute 's'`,
  because Python 3.14 removed the deprecated `ast.Constant.s` alias). That gives exit 0 with
  zero files scanned, which is a false pass of Gate 2. The pin was bumped to the nearest later
  release, `bandit==1.9.1`. It scans all of `src/` (0 files skipped) on Python 3.14.7. The
  other three pins install and run unchanged.

  The harness records `pip freeze` with each run, so the resolved transitive versions (such as
  `coverage`) are captured as evidence.
- **Verification note**: The package index could not be queried from this planning session. The
  pins are known-published releases, but they are not freshly checked as the latest.
  - The first setup task must install them into `Part-1A/.venv` (Python 3.14.7) and run each tool's
    `--version`.
  - If a pin fails to install or run on 3.14, bump it to the nearest later release that works, and
    record the change here.
- **Rationale**: The owner requires exact pins, so the harness results are reproducible.
- **Alternatives considered**:
  - Range specifiers. These are not reproducible.
  - A full lock file (pip-tools/uv). It is more machinery than four dev tools need. The `pip freeze`
    evidence covers the audit need.

## R-10 — Harness runner design

- **Decision**: `.harness/run_harness.sh` is a bash script.
  - **No fail-fast**: it uses `set -u` and `set -o pipefail`, but deliberately not `set -e`.
  - It `cd`s to `Part-1A`, using its own location.
  - It invokes tools through `.venv/bin/`, so the venv is always used.
  - It creates `evidence/harness-results/$(date -u +%Y%m%dT%H%M%SZ)/`.
  - It runs every step, capturing each step's stdout and stderr in its own log file and recording
    its exit code:
    1. **Gate 1, lint**:
       - `ruff check .`
       - `ruff format --check .`

       The gate fails if either fails.
    2. **Gate 2, security**: `bandit -r src -ll`. `-ll` reports severity medium and above. Bandit
       exits non-zero if any are found, so zero medium/high findings is the pass condition.
    3. **Gate 3, tests**:
       `pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90`.
  - It writes `environment.txt` (Python version and `pip freeze`) and `summary.md`. The summary
    holds one row per step with its command, exit code and PASS/FAIL, plus an overall result.
  - It exits 0 only if every gate passed, and 1 otherwise.

  The exact file layout is in [contracts/harness.md](contracts/harness.md).
- **SC-002 vs the 90% gate**: The gate enforces the owner's 90% floor on all of `src`. SC-002
  separately asks for 100% line and branch coverage of the scoring rules (`rules.py`, `scoring.py`
  and `valuation.py`). This is read from the same `term-missing` report and checked as a task
  acceptance criterion. It is not an extra gate, because the owner fixed the gate list.
- **Rationale**:
  - The owner requires every gate to run even after one fails, with per-gate logs and a summary.
  - Bash with explicit exit-code capture is the smallest thing that does this.
- **Alternatives considered**:
  - A Python runner. It works too, but bash matches the owner's script name.
  - `make`. It stops at the first failure by default.
  - tox or nox. These are extra dependencies.

## R-11 — Determinism testing (FR-003, FR-071, SC-003)

- **Decision**:
  - (a) In-process: score the same snapshot 1,000 times and assert one unique `to_json()` string.
  - (b) Cross-process: run the CLI twice with different `PYTHONHASHSEED` values (`0` and `12345`)
    on the same file, and assert byte-identical stdout.
  - (c) The library modules import none of `time`, `datetime`, `random`, `os`, `pathlib`, `socket`,
    `uuid`, `sys` or `importlib`, and contain no call to the builtins `open()` or `__import__()`.
    `cli.py` and `__main__.py` are exempt: they read the file and may use `sys`. This is checked by
    a test that walks each module's AST for imports and for those calls.
- **Rationale**:
  - (a) is exactly SC-003.
  - (b) catches hidden dict or set ordering effects.
  - (c) turns Constitution I into an executable check.
- **Alternatives considered**: Only (a). It would miss hash-seed and environment dependence.

## R-12 — Test naming and traceability

- **Decision**:
  - Unit tests are named `test_frNNN_<behaviour>`.
  - Acceptance tests are named `test_usN_asM_<behaviour>`, and their docstrings start with the id,
    for example `"""US1-AS3: ..."""`.
  - Success-criterion tests cite `SC-00N`.
  - Boundary tables use `pytest.mark.parametrize` with ids like `fr010_ge8_at_8` and
    `fr010_ge8_below_7`.
  - `tests/test_traceability.py` reads `specs/001-gis-scorer/spec.md`, extracts every `FR-\d{3}`
    and every `USn` scenario, and asserts that each appears in at least one test name or docstring
    under `tests/`.
- **Rationale**: This makes Constitution III ("every FR covered by at least one test") a failing
  test rather than a manual review.
- **Alternatives considered**: A hand-maintained traceability matrix. It drifts.

## R-13 — CLI behaviour

- **Decision**: The contract is in [contracts/cli.md](contracts/cli.md).
  - `python -m gis_scorer <snapshot.json>`. It is also available as `gis-scorer`.
  - The file is read as UTF-8, and `json.loads` is used with:
    - `object_pairs_hook`, which rejects duplicate keys. Silently taking the last value would be
      guessing.
    - the default handling of `NaN` and `Infinity` tokens. Python parses them as floats, and the
      validator then rejects them as non-finite, naming the field. This is clearer than a parser
      error that cannot name the field.
  - On success, the result's `to_json()` is printed to stdout, and the exit code is 0.
  - On an invalid snapshot, stdout is empty. The error goes to stderr as
    `gis_scorer: invalid snapshot` followed by one `  <field>: <message>` line per error. The exit
    code is 1.
  - The same applies to malformed JSON, a top-level value that is not an object, and duplicate
    keys: stderr names the problem, and the exit code is 1.
  - A usage error (wrong arguments) exits 2, as argparse does by default.
  - A file that cannot be read (missing, unreadable, not UTF-8) exits 2 with
    `gis_scorer: cannot read <path>: <reason>`.
- **Rationale**: FR-072 only requires a non-zero status. Separating "bad data" (1) from "bad
  invocation" (2) helps scripts and the harness.
- **Alternatives considered**:
  - Reading from stdin as well. It is not required (YAGNI).
  - Emitting errors as JSON. Plain lines are easier to read in a terminal, and the library error
    object is there for programs.

## R-14 — Label reasons (FR-051, FR-053, FR-054, FR-055)

- **Decision**: `label.reasons` is an ordered list of fixed strings.
  - The first entry is always the band reason, for example `"Total 72 >= 70: STRONG BUY"`. For
    STRONG BUY, BUY, HOLD and SELL the wording is `"Total {t} >= {threshold}: {label}"`. For
    STRONG SELL, which has no lower threshold, it is `"Total {t} < 25: STRONG SELL"`.
  - The SUSPICIOUS rule is the exception. Its reasons are then the conditions met, in this order:
    1. `"Net profit margin missing"`
    2. `"Piotroski, Altman Z and Beneish M all missing"`
  - The band entry is followed by any downgrade reasons.
  - `"Missing dimension: <name>"` appears once for each zero-available core dimension, in FR-030
    order.
  - Gate failures appear in this order:
    1. `"ROE missing"`
    2. `"ROE below 12%"`
    3. `"Piotroski below 4"`

    A missing Piotroski does not fail the gate. FR-054 lists only "Piotroski < 4".
  - The gate is evaluated only when the INSUFFICIENT DATA check did not fire (FR-054 says
    "Otherwise").
- **Rationale**: Fixed wording makes the acceptance tests exact (US3-AS2 and US3-AS3 check the
  reason), and FR-055 asks for both labels and the reasons.
- **Alternatives considered**: Free-form messages. These are not testable exactly.

---

## Open items for owner review

1. **R-01 and R-02**: CONFIRMED by Balaji 2026-11-22 (recorded in spec.md Clarifications).
2. **R-07 overflow reporting**: this is output-only and changes no points. Confirm that `null` with
   a reason suffix is acceptable.
3. **R-14 missing Piotroski at the gate**: this follows FR-054 literally. A missing Piotroski does
   not fail the gate, while a missing ROE does. Confirm this is intended.
