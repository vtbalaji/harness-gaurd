"""FR-072: the command-line entry point, every row of contracts/cli.md (research.md R-13)."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from gis_scorer import cli, score_snapshot

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "snapshots"


def run_cli(*args):
    """Run `python -m gis_scorer` in a fresh interpreter (no shell; fixed argument list)."""
    return subprocess.run(
        [sys.executable, "-m", "gis_scorer", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def fixture(name):
    return FIXTURES / name


# --- subprocess: the real command ---------------------------------------------------------------


@pytest.mark.parametrize("name", ["full_max.json", "sparse.json", "empty.json"])
def test_fr072_valid_snapshot_prints_result_and_exits_0(name):
    """FR-072: a valid snapshot -> exit 0, the result JSON on stdout with a newline, no stderr."""
    proc = run_cli(fixture(name))
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert proc.stdout.endswith("}\n")
    expected = score_snapshot(json.loads(fixture(name).read_text(encoding="utf-8"))).to_json()
    assert proc.stdout == expected


def test_fr072_validation_errors_listed_in_r05_order():
    """FR-072, FR-002: an invalid snapshot -> exit 1 and one indented line per error."""
    proc = run_cli(fixture("multi_error.json"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr == (
        "gis_scorer: invalid snapshot\n"
        "  zzz: unknown field\n"
        "  piotroski: must be an integer from 0 to 9\n"
        "  current_ratio: must be >= 0\n"
    )


def test_fr072_malformed_json_exits_1():
    """FR-072: malformed JSON -> exit 1, 'gis_scorer: invalid JSON: ...'."""
    proc = run_cli(fixture("malformed.json"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr.startswith("gis_scorer: invalid JSON: ")


def test_fr072_duplicate_key_exits_1():
    """FR-072: a duplicate key -> exit 1, 'gis_scorer: invalid JSON: duplicate key 'roe''."""
    proc = run_cli(fixture("duplicate_key.json"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr == "gis_scorer: invalid JSON: duplicate key 'roe'\n"


def test_fr072_top_level_array_exits_1():
    """FR-072, FR-002: a top level that is not an object -> exit 1, named <snapshot>."""
    proc = run_cli(fixture("top_level_array.json"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr == (
        "gis_scorer: invalid snapshot\n  <snapshot>: must be an object with string keys\n"
    )


def test_fr072_nan_token_is_rejected_by_the_validator():
    """FR-072, FR-002: a NaN token parses, then the validator names the field."""
    proc = run_cli(fixture("nan_value.json"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert proc.stderr == "gis_scorer: invalid snapshot\n  roe: must be finite\n"


def test_fr072_missing_file_exits_2(tmp_path):
    """FR-072: a file that does not exist -> exit 2, 'gis_scorer: cannot read <path>: ...'."""
    path = tmp_path / "absent.json"
    proc = run_cli(path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith(f"gis_scorer: cannot read {path}: ")


def test_fr072_non_utf8_file_exits_2(tmp_path):
    """FR-072: a file that is not UTF-8 -> exit 2, 'gis_scorer: cannot read <path>: ...'."""
    path = tmp_path / "latin1.json"
    path.write_bytes(b'{"roe": "\xff"}')
    proc = run_cli(path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith(f"gis_scorer: cannot read {path}: ")


@pytest.mark.parametrize(
    "args",
    [pytest.param((), id="fr072_no_argument"), pytest.param(("a", "b"), id="fr072_two_arguments")],
)
def test_fr072_wrong_number_of_arguments_exits_2(args):
    """FR-072: a usage error -> exit 2 with argparse's usage message and empty stdout."""
    proc = run_cli(*args)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "usage:" in proc.stderr


def test_fr072_console_script_matches_module_invocation():
    """FR-072: the installed gis-scorer console script prints the same bytes as -m."""
    script = Path(sys.executable).parent / "gis-scorer"
    assert script.exists()
    path = str(fixture("full_max.json"))
    via_script = subprocess.run([str(script), path], capture_output=True, text=True, check=False)
    via_module = run_cli(path)
    assert via_script.returncode == via_module.returncode == 0
    assert via_script.stdout == via_module.stdout


# --- in-process: the same contract through cli.main() (measured by coverage) -------------------


def test_fr072_main_success_returns_0(capsys):
    """FR-072: cli.main([path]) prints the result JSON and returns 0."""
    assert cli.main([str(fixture("full_max.json"))]) == 0
    out, err = capsys.readouterr()
    assert json.loads(out)["total"] == 100
    assert err == ""


@pytest.mark.parametrize(
    ("name", "stderr_start"),
    [
        pytest.param("multi_error.json", "gis_scorer: invalid snapshot\n", id="fr072_invalid"),
        pytest.param("malformed.json", "gis_scorer: invalid JSON: ", id="fr072_malformed"),
        pytest.param(
            "duplicate_key.json",
            "gis_scorer: invalid JSON: duplicate key 'roe'",
            id="fr072_duplicate",
        ),
    ],
)
def test_fr072_main_bad_data_returns_1(capsys, name, stderr_start):
    """FR-072: bad data -> cli.main returns 1, prints nothing on stdout."""
    assert cli.main([str(fixture(name))]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith(stderr_start)


def test_fr072_main_unreadable_file_returns_2(capsys, tmp_path):
    """FR-072: an unreadable path -> cli.main returns 2 with 'cannot read'."""
    path = tmp_path / "absent.json"
    assert cli.main([str(path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith(f"gis_scorer: cannot read {path}: ")


def test_fr072_main_non_utf8_file_returns_2(capsys, tmp_path):
    """FR-072: a file that is not UTF-8 -> cli.main returns 2 with 'cannot read'."""
    path = tmp_path / "latin1.json"
    path.write_bytes(b'{"roe": "\xff"}')
    assert cli.main([str(path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith(f"gis_scorer: cannot read {path}: ")
    assert "utf-8" in err


def test_fr072_main_usage_error_exits_2(capsys):
    """FR-072: a usage error exits 2 through argparse."""
    with pytest.raises(SystemExit) as info:
        cli.main([])
    assert info.value.code == 2
    assert capsys.readouterr().out == ""


def test_fr072_python_dash_m_entry_point(monkeypatch, capsys):
    """FR-072: `python -m gis_scorer` runs cli.main and exits with its return code."""
    monkeypatch.setattr(sys, "argv", ["gis_scorer", str(fixture("invalid_piotroski.json"))])
    with pytest.raises(SystemExit) as info:
        runpy.run_module("gis_scorer", run_name="__main__")
    assert info.value.code == 1
    assert "piotroski: must be an integer from 0 to 9" in capsys.readouterr().err
