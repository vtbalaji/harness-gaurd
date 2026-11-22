#!/usr/bin/env bash
# Order extraction agent: harness, then evaluation (contracts/harness.md, research.md R-14).
# The evaluation runs only when every deterministic gate passes (constitution: gates must pass
# before an evaluation result is reported). Arguments (e.g. --env-file PATH) go to run_eval.py.
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.." || exit 1

harness_out="$(.harness/run_harness.sh)"
harness_code=$?
echo "${harness_out}"
harness_line="$(printf '%s\n' "${harness_out}" | tail -n 1)"

if [ "${harness_code}" -ne 0 ]; then
  echo "Harness FAILED; evaluation not run (constitution: gates must pass before an evaluation result is reported)"
  echo "Harness: ${harness_line} | Evaluation: not run"
  exit 1
fi

eval_out="$(.venv/bin/python .harness/run_eval.py "$@")"
eval_code=$?
echo "${eval_out}"
eval_line="$(printf '%s\n' "${eval_out}" | tail -n 1)"
echo "Harness: ${harness_line} | Evaluation: ${eval_line}"
exit "${eval_code}"
