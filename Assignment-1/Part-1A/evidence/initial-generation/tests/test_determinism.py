"""FR-003, FR-071, SC-003: deterministic, pure scoring (research.md R-11)."""

import ast
import copy
import os
import subprocess
import sys
from pathlib import Path

from gis_scorer import score_snapshot

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "gis_scorer"
FULL_MAX = Path(__file__).resolve().parent / "fixtures" / "snapshots" / "full_max.json"
LIBRARY_MODULES = ("__init__", "result", "snapshot", "rules", "scoring", "valuation")
FORBIDDEN_IMPORTS = {
    "time",
    "datetime",
    "random",
    "os",
    "pathlib",
    "socket",
    "uuid",
    "sys",
    "importlib",
}
FORBIDDEN_CALLS = {"open", "__import__"}


def test_fr003_sc003_1000_runs_give_one_result(max_snapshot):
    """FR-003, FR-071, SC-003: scoring the same snapshot 1,000 times gives identical results."""
    raw = max_snapshot()
    results = [score_snapshot(raw) for _ in range(1000)]
    assert len({r.to_json() for r in results}) == 1
    assert all(r == results[0] for r in results)


def test_fr003_input_mapping_is_not_mutated(max_snapshot):
    """FR-003 (library-api.md L3): scoring does not change the caller's mapping."""
    raw = max_snapshot()
    before = copy.deepcopy(raw)
    score_snapshot(raw)
    assert raw == before


def _imported_top_level_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module.split(".")[0]


def _called_builtin_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            yield node.func.id


def test_fr003_library_modules_use_no_clock_env_files_or_randomness():
    """FR-003, SC-003: library modules import no time/os/random/... and never call open()."""
    for module in LIBRARY_MODULES:
        path = SRC_DIR / f"{module}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = set(_imported_top_level_modules(tree))
        assert imported.isdisjoint(FORBIDDEN_IMPORTS), (module, imported & FORBIDDEN_IMPORTS)
        called = set(_called_builtin_names(tree))
        assert called.isdisjoint(FORBIDDEN_CALLS), (module, called & FORBIDDEN_CALLS)


def _cli_stdout(hash_seed):
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    proc = subprocess.run(
        [sys.executable, "-m", "gis_scorer", str(FULL_MAX)],
        capture_output=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0
    return proc.stdout


def test_fr003_sc003_cli_output_independent_of_hash_seed():
    """FR-003, FR-071, SC-003 (R-11 b): PYTHONHASHSEED 0 and 12345 give identical CLI bytes."""
    assert _cli_stdout("0") == _cli_stdout("12345")
