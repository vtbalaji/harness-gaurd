# Repair log (spec FR-033, research.md R-15, constitution Principle VII)

Each repair cycle after a failing evaluation run gets one dated entry, using this template. Repairs
change only the prompt, parser, validators or guards, never thresholds, cases or ground truth. The
same evaluation is rerun after every repair.

```text
### <YYYY-MM-DD> — cycle <n>
- Failing run folder: evidence/eval-runs/<stamp>/
- Feedback records cited: feedback/<case>.json, ...
- Change made: prompt | parser | validators | guards — <what changed>
- prompt_version: <old> → <new>   (or: prompt_version: unchanged)
- Reason: <why, citing the feedback records>
- Rerun folder: evidence/eval-runs/<stamp>/
- Outcome: <verdict and layer scores of the rerun>
```

No repair cycles yet.
