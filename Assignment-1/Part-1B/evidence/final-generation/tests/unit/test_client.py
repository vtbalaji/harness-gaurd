"""Ollama and judge clients (spec FR-020, FR-023, FR-030, AC-5.4; research.md R-9, R-12).
Every test uses FakeTransport; no socket is ever opened."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request

import pytest
from conftest import FakeTransport, ollama_envelope

SYSTEM = "system instructions"
PROMPT = "<<<ANNOUNCEMENT id=abc>>>\ntext\n<<<END ANNOUNCEMENT id=abc>>>"


def _generate(settings, responses, no_sleep):
    from order_agent import client

    transport = FakeTransport(responses)
    result = client.generate(settings, SYSTEM, PROMPT, transport=transport, sleep=no_sleep)
    return result, transport


# ------------------------------------- generate part (T019) -------------------------------------


def test_fr020_generate_request_body_exact(settings, no_sleep):
    """FR-020, R-9: POST /api/generate with exactly the pinned body and a 300 s timeout."""
    from order_agent import config

    result, transport = _generate(settings, [(200, ollama_envelope('{"a": 1}'))], no_sleep)
    assert result.ok
    method, url, payload, timeout = transport.calls[0]
    assert (method, url, timeout) == ("POST", "http://localhost:11434/api/generate", 300)
    assert payload == {
        "model": "qwen3.5:4b",
        "system": SYSTEM,
        "prompt": PROMPT,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 700,
            "num_ctx": config.num_ctx(len(SYSTEM) + len(PROMPT)),
            "seed": 42,
        },
    }


def test_fr020_generate_url_joins_without_double_slash(no_sleep):
    """FR-020: a trailing slash in OLLAMA_URL does not produce `//api/generate`."""
    from conftest import make_settings

    settings = make_settings(OLLAMA_URL="http://localhost:11434/")
    _result, transport = _generate(settings, [(200, ollama_envelope("{}"))], no_sleep)
    assert transport.calls[0][1] == "http://localhost:11434/api/generate"


def test_fr020_num_ctx_uses_full_prompt_length(settings, no_sleep):
    """FR-020: num_ctx is computed from len(system) + len(prompt)."""
    from order_agent import client

    long_prompt = "x" * 30000
    transport = FakeTransport([(200, ollama_envelope("{}"))])
    client.generate(settings, SYSTEM, long_prompt, transport=transport, sleep=no_sleep)
    expected = max(4096, (len(SYSTEM) + 30000) // 3 + 700 + 512)
    assert transport.calls[0][2]["options"]["num_ctx"] == expected


KIND_CASES = [
    ("timeout", TimeoutError("timed out")),
    ("timeout", TimeoutError("timed out")),
    ("timeout", urllib.error.URLError(TimeoutError("timed out"))),
    ("unreachable", urllib.error.URLError(ConnectionRefusedError(61, "refused"))),
    ("unreachable", urllib.error.URLError("dns failure")),
    ("unreachable", ConnectionRefusedError(61, "refused")),
    ("connection_lost", http.client.RemoteDisconnected("closed")),
    ("connection_lost", ConnectionResetError(54, "reset")),
    ("connection_lost", ConnectionAbortedError(53, "aborted")),
    ("connection_lost", BrokenPipeError(32, "pipe")),
    ("connection_lost", http.client.IncompleteRead(b"par")),
    ("connection_lost", http.client.BadStatusLine("x")),
    ("connection_lost", OSError("read error")),
]


@pytest.mark.parametrize(
    ("kind", "exc"), KIND_CASES, ids=[f"{k}-{type(e).__name__}" for k, e in KIND_CASES]
)
def test_fr023_exception_kinds_classified_and_retried(settings, no_sleep, kind, exc):
    """FR-023 (rev 2), R-9 (E2): each exception kind is classified (first match) and retried."""
    from order_agent import client

    assert client.classify_exception(exc) == kind
    result, transport = _generate(settings, [exc, exc, exc], no_sleep)
    assert not result.ok
    assert result.last_kind == kind
    assert result.raw_text is None
    assert [a.service_failure_kind for a in result.attempts] == [kind] * 3
    assert [a.outcome for a in result.attempts] == ["service_failure"] * 3
    assert len(transport.calls) == 3
    assert no_sleep.calls == [5, 10]
    assert result.attempts[0].error.startswith(type(exc).__name__ + ":")


@pytest.mark.parametrize(
    ("reply", "kind"),
    [
        ((500, b'{"error": "model runner has unexpectedly stopped"}'), "http_error"),
        ((404, b'{"error": "model not found"}'), "http_error"),
        ((200, b""), "empty_response"),
        ((200, ollama_envelope("")), "empty_response"),
        ((200, b'{"done": true}'), "empty_response"),
        ((200, b"not json"), "bad_envelope"),
        ((200, b"[1, 2]"), "bad_envelope"),
        ((200, b"\xff\xfe"), "bad_envelope"),
        ((200, b'{"response": 5}'), "bad_envelope"),
    ],
    ids=[
        "500",
        "404",
        "empty-body",
        "empty-response",
        "missing-response",
        "not-json",
        "array",
        "undecodable",
        "non-string-response",
    ],
)
def test_fr023_response_kinds_classified_and_retried(settings, no_sleep, reply, kind):
    """FR-023 (rev 2), R-9: http_error, empty_response and bad_envelope are retryable kinds."""
    result, transport = _generate(settings, [reply] * 3, no_sleep)
    assert not result.ok and result.last_kind == kind
    assert len(transport.calls) == 3
    assert result.attempts[0].http_status == reply[0]
    assert result.attempts[0].error


def test_fr023_non_service_exception_propagates_without_retry(settings, no_sleep):
    """FR-023 (rev 2, U1), R-9: a ValueError is not classified and propagates out of generate."""
    from order_agent import client

    assert client.classify_exception(ValueError("bug")) is None
    with pytest.raises(ValueError, match="bug"):
        _generate(settings, [ValueError("bug")], no_sleep)
    assert no_sleep.calls == []


def test_fr023_success_on_second_attempt(settings, no_sleep):
    """FR-023: a retried-then-successful request has 2 attempts, the first a service failure."""
    result, _transport = _generate(
        settings, [ConnectionResetError(54, "reset"), (200, ollama_envelope('{"x": 1}'))], no_sleep
    )
    assert result.ok and result.raw_text == '{"x": 1}'
    assert [a.outcome for a in result.attempts] == ["service_failure", "ok"]
    assert result.attempts[1].service_failure_kind is None
    assert no_sleep.calls == [5]


def test_fr023_length_done_reason_is_not_a_service_failure(settings, no_sleep):
    """FR-023 (CONFIRMED P-3): done_reason "length" is recorded and the text goes to the parser
    verbatim."""
    truncated = '{"is_new_order": true, "orders": [{"order_va'
    result, transport = _generate(
        settings, [(200, ollama_envelope(truncated, done_reason="length"))], no_sleep
    )
    assert result.ok and result.raw_text == truncated
    assert result.attempts[0].envelope["done_reason"] == "length"
    assert len(transport.calls) == 1


def test_fr023_attempt_records_every_field(settings, no_sleep):
    """FR-022, FR-023: each Attempt records n, timing, request, status, outcome, kind, raw text
    and envelope."""
    from order_agent import config

    text = '  {"a": 1}  '
    result, _ = _generate(settings, [(200, ollama_envelope(text))], no_sleep)
    attempt = result.attempts[0]
    assert attempt.n == 1
    assert attempt.started_at.endswith("Z") and attempt.ended_at.endswith("Z")
    assert attempt.elapsed_s >= 0
    assert attempt.request["url"] == "http://localhost:11434/api/generate"
    assert attempt.request["model"] == "qwen3.5:4b"
    assert attempt.request["options"]["num_ctx"] == config.num_ctx(len(SYSTEM) + len(PROMPT))
    assert attempt.request["think"] is False
    assert attempt.request["format"] == "json"
    assert attempt.request["stream"] is False
    assert attempt.http_status == 200
    assert attempt.outcome == "ok"
    assert attempt.service_failure_kind is None
    assert attempt.raw_text == text  # verbatim, not stripped
    assert attempt.envelope == {
        "done_reason": "stop",
        "eval_count": 180,
        "prompt_eval_count": 600,
        "total_duration": 1_500_000_000,
        "model": "qwen3.5:4b",
    }
    assert attempt.error is None
    assert json.loads(attempt.response_body)["response"] == text
    summary = attempt.to_dict()
    assert summary["n"] == 1 and "response_body" not in summary


def test_fr022_get_json_builds_version_request(settings):
    """FR-022, R-11: get_json builds GET {OLLAMA_URL}/api/version."""
    from order_agent import client

    transport = FakeTransport([(200, b'{"version": "0.32.14"}')])
    obj = client.get_json(settings.ollama_url + "/api/version", timeout=30, transport=transport)
    assert obj == {"version": "0.32.14"}
    assert transport.calls == [("GET", "http://localhost:11434/api/version", None, 30)]


def test_fr022_post_json_sends_payload_and_reports_service_errors():
    """FR-022, R-11: post_json sends a JSON body; failures raise ServiceError with a kind."""
    from order_agent import client

    transport = FakeTransport([(200, b'{"details": {}}')])
    assert client.post_json(
        "http://h/api/show", {"model": "m"}, timeout=5, transport=transport
    ) == {"details": {}}
    assert transport.calls[0][2] == {"model": "m"}
    for reply, kind in [
        ((500, b"x"), "http_error"),
        ((200, b""), "empty_response"),
        ((200, b"[]"), "bad_envelope"),
        (urllib.error.URLError("dns"), "unreachable"),
    ]:
        with pytest.raises(client.ServiceError) as info:
            client.get_json("http://h/x", timeout=5, transport=FakeTransport([reply]))
        assert info.value.kind == kind and info.value.detail


def test_r9_build_opener_has_only_the_four_http_handlers():
    """R-9: the opener has only HTTPHandler, HTTPSHandler, HTTPDefaultErrorHandler and
    HTTPErrorProcessor (no file/ftp/data handler)."""
    from order_agent import client

    opener = client.build_opener()
    kinds = sorted(type(h).__name__ for h in opener.handlers)
    assert kinds == sorted(
        ["HTTPHandler", "HTTPSHandler", "HTTPDefaultErrorHandler", "HTTPErrorProcessor"]
    )
    assert isinstance(opener, urllib.request.OpenerDirector)


@pytest.mark.parametrize("url", ["file:///etc/hosts", "ftp://example.com/x", "data:,hello"])
def test_r9_non_http_urls_raise_url_error_without_socket(url):
    """R-9, FR-021: file:, ftp: and data: URLs raise URLError and never touch a socket."""
    from order_agent import client

    with pytest.raises(urllib.error.URLError):
        client.build_opener().open(url, timeout=1)
    with pytest.raises(urllib.error.URLError):
        client.default_transport("GET", url, None, 1)


def test_r9_default_transport_reaches_socket_only_through_http(monkeypatch):
    """R-9, R-14: an http URL goes to the socket layer, which the autouse fixture blocks."""
    from order_agent import client

    with pytest.raises(RuntimeError, match="network blocked"):
        client.default_transport("GET", "http://127.0.0.1:9/api/version", None, 1)


def test_r9_default_transport_returns_status_and_body_for_http_errors(monkeypatch):
    """R-9: an HTTP error status is returned as (status, body), not raised."""
    from order_agent import client

    class _Resp:
        status = 200

        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_open(self, req, timeout=None):
        assert req.get_method() == "POST" and req.data == b"{}"
        assert req.get_header("Content-type") == "application/json"
        return _Resp()

    monkeypatch.setattr(client._HTTPOnlyOpener, "open", fake_open)
    assert client.default_transport("POST", "http://h/x", b"{}", 3) == (200, b"ok")

    def fake_error(self, req, timeout=None):
        import io

        raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, io.BytesIO(b"down"))

    monkeypatch.setattr(client._HTTPOnlyOpener, "open", fake_error)
    assert client.default_transport("GET", "http://h/x", None, 3) == (503, b"down")


def test_fr023_http_error_exception_is_http_error_kind():
    """FR-023, R-9: an HTTPError exception (an HTTP status >= 400) is `http_error`."""
    import io

    from order_agent import client

    exc = urllib.error.HTTPError("http://h", 500, "x", {}, io.BytesIO(b""))
    assert client.classify_exception(exc) == "http_error"


# --------------------------------------- judge part (T042) ---------------------------------------

SOURCE = "Example Transformers Limited has received an order worth ₹1,250.50 crore."
RESULT = {"schema_version": "1.0", "status": "extracted", "company": "Example Transformers Limited"}


def judge_reply(content, status=200):
    body = {
        "id": "x",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }
    return (status, json.dumps(body).encode("utf-8"))


def _judge(settings, responses, no_sleep):
    from order_agent import client

    transport = FakeTransport(responses)
    result = client.judge(settings, SOURCE, RESULT, transport=transport, sleep=no_sleep)
    return result, transport


def test_fr030_judge_request_exact(settings, no_sleep):
    """FR-030, R-12 (rev 2, L5): POST JUDGE_URL with the exact body and a 180 s timeout."""
    from order_agent import prompt

    result, transport = _judge(
        settings, [judge_reply('{"rating": 5, "rationale": "Faithful."}')], no_sleep
    )
    method, url, payload, timeout = transport.calls[0]
    assert (method, url, timeout) == ("POST", "http://127.0.0.1:8081/v1/chat/completions", 180)
    assert set(payload) == {
        "model",
        "temperature",
        "max_tokens",
        "messages",
        "chat_template_kwargs",
    }
    assert payload["model"] == "qwen3.6-35b-a3b"
    assert payload["temperature"] == 0 and payload["max_tokens"] == 600
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    system, user = payload["messages"]
    assert system["role"] == "system" and user["role"] == "user"
    assert '"rating"' in system["content"] and "1" in system["content"]
    assert prompt.build(SOURCE).prompt in user["content"]  # R-4 data markers
    assert json.dumps(RESULT, ensure_ascii=False, indent=2) in user["content"]
    assert result.status == "ok" and result.rating == 5 and result.rationale == "Faithful."
    assert result.kind is None and result.detail is None and len(result.attempts) == 1
    assert result.request == {
        "url_host": "127.0.0.1:8081",
        "model": "qwen3.6-35b-a3b",
        "temperature": 0,
        "max_tokens": 600,
        "timeout_s": 180,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def test_fr030_judge_never_sees_ground_truth():
    """FR-030, R-12: the judge takes the source and the agent result only, no ground truth."""
    import inspect

    from order_agent import client

    params = list(inspect.signature(client.judge).parameters)
    assert params == ["settings", "source_text", "result", "transport", "sleep"]


def test_fr030_judge_strips_leading_think_block(settings, no_sleep):
    """FR-030, R-12: a leading <think>…</think> block is stripped, then PC-1 … PC-3 apply."""
    content = (
        '<think>\nlet me check the value\n</think>\n```json\n{"rating": 4, "rationale": "ok"}\n```'
    )
    result, _ = _judge(settings, [judge_reply(content)], no_sleep)
    assert result.status == "ok" and result.rating == 4


@pytest.mark.parametrize("rating", [0, 6, "5", 5.0, True, None])
def test_ac_5_4_judge_rating_must_be_int_1_to_5(settings, no_sleep, rating):
    """FR-030, AC-5.4: rating must be an int from 1 to 5, else `unparseable` (no retry)."""
    content = json.dumps({"rating": rating, "rationale": "x"})
    result, transport = _judge(settings, [judge_reply(content)], no_sleep)
    assert result.status == "failed" and result.kind == "unparseable"
    assert result.rating is None and result.rationale is None and result.detail
    assert len(transport.calls) == 1 and no_sleep.calls == []


@pytest.mark.parametrize(
    "content", ["not json", '{"rating": 5}', '{"rating": 5, "rationale": ""}', "[5]"]
)
def test_ac_5_4_judge_unparseable_replies(settings, no_sleep, content):
    """FR-030, AC-5.4: prose, a missing or empty rationale, or an array are `unparseable`."""
    result, _ = _judge(settings, [judge_reply(content)], no_sleep)
    assert result.kind == "unparseable"


@pytest.mark.parametrize(
    ("kind", "exc"), KIND_CASES, ids=[f"{k}-{type(e).__name__}" for k, e in KIND_CASES]
)
def test_fr030_judge_service_kinds_are_retried(settings, no_sleep, kind, exc):
    """FR-030, R-12, R-9 (rev 2): judge transport failures use the same 3-attempt retry."""
    result, transport = _judge(settings, [exc, exc, exc], no_sleep)
    assert result.status == "failed" and result.kind == kind
    assert len(transport.calls) == 3 and len(result.attempts) == 3
    assert no_sleep.calls == [5, 10]


@pytest.mark.parametrize(
    ("reply", "kind"),
    [
        ((500, b"oops"), "http_error"),
        ((200, b""), "empty_response"),
        (judge_reply(""), "empty_response"),
        (judge_reply(None), "empty_response"),
        ((200, b"<html>"), "bad_envelope"),
        ((200, b'{"choices": []}'), "bad_envelope"),
        ((200, b'{"no": "choices"}'), "bad_envelope"),
    ],
    ids=["500", "empty-body", "empty-content", "null-content", "not-json", "no-choice", "no-key"],
)
def test_fr030_judge_response_kinds(settings, no_sleep, reply, kind):
    """FR-030: http_error, empty_response and bad_envelope judge failures, retried 3 times."""
    result, transport = _judge(settings, [reply] * 3, no_sleep)
    assert result.status == "failed" and result.kind == kind
    assert len(transport.calls) == 3


def test_fr030_judge_retry_then_success(settings, no_sleep):
    """FR-030, R-12: a judge service failure followed by a good reply succeeds."""
    result, _ = _judge(
        settings,
        [TimeoutError("t"), judge_reply('{"rating": 3, "rationale": "Partly."}')],
        no_sleep,
    )
    assert result.status == "ok" and result.rating == 3 and len(result.attempts) == 2


def test_u1_judge_exceptions_are_contained(settings, no_sleep, monkeypatch):
    """FR-030 (rev 2, U1), AC-5.4: a ValueError from the transport, or an unexpected error while
    parsing, gives JudgeResult(status="failed", kind="exception"); judge never raises."""
    from order_agent import client

    result, transport = _judge(settings, [ValueError("bug in transport")], no_sleep)
    assert result.status == "failed" and result.kind == "exception"
    assert result.detail == "ValueError: bug in transport" and len(transport.calls) == 1

    def broken_parse(_text):
        raise RuntimeError("parser exploded")

    monkeypatch.setattr(client.parser, "parse", broken_parse)
    result, transport = _judge(settings, [judge_reply('{"rating": 5, "rationale": "x"}')], no_sleep)
    assert result.kind == "exception" and "parser exploded" in result.detail
    assert len(transport.calls) == 1 and no_sleep.calls == []


def test_fr030_judge_result_to_dict():
    """FR-030, FR-032: a JudgeResult serialises with its attempts as plain dicts."""
    from order_agent import client

    result = client.JudgeResult("ok", 5, "Fine.", None, None, [], {"model": "m"})
    assert json.loads(json.dumps(result.to_dict()))["rating"] == 5
