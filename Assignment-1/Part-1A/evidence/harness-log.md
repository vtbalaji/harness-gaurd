# Harness log: Part 1A GIS Scorer

Feature: `specs/001-gis-scorer` (a deterministic re-implementation of the General Investor Score
from myportfolio-web; the reference is `Assignment-1/GIS_REFERENCE.md`).
Date: 2026-11-22. All times are UTC.

## 1. How the code was generated

The whole flow ran through GitHub Spec Kit (specify-cli 1.4.4.dev0, Claude integration, sh scripts).
The constitution and the first spec were written by following the skill files by hand. Every later
step ran as a real Spec Kit slash command, headless, with `claude -p` (Claude Code 2.1.330,
`--permission-mode acceptEdits`, a restricted tool allow-list). Transcripts are in
`evidence/speckit-transcripts/`.

| Step | How it ran | Artefact | Transcript |
|---|---|---|---|
| Constitution v1.0.0 | by hand, following `speckit-constitution` | `.specify/memory/constitution.md` | (not a headless run) |
| Specify | by hand, following `speckit-specify` | `spec.md`, `checklists/requirements.md` | (not a headless run) |
| Clarify | headless `/speckit-clarify` | 7 owner decisions recorded, 2 new questions raised | `01-clarify.md` |
| Q1/Q2 | confirmed by Balaji in the project thread 07:23Z | spec.md Clarifications | |
| Plan | headless `/speckit-plan` | plan, research, data-model, contracts, quickstart | `02-plan.md` |
| Tasks | headless `/speckit-tasks` | `tasks.md`, 83 tasks | `03-tasks.md` |
| Analyze | headless `/speckit-analyze` | 15 findings (1 critical) | `04-analyze.md` |
| Remediation | headless | 11 findings fixed in the artefacts; U1, I4, E2 and D1 left on purpose | `05-analyze-remediation.md` |
| Implement | headless `/speckit-implement` | `src/gis_scorer/`, `tests/`, `.harness/`, task-log | `06-implement.md`, `06-implement.events.jsonl` |

The first implement attempt (started 07:00Z) hung before doing any work: no tool calls and no
files written, about 3.7 s of CPU in 33 minutes, waiting on stdin. It was stopped and rerun at 07:34Z
with stdin closed. The rerun finished at 08:00Z.

### What implement was told

- Follow tasks.md in order, test-first: write the tests, confirm they fail (red), implement, confirm
  they pass (green).
- Reference the FR or USn-ASm id in every test name or docstring.
- Do not run the harness. The owner's session runs it, after snapshotting.
- Never weaken a test, lower coverage, add `noqa` or `nosec`, or edit the spec to fit the code.

### What it produced (the initial generation)

- 8 library modules: `snapshot`, `rules`, `scoring`, `valuation`, `result`, `cli`, `__main__` and
  `__init__`.
- 29 test modules in `tests/unit` and `tests/acceptance`, plus CLI, determinism, performance and
  traceability tests.
- 476 tests in all.
- Its own red/green record for every phase is in `specs/001-gis-scorer/task-log.md`.
- 75 of 83 tasks were checked. The 8 left were the ones that need the harness run.

### Snapshot before any harness run

- Path: `evidence/initial-generation/` (src, tests, pyproject.toml, requirements-dev.txt,
  .harness), with `MANIFEST.txt` and `SHA256SUMS`.
- Committed as 133a591 before the first harness run. The harness's `environment.txt` records that
  HEAD.

## 2. Harness

`.harness/run_harness.sh` runs every gate without stopping at the first failure. It writes one log
per step, `environment.txt` and `summary.md` to `evidence/harness-results/<timestamp>/`, and exits 1
if any gate fails.

| Gate | Step | Command |
|---|---|---|
| 1 Lint | 1a | `ruff check .` |
| 1 Lint | 1b | `ruff format --check .` |
| 2 Security | 2 | `bandit -r src -ll` (zero medium or high findings) |
| 3 Tests | 3 | `pytest --cov=gis_scorer --cov-branch --cov-fail-under=90` |

Pinned tools in `.venv`: `ruff==0.14.0`, `bandit==1.9.1`, `pytest==8.4.2`, `pytest-cov==7.0.0`, on
Python 3.14.7. bandit was moved from 1.8.6 to 1.9.1 during implement, because 1.8.6 skips every file
on Python 3.14 and still exits 0. That would have passed Gate 2 without scanning anything.

## 3. Harness runs

