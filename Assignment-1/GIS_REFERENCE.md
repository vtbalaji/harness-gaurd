# General Investor Score (GIS): reference notes from myportfolio-web

Read-only survey, 2026-11-22. Nothing in myportfolio-web was modified.
The "global investing scoring" method in the repo is the **General Investor Score (GIS)**.

## 1. Where it lives

| File | Role |
|---|---|
| `scripts/fundamental/scoring/general_investor_score.py` (2,610 lines) | The scorer: `GeneralInvestorScoreCalculatorV5`. `calculate_score()` pulls the data from the database, `score_breakdown()` does the scoring |
| `scripts/fundamental/scoring/capital_deployment.py` (225 lines) | The Capital Deployment dimension (`score_capital_deployment`) |
| `app/api/general-investor-score-detail/route.ts` (1,848 lines) | TypeScript copy of the same rules, used by the detail page |
| `lib/gis-coverage.ts` (87 lines) | Gates the final label: INSUFFICIENT DATA or HOLD |
| `scripts/shared/entity_type.py` | `resolve_entity_type(industry, symbol)` returns BANK / INSURANCE / NBFC / STANDARD |
| `scripts/shared/financial_periods.py` | `core_pbt(pbt, other_income, exceptional)` = pbt − other_income − (exceptional or 0); None if pbt or other_income is None |

The scorer is **not pure**. `calculate_score` runs about 12 SQL queries, and even `score_breakdown` queries the DB (line 1080, an `industry` lookup, plus the bank and insurance KPI lookups). These pieces are pure and need no DB: `growth_12m`, `year_ago_row`, `npm_improving_yoy`, `growth_acceleration`, `seasonal_qoq`, `red_flag_penalties`, `quality_gate`, `valuation_score_from_ratios`, `consecutive_prior_year` and all the `_score_*` methods.

## 2. Inputs and units

All inputs come from Postgres:
- `fundamentals_quarterly_consolidated`: the latest 8 quarters, the latest Q2/Q4 row (balance sheet) and the previous row of the same type
- `fundamentals_annual_consolidated`: the latest 2 years
- `companies`: sector and industry
- `scoring_parameters`: sector thresholds
- `xbrl_data` (through `ttm_rows`): core PBT

| Metric (metrics key) | Unit | Source |
|---|---|---|
| piotroski_score | integer 0–9 (0–7 for NBFC/INSURANCE) | annual row first, else the Q2/Q4 row |
| altman_z_score, beneish_m_score | unitless; forced to None for BANK/NBFC/INSURANCE | annual first, else Q2/Q4 |
| revenue/earnings/ebitda_growth_yoy | % | 12M vs prior 12M (see growth_12m); earnings are replaced by core growth when measurable |
| net_profit_margin, operating_margin | % | latest quarter |
| equity_growth_yoy | % | Q2/Q4 equity_cr vs the previous Q2/Q4 of the same quarter_num |
| cash_flow_quality | ratio (OCF/NI, TTM) | Q2/Q4 row |
| net_profit_ttm_cr | ₹ crore | sum of the last 4 Q1–Q4 net_profit_cr |
| roe, roce | % | Q2/Q4 row, else the annual forensic row, else the latest annual row |
| current_ratio, debt_to_equity | ratio | Q2/Q4 row |
| cash_conversion_cycle, days_sales_outstanding | days | annual rows (latest FY vs the prior FY) |
| pe_ratio, pb_ratio, peg_ratio | ratio | latest quarter, else Q2/Q4 |
| *_cr fields (revenue, profit, ebitda, equity, fixed_assets, cwip) | ₹ crore | |
| red_flags | JSON `{flags:[{code,severity}], codes:[...]}` | latest quarter |
| bank KPIs (npa_net_percent, npa_gross_percent, cet1_ratio, cost_to_income; nim, casa_ratio, slippage_ratio, cd_ratio) | % | sector_metrics JSON / earnings_intelligence JSON |

## 3. Factors, formulas, thresholds

Every item is a dict `{parameter, value, score, maxScore, criteria}`. **An item with no data gets `maxScore 0`**, so it drops out of the denominator.

### 3.1 Forensic Quality (20)
```python
# Piotroski (10): value scaled to /9 first: value*9/max_score (max 7 for NBFC/INSURANCE)
>=8:10  >=6:7  >=4:4  >=2:2  else 0
# Altman Z (5)
>2.99:5   >=1.81:3   else 0
# Beneish M (5)
<-2.22:5  <=-1.78:2  else 0
```

### 3.2 Growth Metrics
```python
# EBITDA Growth YoY (8): >=20:8 >=15:6 >=10:4 >=5:2 else 0     (banks/insurers/NBFC: 0/0)
# Earnings Growth YoY (7): >=20:7 >=10:5 >=5:3 >=0:2 else 0
# "Capped" (base <= 0 or cur > 4x base): fixed mid points: earnings 3, ebitda 4, revenue 5
# EBITDA/Earnings Growth QoQ (1 each): seasonal_qoq -> earned if growth>0 and
#   (last year's same step unmeasurable or growth > last year's step)
```

