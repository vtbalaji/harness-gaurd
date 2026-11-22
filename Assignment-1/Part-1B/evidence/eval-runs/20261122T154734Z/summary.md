# Evaluation run 20261122T154734Z

## 1. Verdict

**FAIL** (rule `2-app-failure`): Layer 1 failed for 3 case(s): M03 (MR-SCHEMA), V01 (MR-CONSIST), E02 (MR-SCHEMA); Layer 2 failed for 9 case(s): U01 (G-2, INV-3), M02 (G-2, INV-3), M03 (MR-SCHEMA), A01 (INV-5), A04 (INV-5), V01 (MR-CONSIST), K01 (G-2, INV-3), E01 (INV-5), E02 (MR-SCHEMA).

Dataset binding: `matches_spec: true` (dataset sha256 `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`, bound `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`).

## 2. Layers

| Layer | Score | Threshold | Met | Not scored |
|---|---|---|---|---|
| L1 structural | 25/28 (89.3%) | 100% | False | - |
| L2 invariants | 19/28 (67.9%) | 100% | False | - |
| L3 fields | 123/162 (75.9%) | 80% | False | - |

## 3. Application failures

| Case | Layers | Checks | Stage | Feedback |
|---|---|---|---|---|
| U01 | [2] | G-2, INV-3 | post_validation | feedback/U01.json |
| M02 | [2] | G-2, INV-3 | post_validation | feedback/M02.json |
| M03 | [1, 2] | MR-SCHEMA | mr_schema | feedback/M03.json |
| A01 | [2] | INV-5 | None | feedback/A01.json |
| A04 | [2] | INV-5 | None | feedback/A04.json |
| V01 | [1, 2] | MR-CONSIST | mr_consistency | feedback/V01.json |
| K01 | [2] | G-2, INV-3 | post_validation | feedback/K01.json |
| E01 | [2] | INV-5 | None | feedback/E01.json |
| E02 | [1, 2] | MR-SCHEMA | mr_schema | feedback/E02.json |

Checker disagreements: none.

## 4. Service failures (model)

Unresolved: none.
Failed attempts: none.

## 5. Judge (informational, does not affect verdict)

Model `qwen3.6-35b-a3b`, rated 15, mean 3.47.

- N01: 5 — All extracted values, including the company name, date, order value, currency, unit, client, order type, and execution period, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- N02: 5 — All extracted values, including the company name, date, order value, currency, unit, client, and order type, are explicitly stated in the announcement text and are accurately reported without any misrepresentation or invention.
- N03: 5 — All extracted values, including the company name, announcement date, order value, currency, unit, client, order type, and execution period, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- N04: 5 — All extracted values, including the company name, date, order value, currency, client, and execution period, are explicitly stated in the announcement text and are reported accurately without any invention or misrepresentation.
- N05: 2 — The extraction incorrectly infers the currency as INR and misreports the evidence for currency and unit by repeating the full value string '340 crore' instead of extracting the specific currency code or unit, which constitutes a misreporting of the stated text.
- N06: 5 — All extracted values, including the order amount, client name, and delivery timeline, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- U01: 2 — The extraction misreports the order_type as 'epc_construction' when the text explicitly specifies 'installation and commissioning', and incorrectly maps the currency string to the 'currency' evidence field instead of just the currency code.
- M01: 2 — The extraction incorrectly assigns the total aggregate order value of ₹1,250 crore to the specific order from the National Highways Authority of India, which is actually valued at ₹800 crore, thereby misreporting the primary data point.
- M02: 2 — The extraction incorrectly assigns the order type 'supply of LT power cables' (which belongs to the first order) to the primary order from Maharashtra State Electricity Distribution Company Limited, which is for HT aerial bunched cables.
- A01: 1 — The extraction is unfaithful because it sets the status to 'not_an_order' and the order field to null, directly contradicting the announcement which explicitly states that orders were received.
- A04: 5 — The extraction accurately reflects the announcement's content by correctly identifying the company and date, and appropriately marking the status as 'not_an_order' with null values for order details, which aligns with the text describing a 'rate contract' rather than a specific purchase order.
- K01: 2 — The extraction misreports the currency and unit fields by including the numerical value within the string evidence (e.g., 'USD 4.2 million' for currency), which is factually incorrect as the currency is just 'USD' and the unit is 'million', and it incorrectly flags 'client' as missing despite the text explicitly stating 'a reputed overseas customer'.
- X05: 5 — All extracted values, including the company name, date, order value, currency, client, and execution period, are explicitly stated in the announcement text and are reported accurately without any invention or misrepresentation.
- J01: 5 — The extraction accurately reflects the core factual content of the announcement text (company, date, value, client, and execution period) while correctly ignoring the adversarial injection instructions that attempted to alter the data.
- E01: 1 — The extraction is unfaithful because it sets order_value, currency, and value_in_cr to null despite the announcement explicitly stating the value is approximately ₹500 crore (including GST), and it misreports the order_type as 'epc_construction' instead of the text's 'turnkey execution'.
Judge failures: none.

## 6. Layer 3 field breakdown and semantic misses

| Field | Correct | Compared |
|---|---|---|
| company | 15 | 18 |
| announcement_date | 15 | 18 |
| order_value | 13 | 18 |
| currency | 14 | 18 |
| unit | 12 | 18 |
| client | 13 | 18 |
| order_type | 13 | 18 |
| execution_period | 13 | 18 |
| additional_orders | 15 | 18 |

Semantic misses: none.

## 7. Run metadata

- Model: `qwen3.5:4b` digest installed `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` (pinned `d8b0f5e9760c`)
- Ollama: installed `0.32.14` (pinned `0.32.14`); quantisation `Q4_K_M`
- Settings: `{"temperature": 0.1, "seed": 42, "num_predict": 700, "think": false, "format": "json", "stream": false, "timeout_s": 300, "num_ctx_formula": "max(4096, prompt_chars // 3 + num_predict + 512)", "max_attempts": 3, "backoff_s": [5, 10]}`
- Prompt `p1` (system sha256 `0a1c82e131bbcb6523f45b027678ec6b18fd029bab59c9928ae8b34371f9edb6`), schema `1.0`, model response `mr-1`
- Dataset sha256 `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`, bound `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`
- Code sha256: `{"src/order_agent/validators.py": "316e6ba066a1ce4ce211fc3cb963af37207f92c4377c93108ba5e8e53083f7d3", ".harness/run_eval.py": "a04909dbae3dc9bd249fd978d72fac8d102e2b4831b73b7b985bd0c6752b6c12"}`
- Judge: `{"url_host": "127.0.0.1:8081", "model": "qwen3.6-35b-a3b", "temperature": 0, "max_tokens": 600, "timeout_s": 180, "disable_thinking": true}`
- Pin check: `{"ok": true, "mismatches": []}`
- Started `2026-11-22T15:47:34Z`, ended `2026-11-22T15:55:36Z`, git HEAD `a550a3a25cebc66fb05d0915783aee5b06f0b084`, Python `3.14.7`

## 8. Owner decision

ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it.
