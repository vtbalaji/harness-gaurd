# Research: New-Order Announcement Extraction Agent

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-22

The owner fixed the technical context (language, layout, configuration, model, judge, harness and
pinned tool versions), so Technical Context has no open `NEEDS CLARIFICATION`. This file records
the design decisions taken inside those limits (R-1 … R-17) and the domain decisions P-1 … P-5
(P-5 was added in spec rev 2). P-2 and P-3 were confirmed by the owner in spec rev 3; P-1, P-4 and
P-5 are still provisional. Each decision is given as Decision / Rationale / Alternatives
considered.

**Spec rev 2 (2026-11-22)**: the `/speckit-analyze` findings were remediated before any
evaluation run. Every reading that used to be "plan-level" is now written in the spec (FR-027 …
FR-031, AC-5.6), and the decisions below follow that text. Sections changed in rev 2 are marked
"(rev 2)".

**Spec rev 3 (2026-11-22)**: Balakrishnan answered Q3 (P-2) and Q4 (P-3) in the project thread. Both
are confirmed, and the Q3 answer adds the derived field `value_in_cr` (spec FR-035, INV-11; R-17
below). No evaluation has run. Sections changed in rev 3 are marked "(rev 3)".

---

## Provisional decisions

These started as working defaults, not spec Clarifications. The plan, prompt, validators and
dataset use them as written. If the owner changes one, the spec, the prompt and the affected
ground truth change only through a recorded spec revision (constitution Principle III). P-2 and
P-3 have since been confirmed (spec rev 3, Clarifications Q3/Q4) and are labelled so; the section
heading and its anchor are kept so that existing links still work.

### P-1 — The five Assumption defaults in spec.md

**CONFIRMED by Balakrishnan 2026-11-22**

