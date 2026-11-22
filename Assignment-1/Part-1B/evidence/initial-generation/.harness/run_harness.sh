#!/usr/bin/env bash
# Order extraction agent: deterministic-code harness (contracts/harness.md, research.md R-14).
# Same shape as Part 1A's script, with: coverage over order_agent and .harness, the added step
# 2b-nosec-scan, .harness in the bandit scan, and the two coverage gates 3a/3b (rev 2, G2).
# Runs every step (no fail-fast), keeps per-step logs and a summary as evidence, and exits 0
# only when every gate passes.
set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.." || exit 1

VENV_BIN=".venv/bin"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="evidence/harness-results/${STAMP}"
mkdir -p "${EVIDENCE_DIR}"

STEP_IDS=()
STEP_CMDS=()
STEP_CODES=()

# run_step <step-id> <command> [args...]
# Runs the command, writes combined stdout+stderr to <step-id>.log, records the exit code.
run_step() {
  local step_id="$1"
  shift
  local log_file="${EVIDENCE_DIR}/${step_id}.log"
  echo "==> ${step_id}: $*"
  "$@" >"${log_file}" 2>&1
  local code=$?
  STEP_IDS+=("${step_id}")
  STEP_CMDS+=("$*")
  STEP_CODES+=("${code}")
  echo "    exit ${code}"
}

# scan_python_suppressions: passes (exit 0) only when grep finds no suppression comment in
# any Python file under src/ or .harness/ (grep exit 1 = nothing found).
scan_python_suppressions() {
  grep -rn --include="*.py" "nosec" src .harness
  local code=$?
  if [ "${code}" -eq 1 ]; then
    echo "no suppression comments found"
    return 0
  fi
  if [ "${code}" -eq 0 ]; then
    echo "suppression comments found (not allowed)"
  fi
  return 1
}

run_step "1a-ruff-check" "${VENV_BIN}/ruff" check .
run_step "1b-ruff-format" "${VENV_BIN}/ruff" format --check .
run_step "2-bandit" "${VENV_BIN}/bandit" -r src .harness -ll
run_step "2b-nosec-scan" scan_python_suppressions
run_step "3-pytest" "${VENV_BIN}/pytest" --cov=order_agent --cov=.harness --cov-branch \
  --cov-report=term-missing
run_step "3a-cov-src" "${VENV_BIN}/coverage" report --include="src/order_agent/*" --fail-under=90
run_step "3b-cov-run-eval" "${VENV_BIN}/coverage" report --include=".harness/run_eval.py" \
  --fail-under=90

{
  echo "## python --version"
  "${VENV_BIN}/python" --version 2>&1
  echo
  echo "## pip freeze"
  "${VENV_BIN}/python" -m pip freeze 2>&1
  echo
  echo "## git rev-parse HEAD"
  git rev-parse HEAD 2>/dev/null || echo "no commit"
} >"${EVIDENCE_DIR}/environment.txt"

result_of() {
  if [ "$1" -eq 0 ]; then echo "PASS"; else echo "FAIL"; fi
}

all_pass() {
  local c
  for c in "$@"; do
    if [ "${c}" -ne 0 ]; then
      echo "FAIL"
      return
    fi
  done
  echo "PASS"
}

gate1="$(all_pass "${STEP_CODES[0]}" "${STEP_CODES[1]}")"
gate2="$(all_pass "${STEP_CODES[2]}" "${STEP_CODES[3]}")"
gate3="$(all_pass "${STEP_CODES[4]}" "${STEP_CODES[5]}" "${STEP_CODES[6]}")"

if [ "${gate1}" = "PASS" ] && [ "${gate2}" = "PASS" ] && [ "${gate3}" = "PASS" ]; then
  overall="PASS"
else
  overall="FAIL"
fi

{
  echo "# Harness summary (${STAMP})"
  echo
  echo "| Step id | Command | Exit code | Result |"
  echo "|---|---|---|---|"
  for i in "${!STEP_IDS[@]}"; do
    echo "| ${STEP_IDS[$i]} | \`${STEP_CMDS[$i]}\` | ${STEP_CODES[$i]} | $(result_of "${STEP_CODES[$i]}") |"
  done
  echo
  echo "## Gates"
  echo
  echo "- Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): ${gate1}"
  echo "- Gate 2 (security: 2-bandit AND 2b-nosec-scan): ${gate2}"
  echo "- Gate 3 (tests and coverage: 3-pytest AND 3a-cov-src >= 90% AND 3b-cov-run-eval >= 90%): ${gate3}"
  echo
  echo "OVERALL: ${overall}"
} >"${EVIDENCE_DIR}/summary.md"

echo "Evidence: ${EVIDENCE_DIR} OVERALL: ${overall}"
if [ "${overall}" = "PASS" ]; then
  exit 0
fi
exit 1
