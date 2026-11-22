# Feature Specification: GIS Scorer (deterministic General Investor Score)

**Feature Branch**: `001-gis-scorer`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "A new, small, deterministic module that re-implements the General
Investor Score (GIS) method from myportfolio-web: given one company's pre-computed financial
metrics, return a 0–100 quality score, its per-dimension breakdown, a recommendation label and a
separate 0–10 valuation score. Scope is the subset of GIS that can be computed from explicit inputs
alone (see GIS_REFERENCE.md §7)."

## Clarifications

### Session 2026-11-22

Decisions confirmed by the project owner (Balakrishnan); non-interactive session.

- Q: Which companies and which parts of the reference GIS method are in scope? → A: Non-financial
  companies only (banks, NBFCs and insurers are out of scope). Scoring ladders are fixed, with no
  sector-percentile thresholds. Out of scope: Capital Deployment and its re-weighting, red-flag
  penalties, other-income divergence, core-profit substitution, growth acceleration, the QoQ
  momentum items, NPM-improving-YoY, and any database or data fetching.
- Q: Is an input of exactly zero a real value or missing data? → A: Zero is a real value and is
  scored as such, including ROE, ROCE, P/E, P/B and PEG; only an absent value is missing.
- Q: What happens when the input is invalid (unknown field, non-numeric, non-finite or out of
  range)? → A: Scoring is refused with an error that names the field.
- Q: What makes the quality gate fail, and does it include a red-flag check? → A: There is no
  red-flag check; the gate fails only on ROE missing, ROE < 12%, or Piotroski < 4.
- Q: How is the total rounded to a whole number? → A: To the nearest integer, ties to even.
- Q: Is an explicit null the same as an omitted field, and what do a null element or an empty list
  in `recent_net_profit_margins` mean? → A: Explicit null is the same as absent (missing). A null
  element stops the run of consecutive profitable quarters. An empty list means no quarter was
  supplied, so Profitability Sustainability is 0 of 0. (Raised by /speckit-clarify; confirmed by
  Balakrishnan in the project thread, 2026-11-22.)
- Q: Does a whole-number float count as an integer for Piotroski, and are booleans numeric? → A:
  `6.0` is accepted as 6; `6.5` is rejected; booleans are rejected as non-numeric in every field.
  (Raised by /speckit-clarify; confirmed by Balakrishnan in the project thread, 2026-11-22.)

## User Scenarios & Testing *(mandatory)*

The user is an analyst (or a program acting for one) who has a company's financial metrics and
wants a reproducible, explainable quality score for it.

### User Story 1 - Score a company and get its total (Priority: P1)

The analyst supplies one company's metric snapshot and receives a total score from 0 to 100, plus
a breakdown showing, for every scoring item, the points earned, the points available, and the
rule that was applied.

**Why this priority**: The total and its breakdown are the core of the method; every other story
builds on them.

**Independent Test**: Supply a complete snapshot with known values and check every item's points,
each dimension's subtotal and the normalised total against hand-computed figures.

**Acceptance Scenarios**:

1. **Given** a snapshot where every input is present and every item earns its maximum,
   **When** it is scored, **Then** the total is 100 and no penalty is listed.
2. **Given** a snapshot with Piotroski 6, Altman Z 2.5 and Beneish M −2.5, **When** it is scored,
   **Then** Forensic Quality shows 7/10, 3/5 and 5/5 (15 of 20).
3. **Given** revenue for the last 12 months of 115 against 100 for the 12 months before,
   **When** it is scored, **Then** revenue growth is 15% and earns 7 of 10.
4. **Given** a snapshot whose prior-12-month EBITDA is 0, **When** it is scored, **Then** EBITDA
   growth is reported as "capped" and earns the fixed 4 of 8, and no EBITDA decline penalty applies.
5. **Given** raw points of 45 earned out of 90 available, **When** the total is computed,
   **Then** the total is 50.

---

### User Story 2 - Missing data is excluded, never zeroed (Priority: P1)

The analyst often has incomplete data. A missing metric must not drag the score down as if it were
zero; it must drop out of both the earned and the available points, and the breakdown must say
"no data" for it.

**Why this priority**: Wrong handling of missing data silently corrupts every score, so it is as
critical as scoring itself.

**Independent Test**: Score the same snapshot with and without one input; the item disappears from
the available points and the total is re-normalised over what remains.

**Acceptance Scenarios**:

1. **Given** a snapshot with no Altman Z value, **When** it is scored, **Then** the Altman item
   shows 0 of 0 with reason "No data" and Forensic Quality is out of 15, not 20.
