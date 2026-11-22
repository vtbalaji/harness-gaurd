# 03-tasks — headless transcript

Real slash command run headless with `claude -p` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T07:11:32Z.

## Prompt

```text
/speckit-tasks Non-interactive run. Generate tasks.md for the active feature from plan.md, spec.md, research.md, data-model.md and contracts/. Requirements from the owner:
- Tests are REQUIRED (Constitution III, test-first): for each user story, test tasks come before implementation tasks; every FR and every acceptance scenario (US<n>-AS<m>) is covered by at least one test task, and each test task names the FR/AS ids it verifies.
- Include setup tasks: pyproject.toml (src layout, `python -m gis_scorer` entry), requirements-dev.txt with exact pins (ruff, bandit, pytest, pytest-cov), install into Part-1A/.venv, and the harness (.harness/run_harness.sh per contracts/harness.md, plus any harness config such as ruff/coverage settings).
- Final phase: run .harness/run_harness.sh and require all gates green; a traceability check that every FR-0xx appears in at least one test.
- R-01/R-02 remain PROVISIONAL as recorded in research.md; keep their test tags.
Do not write source code. Do not commit. End with the standard completion report (task count per story, parallel opportunities, MVP scope).
```

## Output

Warning: no stdin data received in 3s, proceeding without it. If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.
I've written `specs/001-gis-scorer/tasks.md` with 82 tasks. Nothing outside that file was changed, no source code was written and nothing was committed. There is no `.specify/extensions.yml`, so there were no before or after hooks to run.

I checked the task format with searches: all 82 tasks use the `- [ ] T0nn` checkbox and ID form. All 56 user-story tasks carry their `[USn]` label, and no setup, foundational or final-phase task has one. Every task names a file path or an exact command to run.

## Task counts

| Phase | Tasks | Count |
|---|---|---|
| 1 Setup | T001–T007 | 7 |
| 2 Foundational | T008–T016 | 9 |
| 3 US1 Score and total (P1) 🎯 MVP | T017–T039 | 23 |
| 4 US2 Missing data and validation (P1) | T040–T048 | 9 |
| 5 US3 Labels and gates (P2) | T049–T053 | 5 |
| 6 US4 Penalties (P2) | T054–T059 | 6 |
| 7 US5 Valuation (P3) | T060–T064 | 5 |
| 8 US6 Command line (P3) | T065–T072 | 8 |
| 9 Final phase: harness green and traceability | T073–T082 | 10 |

## How your requirements are covered

- **Tests first:** in every phase the test tasks come first, then a task that confirms they fail, then the code, then a full-suite run that must pass.
- **Every requirement and scenario has a test:** each test task names the FR, `USn-ASm` or SC ids it checks. A table at the end of tasks.md maps every FR, every acceptance scenario and every success criterion to its test tasks.
- **Setup:**
  - `pyproject.toml`, with the src layout, a `gis-scorer` console script, and the ruff, pytest and coverage settings.
  - `requirements-dev.txt` with the exact pins from research.md R-09.
  - Install into `Part-1A/.venv`.
  - `.harness/run_harness.sh` per contracts/harness.md.
  - A trial run of the harness, which should exit 1 with only the test gate failing, proving it runs every gate and keeps its evidence.
- **Final phase:**
  - T075 adds a traceability test. It fails if any FR id or acceptance scenario in spec.md is not named by a test. It also checks that every `FRxxx_*` constant in the code maps to a requirement in the spec, and that the R-01/R-02 tags exist.
  - T079 runs `.harness/run_harness.sh` and requires every gate to pass with `OVERALL: PASS`.
  - T080 checks 100% line and branch coverage of `rules.py`, `scoring.py` and `valuation.py` (SC-002).
- **R-01/R-02 stay provisional:** the tests that depend on them carry the literal tags `PROVISIONAL R-01` or `PROVISIONAL R-02`. T082 lists those tests for your confirmation and leaves both decisions out of spec.md.

## Order between stories

Some features are built across several stories so that each story can be tested on its own:
- **Labels:** US1 adds the score bands, US2 adds the SUSPICIOUS rule, and US3 adds the INSUFFICIENT DATA and quality-gate downgrades.
- **Valuation:** US1 creates the valuation module with only the "no data" case, and US5 adds the P/E, P/B and PEG bands.
- **Penalties:** the Penalties group stays empty until US4.

That gives this order: US1 → US2 → (US3, US6); US1 → US4; US1 → US5.

## Independent test for each story

- **US1:** a full snapshot scores 100 (97 of 97 points) with the expected subtotals for each group, and US1-AS1 to AS5 pass.
- **US2:** removing one input makes that item 0 of 0 with "No data", and bad input raises an error naming every bad field.
- **US3:** totals on each side of every label boundary, plus downgrades when a core group has no data or the quality gate fails.
- **US4:** each penalty line is listed and the total never goes below 0.
- **US5:** the valuation bands sum correctly and never change the quality total or label.
- **US6:** the command's output is byte-identical to the library's JSON, with the exit codes from contracts/cli.md.

## Parallel work

- **Setup:** T003, T004 and T005.
- **Foundational:** T008–T011, then T013–T015.
- **US1:** 12 test files (T017–T028) at once, and T036 alongside the `rules.py` work.
- **Other stories:** the test tasks of US2, US3, US4, US5 and US6 can each run in parallel.
- **Across stories:** after US1, US4 and US5 can run alongside US2; after US2, US3 and US6.
- **Final phase:** T073, T074 and T075.

## MVP

Setup, Foundational and US1 (T001–T039). Adding US2 completes all the P1 work.

## Decisions I made that you may want to check

- **Function names.** I named the internal functions the tests call, such as `score_<item>`, `compute_growth`, `compute_total`, `decide_label` and `score_valuation`. They are listed under "Conventions" in tasks.md so the tests and the code agree.
- **Label wording.** research.md R-14 gives only one example of the label reason (`"Total 72 >= 70: STRONG BUY"`). I extended it to `"Total {t} < 25: STRONG SELL"` for the lowest band, and marked this in T026.
- **Floating-point boundaries.** Boundary tests must first assert that a computed difference lands exactly on the boundary. For example, `1.2 − 1.0` in floating point is just above −0.2, so a test meant to sit on −0.2 would silently test the wrong side.
_Finished 2026-11-22T07:20:08Z, exit 0._
