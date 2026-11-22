# 00-constitution — headless transcript

Real slash command run headless with `claude -p ... --output-format stream-json --verbose < /dev/null` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T08:19:17Z. Full event stream (every tool call and result): `00-constitution.events.jsonl`.

## Prompt

```text
/speckit-constitution Non-interactive run; ratification date 2026-11-22, version 1.0.0. Project: "Order Extraction Agent" (Assignment-1 Part-1B), an LLM agent that extracts new-order details from Indian stock-exchange corporate announcements using a LOCAL 4B model (qwen3.5:4b on Ollama), evaluated by a harness. Principles:
I. Contract-first output: every agent response conforms to a versioned JSON schema; anything else is a failure, never silently patched into a pass.
II. Grounded extraction (no hallucination): every extracted value is backed by an evidence quote that is a verbatim substring of the source text; the agent never invents a client, value or date; absent facts are reported missing.
III. Evaluation threshold declared before evaluation (NON-NEGOTIABLE): the scoring formula and pass thresholds live in the spec before any evaluation run; they are never lowered, cases are never dropped, and ground truth changes only through a spec revision. If the model cannot meet the threshold after reasonable repairs, stop and report.
IV. Layered evaluation: deterministic schema and invariant/property layers are authoritative; semantic field accuracy is measured against ground truth with documented normalisation; an LLM judge may only add information and never replaces layers 1-2. Model/service failures (timeouts, runner down) are reported separately from application failures.
V. Untrusted input: announcement text is data, never instructions; prompt-injection content must not change behaviour, and guardrails are deterministic code around the model.
VI. Reproducible local model: model tag + digest, runner version and generation settings (temperature, seed, context, think off, JSON mode) are pinned and recorded with every evaluation; no API keys or secrets in the repo (endpoint via .env, with .env.example committed).
VII. Repair through evidence: each failure produces a structured feedback file; repairs go to prompt, parser, validators or guardrails, then the SAME evaluation is rerun.
Technical constraints: Python 3.12+ in Part-1B/.venv; stdlib + minimal pinned deps; pytest, ruff, bandit for the deterministic parts; myportfolio-web is read-only reference, never imported.
Workflow: constitution -> specify -> clarify -> plan -> tasks -> analyze -> implement -> evaluate/repair; owner (Balaji) gives the final human decision.
Write only .specify/memory/constitution.md.
```

## Output (final report)

I've written `.specify/memory/constitution.md` as **version 1.0.0**, ratified and last amended **2026-11-22**. It was the first fill-in: the file was still the blank template, so none of your principles were lost or changed. That's why it's 1.0.0 rather than a version bump.

**What's in it:**
- **Seven principles (I–VII)**, matching your list. The template only had five slots, so VI (Reproducible Local Model) and VII (Repair Through Evidence) were added as extra sections. III is marked NON-NEGOTIABLE, and Governance says no exceptions to it are allowed.
- **Technical Constraints:** Python 3.12+ in `Part-1B/.venv`, the standard library plus a few pinned dependencies, `qwen3.5:4b` running locally on Ollama, and `pytest`, `ruff` and `bandit` as gates. `myportfolio-web` is for reading only and is never imported or changed.
- **Development Workflow & Quality Gates:** the stage order from constitution through evaluate/repair, and the checks before the first evaluation and before reporting results. Balaji makes the final accept/reject decision, and agents may recommend but not record that decision.
- **Governance:** how to amend it, how version numbers change, and when compliance is checked (plan, analyze, and before each reported run).

**Other points:**
- **Things I added that you didn't list:**
  - Any clean-up of raw model output (such as stripping code fences) must be in the documented parser and logged for each case.
  - The prompt-injection cases must be part of the evaluation set.
  - Ground-truth comparisons use normalisation rules, such as crore/lakh conversion, written in the spec.
- **Sync Impact Report:** it sits as a comment at the top of the file. It mentions the template's placeholder names on purpose to show what replaced what. It's meant only for review, so delete it before you commit. No placeholders are left in the constitution itself, and nothing was left as a TODO.
- **Nothing else was touched.** There is no `.specify/extensions.yml`, so there were no hooks to run, and no templates were changed. Check the plan template's "Constitution Check" section against these seven principles when you run `/speckit-plan`.

**Suggested commit message** (after removing the report comment):
```
docs: ratify Order Extraction Agent constitution v1.0.0 (7 principles + constraints, workflow, governance)
```

## Next Actions
Everything you asked for was constitution content, so no separate requests were set aside. The next step in your workflow is `/speckit-specify` for the Order Extraction Agent. That spec needs to include the schema version, scoring formula, pass thresholds, normalisation rules and ground truth before any evaluation runs.
_Finished 2026-11-22T08:20:35Z, exit 0._
