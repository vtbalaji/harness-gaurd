# Evaluation run 20261122T160905Z

## 1. Verdict

**FAIL** (rule `2-app-failure`): Layer 1 failed for 1 case(s): E02 (MR-CONSIST); Layer 2 failed for 1 case(s): E02 (MR-CONSIST).

Dataset binding: `matches_spec: true` (dataset sha256 `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`, bound `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`).

## 2. Layers

| Layer | Score | Threshold | Met | Not scored |
|---|---|---|---|---|
| L1 structural | 27/28 (96.4%) | 100% | False | - |
| L2 invariants | 27/28 (96.4%) | 100% | False | - |
| L3 fields | 149/162 (92.0%) | 80% | True | - |

## 3. Application failures

| Case | Layers | Checks | Stage | Feedback |
|---|---|---|---|---|
| E02 | [1, 2] | MR-CONSIST | mr_consistency | feedback/E02.json |

Checker disagreements: none.

## 4. Service failures (model)

Unresolved: none.
Failed attempts: none.

## 5. Judge (informational, does not affect verdict)

Model `qwen3.6-35b-a3b`, rated 17, mean 3.59.

- N01: 5 — All extracted values, including the company name, date, order value, currency, unit, client, order type, and execution period, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- N02: 5 — All extracted values, including the company name, date, order value, currency, unit, client, and order type, are explicitly stated in the announcement text and are accurately reported without any misrepresentation or invention.
- N03: 5 — All extracted values, including the company name, announcement date, order value, currency, unit, client, order type, and execution period, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- N04: 5 — All extracted values, including the company name, date, order value, currency, client, and execution period, are explicitly stated in the announcement text and are reported accurately without any invention or misrepresentation.
- N05: 2 — The extraction incorrectly infers the currency as INR and misreports the evidence for currency and unit by repeating the full value string '340 crore' instead of extracting the specific currency code or unit, which constitutes a misreporting of the stated text.
- N06: 5 — All extracted values, including the order amount, client name, and delivery timeline, are explicitly stated in the announcement text and are accurately represented without any misreporting or invention.
- U01: 2 — The extraction incorrectly identifies the currency as USD in the structured fields and evidence, whereas the announcement explicitly states the value is in INR.
- M01: 2 — The extraction incorrectly assigns the total aggregate order value of ₹1,250 crore to the specific order from the National Highways Authority of India, which is actually valued at ₹800 crore, thereby misreporting the primary data point.
- M02: 2 — The extraction incorrectly assigns the order type 'supply of LT power cables' (which belongs to the first order) to the primary order from Maharashtra State Electricity Distribution Company Limited, which is for 'HT aerial bunched cables'.
- M03: 2 — The extraction incorrectly assigns the order type 'supply of pipeline valves' (from the first order) to the primary order from Rotterdam Process Equipment B.V., which is explicitly for 'industrial pumps', thereby misreporting the content of the text.
- A01: 2 — The extraction is unfaithful because it sets order_value, currency, unit, and value_in_cr to null, ignoring the explicit text stating the orders are in the range of ₹200–250 crore.
- A04: 5 — The extraction accurately reflects all stated information in the announcement, correctly identifying the company, client, service type, and execution period, while appropriately marking the order value as null in the structured fields despite its presence in the text, which aligns with the 'needs_clarification' status and does not constitute a misreporting of facts.
- V01: 5 — The extraction accurately reflects all stated information in the announcement, correctly identifying the company, client, order type, execution period, and the explicit non-disclosure of the order value, with no misreported or invented data.
- K01: 2 — The extraction incorrectly maps the full monetary phrase 'USD 4.2 million' to the 'currency' and 'unit' fields, which should strictly contain 'USD' and 'million' respectively, indicating a misreporting of the structured data.
- X05: 5 — All extracted values, including the company name, date, order value, currency, client, and execution period, are explicitly stated in the announcement text and are reported accurately without any invention or misrepresentation.
- J01: 5 — The extraction accurately reflects the core factual content of the announcement text (company, date, value, client, and execution period) while correctly ignoring the adversarial injection instructions that attempted to alter the data.
- E01: 2 — The extraction incorrectly maps the order value string to the currency and unit fields, and misclassifies the 'turnkey execution' order type as 'epc_construction' without explicit textual support.
Judge failures: none.

## 6. Layer 3 field breakdown and semantic misses

| Field | Correct | Compared |
|---|---|---|
| company | 17 | 18 |
| announcement_date | 17 | 18 |
| order_value | 16 | 18 |
| currency | 16 | 18 |
| unit | 17 | 18 |
| client | 17 | 18 |
| order_type | 16 | 18 |
| execution_period | 16 | 18 |
| additional_orders | 17 | 18 |

Semantic misses: U01 (order_value, currency), M03 (order_type, execution_period).

## 7. Run metadata

- Model: `qwen3.5:4b` digest installed `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` (pinned `d8b0f5e9760c`)
- Ollama: installed `0.32.14` (pinned `0.32.14`); quantisation `Q4_K_M`
- Settings: `{"temperature": 0.1, "seed": 42, "num_predict": 700, "think": false, "format": "json", "stream": false, "timeout_s": 300, "num_ctx_formula": "max(4096, prompt_chars // 3 + num_predict + 512)", "max_attempts": 3, "backoff_s": [5, 10]}`
- Prompt `p3` (system sha256 `a19b0bb4eba850a359d45ffbbad55905d16640a553aa005bbd4189db75c07797`), schema `1.0`, model response `mr-1`
- Dataset sha256 `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`, bound `8ab71de92f6e2def624dc67b9da7c0102be86f8c90b7d78a8172b4a07f24ef98`
- Code sha256: `{"src/order_agent/validators.py": "316e6ba066a1ce4ce211fc3cb963af37207f92c4377c93108ba5e8e53083f7d3", ".harness/run_eval.py": "a04909dbae3dc9bd249fd978d72fac8d102e2b4831b73b7b985bd0c6752b6c12"}`
- Judge: `{"url_host": "127.0.0.1:8081", "model": "qwen3.6-35b-a3b", "temperature": 0, "max_tokens": 600, "timeout_s": 180, "disable_thinking": true}`
- Pin check: `{"ok": true, "mismatches": []}`
- Started `2026-11-22T16:09:05Z`, ended `2026-11-22T16:16:33Z`, git HEAD `358f55bb9fe5e8206c6b453109d64c4d6de405d8`, Python `3.14.7`

## 8. Owner decision

ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it.