### Run 1: 20261122T080110Z, at HEAD 133a591 (the initial generation)

| Gate | Result | Detail |
|---|---|---|
| 1 Lint | **PASS** | ruff check: "All checks passed!"; format: "79 files already formatted" |
| 2 Security | **PASS** | 1,063 lines scanned, 0 files skipped, 0 issues at any severity, 0 `#nosec` |
| 3 Tests | **PASS** | 476 passed in 1.49 s; coverage 100% (528 statements, 128 branches, 0 missed) |
| **OVERALL** | **PASS** | exit 0 |

Evidence: `evidence/harness-results/20261122T080110Z/`.

### Failures, feedback and repairs

**None.** Run 1 passed every gate, so the code was never sent back to the coding agent. There are
no `evidence/feedback/*.md` files, and none were invented. `evidence/final-generation/` is byte-for-byte
the same as `evidence/initial-generation/` (checked with `diff -r`).

### Harness self-test (NOT part of the record above)

A run that passes is only convincing if the harness can fail. To check that, I made a throwaway
copy of Part-1A in the session scratchpad and planted one defect per gate. The defects are in
`evidence/harness-selftest/planted-defects.diff`:
- Altman Z threshold changed from 2.99 to 3.50
- an `import os` at the bottom of `result.py`
- a `subprocess.call(..., shell=True)` helper

The real `src/` was not touched. The harness ran against the copy with `PYTHONPATH` pointing at the
copy's `src`. Result `20261122T080145Z`:
- all four steps ran (no fail-fast)
- 1a and 1b FAIL (E402 and formatting)
- 2 FAIL (B602, high severity)
- 3 FAIL (8 failed, 468 passed)
- OVERALL FAIL, exit 1

This also stands in for task T007, the harness smoke run, which was skipped as instructed.

## 4. Independent spot checks (outside the generated tests)

- `full_max.json` → total 100, 97 of 97 points, as the spec's Assumptions predict.
- `{"piotroski":6,"altman_z":2.5,"beneish_m":-2.5,"net_profit_margin":5}`:
  - Forensic 15/20 (US1-AS2) and Profitability 1/3.
  - Total 16/23 = 69.6, rounded to 70.
  - The label before gating is STRONG BUY; the final label is INSUFFICIENT DATA, because Growth,
    Revenue Quality and Moat have no data (FR-053).
- 37 distinct FR ids in spec.md. With `GIS_TRACE_SCOPE` unset, the traceability test passed inside
  Gate 3 at full scope, so every one appears in a test.

## 5. Known limitations

- **Scope.** Non-financial companies only. Fixed ladders, with no sector percentiles. No capital
  deployment, red flags, core-profit or other-income rules, growth acceleration or QoQ items. These
  are agreed exclusions (spec Clarifications), so scores will differ from myportfolio-web for any
  company those features affect.
- **Inputs are pre-computed.** The module takes 12-month totals, margins and ratios. It does not
  derive them from filings or from a database.
- **Open owner items** (research.md):
  - R-07: an overflowed derived value is reported as `null` with a note. Implement extended this
    to equity growth and the working-capital and D/E changes.
  - R-14: a missing Piotroski does not fail the quality gate. This matches the reference.
  - Also: an integer too big to convert to a float (`10**400`) is rejected as non-finite. This is
    tested but not written in the spec.
- **One Spec Kit file was reformatted.** `ruff format` (T078) reformatted
  `.specify/scripts/bash/markdown_sections.py`, whitespace only, because the lint gates scan the
  whole Part-1A tree.
- **Lint also scans the evidence copies.** The harness's `ruff ... .` also covers
  `evidence/*-generation/`, so a snapshot that stopped matching the format would fail Gate 1.
  pytest collects only `tests/`.
- **Performance is tested inside Gate 3.** SC-005 (10,000 snapshots in under 5 s) is a wall-clock
  test, so it could be flaky on a heavily loaded machine (analyze finding E2, accepted).
- **Two manual checks were done another way.** During implement, a `bash -n` syntax check of the
  harness and the quickstart's shell-form determinism check were blocked by permission prompts.
  The determinism check was redone through Python instead (same result). The harness syntax was
  proven by the harness itself running.
- **CLI input.** The CLI reads only from a file path, not stdin. This matches contracts/cli.md.

## 6. Final human decision

**Final human decision: ACCEPT / REJECT** (Balaji to fill in)

Decision:

Justification:

Signed / date:
