# Research: New-Order Announcement Extraction Agent

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-22

The owner fixed the technical context (language, layout, configuration, model, judge, harness and
pinned tool versions), so Technical Context has no open `NEEDS CLARIFICATION`. This file records
the design decisions taken inside those limits (R-1 … R-16) and the provisional domain decisions
the owner has not confirmed yet (P-1 … P-4). Each decision is given as Decision / Rationale /
Alternatives considered.

---

## Provisional decisions

These are working defaults, not spec Clarifications. The plan, prompt, validators and dataset use
them as written. If the owner changes one, the spec, the prompt and the affected ground truth
change only through a recorded spec revision (constitution Principle III).

### P-1 — The five Assumption defaults in spec.md

**PROVISIONAL — pending Balaji**

Each of the five is adopted as stated in [spec.md › Assumptions](./spec.md#assumptions):

| # | Default | Where it is applied |
|---|---|---|
| P-1.1 | L1-bidder status and MoUs are `not_an_order`. **PROVISIONAL — pending Balaji** | prompt rule; cases A02, A03 |
| P-1.2 | An unnamed client ("a leading PSU", "a reputed overseas customer") counts as missing → `needs_clarification`. A named government department or PSU is a client. **PROVISIONAL — pending Balaji** | prompt rule; case K01 |
| P-1.3 | Ranges, "between", "up to" are ambiguous (value null). "Approximately / about / over / more than X" reports X. **PROVISIONAL — pending Balaji** | prompt rule; cases A01, A04, E01 |
| P-1.4 | Maximum input length is 20,000 code points. **PROVISIONAL — pending Balaji** | `guards.MAX_CHARS`; cases X04, X05 |
| P-1.5 | Reference FX rates for ranking only: USD = 84 INR, EUR = 90 INR. **PROVISIONAL — pending Balaji** | `validators` ranking; INV-9; case M03 |

- **Rationale**: these are the spec's own defaults. They are conservative: when in doubt the agent
  reports "missing" or "not an order" instead of a guess.
- **Alternatives considered**: treating L1/MoU as `needs_clarification` was rejected because no
  order has been received yet. Taking the upper bound of a range was rejected because it would
  invent a value. Live FX rates were rejected because they make runs non-reproducible.

### P-2 — "Cr" / "crore" / "lakh" with no currency symbol is INR

**PROVISIONAL — pending Balaji**

- **Decision**: an amount stated in crore or lakh with no currency marker (e.g. "an order of
  340 crore") is reported as `currency: "INR"`. Its evidence for `order_value`, `currency` and
  `unit` is the value quote itself (e.g. "340 crore"). An amount in million/billion/thousand with
  no currency marker is **not** assumed to be INR. Its currency is null, so `order_value` and `unit`
  are null as well (FR-006 "null iff"), and the order is `needs_clarification`.
- **Rationale**: crore and lakh are Indian-numbering units used only for INR in Indian exchange
  filings, so the unit is itself the currency signal. Million/billion are used for every currency.
- **Applied in**: prompt rule; case N05.
- **Alternatives considered**: (a) currency null → `needs_clarification`. Rejected: it would mark
  many ordinary BSE filings ("Rs" is often dropped in headlines) as incomplete. (b) Requiring a
  separate currency quote. Rejected: no such quote exists in the text.

### P-3 — `num_predict` stays 700; at most 4 itemised orders per announcement in v1

**PROVISIONAL — pending Balaji**

- **Decision**: keep `num_predict = 700` (FR-020, as in myportfolio-web). v1 supports announcements
  with **at most 4 itemised orders**. The dataset respects this limit: no case has more than
  3 orders. To fit the budget, the model returns a compact *model response* (R-5 and
  [contracts/model-response.schema.json](./contracts/model-response.schema.json)), with one
  `value_quote` and one `client_quote` per order instead of six evidence keys. Estimated output is
  about 120 tokens of header plus about 55 tokens per order, so roughly 340 tokens for 4 orders,
  well under 700.
- **Rationale**: the owner pins the setting. Making the response compact is cheaper and more
  reliable than raising the limit.
- **Behaviour beyond the limit**: there is no extra guard. A response cut off at the token limit
  is not valid JSON and fails at layer 1 (spec edge case). `done_reason: "length"` is recorded per
  attempt so the cause shows in the feedback record.
- **Alternatives considered**: raising `num_predict` (rejected: owner-pinned, and it would diverge
  from myportfolio-web); rejecting inputs with more than 4 orders before the model call (rejected:
  counting orders deterministically is unreliable and is not in FR-016).

### P-4 — Amendments, extensions and corrigenda are `not_an_order`

**PROVISIONAL — pending Balaji**

- **Decision**: an announcement that amends, extends, corrects (corrigendum) or re-states an order
  that was **already disclosed** is `not_an_order`, unless the text explicitly calls it a new or
  additional order (e.g. "has received an additional order of ₹X crore"). In that case only the new
  or additional order is extracted.
- **Rationale**: this is consistent with FR-013 ("does not report a new order received"). Counting
  an amendment again would double-count the original order.
- **Applied in**: prompt rule; case P01.
- **Alternatives considered**: extracting the amended value as an order (rejected: double count);
  `needs_clarification` (rejected: it is not an incomplete new order).

---

## Design decisions

### R-1 — JSON Schema validation without a third-party dependency

- **Decision**: no runtime dependency. `validators` contains a small validator for a **declared
  subset** of JSON Schema 2020-12:
  - assertion keywords: `type` (including type lists), `enum`, `const`, `properties`, `required`,
    `additionalProperties`, `items`, `minItems`, `maxItems`, `uniqueItems`, `minLength`,
    `pattern`, `exclusiveMinimum`, `maxProperties`, `anyOf`, `allOf`, `if`/`then`, `$ref` (local
    `#/$defs/...` only);
  - ignored annotations: `$schema`, `$id`, `$defs`, `title`, `description`, `$comment`.

  A contract test walks both schema files and fails on any keyword outside this list, so the
  schema cannot quietly use something the validator ignores. Errors are reported as
  `(json_pointer, keyword, message)`.
- **Rationale**: the constitution says "standard library first". The two schemas use about 20
  keywords, so a validator of roughly 150 lines with exhaustive unit tests (good and bad documents
  for every keyword) is easier to audit than a dependency tree. `jsonschema` would also pull in
  `attrs`, `referencing`, `rpds-py` and `jsonschema-specifications`, which is not "one small
  dependency".
- **Alternatives considered**: `jsonschema==4.x` (rejected as above, so no Complexity Tracking
  entry is needed); hand-written per-field checks with no schema file (rejected: the owner wants
  `schemas/output.schema.json` as the versioned contract).

### R-2 — Where the contract lives

- **Decision**: `Part-1B/schemas/output.schema.json` (contract 1.0) and
  `Part-1B/schemas/model-response.schema.json` (internal, version `mr-1`) are the runtime copies.
  They are byte-identical to the design copies in `specs/001-order-extraction-agent/contracts/`,
  and a contract test enforces that. The package finds the schemas relative to the project root,
  so v1 supports an editable or source-tree install (`pip install -e .`, as the owner specified),
  and a test asserts the files resolve.
- **Rationale**: there is one source of truth, any drift between design and implementation fails
  the harness, and nothing is copied at build time.
- **Alternatives considered**: package data under `src/order_agent/` (rejected: it creates a second
  copy that has to be kept in sync).

### R-3 — Input guards (FR-016, FR-017)

- **Decision**: `guards.check(raw: bytes) -> GuardResult`. Rules are applied in the order below and
  the first one that fails decides the result:
  1. `len(raw) == 0` → `empty`.
  2. Decode as strict UTF-8. On failure → `garbled`. Rules 3–4 cannot be measured on bytes that do
     not decode, so undecodable input is always `garbled`.
  3. `text.isspace()` (Python's Unicode whitespace, including NBSP) → `whitespace_only`.
  4. `len(text) > 20_000` code points → `too_long`. Exactly 20,000 is accepted.
  5. Garbled if any of:
     - (a) a Unicode `Cc` character other than `\t`, `\n`, `\r`;
     - (b) fewer than 85% of non-whitespace characters are *recognised*, where recognised means
       Unicode category L\*, N\*, P\*, `Sc`, or one of the ASCII symbols `+ < = > | ~ ^ \``.
       This excludes `So` (such as U+FFFD and box-drawing characters), `Co`, `Cn` and `Cf`;
     - (c) fewer than 3 words, where a word is a maximal run of `str.isalpha()` characters of
       length ≥ 2.

  A UTF-8 BOM is not stripped; it is `Cf` and counts as unrecognised. A rejected input returns the
  FR-015 `rejected` shape built in code and never reaches `client`. The outcome records
  `model_called: false`.
- **Rationale**: this follows FR-016/017 exactly. The decode step has to come before
  whitespace/length checks because those are defined on characters.
- **Alternatives considered**: stripping a BOM or normalising text before the guards (rejected:
  FR-017 measures "the input as received").

### R-4 — Prompt and injection resistance (FR-018, Principle V)

- **Decision**:
  - The `system` field holds the instructions and the model-response format. The `prompt` field
    holds only the announcement, wrapped as data between markers:
    `<<<ANNOUNCEMENT id=H>>>` … `<<<END ANNOUNCEMENT id=H>>>`, where `H` is the first 12 hex
    characters of SHA-256 of the text. Being derived from the text keeps it reproducible, and the
    text cannot realistically contain its own hash.
  - The system prompt states that everything between the markers is untrusted document content,
    that instructions, role labels, "SYSTEM:" lines, JSON or other languages inside it must be
    ignored as instructions, and that the only output is the JSON object.
  - The prompt also carries the domain rules: as-stated values, unit and currency vocabulary,
    day-first dates, null instead of a guess, the order/non-order list, exchanges are never a
    party, subsidiaries, aggregates, and P-1…P-4.
  - At most two short few-shot examples are allowed. They must be synthetic and **not** taken from
    `evals/dataset.json`; a contract test checks that no dataset input text appears in the prompt.
  - `PROMPT_VERSION = "p1"`. Each run records the SHA-256 of the rendered system template.
- **Deterministic defences that do not rely on the model**:
  - schema allow-list (unknown keys fail);
  - grounding: every quote must appear in the source, and value digits and client name must appear
    in their quotes;
  - status, `missing_fields` and top-order selection are computed in code (R-6);
  - an exchange/regulator denylist for `company` and `client` (R-7, G-5).
- **Known limit**: an injected value that is copied verbatim from the injected text is grounded by
  definition, so grounding cannot catch it. INV-7 in the evaluation is the check for that. This
  residual risk is stated in the plan.
- **Alternatives considered**: a random nonce per request (rejected: it breaks reproducibility);
  deleting "suspicious" lines from the input before the model call (rejected: it alters the
  source, and evidence would then not match it).

### R-5 — The model returns a compact model response; code builds the schema-1.0 result

- **Decision**: the model returns a *model response* (MR, schema `mr-1`):
  - `is_new_order`;
  - `company`, `announcement_date`, `order_type`, `execution_period`, each with a `*_quote`;
  - `orders[]` in order of appearance, each with `order_value`, `currency`, `unit`, `client`,
    `value_quote`, `client_quote`.

  `order_type` and `execution_period` describe the main (largest) order, because schema 1.0 keeps
  them only on the top-level order. Deterministic code in `agent` and `validators` then builds the
  schema-1.0 object (assembly rules A-1 … A-7 in [data-model.md](./data-model.md#assembly-rules)):
  - it ranks orders (FR-009);
  - it computes `missing_fields` (FR-011) and `status` (FR-014);
  - it copies `value_quote` to the `order_value`, `currency` and `unit` evidence keys and
    `client_quote` to `client`, which FR-010 allows ("one quote may support several fields");
  - it adds the constants `schema_version` and `rejection_reason: null`.

  Code never creates, converts or edits a field value.
- **Strictness**: an MR that breaks its own schema or consistency rules is an application failure,
  with no repair. Examples:
  - extra keys, or an enum in the wrong case (`"inr"`);
  - a value given as a string;
  - `is_new_order: false` with non-empty `orders`;
  - a quote for a null field, or a missing quote for a non-null field;
  - `is_new_order: true` with `orders: []`. An order with neither value nor client is one entry
    with nulls.
- **Rationale**: the spec's Assumptions explicitly allow this ("Derived fields"). It takes
  arithmetic and bookkeeping away from a 4B model, which is where small models fail, and it keeps
  the output within `num_predict` (P-3). Because the MR is strict, nothing is silently patched
  (FR-019).
- **Alternatives considered**: (a) the model writes the full schema-1.0 object and code only
  checks it. Rejected: about twice the output tokens, so 4 orders exceed 700, and status and
  `missing_fields` would fail for bookkeeping reasons. (b) Code parses numbers out of the value
  quote. Rejected: code would then be creating field values, and the evaluation would no longer
  measure the model.

### R-6 — Ranking and top-level selection (FR-009, INV-9)

- **Decision**: `ranking_key(order)` is computed as follows:
  - Valued orders in INR, USD or EUR: base value = `order_value × unit_factor × fx`, with unit
    factors crore 1e7, lakh 1e5, million 1e6, billion 1e9, thousand 1e3, absolute 1, and fx
    INR 1, USD 84, EUR 90. These rank first, highest base value first, ties to the first stated.
  - Valued orders in currency `other` come next, in order of appearance (they have no INR
    equivalent).
  - Orders with no value come last, in order of appearance.

  The first-ranked order is the top-level order. `additional_orders` holds the rest in order of
  appearance: valued ones first, then the ones with no value.

  INV-9 compares the top-level order's base value with each additional order that has an INR, USD
  or EUR value. `other`-currency additional orders are outside INV-9 because there is no rate to
  compare them with.
- **Rationale**: this follows FR-009 literally. The spec does not say how `other` ranks, and this
  keeps it out of the comparison without inventing a rate.
- **Alternatives considered**: ranking `other` at its face value. Rejected: it compares incomparable
  amounts.

### R-7 — Post-validation inside the agent (FR-019, Principle II)

- **Decision**: before any result is returned, `validators.post_validate(source, result)` runs
  every check below and collects every error; it does not stop at the first.

  | Code | Check | Layer |
  |---|---|---|
  | `MR-SCHEMA` | the MR does not match `mr-1` | L1 |
  | `MR-CONSIST` | the MR breaks its own consistency rules (R-5 strictness) | L1 |
  | `OUT-SCHEMA` | the assembled result does not match the 1.0 schema, including its if/then status-shape rules | L1 |
  | `OUT-DATE` | `announcement_date` is not a real calendar date | L1 |
  | `G-1` | an evidence quote is not a substring of the source after whitespace normalisation | L2 |
  | `G-2` | the value's digits are not in the digits of its value quote | L2 |
  | `G-3` | the client is not contained (case-insensitively) in its client quote | L2 |
  | `G-4` | the evidence keys are not exactly the non-null fields | L2 |
  | `G-5` | `company` or `client` matches the exchange/regulator denylist (BSE Limited, BSE Ltd, National Stock Exchange of India Limited, NSE, SEBI, Securities and Exchange Board of India), after FR-029 name normalisation | L2 |
  | `C-1` | `missing_fields` is inconsistent | L2 |
  | `C-2` | the ranking does not hold | L2 |
  | `C-3` | the status is inconsistent | L2 |

  C-1 … C-3 hold by construction. They are checked anyway as a guard against regressions.

  If any error is found, the agent returns `ApplicationFailure` carrying the raw text, parser log,
  candidate result and errors, and emits no result.
- **Rationale**: Principle II ("a value whose evidence fails verification MUST be treated as a
  failure"). G-5 turns AC-1.5 into a deterministic guard; it can only cause failures, never accept
  something.
- **Alternatives considered**: dropping ungrounded fields to null (rejected: that is a silent
  patch).

### R-8 — Parser clean-up rules (FR-019)

- **Decision**: `parser.parse(raw_text) -> (obj, log)` applies only these rules, in order, and logs
  each one that changed the text:
  - **PC-1**: strip leading and trailing whitespace.
  - **PC-2**: if the whole text is wrapped in one Markdown code fence (```` ``` ```` or
    ```` ```json ````), remove that fence.
  - **PC-3**: `json.loads`, which must produce a JSON **object**.

  Nothing else is done: no fixing of trailing commas or quotes, no cutting the first `{…}` out of
  surrounding prose, no completing a truncated response, no changing case. A failure is
  `ParseError(rule, message)` → application failure at layer 1.
- **Rationale**: `format: "json"` already constrains Ollama's output. Fences are the only
  documented artefact seen with this model family, and removing them does not change any value.
- **Alternatives considered**: a lenient JSON repair library (rejected: it creates values).

### R-9 — Ollama client and service-failure classification (FR-020, FR-023)

- **Decision**:
  - The client sends `POST {OLLAMA_URL}/api/generate` with body
    `{model, system, prompt, stream: false, think: false, format: "json", options: {temperature: 0.1, num_predict: 700, num_ctx, seed: 42}}`.
  - `num_ctx = max(4096, (len(system) + len(prompt)) // 3 + 700 + 512)`, where the length is in
    characters of everything sent as prompt text. This is the spec's "full prompt".
  - Timeout is 300 s, the socket timeout for the request. With `stream: false` Ollama sends
    nothing until it has finished generating, so in effect this limits the whole request.

  Service failures (retryable):

  | Kind | When |
  |---|---|
  | `unreachable` | `URLError` or connection refused |
  | `timeout` | `TimeoutError` / `socket.timeout` |
  | `http_error` | HTTP status ≥ 400, including Ollama's `{"error": …}` replies |
  | `empty_response` | HTTP 200 with an empty body, or a `response` field that is missing or `""` |
  | `bad_envelope` | the body is not JSON or not an object; a runner protocol fault, not model text |

  Not service failures: `done_reason: "length"` (recorded), and any non-empty `response` text,
  which goes to the parser.

  Retry policy: up to 3 attempts in total, for service failures only, with a fixed backoff of 5 s
  then 10 s. Every attempt records start and end time, elapsed time, kind, HTTP status, `num_ctx`
  and the envelope fields `done_reason`, `eval_count` and `prompt_eval_count`. Application failures
  are never retried.
- **HTTP transport**: `urllib.request.OpenerDirector`, built by hand with only `HTTPHandler`,
  `HTTPSHandler`, `HTTPDefaultErrorHandler` and `HTTPErrorProcessor`. It has no `FileHandler`,
  `FTPHandler` or `DataHandler`, so `file:`, `ftp:` and `data:` URLs cannot be opened at all. In
  addition, `config` refuses any configured URL whose scheme is not `http`/`https`. This is the
  real mitigation for bandit B310, and **no `# nosec` comments are permitted**.
  - If bandit still flags the call site at medium or high severity, fall back to
    `http.client.HTTPConnection`/`HTTPSConnection` from the standard library. It is still stdlib
    only, and this decision is updated before merging.
  - The transport is injected (`client.post_json(url, payload, timeout, transport=…)`), so unit
    tests pass a fake and never open a socket.
- **Rationale**: this follows FR-020/023 and the owner's "HTTP via urllib", and keeps the bandit
  gate clean without suppressions.
- **Alternatives considered**: `requests` (rejected: a dependency); a total-time watchdog thread
  (rejected: not needed with `stream: false`).

### R-10 — Configuration and `.env` (FR-021, Principle VI)

- **Decision**: `config.load(env_file: Path | None)`:
  - It reads `KEY=VALUE` lines from `.env` (stdlib parser: `#` comments, optional quotes, no
    interpolation). Process environment variables override `.env`.
  - Required keys: `OLLAMA_URL`, `AGENT_MODEL`, `AGENT_MODEL_DIGEST`, `JUDGE_URL`, `JUDGE_MODEL`.
    A missing key is a configuration error (CLI exit 78). There are no hidden defaults in code.
  - **Pins live in code, not in `.env`**: `PINNED_MODEL = "qwen3.5:4b"`,
    `PINNED_MODEL_DIGEST = "d8b0f5e9760c"`, `PINNED_RUNNER_VERSION = "0.32.14"`, and the generation
    settings (temperature 0.1, seed 42, num_predict 700, think false, format json, timeout 300,
    the `num_ctx` formula).
  - `AGENT_MODEL` / `AGENT_MODEL_DIGEST` from the environment must equal the pins. If they differ,
    the CLI warns on stderr but still runs (useful for exploration). The evaluation records the
    mismatch and the verdict is **INCONCLUSIVE** (FR-031 step 1).
  - `.env` is git-ignored (`Part-1B/.gitignore`); `.env.example` is committed with the owner's
    values, which contain no secrets.
- **Rationale**: FR-020 says the settings "MUST be pinned in configuration, not chosen per run". A
  `.env` value could be changed per run, so the pins are code constants and `.env` only supplies
  endpoints and confirms identity.
- **Alternatives considered**: everything in `.env` (rejected: the pins could then be edited away
  without trace).

### R-11 — Run environment and pin check (FR-022, AC-5.6)

- **Decision**: at the start of a run, `run_eval.py` collects and checks:
  - `GET {OLLAMA_URL}/api/version` → `version`, which must equal `0.32.14`;
  - `GET {OLLAMA_URL}/api/tags` → the entry whose `name` is the pinned tag; its full `digest` must
    start with `d8b0f5e9760c`;
  - `POST {OLLAMA_URL}/api/show` → `details.quantization_level`, which is recorded and must be
    `Q4_K_M`.

  Python version, `pip freeze`, git HEAD and the platform are also recorded. If any of these calls
  fails, the pin check cannot be confirmed; that counts as a failed check → INCONCLUSIVE, and the
  run still processes every case so the evidence is complete. All of this is written to
  `environment.json` in the run folder.
- **Rationale**: AC-5.6. Matching on the short digest prefix is what `ollama list` shows and what
  the spec pins.

### R-12 — LLM judge (FR-030)

- **Decision**: the judge client sends `POST {JUDGE_URL}` (OpenAI-compatible) with
  `{model: JUDGE_MODEL, temperature: 0, max_tokens: 400, messages: [system, user]}`.
  - The system message asks for a 1–5 faithfulness rating of the agent output against the source
    only, and a reply of exactly `{"rating": <int>, "rationale": "<one sentence>"}`.
  - The user message holds the source between the same data markers as R-4, plus the agent's
    result JSON.
  - The judge sees neither the ground truth nor any layer results.
  - Parsing: strip a leading `<think>…</think>` block if present (qwen3.x reasoning), then apply
    PC-1…PC-3. `rating` must be an integer from 1 to 5.

  Judge failures (`unreachable`, `timeout`, `http_error`, `empty_response`, `bad_envelope`,
  `unparseable`) are counted separately from model service failures and application failures.
  Judge service failures use the same retry policy (3 attempts), and are informational only.

  The judge runs only on layer-3 cases that have a candidate result. `--skip-judge` is not offered,
  so every run tries the judge.
- **Rationale**: FR-030 and AC-5.4. The verdict function does not take judge data as input at all,
  so the judge cannot influence the verdict even by accident; a unit test asserts this.
- **Alternatives considered**: `response_format: json_object`. Rejected: MLX servers do not all
  support it reliably, and the rating is informational.

### R-13 — Evaluation runner `.harness/run_eval.py`

- **Decision**: there is one entry point and no case filter, so a partial run is impossible. Steps:
  1. **Dataset gate**: load `evals/dataset.json`, check that it matches the dataset format
     ([data-model.md](./data-model.md#evaluation-case)), that ids are unique, that FR-025 minimum
     counts per category are met, that every ground truth is valid schema 1.0, and that every
     injection case's counterpart exists. Any failure → exit 3, and no verdict or results file is
     written. Fingerprint = SHA-256 of the raw file bytes.
  2. **Environment and pin check** (R-11).
  3. Run every case sequentially through `order_agent.agent.run` (guards → … → post-validation)
     with retries (R-9), and store every attempt's request and raw response.
  4. Score each case:
     - **Layer 1**: the eval's schema validation of the candidate result, plus `OUT-DATE`.
     - **Layer 2**: INV-1 … INV-9, written **independently** in `run_eval.py` rather than reusing
       `validators` G-checks, so a bug in the agent's checks cannot hide a failure. Only the schema
       validator is shared, because the schema file is the contract.
     - **Layer 3**: field accuracy with the FR-029 normalisation.
     - Judge.
  5. Compute the verdict (FR-031) with a pure function.
  6. Write the run folder, `evidence/eval-results.json` and `summary.md`.

  Exit codes: 0 PASS, 1 FAIL, 2 INCONCLUSIVE, 3 runner or dataset error. The scoring and verdict
  functions are pure and unit-tested through `importlib`, with HTTP faked.
- **How agent post-validation errors map to layers**: a case whose agent run produced no candidate
  (parse or MR failure) fails layer 1, and also fails layer 2, which cannot be evaluated. Any agent
  post-validation error fails the layer of its code (R-7 table), on top of the harness's own checks.
  Both are reported, so a disagreement between the agent's checks and the harness's checks is
  visible as a bug.
- **Invariant applicability** is decided from the spec's "Applies to" column, using the candidate
  output and the ground truth. The dataset's `invariants` list documents what the author expects;
  the dataset gate checks it against the ground truth, but it can never *reduce* the checks that
  run.
- **Layer 3 with no candidate**: such a case scores 0 of 9. A missing output gets no credit, even
  for fields that are null in the ground truth. This is a plan-level reading that is stricter than
  the spec text, never looser.
- **Unresolved service failure**: the case counts as not passing in layers 1, 2 and 3 (0 of 9),
  and is listed under service failures, not application failures (FR-031).
- **Rationale**: this follows FR-026 … FR-033 and the owner's "ONE evaluation runner".

### R-14 — Deterministic-code harness (`.harness/run_harness.sh`, `.harness/run_all.sh`)

- **Decision**: `run_harness.sh` is the same as Part 1A's, with the coverage target changed to
  `--cov=order_agent`. Steps:
  - `1a-ruff-check`: `ruff check .`
  - `1b-ruff-format`: `ruff format --check .`
  - `2-bandit`: `bandit -r src -ll`, i.e. zero medium or high findings
  - `2b-nosec-scan`: no `nosec` in `src/`. This is the one addition over Part 1A. It stops anyone
    from passing gate 2 by suppressing findings.
  - `3-pytest`: `pytest --cov=order_agent --cov-branch --cov-fail-under=90`

  It has no fail-fast, keeps a log per step, writes `environment.txt` and `summary.md` under
  `evidence/harness-results/<UTC stamp>/`, and exits 0 only if every gate passes.

  `run_all.sh` runs `run_harness.sh`. If the harness fails, it **does not run the evaluation** and
  exits 1, because the constitution requires the deterministic gates to pass "before an evaluation
  result is reported". Otherwise it runs `run_eval.py` and exits with its code, so every result
  except PASS is non-zero.
- **Test isolation**:
  - an autouse `conftest.py` fixture replaces `socket.socket.connect` with a function that raises,
    so any test that tries to reach the network fails loudly;
  - every HTTP path uses the injected fake transport.

  Tests reference FR/AC/INV ids in their names or docstrings, e.g.
  `test_ac_3_1_empty_rejected_without_model_call`.
- **ruff scope**: `pyproject.toml` sets `extend-include = [".harness/*.py"]`, so `run_eval.py` is
  linted and format-checked. Coverage is measured on `src` only, as fixed by the owner. The tests
  of `run_eval.py` run under pytest but do not count towards coverage.
- **Rationale**: owner-fixed gates, reusing what Part 1A proved.

### R-15 — Evidence layout and formats

- **Decision**: see [contracts/eval-results.md](./contracts/eval-results.md). Each run writes
  `evidence/eval-runs/<YYYYMMDDTHHMMSSZ>/` containing:
  - `environment.json`
  - `run.json`
  - `raw/<case>/attempt-<n>.json`
  - `cases/<case>.json`
  - `feedback/<case>.json`
  - `judge/<case>.json`
  - `eval-results.json`
  - `summary.md`

  `evidence/eval-results.json` is a copy of the latest completed run's results. An interrupted run
  leaves its folder with `run.json.completed: false` and does not update the top-level file.
- **Repair log**: each repair cycle (FR-033) is a dated entry in `evidence/repair-log.md`, linking
  the failing run folder, the change made, the reason with the feedback records cited, and the
  rerun folder.

### R-16 — Dependencies and tooling pins

- **Decision**: no runtime dependencies (`dependencies = []`). `requirements-dev.txt` contains
  exactly `ruff==0.14.0`, `bandit==1.9.1`, `pytest==8.4.2`, `pytest-cov==7.0.0`, the versions
  proven in Part 1A. `requires-python = ">=3.12"`; the venv runs 3.14.7. Ruff settings are copied
  from Part 1A (`target-version = "py312"`, `line-length = 100`,
  `select = ["E","F","W","I","B","UP","SIM"]`).
- **Rationale**: owner-fixed versions, and the constitution's "standard library first" rule.
