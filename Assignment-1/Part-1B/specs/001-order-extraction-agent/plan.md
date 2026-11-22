# Implementation Plan: New-Order Announcement Extraction Agent

**Branch**: `001-order-extraction-agent` (spec directory name; no branch hook is configured, so work stays on `main`) | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-order-extraction-agent/spec.md`

## Summary

The agent reads the raw text of one NSE/BSE announcement and returns one schema-1.0 JSON object.
The status is `extracted`, `not_an_order`, `needs_clarification` or `rejected`. Every value comes
with verbatim evidence, and the model under test is the local `qwen3.5:4b` on Ollama.

The pipeline is: deterministic **guards** → **prompt** (announcement delimited as data) →
**client** (Ollama `/api/generate`, settings pinned) → **parser** (three documented clean-up rules
only) → strict validation of a compact **model response** → deterministic **assembly** (ranking,
`missing_fields`, status) → **post-validation** (schema, grounding, denylist, consistency). Only a
result that passes all of these is emitted. Anything else is surfaced as an application failure
with the raw output, or as a service failure.

A single evaluation runner (`.harness/run_eval.py`) scores a 27-case dataset:

- layer 1 (schema), layer 2 (INV-1…INV-9), layer 3 (field accuracy ≥ 80%), each implemented
  independently of the agent's own checks;
- an informational judge (`qwen3.6-35b-a3b`);
- the FR-031 verdict, with service, judge and application failures counted separately;
- full evidence written under `evidence/eval-runs/<stamp>/`.

A Part-1A-style harness (ruff, bandit, pytest with ≥ 90% coverage) gates the deterministic code,
and `run_all.sh` chains the harness and the evaluation.

## Technical Context

**Language/Version**: Python ≥ 3.12 (`Part-1B/.venv` runs 3.14.7)

**Primary Dependencies**:

- Runtime: **standard library only**. HTTP uses `urllib.request` through a hand-built
  `OpenerDirector`. JSON Schema validation is done by an in-package validator for a declared
  keyword subset (R-1).
- Dev, pinned exactly: `ruff==0.14.0`, `bandit==1.9.1`, `pytest==8.4.2`, `pytest-cov==7.0.0`.

**Storage**: files only:

- `schemas/*.json` (contracts);
- `evals/dataset.json`;
- `evidence/` (harness results, eval runs, `eval-results.json`, repair log);
- `.env` (git-ignored); `.env.example` is committed.

**Testing**:

- pytest with branch coverage ≥ 90% on `src/order_agent`;
- all HTTP faked through an injected transport;
- an autouse fixture blocks real sockets;
- tests named with FR/AC/INV ids.

**Target Platform**: local macOS (Darwin), offline. Ollama 0.32.14 runs at `localhost:11434`. The
judge is the MLX "tinytitan" server at `127.0.0.1:8081`.

**Project Type**: single Python package with a CLI (`python -m order_agent <file>`), plus an
evaluation runner and harness scripts.

**Performance Goals**: each model request stays within 300 s (SC-006). A full evaluation of 27
cases runs sequentially, about 22 model calls plus 17 judge calls. Expected wall time is
10–30 minutes on the owner's machine. This is not a gate.

**Constraints**:

- generation settings pinned in code: temperature 0.1, seed 42, `num_predict` 700, `think` false,
  `format` json, `num_ctx = max(4096, len(prompt)//3 + 700 + 512)`, timeout 300 s;
- ≤ 3 attempts, for service failures only;
- input ≤ 20,000 code points;
- ≤ 4 itemised orders per announcement (P-3);
- no secrets in the repo;
- `myportfolio-web` is read-only and is not imported.

**Scale/Scope**: one announcement per call and a single user. The dataset has 27 cases (≥ 18
required). Batch processing, fetching, PDF conversion, persistence and UI are out of scope.

No item is marked NEEDS CLARIFICATION. The owner fixed the technical context, and the open domain
defaults are recorded as **PROVISIONAL — pending Balaji** in [research.md](./research.md#provisional-decisions)
(P-1…P-4).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle / rule | How the plan complies | Pre-design | Post-design |
|---|---|---|---|
| **I. Contract-First Output** | `schemas/output.schema.json` is version 1.0 and every result carries `schema_version: "1.0"`. Nonconforming output is an application failure (`MR-SCHEMA`, `MR-CONSIST`, `OUT-SCHEMA`, `OUT-DATE`). The parser's only clean-up is PC-1…PC-3, logged per case (R-8). Assembly A-1…A-7 is documented and derives fields without creating or altering values (R-5). A schema change needs a version bump, enforced by the contract test that requires byte identity with `contracts/`. | ✅ | ✅ |
| **II. Grounded Extraction** | Every non-null field has a verbatim quote. G-1…G-4 run in the agent before emission, and INV-2/3/4/8 are re-implemented independently in the evaluation. Null plus `missing_fields` is used instead of guessing (FR-012). There is no fallback that drops ungrounded fields (R-7). | ✅ | ✅ |
| **III. Threshold Declared Before Evaluation (NON-NEGOTIABLE)** | Thresholds (100% / 100% / ≥ 80%), formulas, normalisation and verdict order are already in the spec. The runner has no threshold, settings or case-filter options. Dataset gate DG-1…DG-7 and the dataset fingerprint make ground-truth changes detectable. The PROVISIONAL defaults change ground truth only through a spec revision. | ✅ | ✅ |
| **IV. Layered Evaluation** | Layers 1 and 2 are deterministic and authoritative. Layer 3 uses the spec's normalisation. The judge is informational and is structurally excluded from the verdict function (R-12, with a unit test). Model service, judge and application failures have separate counters, and an unresolved service failure is never a pass (R-13). | ✅ | ✅ |
| **V. Untrusted Input** | The announcement is delimited as data with a hash-derived marker (R-4). Injection cases J01 and J02 go through the same layers, plus INV-7. Guards, schema allow-list, grounding, code-derived status and ranking, and the exchange denylist are deterministic, so the model's own compliance is not the only defence. The residual risk (an injected value copied verbatim is "grounded") is caught by INV-7 in evaluation and documented. | ✅ | ✅ |
| **VI. Reproducible Local Model** | Pins and settings are code constants. `.env` supplies only endpoints and identity, and an env/pin mismatch means INCONCLUSIVE (R-10). Each run records Ollama version, model digest and quantisation, all settings, `num_ctx` per request, prompt version and hash, schema and MR versions, dataset hash, judge identity and timing (R-11, data-model). `.env` is git-ignored and `.env.example` is committed. | ✅ | ✅ |
| **VII. Repair Through Evidence** | A feedback record is written for every failing case (data-model), including layer-3-only misses. Repairs follow FR-033 and are logged in `evidence/repair-log.md`, then the identical evaluation is rerun (R-15). | ✅ | ✅ |
| **Technical Constraints** | Python 3.12+ in `.venv`. Standard library first, with no runtime dependency (`jsonschema` considered and rejected, R-1). Dev tools pinned exactly. `qwen3.5:4b` on Ollama and no hosted LLM for the agent. pytest, ruff and bandit gates. `myportfolio-web` is not imported. | ✅ | ✅ |
| **Workflow & Quality Gates** | Constitution → specify → clarify → **plan** (this document) → tasks → analyze → implement → evaluate. The gate before first evaluation is already met in the spec. The gate before reporting is enforced by `run_all.sh`, which does not run the evaluation if the harness fails (R-14). ACCEPT/REJECT is left to Balaji: the report states it and never records it (FR-034). | ✅ | ✅ |

**Result**: PASS. There are no violations and no deviations from Principle III. Complexity Tracking
is empty.

Plan-level readings recorded so `/speckit-analyze` can check them. Each is stricter than the spec,
never looser.

- A case with no candidate output scores 0 of 9 in layer 3 (R-13).
- `other`-currency additional orders are outside INV-9's comparison, since they have no reference
  rate (R-6).
- Agent post-validation errors fail their own layer in addition to the harness checks (R-13).
- The G-5 exchange denylist is a guard on top of AC-1.5.
- Under P-2, a million/billion amount with no currency marker makes the value null (P-2).
- Judge service failures get the same 2 retries as the model (R-12).
- `2b-nosec-scan` is added to gate 2 (R-14).

## Project Structure

### Documentation (this feature)

```text
specs/001-order-extraction-agent/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0: R-1…R-16, PROVISIONAL P-1…P-4
├── data-model.md        # Phase 1: entities, assembly rules, dataset format, planned cases, verdict
├── quickstart.md        # Phase 1: run and validation guide
├── contracts/
│   ├── output.schema.json          # public contract, version 1.0 (copied verbatim to schemas/)
│   ├── model-response.schema.json  # internal model response, version mr-1 (copied verbatim to schemas/)
│   ├── cli.md                      # python -m order_agent
│   ├── eval-results.md             # run_eval.py, run folder, eval-results.json, summary.md
│   └── harness.md                  # run_harness.sh, run_all.sh, test layout
├── checklists/
└── tasks.md             # Phase 2, written by /speckit-tasks (not by this command)
```

### Source code (`Assignment-1/Part-1B/`)

```text
pyproject.toml                 # name order-agent, requires-python >=3.12, dependencies = [], ruff/pytest/coverage config
requirements-dev.txt           # ruff==0.14.0 bandit==1.9.1 pytest==8.4.2 pytest-cov==7.0.0
.env.example                   # OLLAMA_URL, AGENT_MODEL, AGENT_MODEL_DIGEST, JUDGE_URL, JUDGE_MODEL (no secrets)
.gitignore                     # .env, .venv/, __pycache__/, .pytest_cache/, .coverage, *.egg-info
schemas/
├── output.schema.json         # contract 1.0 (identical to contracts/)
└── model-response.schema.json # mr-1 (identical to contracts/)
src/order_agent/
├── __init__.py                # __version__, SCHEMA_VERSION
├── __main__.py                # python -m order_agent → cli.main()
├── config.py                  # .env loading, URL scheme check, PINNED_* constants, generation settings, num_ctx()
├── guards.py                  # FR-016/017 deterministic input checks (R-3)
├── prompt.py                  # system/user prompt, data markers, PROMPT_VERSION, template hash (R-4)
├── client.py                  # transport, Ollama generate client, OpenAI-compatible judge client, retries, failure kinds (R-9, R-12)
├── parser.py                  # PC-1…PC-3 (R-8)
├── validators.py              # JSON Schema subset validator, MR consistency, ranking, missing_fields/status derivation, post-validation G/C codes (R-1, R-5…R-7)
├── agent.py                   # pipeline and assembly A-1…A-7, AgentOutcome (data-model)
└── cli.py                     # argument parsing, exit codes (contracts/cli.md)
evals/
└── dataset.json               # 27 cases (data-model › Planned cases)
.harness/
├── run_harness.sh             # gates 1–3 → evidence/harness-results/<stamp>/
├── run_eval.py                # the one evaluation runner → evidence/eval-runs/<stamp>/, evidence/eval-results.json
└── run_all.sh                 # harness, then eval (eval skipped if harness fails)
tests/
├── conftest.py                # network block, fakes
├── unit/                      # test_guards, test_prompt, test_client, test_parser, test_validators, test_agent, test_config, test_cli
├── contract/                  # test_schemas, test_dataset
└── harness/                   # test_run_eval (importlib)
evidence/
├── harness-results/<stamp>/
├── eval-runs/<stamp>/
├── eval-results.json
├── repair-log.md
└── speckit-transcripts/       # existing
```

**Structure decision**: a single project with a `src` layout, using the owner's module list
(guards, prompt, client, parser, validators, agent, cli). Two small supporting modules are added:
`config.py`, so pins and `.env` handling live in one place (Principle VI), and `__main__.py`, which
`python -m` requires. The judge client lives in `client.py` beside the Ollama client, because both
share the transport and retry code.

## Phase outline

- **Phase 0 (done)**: [research.md](./research.md). All design choices and the provisional domain
  defaults are resolved there.
- **Phase 1 (done)**: [data-model.md](./data-model.md), [contracts/](./contracts/),
  [quickstart.md](./quickstart.md). The Constitution Check was re-evaluated and passes.
- **Phase 2 (`/speckit-tasks`)**, suggested order:
  1. scaffolding (pyproject, pins, `.gitignore`, `.env.example`, schemas, harness script);
  2. guards and tests;
  3. schema validator and tests;
  4. parser;
  5. ranking, assembly and post-validation;
  6. prompt and client with a fake transport;
  7. agent and CLI;
  8. dataset of 27 cases with ground truth;
  9. `run_eval.py` with tests;
  10. `run_all.sh`;
  11. green harness, then the first evaluation run, then repair cycles under FR-033.

## Risks

| Risk | Mitigation |
|---|---|
| The 4B model misses layer 2 (grounding, INV-7) or layer 3 < 80% | The compact model response (R-5) keeps arithmetic and bookkeeping out of the model. Strict feedback records drive prompt repairs. If it is still failing after reasonable repairs, stop and report (FR-033). |
| Output truncated at `num_predict` 700 | The compact format takes about 340 tokens for 4 orders. `done_reason` is recorded, and the dataset stays at ≤ 3 orders (P-3). |
| An injected value is copied verbatim and so passes grounding | INV-7 in evaluation. The prompt's data rule. A documented residual risk. |
| bandit B310 on `urllib` | Restricted `OpenerDirector`, URL scheme allow-list, no `nosec`. Fallback to `http.client` (R-9). |
| The judge's reasoning output breaks parsing | `<think>` stripping. Judge failures are informational and counted separately (R-12). |
| A boundary case (X05, 20,000 characters) is slow or degrades the model | `num_ctx` is about 7.9k by formula. The timeout is a service failure, recorded and retried. |

## Complexity Tracking

No constitution violations, so this table is empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
