# 05-analyze-remediation — headless transcript

Real slash command run headless with `claude -p` (Claude Code 2.1.330 (Claude Code)), --permission-mode acceptEdits, allowed tools: Read,Edit,Write,Glob,Grep,Bash(.specify/scripts/bash/*). Started 2026-11-22T07:24:19Z.

## Prompt

```text
Remediate the /speckit-analyze findings recorded in evidence/speckit-transcripts/04-analyze.md for specs/001-gis-scorer, editing ONLY the spec/plan/task artifacts (spec.md, plan.md, research.md, data-model.md, tasks.md). Do not write source code or tests. Apply exactly these:
- C1: add the rule to tasks.md Format/Notes that test-writing and confirm-red tasks are logged and checked off only together with their phase's green-run task.
- I1: data-model.md catalogue wording "8 (capped: earns 4)" etc.; available never drops when capped.
- I2: reword the confirm-red steps: "tests of not-yet-implemented behaviour fail; list any that pass because the behaviour already exists".
- U2: state explicitly in data-model.md where recent_net_profit_margins[i] errors sit in the error order (choose: at the list field's own table position, elements by index).
- U3: in spec.md Key Entities define the periods: previous_net_profit_margin = net margin of the immediately preceding quarter (traceable to the reference, which compares the latest and previous quarterly rows); net_profit_margin_year_ago / operating_margin_year_ago = the same quarter one year earlier.
- E1: strengthen the determinism/purity test task (T028) to also ban sys and importlib imports in the library modules (the CLI module may use sys), and an AST check for open() / __import__ calls in library modules.
- C2: have each phase's green-run task also run the traceability test scoped to that phase's completed stories.
- I3: add the STRONG SELL reason wording to research.md R-14.
- A1: rewrite FR-024 bands with explicit operands, e.g. "ΔCCC ≤ −150 or ΔDSO ≤ −25 → 4" … "ΔCCC < 0 or ΔDSO < 0 → 1". Same meaning.
- A2: remove the non-deviation bullet about missing EBITDA growth from the spec's intentional-deviations list.
- C3: add the reference's capital-deployment redFlag gate condition to the quality-gate deviation bullet.
Do NOT change: U1 (overflow behaviour stays an owner-pending open item in research.md), I4 (status), E2 (accepted), D1 (harmless), and R-01/R-02 stay PROVISIONAL. Do not alter any threshold, weight or boundary. Re-check the spec quality checklist still passes. End with a list of each finding and the exact edit made.
```

## Output

Warning: no stdin data received in 3s, proceeding without it. If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.
Language server "plugin:pyright-lsp:pyright" couldn't start: its program "pyright-langserver" wasn't found. Check that it's installed and on your PATH. If you don't need it, disable the plugin that provides it.
I applied all 11 remediations. Only spec.md, data-model.md, research.md and tasks.md changed; plan.md needed nothing, and no source or test files were written. I couldn't diff against a baseline because the repo has no commits yet, so I checked by hand that no threshold, weight or boundary changed.

## Spec quality checklist re-check
Every item in `checklists/requirements.md` still passes. There are no `[NEEDS CLARIFICATION]` markers, no implementation details went into spec.md (the new environment variable lives only in tasks.md), and A1 and U3 make FR-024 and the margin fields less ambiguous. I didn't edit the checklist file, because it isn't on the list of files you allowed.

## Findings and the exact edits

**C1**: tasks.md, Format section, new bullet "Checking off red-phase tasks (Constitution III)". Test-writing and confirm-red tasks are logged when done and checked off only with their phase's green run:
- T007 and T008–T012 with T016
- T017–T029 with T039
- T040–T044 with T048
- T049–T051 with T053
- T054–T056 with T059
- T060–T062 with T064
- T065–T069 with T072
- T073–T076 with T079

The Notes section repeats the rule.

**I1**: data-model.md catalogue now reads "8 (capped: earns 4)", "7 (capped: earns 3)" and "10 (capped: earns 5)". I also added an invariant: a capped item keeps its full available points and earns the fixed capped points, so available never drops when capped.

**I2**: T012, T029, T044, T051, T056, T062 and T069 now say "confirm that the … tests of not-yet-implemented behaviour fail (red); list any that pass because the behaviour already exists". The Tests header paragraph uses the same wording.

**U2**: data-model.md error order now says `recent_net_profit_margins` errors sit at that field's own table position, between `roce` and `ccc_days`. An error on the field itself (V7/V8) comes first, then the element errors `[i]` in index order, and they are not moved after the scalar fields. I also changed research.md R-05, which listed list elements after all known fields and would otherwise have contradicted this.

**U3**: spec.md Key Entities has a new "Margin periods" bullet:
- `previous_net_profit_margin` is the net margin of the quarter immediately before the one `net_profit_margin` describes, citing GIS_REFERENCE.md §3.7 (the reference compares the latest and previous quarterly rows).
- `net_profit_margin_year_ago` and `operating_margin_year_ago` are the margins of the same quarter one year earlier (FR-043).

**E1**: T028 now also bans imports of `sys` and `importlib` in the library modules. Both `import x` and `from x import y` count, matched on the top-level name, so `os.path` and `importlib.util` are caught. It adds an AST check that bans calls to `open(...)` and `__import__(...)`. `cli.py` and `__main__.py` are exempt, so the CLI may use `sys`. research.md R-11(c) has the same list so the two stay consistent.

**C2**: one structural change you should know about.
- **The traceability test now runs from Phase 2.** It has to exist before the first green run, so I added a Phase 2 task, **T011a**, that writes it. It reads its scope from a `GIS_TRACE_SCOPE` setting (unset means full scope) and checks that the scope table can't drift from spec.md.
- **The new ID is lettered.** I used T011a so that none of the IDs cited in 04-analyze.md move. The task count is now 83.
- **There is a new scope table.** It sits under Conventions and maps `foundation` and `US1`–`US6` to their FR and scenario ids. Together the rows cover exactly the 37 FR ids in spec.md.
- **Every green run sets the scope.** T016, T039, T048, T053, T059, T064 and T072 now run `GIS_TRACE_SCOPE=<completed stories> .venv/bin/pytest`. T079 runs the harness with the setting unset, so traceability is checked at full scope.
- **T075 now finishes the test.** It completes the file T011a creates, adding the SC-006 constant check and the PROVISIONAL tag checks.
- **References are updated** in the parallel list, the SC-006 matrix row, the matrix footnote and the Notes.

**I3**: research.md R-14 now gives the band wording `"Total {t} >= {threshold}: {label}"` for STRONG BUY, BUY, HOLD and SELL, and `"Total {t} < 25: STRONG SELL"` for STRONG SELL. T026 now cites R-14 for this instead of calling it a "task-specific narrowing".

**A1**: FR-024 now reads "ΔCCC ≤ −300 or ΔDSO ≤ −40 → 5; ΔCCC ≤ −150 or ΔDSO ≤ −25 → 4; ΔCCC ≤ −75 or ΔDSO ≤ −12 → 3; ΔCCC ≤ −30 or ΔDSO ≤ −5 → 2; ΔCCC < 0 or ΔDSO < 0 → 1; otherwise 0." The numbers and operators are the same as before and match GIS_REFERENCE §3.7.

**A2**: I removed the bullet "EBITDA growth that is missing is 0 of 0 here; the reference ends with the same outcome" from the intentional deviations.

**C3**: the quality-gate deviation bullet now says the gate omits two of the reference's conditions (GIS_REFERENCE.md §4): the high-severity red flag, and the capital-deployment redFlag, because red flags and Capital Deployment are both out of scope.

**Left unchanged as instructed**:
- U1 is still open item 2 under R-07 in research.md.
- I4: the spec status is still Draft.
- E2 (T074) and D1 are untouched.
- R-01 and R-02 are still PROVISIONAL.

I didn't touch `evidence/speckit-transcripts/05-analyze-remediation.md`, which is this run's own log.
_Finished 2026-11-22T07:29:39Z, exit 0._
