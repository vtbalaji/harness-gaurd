<!--
Sync Impact Report
==================
Version change: (unratified template) → 1.0.0
Bump rationale: initial ratification; every placeholder replaced with project governance.

Modified principles (template slot → adopted title):
  - [PRINCIPLE_1_NAME] → I. Contract-First Output
  - [PRINCIPLE_2_NAME] → II. Grounded Extraction (No Hallucination)
  - [PRINCIPLE_3_NAME] → III. Evaluation Threshold Declared Before Evaluation (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Layered Evaluation
  - [PRINCIPLE_5_NAME] → V. Untrusted Input
Added principles (beyond the template's five slots):
  - VI. Reproducible Local Model
  - VII. Repair Through Evidence
Added sections:
  - Technical Constraints (was [SECTION_2_NAME])
  - Development Workflow & Quality Gates (was [SECTION_3_NAME])
Removed sections: none

Templates requiring updates: none modified by this command (scope limited to this file).
  ⚠ plan-template.md "Constitution Check" gates are derived at runtime; verify during /speckit-plan.
Follow-up TODOs: none. No placeholders deferred.
-->

# Order Extraction Agent Constitution

Assignment-1, Part-1B: an LLM agent that extracts new-order details from Indian stock-exchange
corporate announcements using a local 4B model (`qwen3.5:4b` served by Ollama), evaluated by a
harness.

## Core Principles

### I. Contract-First Output

- Every agent response MUST conform to a versioned JSON schema; the schema version MUST be
  carried in, or unambiguously bound to, every response.
- A response that fails schema validation (malformed JSON, missing required fields, wrong types,
  unknown enum values) MUST be recorded as a failure.
- Code MUST NOT silently coerce, patch or default a non-conforming response into a passing one.
  Any deterministic repair of raw model output (e.g. stripping code fences) MUST be part of the
  documented parser, MUST be logged per case, and MUST NOT invent field values.
- Schema changes MUST bump the schema version and be reflected in the spec before use.

Rationale: a stable contract is what makes downstream consumers and the harness trustworthy;
silent patching hides exactly the failures evaluation exists to reveal.

### II. Grounded Extraction (No Hallucination)

- Every extracted value (client, order value, currency, dates, scope, etc.) MUST be accompanied
  by an evidence quote that is a verbatim substring of the source announcement text, under the
  matching rule (e.g. whitespace normalisation) documented in the spec.
- The agent MUST NOT invent a client, value, date or any other fact. A fact not stated in the
  source MUST be reported as missing (null plus an explicit missing marker), never guessed.
- Evidence verification MUST be performed by deterministic code; a value whose evidence fails
  verification MUST be treated as a failure, not accepted on the model's word.

Rationale: extracted order data may inform financial decisions; an unverifiable value is worse
than an honest "missing".

### III. Evaluation Threshold Declared Before Evaluation (NON-NEGOTIABLE)

- The scoring formula and every pass threshold MUST be written in the spec before any
  evaluation run is executed.
- Thresholds MUST NOT be lowered, and evaluation cases MUST NOT be dropped, skipped or excluded
  to reach a pass.
- Ground truth MUST change only through a recorded spec revision that states the reason; it
  MUST NOT be edited to match model output.
- If the model cannot meet the threshold after reasonable repairs (Principle VII), work MUST
  stop and the result MUST be reported honestly as a failure with the evidence collected.

Rationale: a threshold chosen after seeing results measures nothing; the value of the harness is
that it can say "no".

### IV. Layered Evaluation

- Layer 1 (schema) and Layer 2 (invariants/properties, including evidence grounding) are
  deterministic and authoritative; a case failing either layer fails regardless of other layers.
- Layer 3 (semantic field accuracy) MUST be measured against ground truth using normalisation
  rules (e.g. currency/units, crore/lakh conversion, date formats, name casing) documented in the
  spec before evaluation.
- An LLM judge, if used, MAY only add information (diagnostics, qualitative notes); it MUST NOT
  override, replace or rescue a Layer 1 or Layer 2 result.
- Model/service failures (timeouts, runner unavailable, connection errors) MUST be reported in a
  separate category from application failures, and MUST NOT be counted as passes.

Rationale: deterministic layers are reproducible and cheap to trust; separating infrastructure
faults from application faults keeps repair effort pointed at the right cause.

### V. Untrusted Input

- Announcement text is data, never instructions. It MUST be delimited as data in prompts, and
  instructions embedded in it MUST NOT alter the agent's task, output format or behaviour.
- The evaluation set MUST include prompt-injection cases, and those cases MUST pass the same
  layers as any other case.
- Guardrails (input size limits, output validation, grounding checks, allow-listed fields) MUST
  be deterministic code around the model; the model's own compliance MUST NOT be the only
  defence.

Rationale: exchange filings are third-party content; a small local model is easy to steer, so
safety must not depend on it.

### VI. Reproducible Local Model

- Every evaluation run MUST record: model tag and digest, runner (Ollama) version, and the
  generation settings — temperature, seed, context length, thinking disabled, and JSON/format
  mode — together with the prompt and schema versions.
- These settings MUST be pinned in configuration, not chosen ad hoc per run.
- No API keys, tokens or secrets MAY be committed. The model endpoint MUST be read from `.env`;
  `.env` MUST be git-ignored and a `.env.example` with placeholder values MUST be committed.

Rationale: results from an unpinned model are not comparable across runs, so repairs cannot be
shown to work.

### VII. Repair Through Evidence

- Every failing case MUST produce a structured feedback file (case id, layer failed, expected
  vs. actual, raw model output, reason) that a repair can cite.
- Repairs MUST target the prompt, parser, validators or guardrails — never the thresholds, the
  ground truth (outside Principle III's revision path) or the case list.
- After each repair, the SAME evaluation (same cases, same thresholds, same pinned settings)
  MUST be rerun, and each repair cycle MUST be logged with what changed and why.

Rationale: repairs justified by evidence and verified by the identical evaluation are the only
ones that demonstrate improvement rather than goal-post moving.

## Technical Constraints

- Language/runtime: Python 3.12+ in the project-local virtual environment `Part-1B/.venv`.
- Dependencies: standard library first; any third-party dependency MUST be minimal, justified
  in the plan, and pinned to an exact version.
- Model: `qwen3.5:4b` served locally via Ollama; no hosted LLM API is used for the agent.
- Quality tooling for the deterministic parts: `pytest` (tests), `ruff` (lint/format),
  `bandit` (security scan). These MUST pass before an evaluation result is reported.
- `myportfolio-web` is a read-only reference: it MAY be consulted for domain understanding but
  MUST NOT be imported, vendored, or modified.

## Development Workflow & Quality Gates

- Workflow order: constitution → specify → clarify → plan → tasks → analyze → implement →
  evaluate/repair. A later stage MUST NOT begin while an earlier stage has unresolved
  constitution violations.
- Gate before first evaluation: spec contains the schema version, scoring formula, pass
  thresholds, normalisation rules and ground truth (Principles I, III, IV).
- Gate before reporting: `pytest`, `ruff` and `bandit` pass; run metadata per Principle VI is
  recorded; feedback files exist for every failure (Principle VII).
- Evaluation outcomes MUST be reported with application failures and model/service failures
  shown separately (Principle IV).
- The owner (Balakrishnan) gives the final human decision (accept/reject) on the evaluated result;
  agents MAY recommend but MUST NOT record that decision on the owner's behalf.

## Governance

- This constitution supersedes other practices for this project. The plan's Constitution Check
  and the analyze step MUST verify compliance with every principle; any deviation MUST be listed
  with justification in the plan's complexity/deviation tracking, and deviations from
  Principle III are not permitted.
- Amendments MUST be made by editing this file with a Sync Impact Report, approved by the
  owner, and propagated to dependent spec artifacts before the next evaluation run.
- Versioning follows semantic versioning: MAJOR for removing or redefining a principle in a
  backward-incompatible way; MINOR for adding a principle/section or materially expanding
  guidance; PATCH for clarifications and wording fixes.
- Compliance review occurs at plan, analyze and before each reported evaluation run.

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