2. **Given** a snapshot with ROE exactly 0, **When** it is scored, **Then** ROE is scored as a real
   value (0 of 5), not treated as missing.
3. **Given** a snapshot where nothing at all can be scored, **When** it is scored, **Then** the
   total is 0 and the label is SUSPICIOUS.
4. **Given** an input that is not a number, is infinite, or is outside its allowed range (for
   example Piotroski 11), **When** it is scored, **Then** scoring is refused with an error naming
   the field, and no partial result is returned.

---

### User Story 3 - Get a recommendation label I can trust (Priority: P2)

The analyst wants a plain label (STRONG BUY … STRONG SELL) derived from the total, but a positive
label must not be shown when the data behind it is thin or the business fails basic quality checks.

**Why this priority**: The label is what most users read; it depends on the total being right first.

**Independent Test**: Feed totals on each side of each label boundary, then positive-band snapshots
that are missing a core dimension or fail the quality gate.

**Acceptance Scenarios**:

1. **Given** totals of 70, 69, 55, 54, 40, 39, 25 and 24 with complete data that passes the quality
   gate, **When** labelled,
   **Then** the labels are STRONG BUY, BUY, BUY, HOLD, HOLD, SELL, SELL, STRONG SELL.
2. **Given** a total of 80 but no ROE and no ROCE, **When** labelled, **Then** the label is
   INSUFFICIENT DATA and the reason names the missing dimension.
3. **Given** a total of 80 with complete data and ROE 10%, **When** labelled, **Then** the label is
   HOLD and the reason says ROE is below 12%.
4. **Given** a snapshot with no net profit margin, **When** labelled, **Then** the label is
   SUSPICIOUS whatever the total.
5. **Given** a total of 30, missing ROE and ROCE, **When** labelled, **Then** the label stays SELL
   (gates only ever downgrade positive labels).

---

### User Story 4 - Penalties for a deteriorating business (Priority: P2)

The analyst wants declining revenue, earnings or EBITDA, and shrinking margins, to cost points,
and wants to see each penalty listed.

**Why this priority**: Penalties change the total materially and are a frequent source of disputes.

**Independent Test**: Score a snapshot with declining figures and check each penalty line and the
effect on the total.

**Acceptance Scenarios**:

1. **Given** revenue growth of −2%, **When** scored, **Then** a "Revenue Declining" penalty of −5
   is listed and revenue growth itself earns 0 of 10.
2. **Given** net margin 8% vs 9% a year earlier and operating margin 12% vs 13% a year earlier,
   **When** scored, **Then** a "Margin Compression" penalty of −3 is listed.
3. **Given** only one of the two margins below its year-ago value, **When** scored, **Then** no
   Margin Compression penalty is listed.
4. **Given** penalties that push raw points below zero, **When** the total is computed, **Then** the
   total is 0, never negative.

---

### User Story 5 - Separate valuation score (Priority: P3)

The analyst wants a 0–10 valuation score from P/E, P/B and PEG, reported separately so price never
changes the quality score.

**Why this priority**: Useful context, but independent of the quality score.

**Independent Test**: Score P/E, P/B and PEG values on each side of each band and check the sum.

**Acceptance Scenarios**:

1. **Given** P/E 11, P/B 1.4 and PEG 0.9, **When** valued, **Then** the valuation score is 10.
2. **Given** P/E 60, P/B 4 and PEG 2, **When** valued, **Then** the valuation score is 0.
3. **Given** no P/E, P/B or PEG, **When** valued, **Then** the valuation score is 0 and the quality
   total is unchanged.

---

### User Story 6 - Run it from the command line (Priority: P3)

The analyst wants to score a snapshot stored in a file without writing code, and get the result
as structured output.

**Why this priority**: Convenience for the harness and demos; the library is the product.

**Independent Test**: Run the command on a sample snapshot file and compare its output with the
library's result for the same input.

**Acceptance Scenarios**:

1. **Given** a valid snapshot file, **When** the command is run on it, **Then** it prints the result
   as structured data and exits successfully.
2. **Given** an invalid snapshot file, **When** the command is run on it, **Then** it prints the
   validation error and exits with a failure status.

---

### Edge Cases

- A growth base (prior 12 months) of zero or negative → the item is "capped" (fixed mid points),
  never a division by zero, and no decline penalty applies to it.
- Current value more than 4× its base → "capped" (a recovery or base effect, not real growth).
- Exactly 4× the base → not capped (the cap test is strictly greater than 4×); values are rounded to
  6 decimal places before this test so tiny floating-point noise cannot flip it.
