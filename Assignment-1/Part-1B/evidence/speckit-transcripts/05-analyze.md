# 05-analyze — headless transcript

Real slash command run headless with `claude -p ... --output-format stream-json --verbose < /dev/null` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T10:26:12Z. Full event stream (every tool call and result): `05-analyze.events.jsonl`.

## Prompt

```text
/speckit-analyze Non-interactive run. Produce the standard read-only cross-artifact analysis of spec.md, plan.md, research.md, data-model.md, contracts/ and tasks.md for the active feature against the constitution: findings table (ID, category, severity, location, summary, recommendation), coverage summary, constitution alignment, unmapped tasks, metrics. PROVISIONAL P-1..P-4 are known owner-pending items: report them at most once, not as defects. Pay particular attention to: thresholds and scoring formula being identical everywhere; the evaluation runner being independent of the agent's own validators; service vs application failure separation; the judge never affecting the verdict; dataset category minimums. Do not modify any files.
```

## Output (final report)

I've read all the artifacts and cross-checked them. Here is the report.

## Specification Analysis Report: `001-order-extraction-agent`

**Read:** constitution v1.0.0, spec.md, plan.md, research.md, data-model.md, quickstart.md, all five files in `contracts/`, and tasks.md (T001–T091). No files were changed. There is no `.specify/extensions.yml`, so no hooks ran.

### Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution (III, quality gates) | CRITICAL | constitution.md:143-144; plan.md:97; spec.md:197,212 (FR-024, FR-026); tasks.md:276-316 (T027–T030), :664 (T091) | The gate before the first evaluation requires the **spec** to contain the ground truth. The ground truth only exists in `evals/dataset.json`, written in T027–T029. No task ties it to a spec revision, yet plan.md:97 says the gate "is already met". FR-026 requires ground-truth changes to be "attributable to a spec revision", but the spec never records the expected dataset hash. T030 allows ground-truth fixes with only a task-log note. | After T030, add a task that records the dataset SHA-256 (and `dataset_version`) in spec.md as a dated revision. Have `run_eval` record whether the run's hash matches it. From then on, ground-truth edits go through spec revisions, not the task log. Correct the plan's gate claim. |
| C2 | Constitution (III); scoring formula | CRITICAL | spec.md:216,220,240,255 (FR-027/028/029/031); plan.md:102-112; research.md:232-234 (R-6), :412-425 (R-13); tasks.md:443,481-482 (T044, T053, T054) | The scoring and verdict logic that will run is not the formula written in the spec. The plan's own readings change it: (a) the agent's G-5/C-1…C-3 and MR-SCHEMA/MR-CONSIST errors fail layers 1/2 even though they are not INV-1…INV-9; G-5 alone can turn a spec PASS (a layer-3 miss) into FAIL. (b) OUT-DATE is added to layer 1. (c) A case with no candidate scores 0 of 9 in layer 3. (d) INV-9 skips `other`-currency orders, which is a gap-fill and *looser* than the literal text, not "stricter, never looser". (e) Verdict rule 1 is widened to quantisation, env mismatch and failed API calls. Principle III requires the formula to be **written in the spec**; recording it in the plan is not enough. | Before T091, revise spec FR-027/028/029/031 and AC-5.6 to state (a)–(e). Thresholds and cases do not change. Then T044–T047 test exactly what the spec says. |
| C3 | Constitution (II) | CRITICAL | constitution.md:53-54; spec.md:168-169 (FR-011, FR-012) | Read literally, Principle II requires a missing fact to be "null **plus an explicit missing marker**". `missing_fields` only covers `order_value` and `client`. A missing `company`, `announcement_date` or `execution_period` is just null, and the only signal is that its evidence key is absent. | This needs the owner's decision and cannot be settled by reinterpreting it here. Either add an explicit marker for optional fields (a schema change, made before 1.0 is first used), or amend the constitution to say "required facts". |
| C4 | Constitution (Technical Constraints) | CRITICAL | tasks.md:130 (T002 `setuptools>=77`); plan.md:37-40; research.md:477-484 (R-16) | The build dependency `setuptools` is a range, not an exact pin, and the plan never justifies it. `pip install -e .` fetches it at install time. The dev tools' transitive dependencies (coverage, pluggy, PyYAML, stevedore, …) are not pinned either. | Pin `setuptools==<version>` and justify it in R-16. Consider a constraints file for the transitive dependencies. |
| F1 | Inconsistency (task order) | HIGH | tasks.md:467-469 (T048), :493 (T057), :386 (T036), :402 (T039), :538 (T064), :584-586 (T071, T073), :676-677 | T048 runs the **real 27-case dataset** end to end and expects X01–X04 to have `model_called: false`. During US5, though, the guards only do UTF-8 decoding (the reject rules arrive in T071/T073), and `is_new_order: false` raises `NotImplementedError` until T064. The US5 green run (T057) therefore cannot pass before US2 and US3. The Dependencies section claims US5 does not depend on US2–US4. | Move Phase 4 (US5) after US3, or after US4 so M02/M03 rank correctly, and fix the dependency text. |
| E1 | Evaluation independence | HIGH | research.md:401-404 (R-13); tasks.md:445 (T044 AST allow-list), :479 (T051), :481 (T053); plan.md:90 | Layer 1, INV-1 and dataset gate DG-4 all run on the **agent's own** hand-written schema validator (`validators.validate` / `check_output`, about 150 lines; R-1). One bug in it hides failures in the agent, in the evaluation and in the ground-truth check at once. FR-033 also lets repairs change "validators", so a repair can change the measuring instrument mid-cycle (Principle VII: "SAME evaluation"). | Freeze the shared schema functions during repair cycles (changing them needs a spec revision), and record a hash of `validators.py` in `run.json`. Optionally, re-check the FR-015 status-shape rules independently in `run_eval.py`. |
| E2 | Service vs application failures | HIGH | research.md:298-304 (R-9); tasks.md:221-223 (T019); constitution.md:84 | The classification table only maps `URLError`, connection refused and `TimeoutError`. With urllib, errors raised in `getresponse()`/`read()` reach the caller unwrapped: `RemoteDisconnected`/`ConnectionResetError` and `http.client.IncompleteRead`. That is exactly what happens if Ollama's runner crashes mid-generation with `stream: false`. These are "connection errors" under Principle IV, but they would go unclassified and could crash the run. The judge client has the same gap. | Map every `OSError` and `http.client.HTTPException` to a service-failure kind in `default_transport` (or state that the `Transport` normalises them). Add a test for each in T019 and T042. |
| E3 | Constrained-field coverage | HIGH | tasks.md:394 (T038), :402 (T039), :487 (T056) | Some constrained fields have no exact `data-model.md Entity.field` citation in any task: `Order.order_value`, `Order.currency`, `Order.unit`, `Order.client` (only `ExtractionResult.order`, `Order.order_type` and `Order.execution_period` are cited); `ModelResponse.company_quote`, `.announcement_date_quote`, `.order_type_quote`, `.execution_period_quote` (cited only as the wildcard "`*_quote`"); `CaseResult.categories` and `CaseResult.covers`. | Add the exact citations to T039 (Order.*), T038 (each `*_quote`) and T056 (CaseResult.categories/covers). |
| F2 | Inconsistency (terminology) | MEDIUM | spec.md:189 (FR-023), :269 (Key Entities); contracts/eval-results.md:95,105-107 | The spec defines application failures as "schema, invariant **or semantic** misses". The results contract counts only layer-1/2 failures and explicitly leaves layer-3 misses out of `application_failures`. | Align them: either change FR-023 to say semantic misses are reported separately as layer-3 misses, or include them in the contract's application-failure count. |
| F3 | Inconsistency (acceptance criteria vs FR) | MEDIUM | spec.md:123-124 (AC-5.1, AC-5.2) vs :255 (FR-031); tasks.md:455 (T046) | AC-5.2 says any layer-1/2 failure gives FAIL "regardless". Under FR-031 the pin check comes first, so the result is INCONCLUSIVE, and T046 tests that case. AC-5.1 also leaves out the pin precondition. | Add "Given the pin check passes" to AC-5.1 and AC-5.2. |
| U1 | Underspecification (failure handling, judge) | MEDIUM | research.md:389-425 (R-13); contracts/eval-results.md:21; tasks.md:470 (T048) | Nothing says how an **unexpected exception** is handled, whether from `agent.run` on one case or from the judge client. If it ends the run (`completed: false`, exit 3, no verdict), a judge fault would **prevent** a verdict, which goes against FR-030's "judge failures MUST NOT change the verdict". | In R-13, say that an agent exception becomes a case-level application failure (stage `exception`) and the run continues, and that judge exceptions are contained as `kind: unparseable/other`. Add a test to T046/T048 where the judge raises. |
| U2 | Underspecification (guards vs dataset) | MEDIUM | spec.md:177 (FR-017 "letters (any script)"); research.md:139-142 (R-3); tasks.md:313 (J02 Hindi), :558-568 (T066) | R-3 counts only L\*, N\*, P\* and Sc as recognised, so combining marks (Mn/Mc, e.g. Devanagari vowel signs) count as **unrecognised**, and `isalpha()` splits words at them. Hindi text lowers the 85% ratio. No task checks that every non-rejected dataset input (J02, X05) actually passes `guards.check`. | Add M\* to the recognised set, matching FR-017, and add a test in T066/T068: every dataset case's input gives `guards.check` the expected rejection reason, or `ok`. |
| U3 | Underspecification (reporting) | MEDIUM | contracts/eval-results.md:59-70; research.md:424 | A case with an unresolved service failure "counts as not passing" in layers 1–3 but is never an application failure. Whether it shows up in `layers.layer1.failed_cases` is not stated, so a report could show L1 26/27 next to `application_failures.count: 0`. | Add a separate `not_scored` / `service_unresolved` list to each layer block, and keep such cases out of `failed_cases`. |
| U4 | Service vs application failures | MEDIUM | spec.md:189 (FR-023); research.md:304 (R-9 `bad_envelope`) | `bad_envelope` (a non-JSON Ollama envelope) is a retryable service failure that is not in FR-023's closed list. Because a service failure leads to INCONCLUSIVE rather than FAIL, this classification affects the verdict. | Add `bad_envelope` to FR-023 through the spec revision in C2. |
| G1 | Constitution (I) enforcement | MEDIUM | plan.md:89; tasks.md:204-208 (T016) | The plan says byte identity with `contracts/` enforces a version bump. It does not: the schema can change while `$id` and `const "1.0"` stay the same. | Pin each schema's SHA-256 against its version, in the spec and in T016, so any content change without a bump fails. |
| G2 | Coverage of the evaluation runner | MEDIUM | research.md:453-455 (R-14); contracts/harness.md:26,49 | `.harness/run_eval.py`, which holds all the scoring and verdict code, is outside coverage measurement, outside `bandit -r src` and outside the `nosec` scan. | Add `.harness` to the bandit and `nosec` steps. Consider a separate coverage report for `run_eval.py` (this is the owner's call). |
| A1 | Ambiguity | MEDIUM | data-model.md:201-202 (DG-3 "and so on"); tasks.md:479 (T051) | The runner's DG-3 rule is open-ended ("and so on"). T051 implements it from that text, while T020's enumeration is the complete one. | Copy T020's full FR-025 enumeration into DG-3. |
| L1 | Inconsistency (numbers) | LOW | plan.md:62-63 | "About 22 model calls" should be 23 (27 cases minus X01–X04). | Correct it. |
| L2 | Inconsistency (dataset coverage) | LOW | data-model.md:212-240; tasks.md:237 (T020) | The Covers column has no FR id for N04, M02, A02–A04, V01, K01, R02, X02 and J02, and lists non-FR/AC ids (INV-7, INV-9, P-1.x). T020 requires a non-empty `covers.fr` containing spec ids only. | Add FR ids in the plan table, or state the rule in T027–T029. |
| L3 | Inconsistency | LOW | spec.md:176 (FR-016 order); research.md:132-134 | R-3 checks for undecodable input (garbled) before the whitespace and length checks. The rationale is in R-3 but not in the spec. | Add a note to FR-016 in the C2 spec revision. |
| L4 | Inconsistency | LOW | research.md:418-420; data-model.md:199-206 | R-13 says the gate checks the dataset's `invariants` list against the ground truth, but no DG rule does that. | Add a DG rule, or remove the claim. |
| L5 | Underspecification | LOW | research.md:368-380 (R-12) | The judge timeout is not set (a 300 s default × 3 attempts × 17 cases could add hours), and `max_tokens: 400` may be used up by `<think>`. | Set a judge timeout and token budget in R-12. |
| L6 | Inconsistency (API) | LOW | contracts/cli.md:75; tasks.md:79-90 | `agent.run` has no `sleep` parameter in cli.md but has one in tasks.md. `JudgeResult` and `GenerateResult` are not in data-model.md. | Sync them. |
| L7 | Underspecification | LOW | tasks.md:113; contracts/model-response.schema.json:4 | There is no rule for bumping `PROMPT_VERSION` after a prompt repair, and the mr-1 title is tied to "p1". | Bump the prompt version on every repair that changes the prompt (each repair is logged), and decouple the schema title. |
| D1 | Duplication | LOW | spec.md FR-027/028/029/031, SC-001..003, AC-5.1; contracts/eval-results.md:57; tasks.md T046 | The thresholds are restated in eight or more places. They are **identical today**: 100% / 100% / ≥ 0.80 (0.80 passes, 0.7999 fails), 0.5% tolerance, FX 84/90 and 17 × 9 = 153 all match. | Keep one constant in `run_eval.py` with a test that compares it to the spec. |
| P1 | Provisional (reported once) | INFO | research.md:13-87; spec.md:289-296 | P-1…P-4 are known items waiting on Balaji, not defects. Two side effects are worth knowing: P-2, P-3 and P-4 appear only in research.md, not in spec Assumptions, yet they set ground truth for N05 and P01. And FR-025's ambiguous-non-order and missing-client minimums depend on P-1.1 and P-1.2, each of which only A02/A03 or K01 satisfies. | When the owner decides, record P-2…P-4 in spec Assumptions and re-check the FR-025 rows. |

### What you asked me to check

- **Thresholds and formula:** the numbers agree everywhere I looked, including FX rates, the `num_ctx` boundary values (8652 → 4096, 8655 → 4097), retries (3 attempts) and the 153 layer-3 fields. The scoring *logic* that will actually run differs from what the spec says (C2).
- **Runner independence:** INV-1…INV-9, the layer-3 rules and ranking are re-implemented in `run_eval.py`, and an AST test enforces it. The schema validator is shared (E1), and the agent's own validator errors feed into the layer results (C2a).
- **Service vs application failures:** separate counters are well designed. The gaps are unclassified connection exceptions (E2), `bad_envelope` missing from the spec (U4), the definition of "application failure" (F2) and how unresolved cases are listed (U3).
- **Judge isolation:** solid. `verdict()` takes no judge input, and T046 tests three judge variants. The one remaining risk is a judge exception stopping the run (U1).
- **Dataset minimums:** every FR-025 row is met (6 / 3 / 3 / 4 / 1 / 1 / 2 / 4 / 2). There is a small fragility around P-1.1 and P-1.2 (P1), and no check that the dataset inputs pass the guards (U2).

### Coverage summary

| Requirement key | Has task? | Task IDs | Notes |
|---|---|---|---|
| FR-001, FR-002, FR-005, FR-006, FR-015 | Yes | T016, T017, T033, T060, T068 | |
| FR-003, FR-004 | Yes | T017, T031, T032, T033 | Model behaviour is measured by layer 3 |
| FR-007, FR-008 | Yes | T020, T031 | Prompt and ground truth only (decided by the model) |
| FR-009 | Yes | T075–T077, T079, T081 | |
| FR-010, FR-011, FR-014 | Yes | T032, T033, T059, T060, T076 | |
| FR-012, FR-013 | Yes | T058–T060, T063, T064 | |
| FR-016, FR-017 | Yes | T066, T068, T069, T071, T073, T088 | Combining marks issue (U2) |
| FR-018 | Yes | T031, T067, T068, T072 | |
| FR-019 | Yes | T018, T025, T032–T034 | |
| FR-020, FR-021 | Yes | T006, T013, T015, T019, T023, T026, T034 | |
| FR-022 | Yes | T047, T048, T052, T056 | |
| FR-023 | Yes | T019, T026, T033, T048 | Gap E2 |
| FR-024, FR-025, FR-026 | Yes | T020, T027–T029, T043, T051 | Binding to the spec missing (C1) |
| FR-027, FR-028 | Yes | T044, T053 | C2 |
| FR-029 | Yes | T045, T054 | C2 |
| FR-030 | Yes | T042, T046, T050 | U1 |
| FR-031 | Yes | T046, T055 | F3 |
| FR-032, FR-033, FR-034 | Yes | T010, T048, T056, T091 | |
| SC-001…SC-003, SC-005, SC-006 | Yes | T044–T048, T091 | Only achieved in the owner-run T091 |
| SC-004 | Yes | T066, T068, T069, T088 | |
| SC-007 | Yes | T032, T044 | |
| SC-008 | Yes | T048, T056 | |

### Constrained-field coverage

| Field (`Entity.field`) | Canonical location | Implementing task IDs | Notes |
|---|---|---|---|
| `Settings.*` (pins, generation settings, `num_ctx`, `max_chars`, versions) | data-model.md:12-21 | T003, T023, T024, T037, T071 | Cited; consistent (backoff [5, 10], 3 attempts, 20000) |
| `GuardResult.*` | :25-30 | T036, T071 | Cited; consistent |
| `PromptBundle.*` | :34-35 | T037 | Cited |
| `Attempt.*` | :41-49 | T026 | Cited; the envelope fields match T019 |
| `ModelResponse.is_new_order/orders/company/announcement_date/order_type/execution_period` | :58-63 | T038, T062 | Cited; MC-1 matches T059 |
| `ModelResponse.*_quote` (4 fields) | :59-62 | — | **Missing** (only the wildcard) → E3 |
| `MROrder.*` (6 fields) | :65-69 | T038, T079 | Cited; `>0`, iff rules consistent |
| `ExtractionResult.*` (9 fields) | :81-91 | T039, T064, T073 | Cited |
| `Order.order_type`, `Order.execution_period` | :93-94 | T039 | Cited |
| `Order.order_value/currency/unit/client` | :93-94 | — | **Missing** → E3 |
| `AdditionalOrder.*` | :95-96 | T039, T081 | Cited |
| `Success/ApplicationFailure/ServiceFailure.*`, `ValidationError.*` | :132-141 | T024, T039 | Cited; stage enum consistent |
| `DatasetFile.*`, `EvaluationCase.*` | :161-183 | T027–T029, T051 | Cited; id pattern consistent |
| `CaseResult.*` (except categories/covers) | :261-272 | T053, T054, T056 | Cited |
| `CaseResult.categories`, `CaseResult.covers` | :263 | — | **Missing** → E3 |
| `FeedbackRecord.*` (11 fields) | :276-279 | T056 | Cited |
| `EvaluationRun.*` | :319-328 | T052, T056 | Cited |

No task contradicts a data-model constraint.

### Constitution alignment issues

- **III** (C1, C2): ground truth and the scoring formula as executed are not fully written in the spec.
- **II** (C3): optional fields that are missing have no explicit missing marker.
- **Technical Constraints** (C4): `setuptools` is not pinned exactly.
- Related risks, not violations: VII (E1, repairs can change the shared validator), I (G1, the version bump is not enforced), IV (E2, connection errors are not classified).

### Unmapped tasks

None. T001, T005, T012, T013 and T089 are infrastructure or process tasks and map to the Technical Constraints and quality gates.

### Metrics

- **Total requirements:** 42 (FR-001…FR-034 plus SC-001…SC-008)
- **Total tasks:** 91 (T001–T091, two of them owner-run)
- **Coverage:** 100% of requirements have at least one task
- **Ambiguity count:** 5 (A1, U1, U3, L5, L7)
- **Duplication count:** 1 (D1)
- **Critical issues:** 4 (C1–C4); High 4; Medium 8; Low 8; Info 1

### Next actions

There are critical issues, so resolve them before `/speckit-implement`:

1. **`/speckit-specify` (spec revision):** record the plan's scoring readings (C2), `bad_envelope` (U4), the pin precondition in AC-5.1/5.2 (F3), the FR-016 note (L3), and a section binding the dataset hash (C1).
2. **Owner decision:** C3 needs either a constitution amendment or a schema change. Analyze cannot decide it.
3. **`/speckit-plan`:** pin `setuptools` and justify it in R-16 (C4); add the E2 exception mapping to R-9; freeze the shared validator during repairs (E1); add M\* to the recognised characters in R-3 (U2); set the judge timeout (L5); correct the gate claim and the call count.
4. **Edit tasks.md by hand:** move US5 after US3 or US4 (F1); add the Entity.field citations (E3); add the guard check over all dataset inputs (U2); add a task recording the dataset hash after T030 (C1); add a judge-exception test (U1).

Would you like me to suggest concrete remediation edits for the top 8 issues (C1–C4, F1, E1–E3)? I won't apply anything without your approval.
_Finished 2026-11-22T10:33:19Z, exit 0._
