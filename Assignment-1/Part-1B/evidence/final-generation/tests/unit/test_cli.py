"""Command-line interface (contracts/cli.md; spec FR-016, FR-019, FR-021, FR-023)."""

from __future__ import annotations

import io
import json
import runpy
import sys
import urllib.error

import pytest
from conftest import ENV_EXAMPLE_VALUES, N01_TEXT, FakeTransport, build_mr, ok_reply


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """CLI tests run with cwd = tmp_path and an explicit env file."""
    monkeypatch.chdir(tmp_path)
    env = tmp_path / "test.env"
    env.write_text("".join(f"{k}={v}\n" for k, v in ENV_EXAMPLE_VALUES.items()), "utf-8")
    (tmp_path / "n01.txt").write_bytes(N01_TEXT.encode("utf-8"))
    return tmp_path


def _main(argv, responses=(), stdin=b""):
    from order_agent import cli

    transport = FakeTransport(responses)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, transport=transport, stdin=io.BytesIO(stdin), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue(), transport


def test_cli_exit_0_prints_only_the_schema_result(workdir):
    """contracts/cli.md, FR-001: exit 0, stdout is the 2-space-indented result with ₹ literal and
    a trailing newline; stderr is empty."""
    code, out, err, _ = _main(["n01.txt", "--env-file", "test.env"], [ok_reply(build_mr())])
    assert code == 0 and err == ""
    result = json.loads(out)
    assert result["status"] == "extracted" and result["order"]["value_in_cr"] == 1250.5
    assert out == json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    assert "₹1,250.50 crore" in out


def test_fr019_cli_exit_2_application_failure_report(workdir):
    """FR-019, contracts/cli.md: exit 2, nothing on stdout, the failure report on stderr."""
    mr = build_mr(company="BSE Limited", company_quote="To, BSE Limited")
    code, out, err, _ = _main(["n01.txt", "--env-file", "test.env"], [ok_reply(mr)])
    assert code == 2 and out == ""
    report = json.loads(err)
    assert set(report) == {
        "error",
        "stage",
        "errors",
        "raw_model_output",
        "parser_log",
        "candidate",
    }
    assert report["error"] == "application_failure" and report["stage"] == "post_validation"
    assert report["errors"] == [
        {
            "code": "G-5",
            "pointer": "/company",
            "message": report["errors"][0]["message"],
            "layer": 2,
        }
    ]
    assert json.loads(report["raw_model_output"])["company"] == "BSE Limited"
    assert report["candidate"]["company"] == "BSE Limited" and report["parser_log"] == []


def test_fr023_cli_exit_3_service_failure_report(workdir):
    """FR-023, contracts/cli.md: exit 3 and a service_failure report listing 3 attempts."""
    errors = [urllib.error.URLError(ConnectionRefusedError(61, "refused")) for _ in range(3)]
    from order_agent import cli

    out, err = io.StringIO(), io.StringIO()
    code = cli.main(
        ["n01.txt", "--env-file", "test.env"],
        transport=FakeTransport(errors),
        stdout=out,
        stderr=err,
        sleep=lambda _s: None,
    )
    assert code == 3 and out.getvalue() == ""
    report = json.loads(err.getvalue())
    assert report["error"] == "service_failure"
    assert [a["n"] for a in report["attempts"]] == [1, 2, 3]
    assert {a["kind"] for a in report["attempts"]} == {"unreachable"}
    assert set(report["attempts"][0]) == {"n", "kind", "http_status", "elapsed_s", "message"}


def test_cli_exit_64_usage_and_missing_file(workdir):
    """contracts/cli.md: no argument, an unknown option or a missing file gives exit 64."""
    for argv in ([], ["a.txt", "b.txt"], ["--bogus"], ["-h"]):
        code, out, err, _ = _main(argv)
        assert code == 64 and out == "" and "usage" in err.lower(), argv
    code, out, err, _ = _main(["missing.txt", "--env-file", "test.env"])
    assert code == 64 and out == "" and "missing.txt" in err


