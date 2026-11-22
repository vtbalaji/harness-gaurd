# Harness log: Part 1B Order Extraction Agent

Author: Balakrishnan, student ID 2026ns93087 (2026ns93087@wilp.bits-pilani.ac.in).
Feature: `specs/001-order-extraction-agent`. Date: 2026-11-22. All times are UTC.

Note: the owner's name was changed from "Balaji" to "Balakrishnan" (spec rev 5). The recorded Spec
Kit transcripts are kept verbatim and still show the earlier name.

## 1. Model under test and judge

| | Model under test (production agent) | LLM judge (layer 3, informational only) |
|---|---|---|
| Model | `qwen3.5:4b`, Q4_K_M, digest `d8b0f5e9760c…` | `qwen3.6-35b-a3b` |
| Runner | Ollama 0.32.14, `http://localhost:11434/api/generate` | "tinytitan" MLX OpenAI-compatible server, `http://127.0.0.1:8081/v1/chat/completions` (same Mac) |
| Settings | think=false, format=json, temperature 0.1, seed 42, num_predict 700, num_ctx = max(4096, len(prompt)//3 + 700 + 512), timeout 300 s, up to 3 attempts for service failures only | temperature 0, max_tokens 600, thinking off, timeout 180 s |
| Source | myportfolio-web `scripts/fundamental/announcements_v2/helpers.py` (read-only). The seed is an addition: myportfolio-web sets none | myportfolio-web's switch-back 35B tier (`run-announcements.sh`) |

Endpoints come from `.env`, which is gitignored. `.env.example` is committed. There are no keys or secrets. Every run records
the model digest, Ollama version and settings in `evidence/eval-runs/<run>/environment.json`, and the pin check
passed in all three runs.

## 2. Threshold and scoring, declared in the spec before any evaluation

Spec FR-027 to FR-031, rev 2 (dataset binding rev 4, hash `8ab71de9…`). None of these changed during the runs.

- **Layer 1, structural**: the share of cases whose output is valid against schema 1.0. Must be **100%**.
- **Layer 2, invariants**: INV-1 … INV-11 must hold for **100%** of cases. Among them:
  - evidence quotes are verbatim substrings of the source;
  - the value's digits appear in its quote;
  - no invented client;
  - the status is right;
  - `missing_fields` and `unstated_fields` are right;
  - injection does not change behaviour;
  - the top order really is the largest;
  - `value_in_cr` matches the deterministic conversion.
- **Layer 3, semantic field accuracy**: correct fields ÷ compared fields over the 18 extracted or needs_clarification cases, 162 fields in all. It uses documented normalisation (unit conversion with 0.5% tolerance, a name match that ignores legal suffixes, and so on). Must be **≥ 80%**.
- **Judge**: per-case faithfulness, 1–5. Informational only; it never affects the verdict.
- **Verdict**: PASS only if L1 = 100%, L2 = 100% and L3 ≥ 80%, with no unresolved service failures. A run with an unresolved service failure is INCONCLUSIVE. Model and judge service failures are counted apart from application failures.
- **Rules**: no lowering of thresholds, no dropping of cases, and ground truth changes only by spec revision.

## 3. How the code was generated (Spec Kit)

Spec Kit 1.4.4.dev0 with the Claude integration. Every step ran as a real headless slash command via
`claude -p`. Transcripts and full event streams are in `evidence/speckit-transcripts/`.

- **00 constitution** (v1.0.0, 7 principles) → **01 specify** → **02 clarify**. Clarify recorded the num_ctx fact. The first clarify attempt was lost to an account usage limit and is kept as `02-clarify.failed-usage-limit.md`.
- **03 plan** → **04 tasks** (91 tasks, later 102) → **05 analyze**: 24 findings, 4 of them critical.
- **06 remediation** (spec rev 2) and **07 owner revision rev 3**: Q3 adds `value_in_cr`; Q4 limits v1 to at most 4 orders.
- **08 implement**: in two parts, because the account usage limit interrupted it at 11:54Z.
- **Owner decisions**: Balakrishnan confirmed Q1–Q7 (P-1 … P-5) in the project thread and they are recorded in the spec's Clarifications. Spec rev 5 covers the owner's name change and restores the schema to its pinned bytes.

**Initial generation**: 652 tests, all green with fake transports. It was snapshotted to `evidence/initial-generation/` with
MANIFEST and SHA256SUMS, and committed as a550a3a before any harness or evaluation run.

## 4. Deterministic harness (`.harness/run_harness.sh`)

Steps:
- ruff check
- ruff format --check
- bandit -r src .harness (no medium or high findings)
- a nosec/noqa suppression scan
- pytest
- coverage ≥ 90% on `src/order_agent`
- coverage ≥ 90% on `.harness/run_eval.py`

| Run | Result | Detail |
|---|---|---|
| 20261122T154635Z | **FAIL** | gate 1a E501: a 102-character comment line in `prompt.py`. The owner rename caused it, and the same line in the frozen snapshot copy failed too. → `evidence/feedback/1.md` |
| 20261122T154708Z | PASS | all gates; 652 tests |
| 20261122T155752Z / …155809Z | FAIL (mid-repair) | the p1→p2 prompt bump: a version pin test, then an E501 in a docstring I edited. Fixed before the run that counts |
| 20261122T155830Z | PASS | prompt p2 |
| 20261122T160813Z | FAIL (mid-repair) | the FR-018 test "at most two few-shot examples" caught my first p3 draft, which had 4 examples. The draft was reworked, and the limit was respected rather than relaxed |
| 20261122T160840Z | **PASS** | prompt p3, the final code. 652 tests; total coverage 96% (src and run_eval each ≥ 90%) |

## 5. Evaluation runs (`.harness/run_eval.py`, all 28 cases, same dataset each time)

| Run | Prompt | L1 structural | L2 invariants | L3 field accuracy | Service fail. | Judge mean | Verdict |
|---|---|---|---|---|---|---|---|
| 20261122T154734Z | p1 (initial generation) | 25/28 (89.3%) | 19/28 (67.9%) | 123/162 = 75.9% | 0 | 3.47 | **FAIL** |
| 20261122T155859Z | p2 (repair 1) | 28/28 (100%) | 25/28 (89.3%) | 151/162 = 93.2% | 0 | 3.61 | **FAIL** |
| 20261122T160905Z | p3 (repair 2) | 27/28 (96.4%) | 27/28 (96.4%) | 149/162 = 92.0% | 0 | 3.59 | **FAIL** |

Thresholds: 100% / 100% / ≥ 80%. `evidence/eval-results.json` holds the latest run, and each run's full
record is in `evidence/eval-runs/<run>/`: raw requests and responses, per-case results, feedback files and judge output.

### Repair cycle 1: run 1 → p2 (`evidence/feedback/2.md`)

Issues found in the original generated agent, 9 cases:

| Case | Failed check | Problem |
|---|---|---|
| U01, M02, K01 | INV-3 | the model rescaled amounts ("INR 48.5 million" → 48500000, unit absolute) |
| M03, E02 | MR-SCHEMA → L1 | `client_quote` key missing |
| V01 | MC-1 → L1 | no order entry when no value is stated |
| A01, A04 | INV-5 | a range or "up to" value labelled not_an_order |
| E01 | INV-5 | "approximately ₹500 crore (including GST)" nulled |

Fix: prompt only:
- all six keys on every order;
- worked examples of the "as stated" rule for million and crore amounts;
- "a range, an upper bound or a missing value is still an order".

Considered and rejected: deriving values from the quote in code. FR-019 forbids clean-ups that alter values.

Rerun: 6 of the 9 fixed.

### Repair cycle 2: run 2 → p3 (`evidence/feedback/3.md`)

Remaining failures:

| Case | Failed check | Problem |
|---|---|---|
| M02 | INV-3 | "₹1.2 crore" → 12000000 |
| A04 | INV-5 | "up to" contract labelled not_an_order |
| E01 | INV-5 | "approximately … (incl. GST)" nulled |

Fix: prompt only, keeping the FR-018 limit of two examples:
- a new two-order example (lakh plus a decimal crore, "approximately … excluding taxes");
- an explicit ceiling-contract rule.

Rerun: M02, A04 and E01 fixed, but **E02 regressed**. The input "orders aggregating ₹600 crore from NTPC and NHPC" gave `order_value` null while `value_quote` was "₹600 crore". MC-3 failed, so the case fails layers 1 and 2. The prompt's rule "a stated total of itemised orders is not an order" most likely conflicts with its rule that an aggregate with no breakdown is one order.

### Stop

The brief allowed at most two quick repair cycles, and both were used. The final run is **FAIL**: layer 3 passes at 92.0% against the 80% threshold, but layers 1 and 2 each miss 100% on one case (E02). As the constitution requires, nothing was weakened: no threshold lowered, no case dropped, no ground truth changed, no test relaxed. The next repair would be to separate "aggregate with no breakdown" from "total of itemised orders" more clearly in the prompt. That repair was not attempted.

## 6. Final generation

`evidence/final-generation/` holds the code after both repairs. It differs from `initial-generation/` in exactly three files:
- `src/order_agent/prompt.py`: prompt p1 → p3, plus the comment fix;
- `tests/unit/test_prompt.py`: the FR-033 prompt-version pins p2 and p3;
- `pyproject.toml`: ruff `extend-exclude = ["evidence"]`, from harness repair 1.

## 7. Known limitations

- **Small dataset.** 28 synthetic cases. The prompt repairs were tuned while looking at failures from this same set, so the p2/p3 results show fit to this set, not general accuracy. A held-out set would be needed for that.
- **Run-to-run variation.** Even with seed 42 and temperature 0.1, a prompt change moves other cases: E02 passed with p2 and failed with p3. One run per prompt version does not measure variance.
- **The 4B model's limits.** It rescales units and confuses aggregate wording despite explicit rules. Deterministic code checks catch every such error (INV-3, MC-3), but FR-019 rightly keeps code from silently correcting them.
- **The judge is a model on the same machine.** Both models share the Mac's memory. The judge is informational only, and its ratings (mean ~3.6/5) were not checked against people.
- **Lint scope.** `ruff` excludes the `evidence/` snapshot copies, because frozen code cannot be edited (harness repair 1).
- **Earlier-name artefacts.** The recorded transcripts, and the `$comment` text in the pinned output schema, still contain the earlier owner name and the old "PROVISIONAL" wording, kept byte-for-byte for the G1 pin (spec rev 5).

## 8. Final human decision

**Final human decision: ACCEPT / REJECT** (Balakrishnan to fill in)

Decision:

Justification:

Signed / date:
