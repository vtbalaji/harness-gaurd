"""Shared test fixtures (research.md R-14). No production behaviour lives here.

- Every real socket connect fails the test (``block_network``), so no test can reach Ollama,
  the judge or any other network endpoint.
- The five configuration keys are removed from the process environment (``clean_env``), so the
  real ``.env`` never leaks into a test.
- ``FakeTransport`` replaces HTTP: it returns scripted ``(status, body)`` pairs or raises
  scripted exceptions, and records every call.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evals" / "dataset.json"
SPEC_PATH = PROJECT_ROOT / "specs" / "001-order-extraction-agent" / "spec.md"
DATA_MODEL_PATH = PROJECT_ROOT / "specs" / "001-order-extraction-agent" / "data-model.md"
CONTRACTS_DIR = PROJECT_ROOT / "specs" / "001-order-extraction-agent" / "contracts"
RUN_EVAL_PATH = PROJECT_ROOT / ".harness" / "run_eval.py"

CONFIG_KEYS = ("OLLAMA_URL", "AGENT_MODEL", "AGENT_MODEL_DIGEST", "JUDGE_URL", "JUDGE_MODEL")

ENV_EXAMPLE_VALUES = {
    "OLLAMA_URL": "http://localhost:11434",
    "AGENT_MODEL": "qwen3.5:4b",
    "AGENT_MODEL_DIGEST": "d8b0f5e9760c",
    "JUDGE_URL": "http://127.0.0.1:8081/v1/chat/completions",
    "JUDGE_MODEL": "qwen3.6-35b-a3b",
}

# The quickstart.md section 3 announcement (AC-1.1, AC-1.5).
N01_TEXT = (
    "To, BSE Limited / National Stock Exchange of India Limited\n"
    "Date: November 20, 2026\n"
    "Sub: Receipt of order\n"
    "Example Transformers Limited has received an order worth ₹1,250.50 crore "
    "from NTPC Limited for\n"
    "supply of transformers, to be executed within 18 months.\n"
    "For Example Transformers Limited, Company Secretary\n"
)


def _blocked(*_args, **_kwargs):
    raise RuntimeError("network blocked in tests")


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Any real socket connect fails the test (research.md R-14)."""
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """The real .env and the shell environment never reach a test."""
    for key in CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


class FakeTransport:
    """Scripted stand-in for ``client.Transport``.

    ``responses`` is a list; each entry is a ``(status, body_bytes)`` pair, or an exception
    instance to raise. Every call is recorded as ``(method, url, payload_dict, timeout)``.
    Calling it more often than scripted fails the test (``pytest.fail`` raises a
    ``BaseException``, so no ``except Exception`` in production code can swallow it).
    """

    def __init__(self, responses=()):
        self.responses = list(responses)
        self.calls: list[tuple[str, str, object, float]] = []

    def __call__(self, method, url, body, timeout):
        payload = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, url, payload, timeout))
        if len(self.calls) > len(self.responses):
            pytest.fail(
                f"FakeTransport called {len(self.calls)} times; scripted only "
                f"{len(self.responses)} ({method} {url})"
            )
        item = self.responses[len(self.calls) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


def ollama_envelope(response_text, done_reason="stop", **extra) -> bytes:
    """An Ollama ``/api/generate`` reply (stream false) with ``response_text``."""
    body = {
        "model": "qwen3.5:4b",
        "created_at": "2026-11-22T10:00:00Z",
        "response": response_text,
        "done": True,
        "done_reason": done_reason,
        "total_duration": 1_500_000_000,
        "prompt_eval_count": 600,
        "eval_count": 180,
    }
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def ok_reply(mr_obj) -> tuple[int, bytes]:
    """HTTP 200 whose ``response`` is the JSON text of ``mr_obj``."""
    return (200, ollama_envelope(json.dumps(mr_obj, ensure_ascii=False)))


def make_settings(**overrides):
    from order_agent import config

    values = dict(ENV_EXAMPLE_VALUES)
    values.update(overrides)
    return config.load(env_file=None, environ=values)


@pytest.fixture
def settings():
    """A ``config.Settings`` with the .env.example values."""
    return make_settings()


class SleepRecorder:
    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, seconds):
        self.calls.append(seconds)


@pytest.fixture
def no_sleep():
    return SleepRecorder()


def build_mr(**overrides) -> dict:
    """A valid single-order model response (mr-1) for N01_TEXT; quotes are verbatim from it."""
    order_overrides = overrides.pop("order", {})
    order = {
        "order_value": 1250.5,
        "currency": "INR",
        "unit": "crore",
        "client": "NTPC Limited",
        "value_quote": "₹1,250.50 crore",
        "client_quote": "NTPC Limited",
    }
    order.update(order_overrides)
    mr = {
        "is_new_order": True,
        "company": "Example Transformers Limited",
        "company_quote": "Example Transformers Limited has received an order",
        "announcement_date": "2026-11-20",
        "announcement_date_quote": "Date: November 20, 2026",
        "order_type": "supply",
        "order_type_quote": "supply of transformers",
        "execution_period": "within 18 months",
        "execution_period_quote": "to be executed within 18 months",
        "orders": [order],
    }
    mr.update(overrides)
    return mr


@pytest.fixture
def mr():
    return build_mr


