# Harness summary (20261122T080110Z)

| Step id | Command | Exit code | Result |
|---|---|---|---|
| 1a-ruff-check | `.venv/bin/ruff check .` | 0 | PASS |
| 1b-ruff-format | `.venv/bin/ruff format --check .` | 0 | PASS |
| 2-bandit | `.venv/bin/bandit -r src -ll` | 0 | PASS |
| 3-pytest | `.venv/bin/pytest --cov=gis_scorer --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | PASS |

## Gates

- Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): PASS
- Gate 2 (security: 2-bandit): PASS
- Gate 3 (tests and coverage >= 90%: 3-pytest): PASS

OVERALL: PASS
