# Contract: evaluation runner and results (`.harness/run_eval.py`)

**Design**: [../research.md](../research.md) R-11, R-12, R-13, R-15 | **Entities**: [../data-model.md](../data-model.md#2-evaluation-entities) | **Spec**: FR-022 … FR-034

## Invocation

```text
.venv/bin/python .harness/run_eval.py [--env-file PATH]
```

- There are no case filters and no threshold or settings options, so a partial or retuned run is
  impossible (Principle III).
- Paths are fixed: the dataset is `evals/dataset.json` and output goes to `evidence/`.
- The script changes to `Part-1B/` itself.

| Exit | Meaning |
|---|---|
| 0 | Verdict PASS |
| 1 | Verdict FAIL |
| 2 | Verdict INCONCLUSIVE |
| 3 | Runner or dataset error (dataset gate DG-1…DG-9, unreadable config, or an interrupted run). No verdict, and `evidence/eval-results.json` is not touched. An exception raised by the agent or the judge for one case is **not** a runner error; it is handled per case (rules below). |

The last line on stdout is `Verdict: <V>  L1 <a>/<n>  L2 <b>/<n>  L3 <c>/<m> (<pct>%)  run: evidence/eval-runs/<stamp>`.

## Run folder `evidence/eval-runs/<YYYYMMDDTHHMMSSZ>/`

```text
environment.json            # R-11: ollama version, model digest (installed vs pinned), quantisation,
                            #       python, pip freeze, git HEAD, platform, judge identity
run.json                    # FR-022 run metadata (data-model.md › Evaluation Run); completed: true|false
raw/<case_id>/attempt-<n>.json
                            # {request: {url, model, system, prompt, options incl. num_ctx, think, format,
                            #  stream}, response: {http_status, body (verbatim), raw_text}, timing, outcome}
cases/<case_id>.json        # Case Result (data-model.md) for every case, all layers
feedback/<case_id>.json     # Feedback Record for every failing case (FR-032, Principle VII)
judge/<case_id>.json        # judge request/response verbatim, parsed rating or failure kind
eval-results.json           # the results document below
summary.md                  # human report (layout below)
```

Rejected cases have no `raw/` folder. Each has `model_called: false` in `cases/<id>.json`
(FR-016).

`evidence/eval-results.json` is a byte-identical copy of the latest **completed** run's
`eval-results.json`.

## `eval-results.json` (format `eval-results/1.0`)

```json
{
  "format": "eval-results/1.0",
  "run_id": "20261122T101500Z",
  "run_dir": "evidence/eval-runs/20261122T101500Z",
  "verdict": "PASS | FAIL | INCONCLUSIVE",
  "verdict_rule": "1-pin-check | 2-app-failure | 3-service-failure | 4-thresholds-met | 5-thresholds-not-met",
  "verdict_reason": "one sentence, e.g. 'Layer 2 failed for 2 case(s): J01 (INV-7), M02 (INV-9).'",
  "thresholds": { "layer1": 1.0, "layer2": 1.0, "layer3": 0.8 },
  "layers": {
    "layer1": { "passed": 28, "total": 28, "score": 1.0, "threshold": 1.0, "met": true,
                "failed_cases": [], "not_scored": [], "checker_disagreements": [] },
    "layer2": { "passed": 28, "total": 28, "score": 1.0, "threshold": 1.0, "met": true,
                "failed_cases": [], "not_scored": [],
                "by_invariant": { "INV-1": {"applicable": 28, "failed": 0}, "...": {}, "INV-10": {"applicable": 24, "failed": 0}, "INV-11": {"applicable": 18, "failed": 0} },
                "by_agent_code": { "G-5": 0, "...": 0, "C-5": 0 } },
    "layer3": { "correct": 148, "compared": 162, "score": 0.914, "threshold": 0.8, "met": true,
                "by_field": { "order_value": {"correct": 17, "compared": 18}, "...": {} },
                "cases": 18, "not_scored": [] }
  },
  "application_failures": {
    "count": 0,
    "cases": [ { "case_id": "M02", "layers": [2], "checks": ["INV-9"], "stage": null, "feedback": "feedback/M02.json" } ]
  },
  "semantic_misses": {
    "count": 0,
    "cases": [ { "case_id": "N03", "fields": ["execution_period"], "feedback": "feedback/N03.json" } ]
  },
  "service_failures": {
    "model": { "count": 0, "unresolved_cases": [], "retried_attempts": 0,
               "attempts": [ { "case_id": "N04", "n": 1, "kind": "timeout" } ] },
    "judge": { "count": 0, "cases": [ { "case_id": "N04", "kind": "unparseable" } ] }
  },
  "judge": {
    "informational": true,
    "model": "qwen3.6-35b-a3b",
    "rated": 18,
    "mean_rating": 4.6,
    "ratings": [ { "case_id": "N01", "rating": 5, "rationale": "..." } ]
  },
  "pin_check": { "ok": true, "mismatches": [] },
  "dataset": { "path": "evals/dataset.json", "sha256": "…", "case_count": 28, "dataset_version": "1.0",
               "bound_sha256": "…", "bound_version": "1.0", "matches_spec": true },
  "metadata": "copy of run.json (FR-022)",
  "cases": [
    { "case_id": "N01", "outcome": "success", "status": "extracted", "expected_status": "extracted",
      "model_called": true, "attempts": 1, "scored": true, "l1": true, "l2": true, "l3": "9/9", "judge": 5 }
  ]
}
```

Rules (rev 2 aligns these with spec FR-023 and FR-031):

- **Four categories**, as in spec FR-023 rev 2, each counted only in its own block:
  - `application_failures`: cases that failed layer 1 or layer 2. This includes an unexpected
    agent exception, which has `"stage": "exception"` and `"checks": ["EXC"]`.
  - `semantic_misses`: cases that pass layers 1 and 2 but have at least one wrong layer-3 field.
    They are listed with the wrong fields, and they are never in `application_failures`.
  - `service_failures.model`: cases with an *unresolved* model service failure. The kinds are
    `timeout`, `unreachable`, `connection_lost`, `http_error`, `empty_response` and
    `bad_envelope`. Retried attempts that later succeeded are listed under `attempts` but are not
    counted as failures.
  - `service_failures.judge`: judge failures, with the kinds `unreachable`, `timeout`,
    `connection_lost`, `http_error`, `empty_response`, `bad_envelope`, `unparseable` and
    `exception`. A judge failure never stops the run.
- **Not scored (U3)**:
  - A case with an unresolved model service failure is listed in every layer block's
    `not_scored`, and in no layer's `failed_cases`. It is not in `application_failures` or
    `semantic_misses`.
  - It still counts in each layer's `total` as not passing (0 of 9 in layer 3), so it can never
    help a score (FR-031).
  - Example: one such case gives L1 `27/28`, `not_scored: ["N04"]`, `failed_cases: []`,
    `application_failures.count: 0`, and verdict INCONCLUSIVE (rule 3).
- **`value_in_cr` (rev 3)**: it is checked by INV-11 in layer 2 (and agent code C-5), never in
  layer 3, so `layers.layer3.by_field` keeps the nine FR-029 fields. A wrong `value_in_cr` is an
  application failure (`checks: ["INV-11"]`), not a semantic miss. The example numbers above use
  the rev 3 plan: 28 cases, 18 layer-3 cases, 18 × 9 = 162 compared fields. In the example,
  INV-10 applies to the 24 non-rejected cases and INV-11 to the 18 cases with an order.
- **Checker disagreement (E1)**: `layers.layer1.checker_disagreements` lists the cases where
  exactly one of the schema-file validator and the runner's `structural_check` rejected the
  candidate. Such a case fails layer 1 either way, and the list flags a bug in one of the two
  checkers.
- **Unexpected agent exception (U1)**: the run continues. The case's `cases/<id>.json` and
  `feedback/<id>.json` carry the exception type, message and traceback. `raw/<id>/` holds only the
  attempts made before the exception, if any.
- **Judge**: judge data never feeds `verdict` (FR-030). A unit test checks that `verdict` is the
  same with judge data present, absent, adversarial, or raising an exception.
- **Dataset binding (C1)**: `dataset.matches_spec` is shown in `summary.md` §1. When it is
  `false` or `null`, the run does not meet the constitution's gate before first evaluation and is
  flagged as such. The verdict itself is unchanged (spec FR-026, FR-031).
- **Layer 3**: field misses count against the threshold, not as application failures, per the
  FR-031 rule order. Every case with a wrong layer-3 field gets a `feedback/` record.

## `summary.md` layout (SC-008)

1. **Verdict**, the rule that decided it, and the reason. Also the dataset binding status
   (`matches_spec`), with a warning line when it is not `true`.
2. A layer table: layer, score, threshold, met?, not scored.
3. **Application failures**: a table with case, layer(s), failed checks (including `EXC`),
   expected vs actual (short) and a link to the feedback file. Then checker disagreements.
4. **Service failures (model)**: unresolved cases, then all retried attempts.
5. **Judge (informational, does not affect verdict)**: per-case rating and rationale, then judge
   failures.
6. **Layer 3 field breakdown and semantic misses**: per field and per case, then the
   `semantic_misses` list.
7. **Run metadata**: model tag and digest (installed vs pinned), Ollama version, settings, prompt and
   schema versions, dataset hash and its bound hash, code hashes, judge identity, start and end
   time, git HEAD.
8. A line stating: "ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it."
