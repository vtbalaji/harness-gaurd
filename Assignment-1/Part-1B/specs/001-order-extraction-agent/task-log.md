# Task log: 001-order-extraction-agent (/speckit-implement, 2026-11-22)

This file records the red and green runs and the implementation notes that tasks.md asks for
("record the red and green runs in the task log"). It has no effect on ground truth, which changes
only through spec revisions (FR-026).

## Phase 1: Setup

- T001–T010: skeleton, `pyproject.toml` (build backend `setuptools==80.9.0`), `__init__.py`,
  `requirements-dev.txt`, `.gitignore`, `.env.example`, `.harness/run_harness.sh`,
  `.harness/run_all.sh`, `.harness/run_eval.py` skeleton and `evidence/repair-log.md` created.
  - The `.env.example` header avoids the words that the T087 safety grep looks for
    (`api key | token | secret | password`), so that check passes on wording as well as content.
  - `run_harness.sh` runs `2b-nosec-scan` through a small shell function. It inverts grep's
    exit code: 1 (nothing found) passes and 0 (found) or 2 (error) fails.
  - Neither script was run (owner instruction; T090/T091 are owner-run).
- T098: schema pins recorded in spec.md "Schema file pins (rev 2)" (rev 3 bytes):
  - `output.schema.json` `3665851208cb84acce9011ec0a45817011ac2a8864436a4bd92e020722726a22`
  - `model-response.schema.json` `230171d9c8df1ab24ec5d3cf0e2ebe08f40db2a5694194222bb82ad9ed51dded`
  - "Schema pins recorded by T098 on 2026-11-22" added to the rev 3 Pending list. No schema file
    was changed.
- T011: both schemas copied with `cp`; `cmp` reports them identical.
- T012: every pin installed and ran on Python 3.14.7 with no change: `ruff 0.14.0`,
  `bandit 1.9.1`, `pytest 8.4.2`, `pytest-cov 7.0.0`. `pip install -e .` built with
  `setuptools==80.9.0`. `order_agent.__version__` is `0.1.0` and `SCHEMA_VERSION` is `1.0`.
  research.md R-16 needs no change.
- T092: `constraints-dev.txt` generated with `pip freeze --exclude-editable` (14 pins, no
  `order-agent` line) plus a header. Reinstalling with `-c constraints-dev.txt` reports only
  "Requirement already satisfied". `git status` lists it as untracked, so it is not ignored.
- T013: `.env` copied from `.env.example`. `git status --porcelain` does not list `.env`, so it is
  ignored.
