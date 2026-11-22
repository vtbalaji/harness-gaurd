# Contract: command-line interface (`python -m order_agent`)

**Design**: [../research.md](../research.md) R-3, R-7, R-9, R-10 | **Output contract**: [output.schema.json](./output.schema.json)

## Invocation

```text
python -m order_agent <announcement.txt> [--env-file PATH]
```

| Argument | Required | Meaning |
|---|---|---|
| `<announcement.txt>` | yes | Path to one announcement, read as **raw bytes** so the guards see the input exactly as received (FR-017). `-` reads bytes from stdin. |
| `--env-file PATH` | no | `.env` file to load. The default is `./.env` if it exists. Process environment variables override file values. If a required key is missing from both, exit 78. |

There are no options to change the model, the generation settings or the guard limits. Those are
pinned in code (FR-020, R-10).

## Behaviour

1. Load settings and check URL schemes. On error, write a message to stderr and exit 78.
2. Read the input bytes. If the file is unreadable or missing, exit 64.
3. Run `agent.run(raw_bytes, settings)`. The pipeline is in
   [../data-model.md](../data-model.md#pipeline-states). Guards run first. A rejected input never
   reaches the model.
4. If `AGENT_MODEL`/`AGENT_MODEL_DIGEST` differ from the pins, write one warning line to stderr
   and continue. The evaluation treats a mismatch as INCONCLUSIVE; the CLI does not.

## Output and exit codes

| Exit | Situation | stdout | stderr |
|---|---|---|---|
| 0 | Success. Any `status`, including `rejected`. | the schema-1.0 object (UTF-8 JSON, 2-space indent, `ensure_ascii=False`, trailing newline) | nothing, or the pin warning |
| 2 | Application failure. The model output was not parseable, broke `mr-1` or MR consistency, or failed post-validation (R-7). No result is emitted (FR-019). | nothing | failure report JSON: `{"error": "application_failure", "stage", "errors": [{code, pointer, message, layer}], "raw_model_output", "parser_log", "candidate"}` |
| 3 | Service failure after 3 attempts (FR-023) | nothing | `{"error": "service_failure", "attempts": [{n, kind, http_status, elapsed_s, message}]}` |
| 64 | Usage error or unreadable input file | nothing | usage text or message |
| 78 | Configuration error (missing key, bad URL scheme) | nothing | message naming the key |

stdout carries nothing except a conforming result. A consumer can rely on this: if the exit code is
0, stdout is valid schema 1.0.

## Examples

```text
$ python -m order_agent /path/to/n01.txt               # AC-1.1 text, see quickstart.md
{
  "schema_version": "1.0",
  "status": "extracted",
  "company": "Example Transformers Limited",
  "announcement_date": "2026-11-20",
  "order": {"order_value": 1250.5, "currency": "INR", "unit": "crore",
            "client": "NTPC Limited", "order_type": "supply",
            "execution_period": "within 18 months"},
  "additional_orders": [],
  "evidence": {"company": "...", "announcement_date": "...", "order_value": "₹1,250.50 crore",
               "currency": "₹1,250.50 crore", "unit": "₹1,250.50 crore",
               "client": "NTPC Limited", "order_type": "supply of transformers",
               "execution_period": "within 18 months"},
  "missing_fields": [],
  "rejection_reason": null
}
$ echo $?
0

$ printf '' | python -m order_agent -                   # AC-3.1, no model call
{"schema_version": "1.0", "status": "rejected", "company": null, "announcement_date": null,
 "order": null, "additional_orders": [], "evidence": {}, "missing_fields": [],
 "rejection_reason": "empty"}
```

(The examples are shown compacted. Real output is indented as described above.)

## Library entry point (used by the CLI and by `.harness/run_eval.py`)

`order_agent.agent.run(raw: bytes, settings: Settings, *, transport=None) -> AgentOutcome`. The
`AgentOutcome` variants are described in [../data-model.md](../data-model.md#agentoutcome-agentrun).
`transport` is injectable so tests never open a socket (R-9, R-14).
