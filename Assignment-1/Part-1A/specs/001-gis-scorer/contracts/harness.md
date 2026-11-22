# Contract: test harness runner (`.harness/run_harness.sh`)

**Design**: [../research.md](../research.md) R-10 | **Owner-fixed gates**: lint, security, tests

## Invocation

```text
.harness/run_harness.sh            # run from anywhere; the script cd's to Part-1A itself
```

The script takes no arguments. It requires `Part-1A/.venv` with `requirements-dev.txt` installed and
the package installed editable (`pip install -e .`). Every tool is called through `.venv/bin/`.

## Gates and steps

Every step runs, even after an earlier one fails. There is no fail-fast.

| Gate | Step id | Command (from `Part-1A/`) | Pass condition |
|---|---|---|---|
| 1 Lint | `1a-ruff-check` | `.venv/bin/ruff check .` | exit 0 |
| 1 Lint | `1b-ruff-format` | `.venv/bin/ruff format --check .` | exit 0 |
| 2 Security | `2-bandit` | `.venv/bin/bandit -r src -ll` | exit 0, meaning zero findings of severity medium or high |
| 3 Tests | `3-pytest` | `.venv/bin/pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90` | exit 0: all tests pass and coverage is ≥ 90% |

Gate 1 passes only if both 1a and 1b pass.

## Evidence layout

```text
evidence/harness-results/<YYYYMMDDTHHMMSSZ>/     # UTC, from `date -u +%Y%m%dT%H%M%SZ`
├── 1a-ruff-check.log      # combined stdout+stderr of the step
├── 1b-ruff-format.log
├── 2-bandit.log
├── 3-pytest.log           # includes the term-missing coverage table (used for SC-002 review)
├── environment.txt        # python --version, pip freeze, git rev-parse HEAD (or "no commit")
└── summary.md             # table: step id | command | exit code | PASS/FAIL; then gate results; then OVERALL: PASS|FAIL
```

## Exit status

The script exits **0** only if gates 1, 2 and 3 all pass, and **1** otherwise. It prints the path of
the evidence directory and the overall result as its last line of output.
