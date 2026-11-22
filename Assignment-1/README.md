# Assignment 1: Spec-driven development with a test harness

**Author:** Balakrishnan, student ID 2026ns93087 (2026ns93087@wilp.bits-pilani.ac.in)

Both parts were built with GitHub Spec Kit: constitution → specify → clarify → plan → tasks →
analyze → implement. Claude Code was the coding agent. Each part has a harness that checks the
generated code, and each part keeps its evidence: Spec Kit transcripts, a snapshot of the first
generation taken before any harness run, harness results and a harness log ending in a human
decision.

| Part | What it is | Folder |
|---|---|---|
| 1A | GIS Scorer: a deterministic re-implementation of the General Investor Score | [Part-1A](Part-1A/README.md) |
| 1B | Order Extraction Agent: a local LLM (qwen3.5:4b) agent with a layered evaluation | [Part-1B](Part-1B/README.md) |

The reference for Part 1A, written by reading myportfolio-web: [GIS_REFERENCE.md](GIS_REFERENCE.md).

## Results

| Part | Deterministic harness | Evaluation | Repair cycles | Human decision |
|---|---|---|---|---|
| 1A | PASS on the first run: lint, bandit, 476 tests, 100% coverage | not applicable (no model) | 0 | ACCEPT |
| 1B | PASS on the final code: 652 tests, coverage ≥ 90% on `src` and `run_eval` (the first run failed lint, repaired) | FAIL: L1 27/28, L2 27/28, L3 92.0% (needs 100/100/≥80) | 1 harness + 2 evaluation | open, for the author |

Logs:
- [Part-1A/evidence/harness-log.md](Part-1A/evidence/harness-log.md)
- [Part-1B/evidence/harness-log.md](Part-1B/evidence/harness-log.md)

## How to run

Each part has its own `.venv`. Setup and commands are in that part's README.
- Part 1A needs only Python.
- Part 1B's evaluation also needs Ollama running with `qwen3.5:4b`, plus the judge endpoint set in `.env`.