### 3.3 Revenue Quality (10)
`>=25:10  >=15:7  >=10:5  >=0:3  else 0` (capped → 5)

### 3.4 Financial Health (10)
- Equity growth (5): `>15:5  >=10:3  >=5:2  >0:1  else 0`
- Cash-flow quality, OCF/NI (5): `>=1.5:5  >=1.0:4  >=0.8:3  >=0.5:2  >0:1`. If the ratio is ≤0 and TTM profit > 0 (non-insurer), the score is **−3**; otherwise 0. BANK/NBFC: 0/0.

### 3.5 Profitability Quality (7)
- NPM (3), no sector thresholds: `>15:3  >10:2  >0:1  else 0`. With sector `value_margin`: ≥p90:3, ≥p80:2, >0:1.
- OPM (4), no sector thresholds: `>20:4  >15:3  >10:2  >0:1  else 0`. With sector values: ≥p90:4, ≥p80:3, ≥p50:2, >0:1.

### 3.6 Competitive Moat (10): ROE (5) and ROCE (5), via `_score_return`
```python
full = max(sector_P75 or 0, 15.0); good = max(sector_P50 or 0, 12.0)
>=full:5  >=good:3  >=8:2  >0:1  else 0
```

### 3.7 Turnaround Signals
| Item | Max | Rule |
|---|---|---|
| Loss → Profit | 5 | latest NPM > 0 and the previous period's NPM ≤ 0 |
| NPM Consecutive Improving | 3 | count of newest quarters whose NPM beats the same quarter a year earlier (365±7 days); ≥3:3, 2:2, 1:1 |
| Profitability Sustainability | 2 | consecutive newest quarters with NPM > 0 (up to 5 rows); ≥4:2, ≥2:1 |
| Growth Acceleration | ≤3 | three checks, 1 pt each, and an unmeasurable check is dropped from the max. (a) quarter profit YoY > 0 and > 12M growth + 10; (b) revenue YoY rising over 3 consecutive quarters, newest > 0; (c) OPM > OPM a year earlier |
| Working Capital Efficiency | 5 | ΔCCC/ΔDSO, latest FY − prior FY (a missing one counts as 0): CCC ≤−300 or DSO ≤−40 → 5; ≤−150/≤−25 → 4; ≤−75/≤−12 → 3; ≤−30/≤−5 → 2; <0 → 1. BANK/NBFC 0/0 |
| Debt Reduction | 3 | ΔD/E vs the previous same-type Q2/Q4: ≤−0.5:3, ≤−0.2:2, <0:1. **0/0 when D/E < 0.5 in both years**; BANK/NBFC 0/0 |

The docstring says "0-18 pts", but the item maxima add up to 21.

### 3.8 Capital Deployment (10, STANDARD companies only)
- Investment activity (2)
- Conversion + CWIP control (3)
- Payback (3)
- Funding quality (2)

These are balance-sheet proxies built from fixed_assets_cr and cwip_cr. **For any STANDARD company `score_capital_deployment` always returns status='scored'**: missing evidence earns 0 but still keeps max 10. That triggers a re-weighting:
```python
EBITDA YoY 8->4 {0:0,2:1,4:2,6:3,8:4};  Earnings YoY 7->4 {0:0,2:1,3:2,5:3,7:4}
Loss->Profit 5->3 {0:0,5:3};  WC Efficiency 5->3 {0:0,1:1,2:1,3:2,4:3,5:3}
NPM Improving 3->2 {0:0,1:1,2:1,3:2}
```
For a STANDARD company the realistic maximum is 20+10+10+10+7+10+16+10 plus Sector Specific 10 = 103.

### 3.9 Sector Specific
- **Non-financial:** Current Ratio (5): `>2.0:5  >=1.5:3  >=1.0:1  else 0`. D/E (5): `<0.5:5  <=1.0:3  <=2.0:1  else 0`.
- **Bank** (also any sector containing "bank" or "finance", except AMCs), 36 in total: Net NPA 8, Gross NPA 5, PCR = (G−N)/G×100 4, NIM 4, CASA 3, CET1 4, Cost/Income 4, Slippage 2 (ignored unless 0–10), CD ratio 2 (70–85 scores 2).
- **Insurance:** Solvency 6 (>200%, >180%, ≥150%), Combined Ratio 6 (general insurers), Claims 4 (general), Expense 4 (life and general use different bands), NBP margin 3 (life), Net retention 3 (general).

### 3.10 Penalties (score < 0, maxScore 0)
| Penalty | Points | Trigger |
|---|---|---|
| Revenue Declining | −5 | revenue growth YoY < 0 |
| Earnings Declining | −5 | earnings growth YoY < 0 |
| EBITDA Declining | −5 | EBITDA growth YoY < 0 |
| Margin Compression | −3 | NPM AND OPM both below the same quarter a year earlier |
| Profit Fell on Other Income | −2 | reported ≤ −5% while core ≥ 0 |
| Profit Propped by Other Income | −3 | core ≤ −5% while reported ≥ 0 (skipped if CORE_PROFIT_NEGATIVE is flagged) |
| Red flags | high −3 / medium −1 | worst flag per group, total capped at −10 |

