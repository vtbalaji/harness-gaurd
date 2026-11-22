# Part 1B — New-Order Announcement Extraction Agent

Author: Balakrishnan, student ID 2026ns93087 (2026ns93087@wilp.bits-pilani.ac.in)

The agent reads the raw text of one NSE/BSE corporate announcement and returns **one JSON
object, schema version 1.0**, with status `extracted`, `not_an_order`, `needs_clarification` or
`rejected`. It reports the announcing company, the announcement date, the order (value as
stated, currency, unit, client, order type, execution period), any further orders, and a
verbatim evidence quote for every non-null extracted field. The model under test is the local
`qwen3.5:4b` on Ollama; everything around it is deterministic code.

Design documents: [spec](specs/001-order-extraction-agent/spec.md) (rev 5) ·
[plan](specs/001-order-extraction-agent/plan.md) ·
[research](specs/001-order-extraction-agent/research.md) ·
[data model](specs/001-order-extraction-agent/data-model.md) ·
[contracts](specs/001-order-extraction-agent/contracts/) ·
[quickstart](specs/001-order-extraction-agent/quickstart.md) ·
[tasks](specs/001-order-extraction-agent/tasks.md).

## Pipeline

1. **Guards** (`guards.py`, FR-016/017): empty, whitespace-only, over-length (> 20,000 code
   points) and garbled input is rejected before any model call.
2. **Prompt** (`prompt.py`, FR-018): the instructions go in `system`; the announcement goes in
   `prompt`, between data markers whose id is derived from the text's SHA-256.
3. **Client** (`client.py`, FR-020/023): Ollama `/api/generate` with the pinned settings (think
   false, JSON mode, temperature 0.1, seed 42, `num_predict` 700, the myportfolio-web `num_ctx`
   formula, 300 s timeout). Service failures are classified and retried (at most 3 attempts).
4. **Parser** (`parser.py`, FR-019): only PC-1 (strip), PC-2 (one whole-text code fence) and
   PC-3 (`json.loads` to an object); each rule that changes the text is logged.
5. **Model-response checks** (`validators.check_mr`): the strict `mr-1` schema and the MC-1 …
   MC-3 consistency rules. Nothing is coerced or repaired.
6. **Assembly** (`agent.assemble`, A-1 … A-9): ranking (FR-009), `missing_fields`, status,
   `unstated_fields` and `value_in_cr`, all in code.
7. **Post-validation** (`validators.post_validate`): schema 1.0, calendar date, grounding
   G-1 … G-5 and consistency C-1 … C-5. Only a result that passes everything is emitted.

## Setup and commands

Run everything from `Assignment-1/Part-1B/`.

```bash
.venv/bin/python -m pip install -r requirements-dev.txt -c constraints-dev.txt
.venv/bin/python -m pip install -e .
cp .env.example .env            # .env is git-ignored; no secrets anywhere
.harness/run_harness.sh         # gates: ruff, bandit (+ no-suppression scan), pytest, coverage
.venv/bin/python -m order_agent path/to/announcement.txt
.venv/bin/python .harness/run_eval.py          # needs Ollama and the judge running
.harness/run_all.sh             # harness, then the evaluation only if the harness passes
```

### Exit codes

| Command | 0 | 1 | 2 | 3 | 64 | 78 |
|---|---|---|---|---|---|---|
| `python -m order_agent` ([cli.md](specs/001-order-extraction-agent/contracts/cli.md)) | result on stdout (any status, incl. `rejected`) | — | application failure (report on stderr) | service failure after 3 attempts | usage error or unreadable input | configuration error |
| `run_eval.py` ([eval-results.md](specs/001-order-extraction-agent/contracts/eval-results.md)) | PASS | FAIL | INCONCLUSIVE | runner or dataset error | — | — |
| `run_harness.sh` | every gate passed | a gate failed | — | — | — | — |
| `run_all.sh` | evaluation PASS | harness failed, or evaluation FAIL | INCONCLUSIVE | runner or dataset error | — | — |

## Evidence layout

```text
evidence/
├── harness-results/<UTC stamp>/   # one log per gate step, environment.txt, summary.md
├── eval-runs/<UTC stamp>/         # environment.json, run.json, raw/, cases/, feedback/,
│                                  # judge/, eval-results.json, summary.md
├── eval-results.json              # copy of the latest completed run's results
├── repair-log.md                  # one entry per repair cycle (FR-033)
└── speckit-transcripts/           # the Spec Kit runs that produced this work
```

