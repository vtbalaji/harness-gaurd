# 04-tasks — headless transcript

Real slash command run headless with `claude -p ... --output-format stream-json --verbose < /dev/null` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T10:15:15Z. Full event stream (every tool call and result): `04-tasks.events.jsonl`.

## Prompt

```text
/speckit-tasks Non-interactive run. Generate tasks.md from plan.md, spec.md, research.md, data-model.md and contracts/. Owner requirements:
- Test-first (constitution): test tasks precede implementation per story; each test task names the FR / AC / INV ids it verifies; unit tests mock all HTTP.
- Setup: pyproject.toml (src layout), requirements-dev.txt with the exact pins from research.md, install into Part-1B/.venv, .env.example (and a local .env, gitignored, copied from it), .harness/run_harness.sh, .harness/run_eval.py, .harness/run_all.sh.
- Dataset: evals/dataset.json with the cases planned in research/data-model (>= 18), ground truth authored strictly from the spec's rules, before any evaluation; a dataset-validation test (schema of the dataset file, FR-025 category minimums, every case maps to FR/AC ids).
- The implement phase must NOT run the live evaluation (no calls to the model or judge): the owner snapshots the initial generation first. The final phase holds: run .harness/run_harness.sh (must pass) and then run .harness/run_eval.py — mark those two tasks as owner-run.
- Add the C1 rule from Part 1A: test-writing and confirm-red tasks are checked off only together with their phase's green run.
- PROVISIONAL P-1..P-4 stay labelled as in research.md.
Do not write source code. Do not commit. End with the standard completion report.
```

## Output (final report)

I've written `specs/001-order-extraction-agent/tasks.md`. It has 91 tasks; nothing was run and nothing was committed. There is no `.specify/extensions.yml`, so no hooks ran before or after.

**Task count by phase**

| Phase | Tasks | Count |
|---|---|---|
| 1 Setup | T001–T013 | 13 |
| 2 Foundational (includes the dataset) | T014–T030 | 17 |
| 3 US1 single order (P1) 🎯 MVP | T031–T041 | 11 |
| 4 US5 evaluator (P1) | T042–T057 | 16 |
| 5 US2 triage (P2) | T058–T065 | 8 |
| 6 US3 guards and injection (P3) | T066–T074 | 9 |
| 7 US4 multiple orders (P4) | T075–T082 | 8 |
| 8 Polish, then the two owner-run tasks | T083–T091 | 9 |

50 tasks are marked `[P]` (can run in parallel). Each phase writes its tests first, in parallel, then implements in parallel where tasks touch different files. Some files are shared across stories (`prompt.py`, `validators.py`, `agent.py`, `run_eval.py`); tasks on those run in order.

**How each of your requirements is handled**
- **Test-first:** in every phase the order is test tasks, then a confirm-red task, then implementation, then a full green run. Each test task names the FR / AC / INV ids it checks. All HTTP is faked, and a shared test fixture makes any real network connection fail the test. A traceability test (T083) checks that every FR-001…034, AC-1.1…5.6 and INV-1…9 id appears in some test.
- **Setup:**
  - `pyproject.toml` uses the src layout.
  - `requirements-dev.txt` has the exact pins: ruff 0.14.0, bandit 1.9.1, pytest 8.4.2, pytest-cov 7.0.0.
  - The install goes into `Part-1B/.venv`.
  - T013 copies `.env.example` to a local `.env` and checks with `git check-ignore` that it is ignored.
  - All three `.harness` scripts are created in setup. `run_eval.py` starts as a stub that US5 completes.
- **Dataset:** the 27 planned cases are authored in Phase 2 (T027–T029), before any agent or evaluation code exists. Ground truth comes only from the spec's rules. The validation test (T020) checks:
  - the file's structure and DG-1…DG-7;
  - the FR-025 category minimums;
  - that every case has FR ids, and that every id exists in spec.md;
  - that each of AC-1.1…AC-4.3 is covered by at least one case.
- **No live evaluation during implement:** green runs call pytest, ruff and bandit directly, and `run_eval.py` is tested only by importing it with fakes. T087 checks that no `evidence/eval-runs/` or `evidence/harness-results/` folder was created. T090 (`run_harness.sh`, must pass) and T091 (`run_eval.py`) are marked **[OWNER-RUN]**.
- **C1 rule:** it's in the Format section and repeated in Notes. Each phase's test-writing and confirm-red tasks are checked off together with that phase's green run:
  - T014–T022 with T030
  - T031–T035 with T041
  - T042–T049 with T057
  - T058–T061 with T065
  - T066–T070 with T074
  - T075–T078 with T082
  - T083 with T084
- **PROVISIONAL P-1…P-4:** they keep the "PROVISIONAL — pending Balaji" label wherever they're used. Dependent tests carry a `PROVISIONAL P-n` tag, and dependent dataset cases have the `provisional` category.

**Independent test for each story**
- **US1:** a canned model response for the N01 text gives `extracted` with grounded evidence. Ungrounded or malformed output becomes an application failure.
- **US5:** `run_eval` loaded via `importlib` with a fake transport meets AC-5.1…5.6 and produces the contract's evidence folder.
- **US2:** results and board-meeting filings give `not_an_order`; a missing value or client gives `needs_clarification` with the right `missing_fields`.
- **US3:** inputs like X01–X04 are rejected with zero model calls, and injected structure fails the deterministic checks.
- **US4:** mixed units and currencies rank correctly (AC-4.1…4.3), and evidence on additional orders is checked.

**MVP:** Phases 1–3 (setup, foundation with the dataset, US1).

**Format check:** all 91 lines follow `- [ ] T### [P?] [USn?] description with file path`, numbered T001–T091 in order. Story labels appear only in Phases 3–7 (52 tasks), and every constrained field from data-model.md is cited by name in the task that implements it.

**Choices you may want to review**
- **US5 is Phase 4, ahead of US2–US4,** because the spec gives it priority P1.
- **The agent is built in stages:** US1 builds a basic version of the guards and the result assembly. US2, US3 and US4 then add triage, the input guards and multi-order ranking, so each story can still be tested on its own.
- **I added AC-4.3 to the coverage list of the single-order dataset cases.** The planned case table didn't cover it.
- **There is a new test file, `tests/harness/test_harness_scripts.py`.** It runs copies of `run_harness.sh` and `run_all.sh` against fake tools, so it never calls a model.
_Finished 2026-11-22T10:26:00Z, exit 0._
