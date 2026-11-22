# 04-analyze — headless transcript

Real slash command run headless with `claude -p` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T07:20:16Z.

## Prompt

```text
/speckit-analyze Non-interactive run. Produce the standard read-only cross-artifact analysis of spec.md, plan.md and tasks.md (and the constitution) for the active feature, with the findings table, coverage summary, constitution alignment, unmapped tasks and metrics. Note: the R-01/R-02 PROVISIONAL status is a known, owner-pending item; report it at most once, not as a defect to fix. Do not modify any files.
```

## Output

Warning: no stdin data received in 3s, proceeding without it. If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.
## Specification Analysis Report: `001-gis-scorer`

I compared spec.md, plan.md, tasks.md, data-model.md and constitution v1.0.0, and read research.md and `GIS_REFERENCE.md` for context. No files were changed. Every requirement has at least one task. There is one CRITICAL finding, and it is a one-line fix in tasks.md.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Constitution | CRITICAL | constitution.md:43-44; tasks.md:73, 91, 126, 160, 185, 208, 232, 257 (T007, T012, T029, T044, T051, T056, T062, T069) | Principle III says the suite "MUST pass in full before any task is marked complete". The red-phase tasks, and the test-writing tasks before them, are designed to finish with a failing suite. T007 even expects the harness to FAIL. Taken literally, checking them off breaks the MUST. | Add one rule to tasks.md: test-writing and confirm-red tasks are recorded in the task log, and are checked off only together with their phase's green-run task (T016/T039/T048/T053/T059/T064/T072/T079). This keeps the principle intact without weakening it. |
| I1 | Inconsistency (`ScoreItem.available`) | MEDIUM | data-model.md:104-106 vs spec.md:226-230, data-model.md:95 | The catalogue's Available column says "8 (capped → 4)", "7 (capped → 3)" and "10 (capped → 5)". Read the same way as Debt Reduction's "3, or 0 if not applicable", it says available drops when growth is capped. The spec ("4 of 8"), the invariant at line 95, and T019/T027 all say earned = 4 and available = 8. | Reword to "8 (capped: earns 4)" and similar. |
| I2 | Inconsistency | MEDIUM | tasks.md:160 (T044); also T051, T056, T027 | Several confirm-red steps say "confirm the new tests fail", but some new tests cover behaviour that already exists and will pass at once. Examples: US2-AS2 `roe=0` (already done in US1); PROVISIONAL R-01 `{"roe": None}` equals absent (the lenient `validate` already does this); V6 "0 accepted"; "two of three forensic inputs missing → not SUSPICIOUS"; "growth exactly 0 → no penalty"; US1-AS4 "no EBITDA Declining", which passes trivially until T057. | Reword: "tests of not-yet-implemented behaviour fail; list any that pass because the behaviour already exists". |
| U1 | Underspecification | MEDIUM | research.md:167-174; tasks.md T018, T022, T054 | The R-07 rule for derived values that overflow (value `null`, reason ends with "(value outside float range)", and −inf still triggers the decline penalty) is asserted by tests but is not in the spec. FR-002 allows any finite input, so the case can happen. It is research open item 2. | Once the owner confirms it, add it to the spec's Edge Cases. |
| U2 | Underspecification | MEDIUM | data-model.md:60-61; tasks.md T040, T066 | The error order is "known fields in table order, then list elements by index". It is unclear whether `recent_net_profit_margins[i]` errors sit at the list field's table position or after all the scalar fields. T040 and T066 assert exact order. | State the position explicitly in data-model.md. |
| U3 | Terminology | MEDIUM | spec.md:238, 309-310 | FR-022's "previous net margin" (`previous_net_profit_margin`) sits next to `net_profit_margin_year_ago` (FR-043). The spec never says which period "previous" means (prior quarter? prior year?), so callers cannot tell how to fill the two fields differently. | Define the period of each field in Key Entities. |
| E1 | Coverage gap (FR-003) | MEDIUM | tasks.md:125 (T028); research.md R-11(c) | The determinism check only walks imports. It would miss the builtin `open()`, `importlib` / `__import__`, and `sys` (stdin, argv), so FR-003's "no files / environment" rule is only partly enforced. | Add `sys` and `importlib` to the banned list, and an AST check for calls to `open` / `__import__`. |
| C2 | Constitution (workflow) | MEDIUM | constitution.md:82-83; tasks.md:275 (T075) | The workflow gate says "traceability stays complete" before a task is done. The automated traceability test only appears in Phase 9, so Phases 1–8 never check it. | Add T075 earlier, with the expected IDs scoped to completed stories, or have each green-run task check the coverage matrix. |
| I3 | Inconsistency | LOW | tasks.md:123 (T026) | T026 adds the STRONG SELL reason wording `"Total {t} < 25: STRONG SELL"` as a "task-specific narrowing". R-14 does not have it. | Add the wording to research.md R-14. |
| I4 | Inconsistency | LOW | spec.md:7 | The spec is still marked `Status: Draft`, though plan and tasks are done and the workflow requires owner review between phases. | Update the status after owner review. |
| C3 | Constitution II (record) | LOW | GIS_REFERENCE.md:158; spec.md:351 | The Assumptions record dropping the red-flag gate check. They do not name the reference's separate "capital-deployment redFlag" gate condition, which is only implied by Capital Deployment being out of scope. | Add it to the deviation bullet for completeness. |
| E2 | Coverage (SC-005) | LOW | tasks.md:274 (T074) | A wall-clock assertion inside the gated pytest step could make Gate 3 flaky on a loaded machine. The margin is wide, so the risk is small. | Accept, or add a pytest marker so it can be run separately. |
| A1 | Ambiguity | LOW | spec.md:245-246 (FR-024) | Shorthand like "≤ −150 or ≤ −25" and "< 0 or < 0 → 1" leaves the operands implied. | Write it as "ΔCCC < 0 or ΔDSO < 0 → 1". |
| A2 | Ambiguity | LOW | spec.md:348 | "Missing EBITDA growth is 0 of 0 … the reference ends with the same outcome" is listed as an intentional deviation but describes none. | Remove it, or say what actually differs. |
| D1 | Duplication | LOW | spec.md:82-83, 199-200, 210; tasks.md T021/T043 | "Zero is scored" appears in FR-001, an Edge Case and US2-AS2, and is tested in both T021 and T043. | Harmless; you can leave it. |

### Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
|---|---|---|---|
| FR-001 | ✅ | T010, T014, T021, T040, T041, T043, T045 | |
| FR-002 | ✅ | T040, T043, T045, T067 | |
| FR-003 | ✅ | T028, T068 | Enforcement is partial (E1) |
| FR-010 – FR-012 | ✅ | T017, T027, T030, T041, T046 | |
| FR-013 | ✅ | T018, T031, T041, T046 | |
| FR-014 – FR-016 | ✅ | T019, T027, T031, T055 | |
| FR-017 – FR-018 | ✅ | T020, T032, T041 | |
| FR-019 – FR-021 | ✅ | T021, T033, T043 | |
| FR-022 – FR-025 | ✅ | T022, T034, T041, T046 | |
| FR-026 – FR-027 | ✅ | T023, T035, T041 | |
| FR-030 | ✅ | T024, T037, T043 | |
| FR-040 – FR-044 | ✅ | T027, T054, T055, T057, T058 | |
| FR-050 | ✅ | T025, T037, T041, T047, T055 | |
| FR-051 | ✅ | T042, T047, T050 | |
| FR-052 | ✅ | T026, T037, T050 | |
| FR-053 – FR-055 | ✅ | T049, T050, T052 | |
| FR-060 | ✅ | T036, T060, T061, T063 | |
| FR-070 – FR-071 | ✅ | T009, T013, T024, T028, T067, T068 | |
| FR-072 | ✅ | T066, T067, T070, T071 | |
| SC-001 | ✅ | T027, T043, T050, T055, T061, T067 | |
| SC-002 | ✅ | T017–T026, T054, T060, T080 | The 100% check is a task, not a gate (justified in R-10) |
| SC-003 | ✅ | T028, T068 | |
| SC-004 | ✅ | T073 | |
| SC-005 | ✅ | T074 | See E2 |
| SC-006 | ✅ | T075, T077 | |

