# Harness summary (20261122T080145Z)

| Step id | Command | Exit code | Result |
|---|---|---|---|
| 1a-ruff-check | `.venv/bin/ruff check .` | 1 | FAIL |
| 1b-ruff-format | `.venv/bin/ruff format --check .` | 1 | FAIL |
| 2-bandit | `.venv/bin/bandit -r src -ll` | 1 | FAIL |
| 3-pytest | `.venv/bin/pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90` | 1 | FAIL |

## Gates

- Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): FAIL
- Gate 2 (security: 2-bandit): FAIL
- Gate 3 (tests and coverage >= 90%: 3-pytest): FAIL

OVERALL: FAIL
