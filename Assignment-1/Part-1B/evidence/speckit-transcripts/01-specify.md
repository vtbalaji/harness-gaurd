# 01-specify — headless transcript

Real slash command run headless with `claude -p ... --output-format stream-json --verbose < /dev/null` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T08:21:59Z. Full event stream (every tool call and result): `01-specify.events.jsonl`.

## Prompt

```text
/speckit-specify Non-interactive run (no one can answer questions live; make informed defaults, record them in Assumptions, and use at most 3 [NEEDS CLARIFICATION] markers only for genuinely blocking choices). Short name: order-extraction-agent.

Feature: New-Order Announcement Extraction Agent. Input: the raw text of one Indian stock-exchange (NSE/BSE) corporate announcement. Output: one JSON object (schema version "1.0") with:
- status: extracted | not_an_order | needs_clarification | rejected
- company (the announcing listed company), announcement_date (ISO YYYY-MM-DD or null)
- order: order_value (number as stated), currency (INR | USD | EUR | other), unit (crore | lakh | million | billion | thousand | absolute), client, order_type (enum: supply, epc_construction, services, export, defence, government, other), execution_period (text as stated, or null)
- additional_orders: list (possibly empty) of further orders in the same announcement, each with order_value, currency, unit, client and their evidence; the top-level order is the one with the largest value after unit conversion
- evidence: for every non-null extracted field, a verbatim quote from the source text supporting it
- missing_fields: names of required order fields (order_value, client) that are absent from the source
Behaviour: not_an_order for announcements that are not order wins (results, board meetings, dividends, etc.); needs_clarification when it is an order but the value or the client is absent or ambiguous; rejected for empty, whitespace-only, non-text/garbled or over-length input (decided by deterministic guards before any model call); text inside the announcement that tries to instruct the agent (prompt injection) must not change behaviour.
Production model: local qwen3.5:4b on Ollama (http://localhost:11434, Ollama 0.32.14, digest d8b0f5e9760c, Q4_K_M), same runner and settings as the owner's myportfolio-web pipeline: /api/generate, think=false, format=json, temperature 0.1, num_predict 700, num_ctx = max(4096, prompt-dependent), timeout 300 s; plus seed 42 for reproducibility (an addition over myportfolio-web, which sets no seed). Endpoints come from a .env file; .env.example is committed; no secrets in the repo.

Evaluation (declare this in the spec as requirements, BEFORE any evaluation exists):
- Dataset: at least 18 cases in evals/dataset.json, each with input text, ground-truth output, expected properties and the FR/AC ids it covers. Coverage: normal orders; crore/lakh/million unit handling; multiple orders in one announcement; ambiguous wording; missing value; missing client; non-order announcements (financial results, board meeting); malformed/empty text; adversarial prompt injection. Text is realistic but synthetic or public.
- Layer 1, structural: share of cases whose agent output validates against the schema. Threshold 100%.
- Layer 2, invariants/properties: per case all applicable invariants hold: (INV-1) schema-valid; (INV-2) every evidence quote is a verbatim substring of the source after whitespace normalisation; (INV-3) the stated order_value's digits appear in its evidence quote; (INV-4) client is not invented: its evidence quote is in the source; (INV-5) status equals the ground-truth status (covers not_an_order, needs_clarification, rejected); (INV-6) missing_fields equals the set of required fields that are null; (INV-7) injection cases: output equals what the same announcement without the injected text should produce (status and no injected values). Threshold: 100% of cases.
- Layer 3, semantic field accuracy: over cases whose ground-truth status is extracted or needs_clarification, compare company, order_value (compared after converting to INR-equivalent base units with crore 1e7, lakh 1e5, million 1e6, billion 1e9, thousand 1e3; tolerance 0.5%; currency must match), currency, unit, client and company (case/punctuation/legal-suffix-insensitive match), order_type (exact), execution_period (normalised text), announcement_date (exact), and the count of additional_orders. Score = correct fields / compared fields. Threshold >= 80%.
- An LLM judge (a 35B model, qwen3.6-35b-a3b on the owner's "tinytitan" MLX server, OpenAI-compatible at http://127.0.0.1:8081/v1/chat/completions, temperature 0) adds a per-case faithfulness rating inside layer 3 as an informational signal only; it never replaces or overrides layers 1-2 or the field-accuracy score, and does not gate the verdict.
- Verdict: PASS only if layer 1 = 100%, layer 2 = 100% and layer 3 >= 80% with zero unresolved service failures. Model/service failures (timeouts, runner down, HTTP errors, empty response) are recorded separately from application failures (schema/invariant/semantic misses); a case may be retried up to 2 times for a service failure only; a run with any remaining service failure is INCONCLUSIVE, not PASS. Judge failures are recorded separately and never change the verdict.
- Rules: thresholds are never lowered, cases are never dropped, and ground truth changes only through a spec revision; if the 4B model cannot meet the threshold after reasonable repairs, stop and report.
Users: an analyst who wants reliable order-win data from announcements; the evaluator (Balaji) who decides ACCEPT/REJECT from the evidence.
```

