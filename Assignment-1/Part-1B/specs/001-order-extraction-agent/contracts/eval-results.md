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
| 3 | Runner or dataset error (dataset gate DG-1…DG-7, unreadable config). No verdict, and `evidence/eval-results.json` is not touched. |

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
    "layer1": { "passed": 27, "total": 27, "score": 1.0, "threshold": 1.0, "met": true, "failed_cases": [] },
    "layer2": { "passed": 27, "total": 27, "score": 1.0, "threshold": 1.0, "met": true,
                "failed_cases": [], "by_invariant": { "INV-1": {"applicable": 27, "failed": 0}, "...": {} } },
    "layer3": { "correct": 140, "compared": 153, "score": 0.915, "threshold": 0.8, "met": true,
                "by_field": { "order_value": {"correct": 16, "compared": 17}, "...": {} },
                "cases": 17 }
  },
  "application_failures": {
    "count": 0,
    "cases": [ { "case_id": "M02", "layers": [2], "checks": ["INV-9"], "feedback": "feedback/M02.json" } ]
  },
  "service_failures": {
    "model": { "count": 0, "unresolved_cases": [], "retried_attempts": 0,
               "attempts": [ { "case_id": "N04", "n": 1, "kind": "timeout" } ] },
    "judge": { "count": 0, "cases": [ { "case_id": "N04", "kind": "unparseable" } ] }
  },
  "judge": {
    "informational": true,
    "model": "qwen3.6-35b-a3b",
    "rated": 17,
    "mean_rating": 4.6,
    "ratings": [ { "case_id": "N01", "rating": 5, "rationale": "..." } ]
  },
  "pin_check": { "ok": true, "mismatches": [] },
  "dataset": { "path": "evals/dataset.json", "sha256": "…", "case_count": 27 },
  "metadata": "copy of run.json (FR-022)",
  "cases": [
    { "case_id": "N01", "outcome": "success", "status": "extracted", "expected_status": "extracted",
      "model_called": true, "attempts": 1, "l1": true, "l2": true, "l3": "9/9", "judge": 5 }
  ]
}
```

Rules:

- **Counting**
  - `application_failures.count` is the number of cases that failed layer 1 or layer 2.
  - `service_failures.model.count` is the number of cases with an *unresolved* model service
    failure.
  - Retried attempts that later succeeded are listed under `attempts` but are not counted as
    failures.
  - Judge failures are counted only under `service_failures.judge`.
- **Separation**: an unresolved service failure is never listed under `application_failures`
  (FR-023, FR-032).
- **Judge**: judge data never feeds `verdict` (FR-030). A unit test checks that `verdict` is the
  same with judge data present, absent or adversarial.
- **Layer 3**: only layer-3 failures, with no layer 1 or layer 2 failure, appear in each case's
  `l3` and in `feedback/`. They do not appear in `application_failures`. Field misses count against
  the threshold, not as application failures, per the FR-031 rule order.

## `summary.md` layout (SC-008)

1. **Verdict**, the rule that decided it, and the reason.
2. A layer table: layer, score, threshold, met?
3. **Application failures**: a table with case, layer(s), failed checks, expected vs actual (short)
   and a link to the feedback file.
4. **Service failures (model)**: unresolved cases, then all retried attempts.
5. **Judge (informational, does not affect verdict)**: per-case rating and rationale, then judge
   failures.
6. **Layer 3 field breakdown**: per field and per case.
7. **Run metadata**: model tag and digest (installed vs pinned), Ollama version, settings, prompt and
   schema versions, dataset hash, judge identity, start and end time, git HEAD.
8. A line stating: "ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it."