Each of the five is adopted as stated in [spec.md › Assumptions](./spec.md#assumptions):

| # | Default | Where it is applied |
|---|---|---|
| P-1.1 | L1-bidder status and MoUs are `not_an_order`. **CONFIRMED by Balakrishnan 2026-11-22** | prompt rule; cases A02, A03 |
| P-1.2 | An unnamed client ("a leading PSU", "a reputed overseas customer") counts as missing → `needs_clarification`. A named government department or PSU is a client. **CONFIRMED by Balakrishnan 2026-11-22** | prompt rule; case K01 |
| P-1.3 | Ranges, "between", "up to" are ambiguous (value null). "Approximately / about / over / more than X" reports X. **CONFIRMED by Balakrishnan 2026-11-22** | prompt rule; cases A01, A04, E01 |
| P-1.4 | Maximum input length is 20,000 code points. **CONFIRMED by Balakrishnan 2026-11-22** | `guards.MAX_CHARS`; cases X04, X05 |
| P-1.5 | Reference FX rates for ranking only: USD = 84 INR, EUR = 90 INR. They are never applied to `value_in_cr` (rev 3). **CONFIRMED by Balakrishnan 2026-11-22** | `validators` ranking; INV-9; case M03 |

- **Rationale**: these are the spec's own defaults. They are conservative: when in doubt the agent
  reports "missing" or "not an order" instead of a guess.
- **Alternatives considered**: treating L1/MoU as `needs_clarification` was rejected because no
  order has been received yet. Taking the upper bound of a range was rejected because it would
  invent a value. Live FX rates were rejected because they make runs non-reproducible.

### P-2 — "Cr" / "crore" / "lakh" with no currency symbol is INR

**CONFIRMED by Balakrishnan 2026-11-22**

- **Confirmation (rev 3)**: spec Clarifications Q3, answered in the project thread on 2026-11-22
  in the owner's words: "1b unless is mentioned in $". It is read as two rules:
  - (1) an amount stated in crore/Cr/lakh with no currency marker is INR (this decision);
  - (2) every INR amount is **also** reported converted to crore, unless the amount is in $ (USD)
    or another non-INR currency, which is not converted. This became spec FR-035 / INV-11; the
    design is in R-17.
- **Decision**: an amount stated in crore or lakh with no currency marker (e.g. "an order of
  340 crore") is reported as `currency: "INR"`. Its evidence for `order_value`, `currency` and
  `unit` is the value quote itself (e.g. "340 crore"). Being INR, it also gets `value_in_cr`
  (340 in this example; R-17). An amount in million/billion/thousand with no currency marker is
  **not** assumed to be INR. Its currency is null, so `order_value` and `unit` are null as well
  (FR-006 "null iff"), so `value_in_cr` is null too, and the order is `needs_clarification`.
  - The owner's answer covers crore and lakh explicitly. The million/billion/thousand sub-rule is
    carried over unchanged from the provisional text, and no dataset case uses it.
- **Rationale**: crore and lakh are Indian-numbering units used only for INR in Indian exchange
  filings, so the unit is itself the currency signal. Million/billion are used for every currency.
- **Applied in**: prompt rule; spec FR-006 (rev 3); case N05 (value_in_cr 340).
- **Alternatives considered**: (a) currency null → `needs_clarification`. Rejected: it would mark
  many ordinary BSE filings ("Rs" is often dropped in headlines) as incomplete. (b) Requiring a
  separate currency quote. Rejected: no such quote exists in the text.

### P-3 — `num_predict` stays 700; at most 4 itemised orders per announcement in v1

**CONFIRMED by Balakrishnan 2026-11-22**

- **Confirmation (rev 3)**: spec Clarifications Q4, answered in the project thread on 2026-11-22
  in the owner's words: "max 4 order". v1 handles at most 4 itemised orders per announcement, and
  `num_predict` stays 700. Spec FR-009 now states the limit.
- **Decision**: keep `num_predict = 700` (FR-020, as in myportfolio-web). v1 supports announcements
  with **at most 4 itemised orders**. The dataset respects this limit: no case has more than
  3 orders. To fit the budget, the model returns a compact *model response* (R-5 and
  [contracts/model-response.schema.json](./contracts/model-response.schema.json)), with one
  `value_quote` and one `client_quote` per order instead of six evidence keys. Estimated output is
  about 120 tokens of header plus about 55 tokens per order, so roughly 340 tokens for 4 orders,
  well under 700. Rev 3's `value_in_cr` does not change this estimate: code computes it after the
  model call, and `mr-1` has no such field (R-17).
- **Rationale**: the owner pins the setting. Making the response compact is cheaper and more
  reliable than raising the limit.
- **Behaviour beyond the limit**: there is no extra guard. A response cut off at the token limit
  is not valid JSON and fails at layer 1 (spec edge case). `done_reason: "length"` is recorded per
  attempt so the cause shows in the feedback record.
- **Alternatives considered**: raising `num_predict` (rejected: owner-pinned, and it would diverge
  from myportfolio-web); rejecting inputs with more than 4 orders before the model call (rejected:
  counting orders deterministically is unreliable and is not in FR-016).

### P-4 — Amendments, extensions and corrigenda are `not_an_order`

**CONFIRMED by Balakrishnan 2026-11-22**

- **Decision**: an announcement that amends, extends, corrects (corrigendum) or re-states an order
  that was **already disclosed** is `not_an_order`, unless the text explicitly calls it a new or
  additional order (e.g. "has received an additional order of ₹X crore"). In that case only the new
  or additional order is extracted.
- **Rationale**: this is consistent with FR-013 ("does not report a new order received"). Counting
  an amendment again would double-count the original order.
- **Applied in**: prompt rule; case P01.
- **Alternatives considered**: extracting the amended value as an order (rejected: double count);
  `needs_clarification` (rejected: it is not an incomplete new order).

### P-5 — Explicit marker for unstated optional fields: `unstated_fields` (spec rev 2)

**CONFIRMED by Balakrishnan 2026-11-22**

- **Decision**: schema 1.0 gains a required top-level array `unstated_fields`. It lists every
  **optional** field that is null in the result: `company` and `announcement_date` when null, and,
  only when `order` is non-null, `order_type` and `execution_period` when null. Entries are unique,
  in the fixed order `company`, `announcement_date`, `order_type`, `execution_period`.
  - It is distinct from `missing_fields`, which keeps listing only the **required** order fields
    (`order_value`, `client`) and alone drives `needs_clarification` (FR-014).
  - For `not_an_order` only `company` / `announcement_date` can appear. For `rejected` it is `[]`
    (FR-015).
  - `order_type` is never null inside an order object, so it never appears in practice. It is in
    the enum so that the list covers every optional field.
  - The model does not produce it. Assembly derives it from the nulls (A-8), the agent checks it
    (C-4), and the evaluation checks it as INV-10 (layer 2).
- **Rationale**: constitution Principle II says "a fact not stated in the source MUST be reported
  as missing (null plus an explicit missing marker)". Read literally, that covers optional facts as
  well. Before rev 2, a missing company, date or execution period was just null, and the only
  signal was an absent evidence key.
- **Applied in**: `contracts/output.schema.json`; FR-001, FR-012, FR-015; A-8; C-4; INV-10;
  every ground truth (T027–T029); the CLI examples.
- **Alternatives considered**:
  - (a) Amend the constitution to say "required facts". This is the owner's choice, and the
    reason P-5 is provisional. If chosen before the first evaluation, the field and INV-10 are
    removed through a spec revision.
  - (b) Put optional fields into `missing_fields`. Rejected: `missing_fields` decides the status
    (FR-014), so every order without an execution period would become `needs_clarification`.
  - (c) A per-field `{value, stated}` object. Rejected: it changes every field's type for little
    gain.

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
- **Independence (rev 2, E1)**: this validator belongs to the agent. The evaluation runner does
  use it, against the schema file, but it is not the runner's only structural check. `run_eval.py`
  also holds its own hand-written structural check of schema 1.0 (R-13, data-model.md "Runner
  structural check"). Layer 1, INV-1 and dataset gate DG-4 pass only if **both** accept the
  document. A bug in this validator therefore cannot hide a failure in the agent, the evaluation
  and the ground-truth check all at once.
- **Alternatives considered**: `jsonschema==4.x` (rejected as above, so no Complexity Tracking
  entry is needed); hand-written per-field checks with no schema file (rejected: the owner wants
  `schemas/output.schema.json` as the versioned contract).

### R-2 — Where the contract lives

- **Decision**: `Part-1B/schemas/output.schema.json` (contract 1.0) and
  `Part-1B/schemas/model-response.schema.json` (internal, version `mr-1`) are the runtime copies.
  They are byte-identical to the design copies in `specs/001-order-extraction-agent/contracts/`,
  and a contract test enforces that.
  - **Version pin (rev 2, G1)**: byte identity alone does not force a version bump, since a schema
    could change while its `$id` and `const "1.0"` stay the same. So each file's SHA-256 is pinned
    against its version in spec.md, in the table "Schema file pins (rev 2)".
  - The contract test (T016) reads that table. It fails if a file's hash differs from the row for
    its `$id`, and it treats a `PENDING-` value as a failure. Any byte change therefore needs a new
    version and a new row through a spec revision.
  - **Rev 3**: `output.schema.json` gained `value_in_cr` while its pin was still `PENDING-T098`
    and before any run, so version 1.0 was still pre-release. It keeps `$id`
    `urn:order-agent:output:1.0`, and T098 records the hash of the rev 3 bytes (spec "Schema file
    pins", rev 3 note). `model-response.schema.json` is unchanged.

  The package finds the schemas relative to the project root,
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
       Unicode category L\*, **`Mn`, `Mc`** (combining marks, rev 2), N\*, P\*, `Sc`, or one of the
       ASCII symbols `+ < = > | ~ ^ \``. This excludes `Me`, `So` (such as U+FFFD and box-drawing
       characters), `Co`, `Cn` and `Cf`;
     - (c) fewer than 3 words (rev 2). A word is a maximal run of characters whose
       `unicodedata.category` is L\*, `Mn` or `Mc`, and it must contain at least 2 L\* characters.
       Combining marks are word-internal: they never end a word and are not counted as letters.
       `str.isalpha()` is **not** used, because it is false for `Mn`/`Mc` and would split
       Devanagari words at vowel signs (e.g. "किया").

  A UTF-8 BOM is not stripped; it is `Cf` and counts as unrecognised. A rejected input returns the
  FR-015 `rejected` shape built in code and never reaches `client`. The outcome records
  `model_called: false`.
- **Rationale**: this follows FR-016/017 exactly. The decode step has to come before
  whitespace/length checks because those are defined on characters, which the spec states as a note
  to FR-016 (rev 2, L3). Counting combining marks follows FR-017's "letters (any script)", stated
  explicitly in rev 2 (U2).
- **Dataset check (rev 2, U2)**: a contract test (T094) runs `guards.check` on every dataset
  input:
  - every case whose id does not start with `X`, and X05, gives `ok`. This covers the Hindi
    injection in J02;
  - X01–X04 give exactly their ground-truth `rejection_reason`.
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
  - **Version bump rule (rev 2, L7; FR-033)**:
    - `PROMPT_VERSION` stays `"p1"` while the prompt is being built (US1–US4).
    - From the first owner-run evaluation on, every repair cycle that changes any `SECTIONS` text
      bumps it (`p2`, `p3`, …). The repair-log entry names the old and new versions.
    - A test (T097) keeps a table `KNOWN_PROMPTS = {version: system_sha256}` and fails when the
      current system prompt's hash is not the entry for the current version. A prompt change
      without a bump therefore fails the harness.
    - The MR schema version (`mr-1`) is independent of the prompt version; its title no longer
      names a prompt version.
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
  schema-1.0 object (assembly rules A-1 … A-9 in [data-model.md](./data-model.md#assembly-rules)):
  - it ranks orders (FR-009);
  - it computes `missing_fields` (FR-011) and `status` (FR-014);
  - it copies `value_quote` to the `order_value`, `currency` and `unit` evidence keys and
    `client_quote` to `client`, which FR-010 allows ("one quote may support several fields");
  - it adds the constants `schema_version` and `rejection_reason: null`;
  - it derives `unstated_fields` from the nulls (A-8, P-5, **CONFIRMED by Balakrishnan 2026-11-22**);
  - it computes `value_in_cr` for every order from the order's own `order_value`, `currency` and
    `unit` (A-9, spec FR-035, rev 3; R-17).

  Code never creates, converts or edits an **extracted** field value. `value_in_cr` is the one
  value code computes. The spec declares it as a derived field, and computing it leaves
  `order_value` and `unit` unchanged.
- **Strictness**: an MR that breaks its own schema or consistency rules is an application failure,
  with no repair. Examples:
  - extra keys, or an enum in the wrong case (`"inr"`). This includes a `value_in_cr` key in an
    order: the model cannot supply the conversion (rev 3);
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
  measure the model. `value_in_cr` (rev 3) does not reopen this. It is computed from the
  model's validated `order_value` and `unit`, never from the quote text.

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

  **INV-9 and C-2 (rev 2)** implement the spec's INV-9 text exactly:
  - (i) every INR/USD/EUR additional order with a value has a base value ≤ the top-level order's,
    and in that case the top-level order is itself INR/USD/EUR;
  - (ii) an `other` order is compared by value only if it is convertible, which never happens in
    schema 1.0;
  - (iii) the top-level order may be `other` only if it is the only order with a non-null value.

  The ranking above satisfies (i) and (iii) whenever at most one valued order is `other`. With two
  or more valued `other` orders, no ranking can satisfy (iii). That is deliberate: it is out of
  scope for v1, absent from the dataset, and fails loudly instead of passing unchecked.
- **Rationale**: this follows FR-009 literally. Before rev 2, INV-9 simply skipped `other` orders,
  which was looser than the spec text. Rev 2's (iii) closes that gap without inventing a rate.
- **Rev 3**: ranking does not use `value_in_cr`. It keeps the base value above, because
  `value_in_cr` is null for USD and EUR orders. The FX rates are still used only here and never
  feed `value_in_cr` (spec FR-035).
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
  | `C-4` | `unstated_fields` is not exactly the null optional fields (rev 2, P-5, **CONFIRMED by Balakrishnan 2026-11-22**) | L2 |
  | `C-5` | a `value_in_cr` is not the FR-035 conversion of its order, or is non-null for a non-INR order (rev 3) | L2 |

  C-1 … C-5 hold by construction. They are checked anyway as a guard against regressions. C-5
  calls the same `validators.value_in_cr` that assembly uses, so it guards against assembly
  wiring errors only. A bug in the conversion itself is caught by the runner's independent INV-11
  (R-13, R-17).

  **Rev 2**: this code table, with these layers, is now in spec FR-028. An error from any code
  fails its layer in the evaluation (reading (a)). G-5 is therefore a spec-level layer-2 rule, not
  only a plan-level guard. The runner adds one code of its own, `EXC` (layer 1), for an unexpected
  exception raised by `agent.run` (R-13). The agent never emits `EXC`.

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

  Service failures (retryable). Rev 2 (E2) adds `connection_lost` and makes the list match spec
  FR-023 exactly. With `urllib`, errors raised in `getresponse()` or `read()` reach the caller
  **unwrapped**. That is exactly what happens when Ollama's runner crashes mid-generation with
  `stream: false`, so those errors are classified too.

  `client` classifies whatever the transport raises, using the **first matching row**. So a fake
  transport can raise these exceptions directly, and `default_transport` performs the body read
  inside the transport call so that read-time errors surface there.

  | Order | Kind | When |
  |---|---|---|
  | 1 | `timeout` | `TimeoutError` (`socket.timeout` is an alias of it since Python 3.10), at connect or during read, including a `URLError` whose `reason` is a `TimeoutError` |
  | 2 | `unreachable` | any other `URLError` (e.g. `reason` is `ConnectionRefusedError` or a DNS error), or `ConnectionRefusedError` |
  | 3 | `connection_lost` | `http.client.RemoteDisconnected`, `ConnectionResetError`, `ConnectionAbortedError`, `BrokenPipeError`, `http.client.IncompleteRead`, any other `http.client.HTTPException`, and any other `OSError` raised while the request is sent or the response is read |
  | 4 | `http_error` | HTTP status ≥ 400, including Ollama's `{"error": …}` replies |
  | 5 | `empty_response` | HTTP 200 with an empty body, or a `response` field that is missing or `""` |
  | 6 | `bad_envelope` | the body is not JSON or not an object; a runner protocol fault, not model text |

  An exception that is not an `OSError` or an `http.client.HTTPException` (e.g. a `ValueError`
  from a bug) is **not** a service failure. It propagates out of `client` and `agent.run`, and the
  evaluation runner records it as an application failure of that case (R-13, U1).

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
  `pin_check.ok` is false if any of the five conditions in spec FR-031 step 1 (rev 2, reading (e))
  holds: a version, digest or quantisation mismatch; a failed request; or an `AGENT_MODEL` /
  `AGENT_MODEL_DIGEST` mismatch from R-10. `pin_check.mismatches` names each one.
- **Rationale**: AC-5.6. Matching on the short digest prefix is what `ollama list` shows and what
  the spec pins.

### R-12 — LLM judge (FR-030)

- **Decision** (rev 2, L5): the judge client sends `POST {JUDGE_URL}` (OpenAI-compatible) with
  `{model: JUDGE_MODEL, temperature: 0, max_tokens: 600, messages: [system, user], chat_template_kwargs: {enable_thinking: false}}`
  and a **180 s** request timeout per attempt.
  - `chat_template_kwargs.enable_thinking: false` disables qwen3.x reasoning where the server
    supports it. Servers built on the Hugging Face chat template honour it; servers that do not
    know the field ignore it. `<think>` stripping (below) stays as the fallback.
  - `max_tokens` is 600 rather than 400, so that a reasoning block a server still emits does not
    use up the budget before the JSON.
  - Worst case: 3 attempts × 180 s plus 5 s + 10 s backoff = 555 s per case, about 2.8 h for the
    18 layer-3 cases (rev 3; it was 2.6 h for 17). Typical runs take seconds per case. These values are code constants
    (`JUDGE_TIMEOUT_S = 180`, `JUDGE_MAX_TOKENS = 600`, `JUDGE_DISABLE_THINKING = True`), recorded
    in `run.json › judge`.
  - The system message asks for a 1–5 faithfulness rating of the agent output against the source
    only, and a reply of exactly `{"rating": <int>, "rationale": "<one sentence>"}`.
  - The user message holds the source between the same data markers as R-4, plus the agent's
    result JSON.
  - The judge sees neither the ground truth nor any layer results.
  - Parsing: strip a leading `<think>…</think>` block if present (qwen3.x reasoning), then apply
    PC-1…PC-3. `rating` must be an integer from 1 to 5.

  Judge failures (`unreachable`, `timeout`, `connection_lost`, `http_error`, `empty_response`,
  `bad_envelope`, `unparseable`, `exception`) are counted separately from model service failures
  and application failures. Judge service failures use the same retry policy (3 attempts), and are
  informational only.
  - **Judge exceptions (rev 2, U1)**: `client.judge` never raises. Any exception inside it (an
    `Exception` subclass, e.g. a bug while parsing) becomes `JudgeResult(status="failed",
    kind="exception", detail="<type>: <message>")`.
  - The runner also wraps its call to `judge` the same way, as a second line of defence.
  - A judge failure never stops the run and never reaches `verdict()`.

  The judge runs only on layer-3 cases that have a candidate result. `--skip-judge` is not offered,
  so every run tries the judge.
- **Rationale**: FR-030 and AC-5.4. The verdict function does not take judge data as input at all,
  so the judge cannot influence the verdict even by accident; a unit test asserts this.
- **Alternatives considered**: `response_format: json_object`. Rejected: MLX servers do not all
  support it reliably, and the rating is informational.

### R-13 — Evaluation runner `.harness/run_eval.py`

- **Decision**: there is one entry point and no case filter, so a partial run is impossible. Steps:
  1. **Dataset gate**: load `evals/dataset.json` and enforce DG-1 … DG-9
     ([data-model.md](./data-model.md#evaluation-case)): format, unique ids, the full FR-025
     enumeration, every ground truth valid under **both** the schema file and the runner's own
     structural check, injection counterparts, the `invariants` lists, the order limit, and (rev 3,
     DG-9) the `value_in_cr` coverage and exactness of every ground-truth order. Any
     failure → exit 3, and no verdict or results file is written. Fingerprint = SHA-256 of the raw
     file bytes.
  1b. **Dataset binding (rev 2, C1; FR-026)**: read the last `DATASET-BINDING` line from
     `specs/001-order-extraction-agent/spec.md`, using the regex
     `^DATASET-BINDING dataset_version=(\S+) sha256=([0-9a-f]{64})$` on whole lines. Record
     `dataset.bound_sha256`, `dataset.bound_version` and `dataset.matches_spec` (true / false, or
     null when no line exists) in `run.json` and `eval-results.json`. Show a mismatch in
     `summary.md` §1. It is not a verdict input (FR-031).
  2. **Environment and pin check** (R-11).
  3. Run every case sequentially through `agent_run` (default `order_agent.agent.run`: guards → …
     → post-validation) with retries (R-9), and store every attempt's request and raw response.
     - `run(..., agent_run=None)` lets tests pass a scripted stand-in (T048). `main()` does not
       expose it.
     - **Unexpected exception (rev 2, U1; FR-023)**: if `agent_run` raises an `Exception` for one
       case, the runner records `ApplicationFailure(stage="exception", errors=[ValidationError(code="EXC", pointer="", message="<type>: <message>", layer=1)], raw_text=None, candidate=None, attempts=[])`
       for that case. It stores the traceback in `cases/<id>.json` and the feedback record, and
       continues with the next case. The case fails layers 1 and 2 and scores 0 of 9.
     - `BaseException`s that are not `Exception` (`KeyboardInterrupt`, `SystemExit`) end the run
       as interrupted (`completed: false`, exit 3, `evidence/eval-results.json` untouched).
  4. Score each case:
     - **Layer 1** (FR-027 rev 2): the case has a candidate, **and** the schema-file validation
       (`validators.check_output`) passes, **and** the runner's own `structural_check` passes,
       **and** the calendar-date check passes, **and** the agent reported no layer-1 code.
       - `structural_check` (E1) is plain Python inside `run_eval.py`. It neither reads the schema
         file nor calls `order_agent.validators`. Its rules S-1 … S-11 are in data-model.md (S-11,
         the `value_in_cr` shape, is rev 3).
       - If the two schema checks disagree on a document, the case still fails, and the case is
         listed in `layers.layer1.checker_disagreements`: one of the two checkers has a bug.
     - **Layer 2** (FR-028 rev 2): INV-1 … INV-11, written **independently** in `run_eval.py`
       rather than reusing the `validators` G-checks, so a bug in the agent's checks cannot hide a
       failure. In addition, any agent-reported layer-2 code fails the case. INV-11 (rev 3) has
       its own conversion helper, which derives each multiplier from `SPEC_CONSTANTS` (R-17).
     - **Layer 3**: field accuracy with the FR-029 normalisation.
     - Judge, contained (R-12).
  5. Compute the verdict (FR-031) with a pure function.
  6. Write the run folder, `evidence/eval-results.json` and `summary.md`.

  Exit codes: 0 PASS, 1 FAIL, 2 INCONCLUSIVE, 3 runner or dataset error. The scoring and verdict
  functions are pure and unit-tested through `importlib`, with HTTP faked.
- **Constants (rev 2, D1)**: `SPEC_CONSTANTS` is the runner's one constants table: thresholds,
  tolerance, unit factors, FX, fields per case, attempts, minimum cases and, from rev 3,
  `value_in_cr_decimals`. Every scoring and
  verdict function reads its values from it. A test parses spec.md's "Evaluation constants
  (rev 2)" table and requires equality, key for key.
- **Code fingerprints (rev 2, E1)**: `run.json` records the SHA-256 of
  `src/order_agent/validators.py` and `.harness/run_eval.py` (`code_sha256`). A repair that changes
  the shared validator between runs is therefore visible in the evidence (Principle VII, "the SAME
  evaluation").
- **How agent post-validation errors map to layers** (now spec FR-027/028 reading (a)):
  - A case whose agent run produced no candidate (parse, MR or exception failure) fails layer 1,
    and also fails layer 2, which cannot be evaluated.
  - Any agent error fails the layer of its code (spec FR-028 code table), on top of the runner's
    own checks.
  - Both are reported, so a disagreement between the agent's checks and the runner's checks is
    visible as a bug.
- **Invariant applicability** is decided from the spec's "Applies to" column, using the candidate
  output and the ground truth: an invariant applies if it applies to either. The dataset's
  `invariants` list must equal the set that applies to the ground truth alone (DG-8, rev 2, L4).
  It documents what the author expects and can never *reduce* the checks that run.
- **Layer 3 with no candidate**: 0 of 9. This is spec FR-029 reading (c), no longer a plan-level
  reading.
- **Unresolved service failure** (FR-031 rev 2, U3): the case counts in each layer's `total` as not
  passing (0 of 9 in layer 3). It is listed in each layer's `not_scored`, not in `failed_cases`,
  and under service failures, not application failures.
- **Semantic misses** (FR-023 rev 2, F2): cases that pass layers 1 and 2 but have at least one
  wrong layer-3 field are listed under `semantic_misses`, never under `application_failures`.
- **Rationale**: this follows FR-026 … FR-033 and the owner's "ONE evaluation runner".

### R-14 — Deterministic-code harness (`.harness/run_harness.sh`, `.harness/run_all.sh`)

- **Decision**: `run_harness.sh` is the same as Part 1A's, with the coverage target changed to
  `--cov=order_agent`. Steps:
  - `1a-ruff-check`: `ruff check .`
  - `1b-ruff-format`: `ruff format --check .`
  - `2-bandit`: `bandit -r src .harness -ll`, i.e. zero medium or high findings. Rev 2 (G2) adds
    `.harness`, so the evaluation runner is scanned too.
  - `2b-nosec-scan`: `grep -rn --include="*.py" "nosec" src .harness` must find nothing. This
    stops anyone from passing gate 2 by suppressing findings. `--include="*.py"` is needed because
    `run_harness.sh` itself contains the word.
  - `3-pytest`: `pytest --cov=order_agent --cov=.harness --cov-branch --cov-report=term-missing`.
    It passes when every test passes. Coverage data for both sources goes to `.coverage`.
  - `3a-cov-src`: `coverage report --include="src/order_agent/*" --fail-under=90`. This is the
    owner's ≥ 90% branch coverage on the package, unchanged in substance.
  - `3b-cov-run-eval` (rev 2, G2): `coverage report --include=".harness/run_eval.py" --fail-under=90`.
    It **gates** at ≥ 90%, because `run_eval.py` holds all the scoring and verdict logic.

  Gate 3 = 3 AND 3a AND 3b.

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
  linted and format-checked.
- **Coverage scope (rev 2, G2)**: coverage is measured on `order_agent` and on `.harness`. The two
  are gated **separately** (3a, 3b), each at ≥ 90% branch coverage, so neither can carry the
  other.
  - `run_eval.py` is loaded with `importlib.util.spec_from_file_location`. coverage.py tracks it
    by file path, so `--cov=.harness` measures it.
  - The shell scripts in `.harness/` are not Python and are not measured. They are covered
    behaviourally by `tests/harness/test_harness_scripts.py`.
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
- **Repair log**: each repair cycle (FR-033) is a dated entry in `evidence/repair-log.md`. It
  links the failing run folder, the change made, the reason with the feedback records cited, and
  the rerun folder. From rev 2 (L7) it also gives `prompt_version: <old> → <new>` whenever the
  prompt changed, or `prompt_version: unchanged`.

### R-16 — Dependencies and tooling pins

- **Decision**: no runtime dependencies (`dependencies = []`). `requirements-dev.txt` contains
  exactly `ruff==0.14.0`, `bandit==1.9.1`, `pytest==8.4.2`, `pytest-cov==7.0.0`, the versions
  proven in Part 1A. `requires-python = ">=3.12"`; the venv runs 3.14.7. Ruff settings are copied
  from Part 1A (`target-version = "py312"`, `line-length = 100`,
  `select = ["E","F","W","I","B","UP","SIM"]`).
- **Build backend pin (rev 2, C4)**: `[build-system] requires = ["setuptools==80.9.0"]`, an exact
  pin instead of the earlier `>=77` range.
  - `pip install -e .` fetches the build backend into an isolated build environment at install
    time, so a range would let that dependency drift between installs. The constitution requires
    every third-party dependency to be pinned exactly.
  - 80.9.0 is a published release of the 80.x line (May 2025), chosen by the owner in the rev 2
    remediation. It supports the PEP 621 `[project]` table (setuptools ≥ 61) and PEP 660 editable
    installs (≥ 64), the only two features this project needs from the backend, and it needs no
    plugins.
  - Newer releases may exist. Moving to one is an R-16 change like any other pin change, not
    something to do silently.
  - setuptools is a build-time tool only. It is not imported at runtime, so `dependencies = []`
    still holds.
  - If 80.9.0 fails to build on Python 3.14.7 during T012, stop and record the replacement version
    here before changing it (T012).
- **Transitive dev dependencies (rev 2, C4)**: the four dev tools pull in further packages
  (`coverage`, `pluggy`, `iniconfig`, `packaging`, `Pygments`, `PyYAML`, `stevedore`, `rich`,
  `markdown-it-py`, `mdurl`, and so on). These are pinned through a committed constraints file,
  `constraints-dev.txt`.
  - It is generated once, after the first install, by
    `.venv/bin/python -m pip freeze --exclude-editable > constraints-dev.txt` (T092).
  - Every later install uses
    `.venv/bin/python -m pip install -r requirements-dev.txt -c constraints-dev.txt`.
  - It is regenerated only when a pin in `requirements-dev.txt` changes, and that change is
    recorded here.
  - T087 checks that `pip freeze --exclude-editable` still equals the file.
- **Rationale**: owner-fixed versions, the constitution's "standard library first" rule, and its
  "pinned to an exact version" rule, applied to the build backend and the transitive tools too.

### R-17 — `value_in_cr`: deterministic crore conversion of INR amounts (spec rev 3, FR-035, INV-11)

- **Decision**:
  - **Agent side** (`validators`): `CRORE_MULTIPLIER` maps each unit to an exact decimal string,
    exactly as the owner listed them: crore `"1"`, lakh `"0.01"`, million `"0.1"`, billion
    `"100"`, thousand `"0.0001"`, absolute `"0.0000001"`.
    `value_in_cr(order_value, currency, unit) -> float | None`:
    - returns `None` unless `currency == "INR"`, which also covers a null value;
    - otherwise computes
      `(Decimal(str(order_value)) * Decimal(CRORE_MULTIPLIER[unit])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)`
      and returns it as a `float`.

    Assembly rule A-9 calls it for the top-level order and for every additional order. C-5
    re-checks the result.
  - **Runner side** (`run_eval.py`): its own helper, `expected_value_in_cr(order)`, is written
    separately. It derives each multiplier as
    `Decimal(SPEC_CONSTANTS["unit_factor"][unit]) / Decimal(SPEC_CONSTANTS["unit_factor"]["crore"])`,
    an exact division in the default 28-digit context, and rounds half up to
    `SPEC_CONSTANTS["value_in_cr_decimals"]` places. INV-11 compares
    `Decimal(str(candidate_value))` with that result by numeric equality, so `340` equals `340.0`.
    The runner does not import `validators.value_in_cr` or `CRORE_MULTIPLIER` (T044 AST check).
  - **Model side**: nothing changes. `mr-1` has no `value_in_cr`, the prompt does not mention a
    conversion, and an MR that contains the key fails `MR-SCHEMA` (strict `additionalProperties`).
    `PROMPT_VERSION` stays `p1`.
  - **Contract**: schema 1.0 requires `value_in_cr` in `$defs/order` and
    `$defs/additional_order` (`number | null`), plus a shape rule `value_in_cr_rule`: a number if
    and only if currency is `INR`. The exact value is INV-11, which a schema cannot express.
  - **No evidence key, no layer-3 field**: FR-010's key list, INV-8, G-4, `unstated_fields` and the
    nine layer-3 fields are unchanged. INV-7's walk over every number in the candidate includes
    `value_in_cr`, so an injected amount that reached `order_value` is also caught there.
- **Rationale**:
  - The owner asked for the conversion and for it to be done in code. Code-side arithmetic is
    exact and testable; a 4B model is unreliable at arithmetic, and the output budget (P-3) has no
    room to spare.
  - Decimal arithmetic with an explicit rounding mode makes the agent and the runner agree
    bit-for-bit. Binary floats can round the same tie both ways (e.g. `0.12345` crore, or 12.345
    lakh → 0.12345).
  - Half-up is the reading of "rounded to 4 decimals" that an analyst expects, so it was chosen
    over Python's half-even `round()`.
  - Two independent derivations of the multiplier catch a typo in either table: the owner's list
    on the agent side, the unit factors ÷ 1e7 on the runner side.
- **Alternatives considered**:
  - (a) The model emits `value_in_cr`. Rejected: the owner said code, not model. It would also cost
    output tokens and put arithmetic on the model.
  - (b) Convert USD/EUR with the FX rates. Rejected: the owner excluded non-INR amounts, and the
    FX rates are provisional and only for ranking (P-1.5).
  - (c) A layer-3 field. Rejected by the owner: the value follows exactly from `order_value` and
    `unit`, so an exact invariant (INV-11) is stricter than a tolerance-based field comparison, and
    the 9-field formula stays unchanged.
  - (d) An evidence quote for `value_in_cr`. Rejected: no such text exists. The `order_value` quote
    already grounds it.
  - (e) A new schema version 1.1. Rejected: 1.0 has never been used by a run and its pin was still
    pending, so the constitution's "version bump on change" applies from T098 on.

---

## Implementation notes (`/speckit-implement`, 2026-11-22)

Details settled while implementing (T089). None changes a requirement, threshold, case or
ground truth; each one narrows a design statement above.

- **R-9, opener**: a bare `urllib.request.OpenerDirector` with only the four HTTP handlers
  returns `None` (no error) for a `file:`, `ftp:` or `data:` URL. `client.build_opener()`
  therefore returns a small `OpenerDirector` subclass, still holding only those four handlers,
  that raises `URLError` for any scheme other than http/https before any handler or socket is
  involved. `bandit -r src .harness -ll` reports nothing, so the `http.client` fallback was not
  needed.
- **R-9, classification**: an `HTTPError` exception (an HTTP status ≥ 400) is classified as
  `http_error`, ahead of the generic `URLError` → `unreachable` row. `default_transport` never
  raises it, because it returns the status and body instead.
- **R-9, evidence**: each `Attempt` keeps the verbatim response body (`response_body`) for the
  `raw/` evidence files; the per-case summary (`to_dict()`) omits it.
- **R-8**: PC-3 also rejects the non-JSON constants `NaN` / `Infinity` and duplicate object keys.
  Neither is valid, unambiguous JSON, and nothing is repaired.
- **R-1**: a trailing `$` in a schema `pattern` is matched as ECMA-262 end of input (Python's
  `$` would also match before a final newline).
- **R-3**: the 85% recognised-ratio comparison is exact decimal arithmetic (`0.85 * 100` is not
  85.0 in binary floating point, which would reject the exact boundary).
- **R-4**: the parties section names the NSE as "the National Stock Exchange of India (NSE)",
  without "Limited", because the bare addressee line "National Stock Exchange of India Limited"
  occurs in dataset inputs, and no dataset line may appear in the prompt (T067).
- **R-11**: `pip_freeze` is read through `importlib.metadata` and git HEAD is read from the
  `.git` directory, so the runner starts no subprocess. A pin-check request failure is recorded
  as `request_failed: <path> <kind>: …` in `pin_check.mismatches`.
- **R-13, dataset gate**: DG-9 is checked before DG-4, so a wrong or missing ground-truth
  `value_in_cr` is reported as DG-9 even when the schema also rejects it. DG-3 checks an injection
  case's own status class; equality with the counterpart is DG-5.
- **R-13, counting**: `service_failures.model.retried_attempts` counts the failed attempts of
  cases that were resolved by a later attempt. A case with no candidate has one layer-2 entry
  `INV-1: no candidate`; its `application_failures.checks` list the agent codes (e.g. `EXC`).
- **R-15**: two runs started in the same second get distinct folders (`<stamp>`, `<stamp>-2`).
- **CLI**: `cli.main` also takes a keyword-only `sleep` (default `time.sleep`), so tests do not
  wait through the backoff.
