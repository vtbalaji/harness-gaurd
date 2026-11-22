"""User Story 6 - Run it from the command line (US6-AS1, US6-AS2)."""

import json
import subprocess
import sys
from pathlib import Path

from gis_scorer import score_snapshot

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "snapshots"


def _run(path):
    return subprocess.run(
        [sys.executable, "-m", "gis_scorer", str(path)],
        capture_output=True,
        check=False,
    )


def test_us6_as1_valid_file_prints_the_library_result():
    """US6-AS1: a valid file -> exit 0 and stdout byte-identical to the library (FR-071/072)."""
    path = FIXTURES / "full_max.json"
    proc = _run(path)
    assert proc.returncode == 0
    expected = score_snapshot(json.loads(path.read_text(encoding="utf-8"))).to_json()
    assert proc.stdout == expected.encode("utf-8")


def test_us6_as2_invalid_file_prints_the_error_and_fails():
    """US6-AS2: an invalid file -> exit 1, empty stdout, the field error on stderr (FR-002/072)."""
    proc = _run(FIXTURES / "invalid_piotroski.json")
    assert proc.returncode == 1
    assert proc.stdout == b""
    assert "piotroski: must be an integer from 0 to 9" in proc.stderr.decode("utf-8")
