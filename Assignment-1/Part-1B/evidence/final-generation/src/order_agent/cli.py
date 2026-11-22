"""Command-line interface: `python -m order_agent <announcement.txt | -> [--env-file PATH]`.

contracts/cli.md. stdout carries nothing but a conforming schema-1.0 result: exit 0 means stdout
is valid schema 1.0. Failures go to stderr as JSON reports.

Exit codes: 0 success (any status, including rejected), 2 application failure, 3 service failure,
64 usage error or unreadable input, 78 configuration error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import agent, config

EXIT_OK = 0
EXIT_APPLICATION_FAILURE = 2
EXIT_SERVICE_FAILURE = 3
EXIT_USAGE = 64
EXIT_CONFIG = 78


class _UsageError(Exception):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):  # argparse would print and exit 2; contracts/cli.md wants 64
        raise _UsageError(message)


def _parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="python -m order_agent",
        add_help=False,
        description="Extract a new-order record from one NSE/BSE announcement.",
    )
    parser.add_argument("input", help="announcement file, read as raw bytes; '-' reads stdin")
    parser.add_argument("--env-file", default=None, help=".env file (default: ./.env if present)")
    return parser


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _application_report(outcome: agent.ApplicationFailure) -> dict:
    return {
        "error": "application_failure",
        "stage": outcome.stage,
        "errors": [e.to_dict() for e in outcome.errors],
        "raw_model_output": outcome.raw_text,
        "parser_log": outcome.parser_log,
        "candidate": outcome.candidate,
    }


def _service_report(outcome: agent.ServiceFailure) -> dict:
    return {
        "error": "service_failure",
        "attempts": [
            {
                "n": a.n,
                "kind": a.service_failure_kind,
                "http_status": a.http_status,
                "elapsed_s": a.elapsed_s,
                "message": a.error,
            }
            for a in outcome.attempts
        ],
    }


def main(argv=None, *, transport=None, stdin=None, stdout=None, stderr=None, sleep=None) -> int:
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr
    parser = _parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except _UsageError as exc:
        stderr.write(parser.format_usage() + f"error: {exc}\n")
        return EXIT_USAGE

    env_file = args.env_file
    if env_file is None and Path(".env").is_file():
        env_file = ".env"
    try:
        settings = config.load(env_file, os.environ)
    except config.ConfigError as exc:
        stderr.write(f"configuration error: {exc}\n")
        return EXIT_CONFIG

    try:
        if args.input == "-":
            raw = (stdin if stdin is not None else sys.stdin.buffer).read()
        else:
            raw = Path(args.input).read_bytes()
    except OSError as exc:
        stderr.write(f"cannot read input {args.input}: {exc}\n")
        return EXIT_USAGE

    mismatches = config.pin_mismatches(settings)
    if mismatches:
        stderr.write(
            "warning: " + "; ".join(mismatches) + " (an evaluation would be INCONCLUSIVE)\n"
        )

    outcome = agent.run(raw, settings, transport=transport, sleep=sleep)
    if isinstance(outcome, agent.Success):
        stdout.write(_dump(outcome.result))
        return EXIT_OK
    if isinstance(outcome, agent.ApplicationFailure):
        stderr.write(_dump(_application_report(outcome)))
        return EXIT_APPLICATION_FAILURE
    stderr.write(_dump(_service_report(outcome)))
    return EXIT_SERVICE_FAILURE
