"""Command-line entry point (FR-072; contracts/cli.md, research.md R-13).

`python -m gis_scorer <snapshot.json>` or `gis-scorer <snapshot.json>`.
Exit 0: result JSON on stdout. Exit 1: invalid JSON or snapshot. Exit 2: unreadable file or
usage error. Nothing is written to stdout when the exit code is non-zero.
"""

import argparse
import json
import sys
from pathlib import Path

from gis_scorer.scoring import score_snapshot
from gis_scorer.snapshot import SnapshotValidationError

PROG = "gis_scorer"
EXIT_OK = 0
EXIT_BAD_DATA = 1
EXIT_CANNOT_READ = 2


class DuplicateKeyError(ValueError):
    """A JSON object repeats a key; taking either value would be guessing."""

    def __init__(self, key):
        super().__init__(f"duplicate key {key!r}")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _parser():
    parser = argparse.ArgumentParser(
        prog=PROG, description="Score one company snapshot (JSON file) with the GIS method."
    )
    parser.add_argument("snapshot", help="path to a UTF-8 JSON file whose top level is an object")
    return parser


def _error(message):
    sys.stderr.write(f"{PROG}: {message}\n")


def main(argv=None):
    """Run the CLI and return its exit code (argparse exits 2 itself on a usage error)."""
    args = _parser().parse_args(argv)
    path = args.snapshot
    try:
        text = Path(path).read_bytes().decode("utf-8")
    except OSError as exc:
        _error(f"cannot read {path}: {exc.strerror or exc}")
        return EXIT_CANNOT_READ
    except UnicodeDecodeError as exc:
        _error(f"cannot read {path}: {exc}")
        return EXIT_CANNOT_READ
    try:
        raw = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, DuplicateKeyError) as exc:
        _error(f"invalid JSON: {exc}")
        return EXIT_BAD_DATA
    try:
        result = score_snapshot(raw)
    except SnapshotValidationError as exc:
        lines = "".join(f"  {e.field}: {e.message}\n" for e in exc.errors)
        sys.stderr.write(f"{PROG}: invalid snapshot\n{lines}")
        return EXIT_BAD_DATA
    sys.stdout.write(result.to_json())
    return EXIT_OK
