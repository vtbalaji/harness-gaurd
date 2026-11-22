# Harness summary (20261122T154635Z)

| Step id | Command | Exit code | Result |
|---|---|---|---|
| 1a-ruff-check | `.venv/bin/ruff check .` | 1 | FAIL |
| 1b-ruff-format | `.venv/bin/ruff format --check .` | 0 | PASS |
| 2-bandit | `.venv/bin/bandit -r src .harness -ll` | 0 | PASS |
| 2b-nosec-scan | `scan_python_suppressions` | 0 | PASS |
| 3-pytest | `.venv/bin/pytest --cov=order_agent --cov=.harness --cov-branch --cov-report=term-missing` | 0 | PASS |
| 3a-cov-src | `.venv/bin/coverage report --include=src/order_agent/* --fail-under=90` | 0 | PASS |
| 3b-cov-run-eval | `.venv/bin/coverage report --include=.harness/run_eval.py --fail-under=90` | 0 | PASS |

## Gates

- Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): FAIL
- Gate 2 (security: 2-bandit AND 2b-nosec-scan): PASS
- Gate 3 (tests and coverage: 3-pytest AND 3a-cov-src >= 90% AND 3b-cov-run-eval >= 90%): PASS

OVERALL: FAIL
