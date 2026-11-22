# Contract: deterministic-code harness (`.harness/run_harness.sh`) and wrapper (`.harness/run_all.sh`)

**Design**: [../research.md](../research.md) R-14, R-16 | **Same shape as**: Part 1A `contracts/harness.md`

## `run_harness.sh`

```text
.harness/run_harness.sh            # takes no arguments; the script cd's to Part-1B itself
```

Requirements:

- `Part-1B/.venv` exists, with `requirements-dev.txt` installed (`ruff==0.14.0`, `bandit==1.9.1`,
  `pytest==8.4.2`, `pytest-cov==7.0.0`).
- The package is installed editable (`pip install -e .`).
- Every tool is called through `.venv/bin/`.
- No model, judge or network access is needed. Tests fake all HTTP, and an autouse fixture makes
  any real socket connect fail the test.

Every step runs, even after an earlier one fails. There is no fail-fast.

| Gate | Step id | Command (from `Part-1B/`) | Pass condition |
|---|---|---|---|
| 1 Lint | `1a-ruff-check` | `.venv/bin/ruff check .` | exit 0. `.harness/*.py` is included through `extend-include`. |
| 1 Lint | `1b-ruff-format` | `.venv/bin/ruff format --check .` | exit 0 |
| 2 Security | `2-bandit` | `.venv/bin/bandit -r src -ll` | exit 0, i.e. zero medium or high findings. No `# nosec` comments are allowed in `src/`; the harness greps for them and fails gate 2 if any are found. |
| 3 Tests | `3-pytest` | `.venv/bin/pytest --cov=order_agent --cov-branch --cov-report=term-missing --cov-fail-under=90` | exit 0: every test passes and branch coverage on `src/order_agent` is ≥ 90% |

- Gate 1 passes only if both 1a and 1b pass.
- Gate 2 runs the extra check `2b-nosec-scan` (`grep -rn "nosec" src`, which must find nothing).
  That step is included in gate 2's result.

### Test suite layout and id references

Each test's name or docstring names the FR, AC or INV id it covers.

| Path | Covers |
|---|---|
| `tests/unit/test_guards.py` | FR-016, FR-017, AC-3.1–3.4. Covers boundaries: 20,000 vs 20,001 code points, the 85% ratio, 3 words, `Cc` characters, invalid UTF-8. |
| `tests/unit/test_prompt.py` | FR-018: markers, hash id, version and hash, no dataset text in the prompt |
| `tests/unit/test_client.py` | FR-020 (exact request body, the `num_ctx` formula, seed, think, format) and FR-023 (every service-failure kind, retry count, no retry on application failure, attempt log), using a fake transport |
| `tests/unit/test_parser.py` | FR-019: PC-1…PC-3 only, logging, rejection of prose, truncated JSON and arrays |
| `tests/unit/test_validators.py` | R-1 (every schema keyword, good and bad), FR-001…FR-015, MC-1…MC-3, G-1…G-5, C-1…C-3, FR-009 ranking including FX and `other` |
| `tests/unit/test_agent.py` | The pipeline with canned model responses: AC-1.1…1.5, AC-2.1…2.6, AC-3.5/3.6 (pipeline level), AC-4.1…4.3 |
| `tests/unit/test_config.py` | FR-021 and R-10: `.env` parsing, precedence, missing keys, URL scheme, pins |
| `tests/unit/test_cli.py` | Exit codes and stdout/stderr separation ([cli.md](./cli.md)) |
| `tests/contract/test_schemas.py` | The schema keyword subset; `schemas/*.json` byte-identical to `contracts/*.json` |
| `tests/contract/test_dataset.py` | FR-024/025, DG-1…DG-7, every ground truth valid |
| `tests/harness/test_run_eval.py` | INV-1…INV-9 implementations, layer-3 normalisation, verdict rules AC-5.1…5.6, judge isolation (FR-030), output layout. Loaded through `importlib` with HTTP faked. Not counted in coverage. |
| `tests/conftest.py` | autouse network block and shared fakes |

### Evidence layout

```text
evidence/harness-results/<YYYYMMDDTHHMMSSZ>/     # UTC, from `date -u +%Y%m%dT%H%M%SZ`
├── 1a-ruff-check.log
├── 1b-ruff-format.log
├── 2-bandit.log
├── 2b-nosec-scan.log
├── 3-pytest.log           # includes the term-missing coverage table
├── environment.txt        # python --version, pip freeze, git rev-parse HEAD (or "no commit")
└── summary.md             # step id | command | exit code | PASS/FAIL; gate results; OVERALL: PASS|FAIL
```

### Exit status

The script exits **0** only if gates 1, 2 and 3 all pass, and **1** otherwise. Its last line of
output is `Evidence: <dir> OVERALL: <PASS|FAIL>`.

## `run_all.sh`

```text
.harness/run_all.sh [--env-file PATH]    # the option is passed through to run_eval.py
```

1. Run `.harness/run_harness.sh`. If it exits non-zero, print
   `Harness FAILED; evaluation not run (constitution: gates must pass before an evaluation result is reported)`
   and exit **1**.
2. Otherwise run `.venv/bin/python .harness/run_eval.py` and exit with its code: 0 PASS, 1 FAIL,
   2 INCONCLUSIVE, 3 runner or dataset error. Only PASS gives 0.

The last line names both evidence folders.