## Owner decisions

All domain decisions are **CONFIRMED by Balakrishnan 2026-11-22** (spec Clarifications; details in
[research.md › Provisional decisions](specs/001-order-extraction-agent/research.md#provisional-decisions)):

- **P-1.1** L1-bidder status and MoUs are `not_an_order`.
- **P-1.2** An unnamed client ("a leading PSU", "a reputed overseas customer") is a missing
  client → `needs_clarification`; a named government department or PSU is a client.
- **P-1.3** Ranges, "between" and "up to" are ambiguous (value null); "approximately / about /
  over / more than X" reports X.
- **P-1.4** The input limit is 20,000 code points.
- **P-1.5** USD = 84 INR and EUR = 90 INR, for ranking orders only.
- **P-4** Amendments, extensions and corrigenda of a disclosed order are `not_an_order`.
- **P-5** Null optional fields are listed in `unstated_fields`.

And, from spec rev 3, also **CONFIRMED by Balakrishnan 2026-11-22**:

- **P-2** An amount in crore or lakh with no currency marker is INR.
- **P-3** At most 4 itemised orders per announcement; `num_predict` stays 700.

## `value_in_cr` (FR-035)

Every order object carries `value_in_cr`: the order value in crore **for INR amounts only**,
computed by deterministic code (never by the model) with exact decimal arithmetic, rounded half
up to 4 places (crore × 1, lakh × 0.01, million × 0.1, billion × 100, thousand × 0.0001, absolute
× 0.0000001). It is null for USD, EUR, `other` and null amounts: no FX conversion is ever applied
to a reported value. `order_value` itself is always reported as stated. The agent checks it as
C-5 and the evaluation re-derives it independently as INV-11.

## Spec revisions

| Rev | Date | What |
|---|---|---|
| 1 | 2026-11-22 | Initial spec (`/speckit-specify`, `/speckit-clarify`). |
| 2 | 2026-11-22 | Pre-evaluation remediation of the `/speckit-analyze` findings: scoring readings moved into the spec, `unstated_fields` (P-5), four failure categories, schema pins, the constants table. |
| 3 | 2026-11-22 | Owner answers Q3/Q4: P-2 and P-3 confirmed; the derived field `value_in_cr` (FR-035, INV-11, C-5); case U01. |
| 4 | 2026-11-22 | Dataset binding: the SHA-256 of `evals/dataset.json` recorded as a `DATASET-BINDING` line. |

Thresholds (layer 1 100%, layer 2 100%, layer 3 ≥ 80%), cases and ground truth change **only**
through a new dated spec revision that states the reason; a dataset change also needs a new
`DATASET-BINDING` line, and the contract test fails the harness for any unbound edit.

## Known residual risk: prompt injection

Injected text is presented to the model as data, and deterministic checks (strict schema,
grounding, code-derived status and ranking, the exchange denylist) limit what an injection can
change. One gap remains by design: an injected value copied **verbatim** from the injected text
is "grounded" by definition, so the agent's own grounding checks cannot catch it. The
evaluation's INV-7 (forbidden injected strings and numbers anywhere in the output) is the check
for that case (research.md R-4).

## Results (2026-11-22)

All runs used the same 28 cases, thresholds declared before any evaluation (L1 100%, L2 100%,
L3 ≥ 80%), qwen3.5:4b with seed 42, and the 35B judge as an informational signal.

| Run | Prompt | L1 | L2 | L3 | Verdict |
|---|---|---|---|---|---|
| 20261122T154734Z | p1 (initial generation) | 25/28 | 19/28 | 75.9% | FAIL |
| 20261122T155859Z | p2 (repair 1) | 28/28 | 25/28 | 93.2% | FAIL |
| 20261122T160905Z | p3 (repair 2) | 27/28 | 27/28 | 92.0% | FAIL |

The deterministic harness passes on the final code: 652 tests, coverage of at least 90% on `src`
and `run_eval`. On the original generated agent it found 9 failing evaluation cases and 1 lint
failure. The two prompt-only repairs fixed 8 of the 9. The final run still fails layers 1 and 2
on one case (E02, an aggregate order whose value was nulled), so the verdict is FAIL. Nothing was
lowered or dropped. Full account: [evidence/harness-log.md](evidence/harness-log.md).

## Decision

The evaluation reports a verdict (PASS / FAIL / INCONCLUSIVE) with all its evidence. **The
ACCEPT/REJECT decision is Balakrishnan's** (FR-034); no part of this system records it.