## Output (final report)

I've written the spec for the order-extraction agent. It has no open clarification markers, and every quality-checklist item passed on the first pass. No git commit was made.

- **Feature directory:** `specs/001-order-extraction-agent`
- **Spec:** `specs/001-order-extraction-agent/spec.md`
- **Checklist:** `specs/001-order-extraction-agent/checklists/requirements.md`
- `.specify/feature.json` now points at that directory.

There is no `.specify/extensions.yml`, so no hooks ran before or after, and no branch was created. Work stays on `main`.

**What's in the spec**
- **Five user stories:**
  - US1 (P1): extract a single order with evidence.
  - US5 (P1): you decide ACCEPT/REJECT from the run report.
  - US2: label non-orders and orders with a missing value or client.
  - US3: reject bad input and resist prompt injection.
  - US4: several orders in one announcement.
  - Each acceptance scenario has an id (AC-1.1 … AC-5.6) so dataset cases can name what they cover.
- **FR-001 to FR-034:**
  - The output schema "1.0" and the rules for each status.
  - Fixed input checks that run before any model call.
  - Injection handling.
  - The model settings you specified.
  - The evaluation: 18 or more cases with a minimum per category, the three layers with their formulas and comparison rules, the judge as information only, how the verdict is decided, and the integrity rules.

**Things I added beyond your brief** (all stricter, none looser):
- **`rejection_reason` field:** one of `empty`, `whitespace_only`, `too_long` or `garbled` for rejected input, null otherwise.
- **INV-4 is tighter:** the client name itself must appear inside its quote. Without this, INV-4 adds nothing that INV-2 doesn't already check.
- **INV-8:** a field has an evidence entry if and only if it is non-null.
- **INV-9:** the top-level order really is the largest.
- **Verdict order:** a layer 1 or 2 failure makes the run FAIL even if a service failure is also unresolved. A model digest or Ollama version mismatch makes it INCONCLUSIVE.

**Defaults I chose that you should check** (all listed under Assumptions):
- **Length limit:** 20,000 characters.
- **Garbled input:** under 85% recognisable characters, or fewer than 3 real words.
- **Not an order:** L1-bidder status, MoUs and cancellations. Letters of Award or Intent and work orders do count as orders.
- **Unnamed client:** "a leading PSU" counts as a missing client.
- **Ambiguous value:** ranges and "up to X" count as ambiguous. "Approximately X" and "over X" report X.
- **Mixed currencies:** fixed rates of USD = 84 and EUR = 90 INR, used only to pick the largest order. Reported values are never converted.
- **Context-length formula:** left for the plan to define, because I couldn't read myportfolio-web from this workspace. If you can share its exact formula, I'll write it in so the settings truly match.

**Next step:** run `/speckit-clarify` to confirm those defaults before ground truth is written, or go straight to `/speckit-plan`.
_Finished 2026-11-22T08:27:39Z, exit 0._
