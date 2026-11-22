"""Harness scripts `.harness/run_harness.sh` and `.harness/run_all.sh` (contracts/harness.md;
research.md R-14). Each test copies the script into a tmp tree with stub tools in
`.venv/bin/`; the real tools, Ollama and the network are never used."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from conftest import PROJECT_ROOT

STEP_LOGS = [
    "1a-ruff-check.log",
    "1b-ruff-format.log",
    "2-bandit.log",
    "2b-nosec-scan.log",
    "3-pytest.log",
    "3a-cov-src.log",
    "3b-cov-run-eval.log",
]

STUB = """#!/usr/bin/env bash
echo "{name} $*" >> "$STUB_LOG"
{body}
"""

STUB_BODIES = {
    "ruff": (
        'if [ "$1" = "check" ]; then exit "${RUFF_CHECK_RC:-0}"; fi\nexit "${RUFF_FORMAT_RC:-0}"'
    ),
    "bandit": 'exit "${BANDIT_RC:-0}"',
    "pytest": 'exit "${PYTEST_RC:-0}"',
    "coverage": (
        'for a in "$@"; do\n'
        '  if [ "$a" = "--include=.harness/run_eval.py" ]; then exit "${COV_EVAL_RC:-0}"; fi\n'
        "done\n"
        'exit "${COV_SRC_RC:-0}"'
    ),
    "python": (
        'if [ "$1" = ".harness/run_eval.py" ]; then\n'
        '  echo "Verdict: FAKE"; exit "${EVAL_RC:-0}"\n'
        "fi\n"
        'echo "Python 3.14.7"'
    ),
    "pip": "exit 0",
}


def _executable(path: Path, text: str):
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)


def _tree(tmp_path, script, *, fake_harness_rc=None):
    root = tmp_path / "Part-1B"
    (root / ".harness").mkdir(parents=True)
    (root / "src" / "order_agent").mkdir(parents=True)
    (root / "src" / "order_agent" / "__init__.py").write_text('"""clean"""\n', encoding="utf-8")
    (root / ".harness" / "run_eval.py").write_text('"""fake runner"""\n', encoding="utf-8")
    bin_dir = root / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    for name, body in STUB_BODIES.items():
        _executable(bin_dir / name, STUB.format(name=name, body=body))
    shutil.copy2(PROJECT_ROOT / ".harness" / script, root / ".harness" / script)
    if fake_harness_rc is not None:
        _executable(
            root / ".harness" / "run_harness.sh",
            "#!/usr/bin/env bash\n"
            'echo "fake harness"\n'
            f'echo "Evidence: evidence/harness-results/FAKE OVERALL: X"\nexit {fake_harness_rc}\n',
        )
    return root


def _run(root, script, *args, **rcs):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(root),
        "STUB_LOG": str(root / "stub.log"),
        "GIT_CEILING_DIRECTORIES": str(root.parent),
        **{k: str(v) for k, v in rcs.items()},
    }
    # Fixed argv, no shell, and only the local stub tree: nothing here can reach the network.
    proc = subprocess.run(
        ["bash", str(root / ".harness" / script), *args],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    log = (root / "stub.log").read_text(encoding="utf-8") if (root / "stub.log").exists() else ""
    return proc, log


def _evidence_dir(root, proc):
    last = proc.stdout.strip().splitlines()[-1]
    assert last.startswith("Evidence: ")
    rel = last.split()[1]
    return root / rel, last


def test_harness_runs_every_step_without_fail_fast(tmp_path):
    """contracts/harness.md, R-14: with 1a and 3 failing every step still runs; nine evidence
    files exist; summary.md shows the table, the gates and OVERALL: FAIL; exit 1."""
    root = _tree(tmp_path, "run_harness.sh")
    proc, log = _run(root, "run_harness.sh", RUFF_CHECK_RC=1, PYTEST_RC=1)
    assert proc.returncode == 1
    evidence, last = _evidence_dir(root, proc)
    assert last.endswith("OVERALL: FAIL")
    assert sorted(p.name for p in evidence.iterdir()) == sorted(
        [*STEP_LOGS, "environment.txt", "summary.md"]
    )
    for tool in ("ruff check .", "ruff format --check .", "bandit", "pytest", "coverage"):
        assert tool in log
    summary = (evidence / "summary.md").read_text(encoding="utf-8")
    assert "| Step id | Command | Exit code | Result |" in summary
    assert "| 1a-ruff-check |" in summary and "| 3b-cov-run-eval |" in summary
    assert "Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): FAIL" in summary
    assert "Gate 2 (security: 2-bandit AND 2b-nosec-scan): PASS" in summary
    assert "Gate 3" in summary and summary.rstrip().endswith("OVERALL: FAIL")
    environment = (evidence / "environment.txt").read_text(encoding="utf-8")
    assert "Python 3.14.7" in environment and "no commit" in environment


def test_harness_bandit_and_coverage_commands(tmp_path):
    """R-14 (rev 2, G2): bandit scans `src .harness -ll`; pytest covers both sources; the two
    coverage gates use their own --include."""
    root = _tree(tmp_path, "run_harness.sh")
    proc, log = _run(root, "run_harness.sh")
    assert proc.returncode == 0
    assert "bandit -r src .harness -ll" in log
    assert "pytest --cov=order_agent --cov=.harness --cov-branch --cov-report=term-missing" in log
    assert "coverage report --include=src/order_agent/* --fail-under=90" in log
    assert "coverage report --include=.harness/run_eval.py --fail-under=90" in log


@pytest.mark.parametrize("where", ["src/order_agent/bad.py", ".harness/run_eval.py"])
def test_harness_nosec_comment_fails_gate_2(tmp_path, where):
    """R-14, G2: a `# nosec` line in src/ or .harness/*.py fails gate 2 via 2b-nosec-scan."""
    root = _tree(tmp_path, "run_harness.sh")
    (root / where).write_text("x = 1  # nosec\n", encoding="utf-8")
    proc, _log = _run(root, "run_harness.sh")
    assert proc.returncode == 1
    evidence, _ = _evidence_dir(root, proc)
    summary = (evidence / "summary.md").read_text(encoding="utf-8")
    assert "| 2b-nosec-scan |" in summary
    assert "Gate 2 (security: 2-bandit AND 2b-nosec-scan): FAIL" in summary
    assert "Gate 1 (lint: 1a-ruff-check AND 1b-ruff-format): PASS" in summary


def test_harness_script_own_nosec_word_does_not_fail(tmp_path):
    """R-14: the word inside run_harness.sh itself does not trip the scan (--include=*.py)."""
    root = _tree(tmp_path, "run_harness.sh")
    assert "nosec" in (root / ".harness" / "run_harness.sh").read_text(encoding="utf-8")
    proc, _log = _run(root, "run_harness.sh")
    evidence, _ = _evidence_dir(root, proc)
    assert "no suppression comments found" in (evidence / "2b-nosec-scan.log").read_text(
        encoding="utf-8"
    )


def test_harness_run_eval_coverage_gate_fails_gate_3_alone(tmp_path):
    """R-14 (rev 2, G2): coverage below 90% only for run_eval.py fails gate 3 through 3b."""
    root = _tree(tmp_path, "run_harness.sh")
    proc, _log = _run(root, "run_harness.sh", COV_EVAL_RC=2)
    assert proc.returncode == 1
    evidence, last = _evidence_dir(root, proc)
    assert last.endswith("OVERALL: FAIL")
    summary = (evidence / "summary.md").read_text(encoding="utf-8")
    rows = {line.split("|")[1].strip(): line for line in summary.splitlines() if "| 3" in line}
    assert rows["3-pytest"].endswith("| 0 | PASS |")
    assert rows["3a-cov-src"].endswith("| 0 | PASS |")
    assert "--include=.harness/run_eval.py --fail-under=90" in rows["3b-cov-run-eval"]
    assert rows["3b-cov-run-eval"].endswith("| 2 | FAIL |")
    assert "3b-cov-run-eval >= 90%): FAIL" in summary


def test_harness_all_passing_exits_0(tmp_path):
    """contracts/harness.md: every stub passing and no nosec gives exit 0 and OVERALL: PASS."""
    root = _tree(tmp_path, "run_harness.sh")
    proc, _log = _run(root, "run_harness.sh")
    assert proc.returncode == 0
    evidence, last = _evidence_dir(root, proc)
    assert last == f"Evidence: {evidence.relative_to(root)} OVERALL: PASS"
    assert evidence.parent == root / "evidence" / "harness-results"


def test_run_all_failing_harness_skips_evaluation(tmp_path):
    """contracts/harness.md: a failing harness gives exit 1, the exact message, and no eval."""
    root = _tree(tmp_path, "run_all.sh", fake_harness_rc=1)
    proc, log = _run(root, "run_all.sh")
    assert proc.returncode == 1
    assert (
        "Harness FAILED; evaluation not run (constitution: gates must pass before an evaluation "
        "result is reported)" in proc.stdout
    )
    assert ".harness/run_eval.py" not in log


@pytest.mark.parametrize("code", [0, 1, 2, 3])
def test_run_all_passing_harness_returns_eval_exit_code(tmp_path, code):
    """contracts/harness.md: with a passing harness the exit code equals run_eval.py's and
    `--env-file X` is passed through; the last line names both evidence folders."""
    root = _tree(tmp_path, "run_all.sh", fake_harness_rc=0)
    proc, log = _run(root, "run_all.sh", "--env-file", "X", EVAL_RC=code)
    assert proc.returncode == code
    assert "python .harness/run_eval.py --env-file X" in log
    last = proc.stdout.strip().splitlines()[-1]
    assert "evidence/harness-results/FAKE" in last and "Verdict: FAKE" in last