**Boundary spot-check:** every threshold in FR-010 to FR-060 is tested on both sides. Tasks use precondition asserts where a float subtraction could land off the boundary (FR-024 and FR-025 ΔD/E).

### Constrained-Field Coverage

| Field (`Entity.field`) | Canonical Location | Implementing Task IDs | Coverage / Consistency Notes |
|---|---|---|---|
| `Snapshot.piotroski` (int 0–9) | data-model.md §1 L16, V5 | T014, T045 | ✅ consistent (the R-02 normalisation is provisional) |
| `Snapshot.current_ratio` (≥ 0) | §1 L25, V6 | T045 | ✅ |
| `Snapshot.recent_net_profit_margins` (≤ 8 elements) | §1 L34, V7–V9 | T014, T045 | ✅ |
| The other 27 `Snapshot.*` fields (finite) | §1 | T045 (each named explicitly) | ✅ all 30 fields cited |
| `ScoreItem.status` (enum) / `.available` / `.earned` | §3 | T013, T057 | ⚠️ The catalogue's Available column contradicts the invariant (I1) |
| `Dimension.name` (9 values, fixed order) | §4 | T013 | ✅ |
| `LabelDecision.pre_gate` / `.final` (enum) / `.reasons` | §5 | T013, T052 | ✅ |
| `ValuationPart.available` (5/3/2), `Valuation.score` (0–10), `Valuation.max` / `.parts` | §6 | T013, T036, T063 | ✅ |
| `ScoreResult.total` (0–100), `.max` = 100, `.dimensions` (9) | §7 | T013, T037 | ✅ |
| `SnapshotValidationError.errors` (never empty), `FieldError.*` | §8 | T014 | ✅ |

No citation is unresolved, and no task restates a constraint that contradicts data-model.md.

### Constitution Alignment Issues

- **C1 (CRITICAL)**: under Principle III, test-writing and confirm-red tasks get checked off while the suite is red. The tasks.md fix is in the table.
- **C2 (MEDIUM)**: the traceability gate is only automated in Phase 9.
- Principles I, II, IV and V and the technical constraints are otherwise satisfied.
- **Known owner-pending item (reported once, as asked):** R-01 and R-02 are still PROVISIONAL, as the plan's Constitution Check condition and T082 already track. I'm not treating this as a defect.

### Unmapped Tasks

None are orphaned. These are infrastructure or quality-gate tasks with no FR of their own, each tied to the plan or the constitution: T001–T007 (setup and harness), T011/T015 (ladder primitive, R-03 / SC-006), T016, T038, T078, T079, T081, T082.

### Metrics

- Total requirements: 43 (37 FR, 6 SC)
- Total tasks: 82
- Coverage: 100% (43 of 43 have at least one task)
- Ambiguity count: 2 (A1, A2), plus 3 underspecified items (U1–U3)
- Duplication count: 1
- Critical issues: 1

### Next Actions

- **Before `/speckit-implement`:** fix C1. The quickest fix is to edit tasks.md by hand and add the "check off red-phase tasks with their green run" rule to the Format / Notes section.
- **Should fix:** I1 (data-model wording) and I2 (red-step wording). These are hand edits to data-model.md and tasks.md.
- **Spec refinement (`/speckit-specify` or `/speckit-clarify`):** U1 (overflow behaviour, together with owner open item 2), U2 (error order) and U3 (the meaning of `previous_net_profit_margin`).
- **Optional:** E1 (stronger AST check in T028), C2 (move T075 earlier), and the LOW items.

Would you like me to suggest concrete remediation edits for the top 5 issues (C1, I1, I2, U1, U2)? I won't apply anything without your approval.
_Finished 2026-11-22T07:24:04Z, exit 0._
