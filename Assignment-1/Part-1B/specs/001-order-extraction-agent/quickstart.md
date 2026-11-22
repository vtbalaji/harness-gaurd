# Quickstart and validation guide: Order Extraction Agent

**Contracts**: [cli](./contracts/cli.md) · [output schema](./contracts/output.schema.json) · [eval results](./contracts/eval-results.md) · [harness](./contracts/harness.md) | **Data model**: [data-model.md](./data-model.md)

Run every command from `Assignment-1/Part-1B/`.

## 0. Prerequisites

| Need | Check | Expected |
|---|---|---|
| Python venv | `.venv/bin/python --version` | `Python 3.14.7` (any version ≥ 3.12 is supported) |
| Ollama | `curl -s http://localhost:11434/api/version` | `{"version":"0.32.14"}` |
| Model under test | `ollama list \| grep qwen3.5:4b` | ID column starts with `d8b0f5e9760c` |
| Judge, needed only for a complete eval report | `curl -s http://127.0.0.1:8081/v1/models` | lists `qwen3.6-35b-a3b` |

## 1. Setup

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
cp .env.example .env          # edit only if your endpoints differ; .env is git-ignored
git check-ignore .env         # must print ".env"
```

## 2. Deterministic gates (no model needed)

```bash
.harness/run_harness.sh
```

Expected result: the last line is `Evidence: evidence/harness-results/<stamp> OVERALL: PASS`, and
`summary.md` shows:

- gate 1: ruff check and ruff format, both pass;
- gate 2: bandit with zero medium or high findings, and no `nosec`;
- gate 3: pytest all green with coverage ≥ 90%.

Stopping Ollama must not change this result, because no test uses the network.

## 3. Single-announcement smoke checks (CLI)

```bash
S=$(mktemp -d)
cat > "$S/n01.txt" <<'EOF'
To, BSE Limited / National Stock Exchange of India Limited
Date: November 20, 2026
Sub: Receipt of order
Example Transformers Limited has received an order worth ₹1,250.50 crore from NTPC Limited for
supply of transformers, to be executed within 18 months.
For Example Transformers Limited, Company Secretary
EOF
.venv/bin/python -m order_agent "$S/n01.txt"; echo "exit=$?"
```

Expected (AC-1.1, AC-1.5):

- exit is 0;
- `status` is `extracted`;
- `order_value` is 1250.5, `INR`, `crore`;
- client is `NTPC Limited` and `order_type` is `supply`;
- `execution_period` is `within 18 months`;
- `missing_fields` is `[]`;
- every evidence quote can be found in the file;
- neither exchange appears as the company or the client.

Guard checks. Each needs no running model:

```bash
printf '' | .venv/bin/python -m order_agent -           # → rejected / empty           (AC-3.1)
printf ' \n\t ' | .venv/bin/python -m order_agent -     # → rejected / whitespace_only (AC-3.2)
.venv/bin/python -c "print('a'*20001, end='')" | .venv/bin/python -m order_agent -   # → too_long (AC-3.3)
printf '\xff\xfe\x00garbage' | .venv/bin/python -m order_agent -   # → rejected / garbled (AC-3.4)
```

Each prints a `rejected` object and exits 0. Running them with Ollama stopped proves that the
guards make no model call.

Failure-path checks:

- With Ollama stopped, run the `n01.txt` command again. Expect exit 3 and a `service_failure` JSON
  on stderr listing 3 attempts of kind `unreachable` (FR-023).
- Set `AGENT_MODEL=qwen3.5:9b` in the environment, then run any command. Expect a pin warning on
  stderr (R-10).

## 4. Evaluation

```bash
.venv/bin/python .harness/run_eval.py; echo "exit=$?"
```

Expected:

- exit 0, 1 or 2 for PASS, FAIL or INCONCLUSIVE;
- the last line gives the verdict, the three layer scores and the run folder;
- `evidence/eval-results.json` is updated and matches
  [contracts/eval-results.md](./contracts/eval-results.md).

Check these in the run folder `evidence/eval-runs/<stamp>/`:

| Check | Where | Expected |
|---|---|---|
| All cases ran, none skipped | `eval-results.json › dataset.case_count` = number of `cases/*.json` | ≥ 18 (27 planned) |
| Pins recorded and checked | `environment.json`, `run.json › pin_check` | Ollama 0.32.14, digest starts `d8b0f5e9760c`, Q4_K_M, `ok: true` |
| Settings recorded | `run.json › settings` and each `raw/*/attempt-*.json` | temperature 0.1, seed 42, num_predict 700, think false, format json, timeout 300, the `num_ctx` value per request |
| Rejected cases made no model call | `cases/X01…X04.json` | `model_called: false`, no `raw/X0n/` folder |
| Failures have feedback | `feedback/` | one file for every case that is not passing |
| Service vs application vs judge failures separated | `eval-results.json` | `application_failures`, `service_failures.model`, `service_failures.judge` |
| Judge is informational | `summary.md` section 5 | ratings shown; the verdict rule does not mention the judge |

Degraded-run checks, which prove the verdict rules (AC-5.3, AC-5.4, AC-5.6):

- Stop the judge server and rerun. The verdict is the same as with the judge running, and the judge
  failures are listed separately.
- Stop Ollama and rerun. The verdict is INCONCLUSIVE (the pin check cannot be confirmed, and there
  are unresolved service failures), with exit 2. The guard cases X01–X04 still pass layers 1 and 2.

## 5. Everything in one go

```bash
.harness/run_all.sh; echo "exit=$?"
```

Expected: the harness runs first. If it fails, the evaluation is not run and the exit is 1.
Otherwise the exit equals `run_eval.py`'s code, and only PASS gives 0.

## 6. If the verdict is FAIL

Follow FR-033 and constitution Principle VII:

1. Read `feedback/<case>.json`.
2. Change only the prompt, parser, validators or guards.
3. Log the cycle in `evidence/repair-log.md`.
4. Rerun the **same** evaluation.

Do not edit thresholds, cases or ground truth. If the 4B model still fails after reasonable
repairs, stop and report the failure with the evidence. ACCEPT/REJECT is Balaji's decision.