def test_fr021_cli_exit_78_missing_key_and_bad_scheme(workdir):
    """FR-021, R-10: a missing key (named in the message) or a file: URL gives exit 78."""
    (workdir / "partial.env").write_text("OLLAMA_URL=http://localhost:11434\n", "utf-8")
    code, out, err, transport = _main(["n01.txt", "--env-file", "partial.env"])
    assert code == 78 and out == "" and "AGENT_MODEL" in err and transport.calls == []
    values = dict(ENV_EXAMPLE_VALUES, OLLAMA_URL="file:///etc/passwd")
    (workdir / "bad.env").write_text("".join(f"{k}={v}\n" for k, v in values.items()), "utf-8")
    code, _out, err, _ = _main(["n01.txt", "--env-file", "bad.env"])
    assert code == 78 and "OLLAMA_URL" in err
    code, _out, err, _ = _main(["n01.txt", "--env-file", "nope.env"])
    assert code == 78 and "nope.env" in err


def test_cli_dash_reads_stdin_bytes(workdir):
    """contracts/cli.md: `-` reads raw bytes from stdin."""
    code, out, _err, transport = _main(
        ["-", "--env-file", "test.env"], [ok_reply(build_mr())], stdin=N01_TEXT.encode("utf-8")
    )
    assert code == 0 and json.loads(out)["company"] == "Example Transformers Limited"
    assert N01_TEXT in transport.calls[0][2]["prompt"]


def test_cli_default_env_file_is_dot_env_in_cwd(workdir):
    """contracts/cli.md: without --env-file, ./.env is loaded when it exists."""
    (workdir / ".env").write_text((workdir / "test.env").read_text("utf-8"), "utf-8")
    code, out, _err, _ = _main(["n01.txt"], [ok_reply(build_mr())])
    assert code == 0 and json.loads(out)["status"] == "extracted"
    (workdir / ".env").unlink()
    code, _out, err, _ = _main(["n01.txt"])
    assert code == 78 and "OLLAMA_URL" in err


def test_r10_cli_pin_mismatch_warns_once_and_still_runs(workdir, monkeypatch):
    """R-10, contracts/cli.md: AGENT_MODEL=qwen3.5:9b gives one stderr warning; exit is 0."""
    monkeypatch.setenv("AGENT_MODEL", "qwen3.5:9b")
    code, out, err, transport = _main(["n01.txt", "--env-file", "test.env"], [ok_reply(build_mr())])
    assert code == 0 and json.loads(out)["status"] == "extracted"
    lines = err.strip().splitlines()
    assert len(lines) == 1 and "qwen3.5:9b" in lines[0] and "warning" in lines[0].lower()
    assert transport.calls[0][2]["model"] == "qwen3.5:9b"


def test_cli_python_dash_m_order_agent_resolves_to_main(monkeypatch, capsys):
    """contracts/cli.md: `python -m order_agent` runs cli.main (usage error → 64)."""
    monkeypatch.setattr(sys, "argv", ["order_agent"])
    with pytest.raises(SystemExit) as info:
        runpy.run_module("order_agent", run_name="__main__")
    assert info.value.code == 64
    assert "usage" in capsys.readouterr().err.lower()


@pytest.mark.parametrize(
    ("stdin", "reason"),
    [
        (b"", "empty"),
        (b" \n\t ", "whitespace_only"),
        (b"a" * 20001, "too_long"),
        (b"\xff\xfe\x00garbage", "garbled"),
    ],
)
def test_ac_3_1_to_3_4_cli_guard_smoke_checks(workdir, stdin, reason):
    """AC-3.1 … AC-3.4, FR-016, quickstart.md §3: each guard input gives exit 0 and a rejected
    object with the right reason on stdout, with zero transport calls."""
    code, out, err, transport = _main(["-", "--env-file", "test.env"], [], stdin=stdin)
    assert code == 0 and err == ""
    result = json.loads(out)
    assert result["status"] == "rejected" and result["rejection_reason"] == reason
    assert transport.calls == []