def build_result(**overrides) -> dict:
    """The AC-1.1 schema-1.0 result for N01_TEXT (value_in_cr 1250.5, FR-035 rev 3)."""
    order_overrides = overrides.pop("order", {})
    order = {
        "order_value": 1250.5,
        "currency": "INR",
        "unit": "crore",
        "value_in_cr": 1250.5,
        "client": "NTPC Limited",
        "order_type": "supply",
        "execution_period": "within 18 months",
    }
    if order_overrides is None:
        order = None
    else:
        order.update(order_overrides)
    result = {
        "schema_version": "1.0",
        "status": "extracted",
        "company": "Example Transformers Limited",
        "announcement_date": "2026-11-20",
        "order": order,
        "additional_orders": [],
        "evidence": {
            "company": "Example Transformers Limited has received an order",
            "announcement_date": "Date: November 20, 2026",
            "order_value": "₹1,250.50 crore",
            "currency": "₹1,250.50 crore",
            "unit": "₹1,250.50 crore",
            "client": "NTPC Limited",
            "order_type": "supply of transformers",
            "execution_period": "to be executed within 18 months",
        },
        "missing_fields": [],
        "unstated_fields": [],
        "rejection_reason": None,
    }
    result.update(overrides)
    return result


def rejected(reason) -> dict:
    """The FR-015 rejected shape."""
    return {
        "schema_version": "1.0",
        "status": "rejected",
        "company": None,
        "announcement_date": None,
        "order": None,
        "additional_orders": [],
        "evidence": {},
        "missing_fields": [],
        "unstated_fields": [],
        "rejection_reason": reason,
    }


def not_an_order(**overrides) -> dict:
    """A valid not_an_order result (FR-015)."""
    result = rejected(None)
    result.update(
        status="not_an_order",
        company="Example Transformers Limited",
        announcement_date="2026-11-20",
        evidence={
            "company": "Example Transformers Limited has received an order",
            "announcement_date": "Date: November 20, 2026",
        },
    )
    result.update(overrides)
    return result


def additional(**overrides) -> dict:
    """A valid additional order (₹450 crore) for building multi-order results."""
    entry = {
        "order_value": 450,
        "currency": "INR",
        "unit": "crore",
        "value_in_cr": 450.0,
        "client": "Y Limited",
        "evidence": {
            "order_value": "₹450 crore",
            "currency": "₹450 crore",
            "unit": "₹450 crore",
            "client": "Y Limited",
        },
    }
    entry.update(overrides)
    return entry


def load_run_eval():
    """Load .harness/run_eval.py through importlib (it is not a package module)."""
    import importlib.util
    import sys

    name = "run_eval_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, RUN_EVAL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def mr_from_ground_truth(gt: dict, source: str) -> dict:
    """A canned mr-1 model response built from a ground truth: value_quote = the order_value
    evidence, client_quote = the client evidence, and so on. Orders are listed in order of
    appearance in `source`, so the agent's own ranking (A-2) must pick the top-level order.
    There is no value_in_cr key: mr-1 has none, so the agent's A-9 must compute it."""
    evidence = gt["evidence"]
    order = gt["order"]
    is_order = gt["status"] in ("extracted", "needs_clarification")
    entries = []
    if order is not None:
        top = {"order": order, "evidence": evidence}
        entries = [top] + [{"order": o, "evidence": o["evidence"]} for o in gt["additional_orders"]]
    flat = " ".join(source.split())

    def position(entry):
        quote = entry["evidence"].get("order_value") or entry["evidence"].get("client") or ""
        found = flat.find(" ".join(quote.split()))
        return found if found >= 0 else len(flat)

    orders = [
        {
            "order_value": e["order"]["order_value"],
            "currency": e["order"]["currency"],
            "unit": e["order"]["unit"],
            "client": e["order"]["client"],
            "value_quote": e["evidence"].get("order_value"),
            "client_quote": e["evidence"].get("client"),
        }
        for e in sorted(entries, key=position)
    ]
    return {
        "is_new_order": is_order,
        "company": gt["company"],
        "company_quote": evidence.get("company"),
        "announcement_date": gt["announcement_date"],
        "announcement_date_quote": evidence.get("announcement_date"),
        "order_type": order["order_type"] if order else None,
        "order_type_quote": evidence.get("order_type"),
        "execution_period": order["execution_period"] if order else None,
        "execution_period_quote": evidence.get("execution_period"),
        "orders": orders,
    }


PIN_DIGEST = "d8b0f5e9760c" + "ab" * 26


def pin_routes(version="0.32.14", digest=PIN_DIGEST, quant="Q4_K_M", tag="qwen3.5:4b"):
    """RoutingTransport routes for the three pin-check endpoints (research.md R-11)."""
    models = [{"name": tag, "model": tag, "digest": digest}] if tag else []
    return {
        "/api/version": (200, json.dumps({"version": version}).encode()),
        "/api/tags": (200, json.dumps({"models": models}).encode()),
        "/api/show": (200, json.dumps({"details": {"quantization_level": quant}}).encode()),
    }


def judge_body(rating=5, rationale="Faithful to the source."):
    content = json.dumps({"rating": rating, "rationale": rationale})
    body = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    return (200, json.dumps(body).encode("utf-8"))


class RoutingTransport:
    """A fake transport that answers by URL path suffix, for the evaluation runner.

    Each route value is a `(status, body)` pair, an exception instance to raise, or a callable
    `(method, url, payload) -> (status, body)` (which may raise). An unrouted URL fails the test.
    Every call is recorded as `(method, url, payload_dict, timeout)`.
    """

    JUDGE_SUFFIX = "/v1/chat/completions"

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls: list[tuple[str, str, object, float]] = []

    def __call__(self, method, url, body, timeout):
        payload = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, url, payload, timeout))
        for suffix, route in self.routes.items():
            if url.endswith(suffix):
                if isinstance(route, BaseException):
                    raise route
                if callable(route):
                    return route(method, url, payload)
                return route
        pytest.fail(f"RoutingTransport: no route for {method} {url}")

    def urls(self, suffix):
        return [call for call in self.calls if call[1].endswith(suffix)]
