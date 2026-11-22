#!/usr/bin/env bash
# GIS Scorer test harness (contracts/harness.md, research.md R-10).
# Runs every gate (no fail-fast), keeps per-step logs and a summary as evidence,
# and exits 0 only when all gates pass.
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

run_step "1a-ruff-check" "${VENV_BIN}/ruff" check .
run_step "1b-ruff-format" "${VENV_BIN}/ruff" format --check .
run_step "2-bandit" "${VENV_BIN}/bandit" -r src -ll
run_step "3-pytest" "${VENV_BIN}/pytest" --cov=gis_scorer --cov-branch \
  --cov-report=term-missing --cov-fail-under=90

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

if [ "${STEP_CODES[0]}" -eq 0 ] && [ "${STEP_CODES[1]}" -eq 0 ]; then
  gate1="PASS"
else
  gate1="FAIL"
fi
gate2="$(result_of "${STEP_CODES[2]}")"
gate3="$(result_of "${STEP_CODES[3]}")"

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
  echo "- Gate 2 (security: 2-bandit): ${gate2}"
  echo "- Gate 3 (tests and coverage >= 90%: 3-pytest): ${gate3}"
  echo
  echo "OVERALL: ${overall}"
} >"${EVIDENCE_DIR}/summary.md"

echo "Evidence: ${EVIDENCE_DIR} OVERALL: ${overall}"
if [ "${overall}" = "PASS" ]; then
  exit 0
fi
exit 1