- Negative current value against a positive base → normal growth (negative %), scored and penalised.
- Total exactly on a half point (e.g. 72.5) → rounded half to even (72), matching the reference.
- Operating cash flow ÷ net profit below 0 while TTM profit is positive → −3 (worse than 0).
  The same ratio when TTM profit is a loss or unknown, or a ratio of exactly 0 → 0.
- A negative P/E (loss-making company) is scored as given, so it falls in the cheapest band; callers
  should pass P/E as missing for a loss-maker, as the reference's data does.
- D/E below 0.5 in both years → Debt Reduction is not applicable (0 of 0), not 0 of 3.
- Working capital with only CCC or only DSO available → the missing change counts as 0 and the
  item is still scored; with neither → 0 of 0.
- Profitability Sustainability with fewer than 2 quarters supplied → 0 of 2 (scored, not missing)
  unless no quarter is supplied at all.
- Piotroski must be an integer 0–9; anything else is an input error.
- An unknown field name, a non-numeric value, a non-finite value (NaN, ±infinity) or an
  out-of-range value → scoring is refused with an error naming the field; nothing is scored.
- ROE or ROCE of exactly 0 → scored as 0 of 5 (not missing). P/E, P/B or PEG of exactly 0 → scored
  in its lowest band (P/E 5, P/B 3, PEG 2), not treated as missing.

## Requirements *(mandatory)*

### Functional Requirements

**Inputs and validation**

- **FR-001**: The system MUST accept one company snapshot made of the named metrics in the Key
  Entities section. Every metric is optional; only an absent value (or an explicit null, which is the same) means "missing". Zero is a real
  value and is scored as such for every metric, including ROE, ROCE, P/E, P/B and PEG.
- **FR-002**: The system MUST reject a snapshot containing an unknown field, a non-numeric value, a
  non-finite value, or a value outside its stated range, with an error that names the field.
- **FR-003**: The system MUST produce identical output for identical input, with no dependence on
  time, environment, files, network or randomness.

**Item scoring**: each item yields points earned, points available and a reason. A missing input
gives 0 of 0 with reason "No data". All boundaries below are exact.

- **FR-010 Piotroski F-score** (available 10): ≥8 → 10; ≥6 → 7; ≥4 → 4; ≥2 → 2; otherwise 0.
- **FR-011 Altman Z** (5): >2.99 → 5; ≥1.81 → 3; otherwise 0.
- **FR-012 Beneish M** (5): <−2.22 → 5; ≤−1.78 → 2; otherwise 0.
- **FR-013 Growth calculation**: For revenue, EBITDA and net profit, growth % =
  (current 12M − prior 12M) ÷ |prior 12M| × 100, both values first rounded to 6 decimals. If the
  prior 12M is ≤ 0, or the current 12M is > 0 and greater than 4 × prior 12M, the growth is
  "capped" and no percentage is reported. If either value is missing, growth is missing.
- **FR-014 EBITDA growth** (8): ≥20% → 8; ≥15 → 6; ≥10 → 4; ≥5 → 2; otherwise 0. Capped → 4 of 8.
- **FR-015 Earnings (net profit) growth** (7): ≥20% → 7; ≥10 → 5; ≥5 → 3; ≥0 → 2; otherwise 0.
  Capped → 3 of 7.
- **FR-016 Revenue growth** (10): ≥25% → 10; ≥15 → 7; ≥10 → 5; ≥0 → 3; otherwise 0.
  Capped → 5 of 10.
- **FR-017 Equity growth** (5), from current and prior equity, growth = (current − prior) ÷ |prior|
  × 100, missing if prior is 0: >15% → 5; ≥10 → 3; ≥5 → 2; >0 → 1; otherwise 0.
- **FR-018 Cash-flow quality** (5), operating cash flow ÷ net profit: ≥1.5 → 5; ≥1.0 → 4; ≥0.8 → 3;
  ≥0.5 → 2; >0 → 1; <0 with TTM net profit (`net_profit_12m`) > 0 → −3; otherwise 0.
- **FR-019 Net profit margin** (3): >15% → 3; >10 → 2; >0 → 1; otherwise 0.
- **FR-020 Operating margin** (4): >20% → 4; >15 → 3; >10 → 2; >0 → 1; otherwise 0.
- **FR-021 ROE and ROCE** (5 each): ≥15% → 5; ≥12 → 3; ≥8 → 2; >0 → 1; otherwise 0.
- **FR-022 Loss → Profit transition** (5): available when current and previous net margin are both
  present; 5 when current > 0 and previous ≤ 0, otherwise 0.