Red-flag groups:
- Governance: PROMOTER_PLEDGE, PLEDGE_RISING, INSTITUTIONS_EXITING
- Earnings Quality: OTHER_INCOME_HIGH, TAX_RATE_LOW, CORE_PROFIT_NEGATIVE
- Debt Servicing: INTEREST_COVER_THIN
- Funding Quality: PAYABLES_STRETCHED, EQUITY_DILUTION
- Capital Deployment: CAPEX_NOT_COMMISSIONING, CWIP_STAGNANT. This group is dropped when the conversion component is assessed.

## 4. Total score and rating

```python
raw_score = sum(item['score'] for every item in every dimension)      # penalties included
raw_max   = sum(item['maxScore'] ...)                                  # penalties add 0
total_score = round(raw_score * 100 / raw_max) if raw_max > 0 else 0
total_score = max(0, min(100, total_score))
```
This normalises to 100 over whatever could be scored. Python `round()` rounds half to even.

```python
if data_quality_issues:            # NPM None | all 3 forensic None | OPM and NPM None
    recommendation = 'SUSPICIOUS'
elif total >= 70: 'STRONG BUY'
elif total >= 55: 'BUY'
elif total >= 40: 'HOLD'
elif total >= 25: 'SELL'
else: 'STRONG SELL'
```

Display gating, in `lib/gis-coverage.ts` (positive labels only):
1. Any core dimension (forensicQuality, growthMetrics, revenueQuality, competitiveMoat) has max 0 → **INSUFFICIENT DATA**.
2. Otherwise, `qualityGate.pass == False` → **HOLD**. The gate fails on any of:
   - a high-severity red flag
   - a capital-deployment redFlag
   - non-lender with ROE missing or below 12
   - Piotroski/scale < 4/9

The score itself never changes.

Valuation score is separate, 0–10:
- P/E (5), with no sector thresholds: `<12:5 <18:3 <25:2 <50:1`. With sector values: <p50:5, <p80:3, <max:2, else 1.
- P/B (3): `<1.5:3 <3.0:2`, or sector p20/p50.
- PEG (2): `<1:2 <1.5:1`.
- Clamped to 0..10.

## 5. Edge cases

- **Missing data → excluded, not zero.** Almost every `_score_*` returns `maxScore 0` on None. EBITDA None on a non-lender returns 0/8, but `score_breakdown` then resets maxScore to 0 (line 905).
- **Division by zero:**
  - single-quarter growth is skipped when prev == 0
  - `_growth_pct` returns None when prev ≤ 0
  - `growth_12m` marks the item capped when base ≤ 0 or cur > 4× base
  - PCR needs gross > 0 and 0 ≤ net ≤ gross
  - total is 0 when raw_max == 0
- **Negatives:**
  - QoQ/YoY growth divides by `abs(base)`
  - a negative OCF/NI ratio scores −3 only when TTM profit is positive
  - a negative total is clamped to 0
- **Zero vs None:** Piotroski, Altman and Beneish use `is None`, so a 0 is a real value. ROE, ROCE, PE, PB and PEG fall back with `or` (lines 802–813), so **a stored 0 is treated as missing** and replaced by the fallback.
- **Rounding:** growth sums are rounded to 6 dp before the 4× cap test, so Python and JS agree on exact ties.
- **Entity type:** BANK, NBFC and INSURANCE get Altman/Beneish forced to None, EBITDA 0/0, CFQ/WC/Debt-reduction 0/0 (lenders) and a different Sector Specific block.
- **Shape:** Python and TS must stay in step ("Mirrored in ... route.ts" comments throughout).

## 6. Existing tests

There is no dedicated end-to-end GIS test file, and the existing tests need the repo's import paths.
- `tests/test_capital_deployment.py`: 6 tests. Capital deployment, the 10-point re-weight through `score_breakdown`, `quality_gate` with a pending build, and the IPO items.
- `scripts/tests/test_xbrl_contracts.py`: 31 tests. The GIS-related ones:
  - `year_ago_row` matching by date
  - `npm_improving_yoy` → 2
  - `growth_acceleration` → (3,3) and (2,2) when the 12M figure is None
  - `seasonal_qoq`: RELIANCE / BIKAJI / BHEL-like cases
  - `_score_piotroski(7,7)` and `(9,9)` → 10

## 7. Scoping note for Part 1A

The whole scorer is too big and too DB-bound to rebuild cleanly. These parts can be rebuilt deterministically from explicit inputs:
- §3.1–3.7, without Growth Acceleration, the QoQ items and capital deployment
- §3.9 for non-financials
- §3.10 decline and margin penalties
- §4 normalisation and labels
- valuation

The tables above are exact enough to write as acceptance scenarios.