- **FR-023 Profitability sustainability** (2): count the consecutive quarters, newest first, with net
  margin > 0 (stopping at the first that is not, or is missing); ≥4 → 2; ≥2 → 1; otherwise 0.
  Missing only when no quarterly margin is supplied (field absent, null, or an empty list).
- **FR-024 Working-capital efficiency** (5): ΔCCC = current − prior CCC days; ΔDSO = current − prior
  DSO days; a change that cannot be computed counts as 0, and the item is missing when neither can.
  ΔCCC ≤ −300 or ΔDSO ≤ −40 → 5; ΔCCC ≤ −150 or ΔDSO ≤ −25 → 4; ΔCCC ≤ −75 or ΔDSO ≤ −12 → 3;
  ΔCCC ≤ −30 or ΔDSO ≤ −5 → 2; ΔCCC < 0 or ΔDSO < 0 → 1; otherwise 0.
- **FR-025 Debt reduction** (3): needs current and prior D/E. If both are < 0.5 → 0 of 0 ("not
  applicable"). Otherwise ΔD/E = current − prior: ≤ −0.5 → 3; ≤ −0.2 → 2; < 0 → 1; otherwise 0.
- **FR-026 Current ratio** (5): >2.0 → 5; ≥1.5 → 3; ≥1.0 → 1; otherwise 0.
- **FR-027 Debt-to-equity level** (5): <0.5 → 5; ≤1.0 → 3; ≤2.0 → 1; otherwise 0.

**Dimensions**

- **FR-030**: Items MUST be grouped and reported in this order:
  Forensic Quality (FR-010–012), Growth (FR-014–015), Revenue Quality (FR-016),
  Financial Health (FR-017–018), Profitability (FR-019–020), Competitive Moat (FR-021),
  Turnaround (FR-022–025), Balance Sheet (FR-026–027), Penalties (FR-040–043).
  Each dimension reports the sum of its items' earned and available points.

**Penalties**: points < 0 with 0 available.

- **FR-040**: Revenue growth < 0 → "Revenue Declining" −5.
- **FR-041**: Earnings growth < 0 → "Earnings Declining" −5.
- **FR-042**: EBITDA growth < 0 → "EBITDA Declining" −5.
- **FR-043**: Net margin below year-ago net margin AND operating margin below year-ago operating
  margin → "Margin Compression" −3.
- **FR-044**: Capped or missing growth never triggers a decline penalty.

**Total and label**

- **FR-050**: Total = raw earned ÷ raw available × 100 over all items (penalties included in earned,
  adding 0 to available), rounded to the nearest integer with ties to even, then limited to 0–100.
  If nothing is available the total is 0.
- **FR-051**: The label is SUSPICIOUS when net profit margin is missing, or when Piotroski, Altman Z
  and Beneish M are all missing. The reason lists every condition met.
- **FR-052**: Otherwise: ≥70 STRONG BUY; ≥55 BUY; ≥40 HOLD; ≥25 SELL; otherwise STRONG SELL.
- **FR-053**: A STRONG BUY or BUY becomes INSUFFICIENT DATA when any of Forensic Quality, Growth,
  Revenue Quality or Competitive Moat has 0 available points.
- **FR-054**: Otherwise, a STRONG BUY or BUY becomes HOLD when the quality gate fails. The gate fails
  only on: ROE missing, ROE < 12%, or Piotroski < 4. It has no red-flag check. The reason lists every
  failed check.
- **FR-055**: The result MUST report the label before gating, the final label and the reasons, and
  the total MUST be the same whatever the label.

**Valuation**

- **FR-060**: Valuation (0–10) = P/E points + P/B points + PEG points, each 0 when missing:
  P/E <12 → 5, <18 → 3, <25 → 2, <50 → 1, else 0; P/B <1.5 → 3, <3.0 → 2, else 0;
  PEG <1 → 2, <1.5 → 1, else 0. It never affects the quality total or label.

**Output and interface**

- **FR-070**: The result MUST contain the total, maximum (100), raw earned and available points,
  each dimension with its items (name, input value, earned, available, reason), the penalties, the
  pre-gate and final labels with reasons, and the valuation score with its three parts.
- **FR-071**: The result MUST be structured data that serialises the same way every time.
- **FR-072**: A command-line entry point MUST score a snapshot read from a file and print the result;
  on invalid input it prints the error and exits with a non-zero status.

### Key Entities *(include if feature involves data)*

- **Company Snapshot**: one company's metrics at one point in time. Fields (all optional):
  - Forensic: `piotroski` (integer 0–9), `altman_z`, `beneish_m`
  - 12-month totals, ₹ crore: `revenue_12m`, `revenue_prior_12m`, `ebitda_12m`, `ebitda_prior_12m`,
    `net_profit_12m`, `net_profit_prior_12m`
  - Balance sheet: `equity`, `equity_prior` (₹ crore), `debt_to_equity`, `debt_to_equity_prior`
    (ratios), `current_ratio` (ratio, ≥ 0)
  - Cash flow: `ocf_to_net_profit` (ratio)
  - Margins and returns, %: `net_profit_margin`, `operating_margin`, `net_profit_margin_year_ago`,
    `operating_margin_year_ago`, `previous_net_profit_margin`, `roe`, `roce`
  - Margin periods: `previous_net_profit_margin` is the net margin of the quarter immediately
    before the one `net_profit_margin` describes (the reference's Loss → Profit item compares the
    latest and previous quarterly rows, `GIS_REFERENCE.md` §3.7). `net_profit_margin_year_ago` and
    `operating_margin_year_ago` are the net and operating margins of the same quarter one year
    earlier than the one `net_profit_margin` and `operating_margin` describe (FR-043).
  - `recent_net_profit_margins`: list of quarterly net margins %, newest first, at most 8
  - Working capital, days: `ccc_days`, `ccc_days_prior`, `dso_days`, `dso_days_prior`
  - Valuation: `pe`, `pb`, `peg`
  - TTM net profit sign is taken from `net_profit_12m`.
  - Ranges: `piotroski` integer 0–9 (a whole-number value such as 6.0 is accepted as 6); booleans are not numeric in any field; `current_ratio` ≥ 0; `recent_net_profit_margins` at most 8
    numbers; every other field any finite number.
- **Score Item**: name, input value, points earned, points available, reason.
- **Dimension**: name, its items, earned and available subtotals.
- **Score Result**: total, raw points, dimensions, penalties, labels and reasons, valuation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every acceptance scenario in this spec passes as an automated test (100%).
- **SC-002**: Every threshold in FR-010 to FR-060 has a test on each side of its boundary; coverage of
  the scoring rules is 100% of lines and branches.
- **SC-003**: Scoring the same snapshot 1,000 times yields 1,000 identical results.
- **SC-004**: At least 5 worked examples, hand-computed from the reference method, produce exactly the
  expected total, label and valuation.
- **SC-005**: 10,000 snapshots are scored in under 5 seconds on a standard laptop.
- **SC-006**: A reviewer can trace every scoring constant in the implementation to one numbered
  requirement in this spec.

## Assumptions

- **Scope: non-financial companies only** (confirmed 2026-11-22). Banks, NBFCs and insurers (with
  their own KPI blocks and exemptions) are out of scope for this version.
- **Out of scope** (confirmed 2026-11-22): sector-percentile thresholds (scoring ladders are
  fixed), Capital Deployment and its re-weighting, red-flag penalties, other-income divergence,
  core-profit substitution, growth acceleration, the QoQ momentum items, NPM-improving-YoY, and any
  database or data fetching. Callers supply pre-computed metrics. Without Capital Deployment, the reference keeps its original weights,
  so the weights above are the reference's un-reweighted ones.
- **Intentional deviations from the reference**, recorded per Constitution II:
  - A stored 0 for ROE/ROCE/P/E/P/B/PEG is scored as 0; the reference treats it as missing (an
    `or` fallback). Constitution IV requires zero to be a real value.
  - Invalid inputs are rejected; the reference silently turns them into "missing".
  - When TTM profit is unknown, a non-positive cash-flow ratio scores 0; the reference then falls back
    to the sign of a half-year cash flow that is not an input here.
  - The quality gate omits two of the reference's gate conditions (`GIS_REFERENCE.md` §4, display
    gating): the "high-severity red flag" check, because red flags are out of scope, and the
    "capital-deployment redFlag" check, because red flags and Capital Deployment are both out of
    scope.
  - The SUSPICIOUS rule's "both margins missing" condition is covered by "net margin missing".
- Maximum available points when every input is present: 97 (Forensic 20, Growth 15, Revenue 10,
  Financial Health 10, Profitability 7, Moat 10, Turnaround 15, Balance Sheet 10).
- Units: money in ₹ crore, margins/growth/returns in percent (15 means 15%), days in days.
- The reference method is documented in `Assignment-1/GIS_REFERENCE.md`.
