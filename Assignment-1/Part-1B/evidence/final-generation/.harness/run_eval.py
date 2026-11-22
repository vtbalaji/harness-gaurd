"""The one evaluation runner for the order extraction agent (contracts/eval-results.md).

    .venv/bin/python .harness/run_eval.py [--env-file PATH]

Steps (research.md R-13): configuration → dataset gate DG-1 … DG-9 → dataset binding (FR-026)
→ environment and pin check (R-11) → every case, sequentially, through the agent → layers 1–3,
each scored by this file's own code (only the schema-file functions of `order_agent.validators`
are shared) → the informational judge → the FR-031 verdict → the evidence folder
`evidence/eval-runs/<UTC stamp>/` and a copy of its `eval-results.json` in `evidence/`.

There are no case filters and no threshold or settings options. Exit codes: 0 PASS, 1 FAIL,
2 INCONCLUSIVE, 3 runner or dataset error (no verdict; `evidence/eval-results.json` untouched).
ACCEPT/REJECT is the owner's decision (FR-034); nothing here records it.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
import traceback
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlsplit

import order_agent
from order_agent import agent, client, config, prompt, validators

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = "evals/dataset.json"
EVIDENCE_DIR = "evidence"
SPEC_PATH = "specs/001-order-extraction-agent/spec.md"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INCONCLUSIVE = 2
EXIT_ERROR = 3

# The one constants table (spec "Evaluation constants (rev 2)", D1; rev 3 adds
# value_in_cr_decimals). Every scoring and verdict function reads its values from here.
SPEC_CONSTANTS = {
    "layer1_threshold": 1.00,
    "layer2_threshold": 1.00,
    "layer3_threshold": 0.80,
    "value_tolerance": 0.005,
    "unit_factor": {
        "crore": 10000000,
        "lakh": 100000,
        "million": 1000000,
        "billion": 1000000000,
        "thousand": 1000,
        "absolute": 1,
    },
    "fx": {"INR": 1, "USD": 84, "EUR": 90},
    "layer3_fields_per_case": 9,
    "max_attempts": 3,
    "min_cases": 18,
    "value_in_cr_decimals": 4,
}

LAYER3_FIELDS = [
    "company",
    "announcement_date",
    "order_value",
    "currency",
    "unit",
    "client",
    "order_type",
    "execution_period",
    "additional_orders",
]

STATUSES = ("extracted", "not_an_order", "needs_clarification", "rejected")
REASONS = ("empty", "whitespace_only", "too_long", "garbled")
CURRENCIES = ("INR", "USD", "EUR", "other")
UNITS = ("crore", "lakh", "million", "billion", "thousand", "absolute")
ORDER_TYPES = ("supply", "epc_construction", "services", "export", "defence", "government", "other")
TOP_KEYS = (
    "schema_version",
    "status",
    "company",
    "announcement_date",
    "order",
    "additional_orders",
    "evidence",
    "missing_fields",
    "unstated_fields",
    "rejection_reason",
)
ORDER_KEYS = (
    "order_value",
    "currency",
    "unit",
    "value_in_cr",
    "client",
    "order_type",
    "execution_period",
)
ADDITIONAL_KEYS = ("order_value", "currency", "unit", "value_in_cr", "client", "evidence")
EVIDENCE_KEYS = (
    "company",
    "announcement_date",
    "order_value",
    "currency",
    "unit",
    "client",
    "order_type",
    "execution_period",
)
ORDER_EVIDENCE_KEYS = EVIDENCE_KEYS[2:]
ADDITIONAL_EVIDENCE_KEYS = ("order_value", "currency", "unit", "client")
REQUIRED_FIELDS = ("order_value", "client")
UNSTATED_ITEMS = ("company", "announcement_date", "order_type", "execution_period")
LEGAL_SUFFIXES = {"limited", "ltd", "private", "pvt", "inc", "llp", "plc", "corp", "co"}

CATEGORIES = (
    "normal_single_order",
    "unit_crore",
    "unit_lakh",
    "unit_million",
    "multiple_orders",
    "multiple_orders_mixed_units",
    "ambiguous_value",
    "ambiguous_non_order",
    "missing_value",
    "missing_client",
    "non_order_results",
    "non_order_board_meeting",
    "malformed_empty",
    "malformed_whitespace",
    "malformed_garbled",
    "malformed_too_long",
    "injection_order",
    "injection_non_order",
    "edge_case",
    "owner_decision",
)
CATEGORY_STATUS = {
    "normal_single_order": "extracted",
    "unit_crore": "extracted",
    "unit_lakh": "extracted",
    "unit_million": "extracted",
    "multiple_orders": "extracted",
    "multiple_orders_mixed_units": "extracted",
    "ambiguous_value": "needs_clarification",
    "missing_value": "needs_clarification",
    "missing_client": "needs_clarification",
    "ambiguous_non_order": "not_an_order",
    "non_order_results": "not_an_order",
    "non_order_board_meeting": "not_an_order",
    "malformed_empty": "rejected",
    "malformed_whitespace": "rejected",
    "malformed_garbled": "rejected",
    "malformed_too_long": "rejected",
}
CATEGORY_REASON = {
    "malformed_empty": "empty",
    "malformed_whitespace": "whitespace_only",
    "malformed_garbled": "garbled",
    "malformed_too_long": "too_long",
}
INV_IDS = tuple(f"INV-{n}" for n in range(1, 12))
# Spec FR-028 code table; EXC is the runner's own code for an agent exception (layer 1).
AGENT_CODE_LAYER = {
    "MR-SCHEMA": 1,
    "MR-CONSIST": 1,
    "OUT-SCHEMA": 1,
    "OUT-DATE": 1,
    "EXC": 1,
    "G-1": 2,
    "G-2": 2,
    "G-3": 2,
    "G-4": 2,
    "G-5": 2,
    "C-1": 2,
    "C-2": 2,
    "C-3": 2,
    "C-4": 2,
    "C-5": 2,
}
LAYER2_AGENT_CODES = tuple(code for code, layer in AGENT_CODE_LAYER.items() if layer == 2)
PIN_TIMEOUT_S = 30
BINDING_LINE = re.compile(r"^DATASET-BINDING dataset_version=(\S+) sha256=([0-9a-f]{64})$")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
FEEDBACK_LINE = "ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it."


# ============================================================================================
# helpers written for the runner alone (they do not come from order_agent.validators)
# ============================================================================================


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_text(value) -> bool:
    return isinstance(value, str) and len(value) > 0


def _ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _canon_digits(value) -> str:
    return format(Decimal(str(value)).normalize(), "f").replace(".", "").lstrip("-")


def _digits(text: str) -> str:
    return re.sub(r"[^0-9]", "", text)


def _strip_punctuation(text: str) -> str:
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))


def layer3_name(name: str) -> str:
    """FR-029 name normalisation (runner's own copy)."""
    text = _ws(_strip_punctuation(name.casefold().replace("&", " and ")))
    tokens = text.split(" ") if text else []
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _period(text: str) -> str:
    return _ws(_strip_punctuation(text.casefold()))


def _orders(result) -> list[tuple[str, dict, dict]]:
    """(pointer, order, evidence) for the top-level order and each additional order."""
    if not isinstance(result, dict):
        return []
    entries = []
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    if isinstance(result.get("order"), dict):
        entries.append(("/order", result["order"], evidence))
    extras = result.get("additional_orders")
    for i, extra in enumerate(extras if isinstance(extras, list) else []):
        if isinstance(extra, dict):
            ev = extra.get("evidence") if isinstance(extra.get("evidence"), dict) else {}
            entries.append((f"/additional_orders/{i}", extra, ev))
    return entries


def _quotes(result) -> list[tuple[str, object]]:
    if not isinstance(result, dict):
        return []
    quotes = []
    evidence = result.get("evidence")
    if isinstance(evidence, dict):
        quotes += [(f"/evidence/{k}", q) for k, q in evidence.items()]
    for pointer, _order, ev in _orders(result):
        if pointer != "/order":
            quotes += [(f"{pointer}/evidence/{k}", q) for k, q in ev.items()]
    return quotes


def _date_error(result) -> str | None:
    date = result.get("announcement_date") if isinstance(result, dict) else None
    if isinstance(date, str) and DATE_PATTERN.fullmatch(date):
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            return f"announcement_date {date!r} is not a calendar date (reading (b))"
    return None


def expand_input(spec: dict) -> bytes:
    """EvaluationCase.input → raw bytes: text, base64, or text + filler cut to `length`."""
    kind = spec["kind"]
    if kind == "text":
        return spec["text"].encode("utf-8")
    if kind == "base64":
        return base64.b64decode(spec["data"], validate=True)
    if kind == "padded":
        text = spec["text"]
        while len(text) < spec["length"]:
            text += spec["filler"]
        return text[: spec["length"]].encode("utf-8")
    raise ValueError(f"unknown input kind {kind!r}")


# ============================================================================================
# runner structural check S-1 … S-11 (data-model.md; FR-027 item 3; E1)
# ============================================================================================


def structural_check(result) -> list[str]:
    """Schema 1.0 restated rule by rule in plain Python. [] means the document passes."""
    errors: list[str] = []

    def err(rule, pointer, message):
        errors.append(f"{rule}: {pointer}: {message}")

    if not isinstance(result, dict):
        err("S-1", "", "the document is not an object")
        return errors
    if set(result) != set(TOP_KEYS):
        missing = sorted(set(TOP_KEYS) - set(result))
        extra = sorted(set(result) - set(TOP_KEYS))
        err("S-1", "", f"keys must be the 10 FR-001 names; missing {missing}, extra {extra}")

    version, status, reason = (
        result.get("schema_version"),
        result.get("status"),
        result.get("rejection_reason"),
    )
    if not (isinstance(version, str) and version == "1.0"):
        err("S-2", "/schema_version", f"must be '1.0', got {version!r}")
    if not (isinstance(status, str) and status in STATUSES):
        err("S-2", "/status", f"not a status: {status!r}")
    if reason is not None and not (isinstance(reason, str) and reason in REASONS):
        err("S-2", "/rejection_reason", f"not a rejection reason: {reason!r}")

    company, date = result.get("company"), result.get("announcement_date")
    if company is not None and not _is_text(company):
        err("S-3", "/company", "must be a non-empty string or null")
    if date is not None:
        if not (isinstance(date, str) and DATE_PATTERN.fullmatch(date)):
            err("S-3", "/announcement_date", f"must be YYYY-MM-DD or null, got {date!r}")
        else:
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                err("S-3", "/announcement_date", f"{date!r} is not a calendar date")

    def value_fields(o, pointer, rule):
        value = o.get("order_value")
        if value is not None and not (_is_number(value) and value > 0):
            err(rule, f"{pointer}/order_value", "must be a number > 0 or null")
        currency = o.get("currency")
        if currency is not None and not (isinstance(currency, str) and currency in CURRENCIES):
            err(rule, f"{pointer}/currency", f"not a currency: {currency!r}")
        unit = o.get("unit")
        if unit is not None and not (isinstance(unit, str) and unit in UNITS):
            err(rule, f"{pointer}/unit", f"not a unit: {unit!r}")
        in_cr = o.get("value_in_cr")
        if in_cr is not None and not _is_number(in_cr):
            err(rule, f"{pointer}/value_in_cr", "must be a number or null")
        name = o.get("client")
        if name is not None and not _is_text(name):
            err(rule, f"{pointer}/client", "must be a non-empty string or null")
        triplet = [o.get("order_value"), o.get("currency"), o.get("unit")]
        if any(v is None for v in triplet) and any(v is not None for v in triplet):
            err("S-5", pointer, "order_value, currency and unit must be all null or all set")
        if "value_in_cr" in o and "currency" in o:
            if o["currency"] == "INR" and not _is_number(in_cr):
                err("S-11", f"{pointer}/value_in_cr", "must be a number for an INR order")
            if o["currency"] != "INR" and in_cr is not None:
                err("S-11", f"{pointer}/value_in_cr", "must be null unless currency is INR")

    order = result.get("order")
    if order is not None:
        if not isinstance(order, dict):
            err("S-4", "/order", "must be an object or null")
        else:
            if set(order) != set(ORDER_KEYS):
                err("S-4", "/order", f"keys must be exactly {list(ORDER_KEYS)}")
            value_fields(order, "/order", "S-4")
            period = order.get("execution_period")
            if period is not None and not _is_text(period):
                err("S-4", "/order/execution_period", "must be a non-empty string or null")
            kind = order.get("order_type")
            if not (isinstance(kind, str) and kind in ORDER_TYPES):
                err("S-4", "/order/order_type", f"not an order type: {kind!r}")

    extras = result.get("additional_orders")
    if not isinstance(extras, list):
        err("S-6", "/additional_orders", "must be a list")
        extras = None
    else:
        for i, extra in enumerate(extras):
            pointer = f"/additional_orders/{i}"
            if not isinstance(extra, dict):
                err("S-6", pointer, "must be an object")
                continue
            if set(extra) != set(ADDITIONAL_KEYS):
                err("S-6", pointer, f"keys must be exactly {list(ADDITIONAL_KEYS)}")
            value_fields(extra, pointer, "S-6")
            ev = extra.get("evidence")
            if not isinstance(ev, dict):
                err("S-6", f"{pointer}/evidence", "must be an object")
                continue
            for key, quote in ev.items():
                if key not in ADDITIONAL_EVIDENCE_KEYS:
                    err("S-6", f"{pointer}/evidence/{key}", "not an additional-order field")
                if not _is_text(quote):
                    err("S-6", f"{pointer}/evidence/{key}", "quote must be a non-empty string")

    evidence = result.get("evidence")
    if not isinstance(evidence, dict):
        err("S-7", "/evidence", "must be an object")
        evidence = None
    else:
        for key, quote in evidence.items():
            if key not in EVIDENCE_KEYS:
                err("S-7", f"/evidence/{key}", "not an FR-010 field")
            if not _is_text(quote):
                err("S-7", f"/evidence/{key}", "quote must be a non-empty string")

    lists = {}
    for key, allowed in (("missing_fields", REQUIRED_FIELDS), ("unstated_fields", UNSTATED_ITEMS)):
        items = result.get(key)
        if not isinstance(items, list):
            err("S-8", f"/{key}", "must be a list")
            continue
        lists[key] = items
        for i, item in enumerate(items):
            if not (isinstance(item, str) and item in allowed):
                err("S-8", f"/{key}/{i}", f"not one of {list(allowed)}")
            elif item in items[:i]:
                err("S-8", f"/{key}/{i}", "duplicate item")
    missing, unstated = lists.get("missing_fields"), lists.get("unstated_fields")

    def shape(condition, pointer, message):
        if not condition:
            err("S-9", pointer, f"{status}: {message} (FR-015)")

    if status in ("extracted", "needs_clarification"):
        shape(isinstance(order, dict), "/order", "order must be an object")
        if missing is not None:
            wanted = missing == [] if status == "extracted" else len(missing) > 0
            shape(wanted, "/missing_fields", "missing_fields has the wrong size")
        shape(reason is None, "/rejection_reason", "rejection_reason must be null")
    elif status == "not_an_order":
        shape(order is None, "/order", "order must be null")
        shape(extras is None or extras == [], "/additional_orders", "must be empty")
        shape(missing is None or missing == [], "/missing_fields", "must be empty")
        shape(
            unstated is None or set(unstated) <= {"company", "announcement_date"},
            "/unstated_fields",
            "only company / announcement_date may be unstated",
        )
        shape(reason is None, "/rejection_reason", "rejection_reason must be null")
    elif status == "rejected":
        shape(company is None, "/company", "must be null")
        shape(date is None, "/announcement_date", "must be null")
        shape(order is None, "/order", "must be null")
        shape(extras is None or extras == [], "/additional_orders", "must be empty")
        shape(evidence is None or evidence == {}, "/evidence", "must be {}")
        shape(missing is None or missing == [], "/missing_fields", "must be empty")
        shape(unstated is None or unstated == [], "/unstated_fields", "must be empty")
        shape(isinstance(reason, str) and reason in REASONS, "/rejection_reason", "needs a reason")

    if (reason is not None) != (status == "rejected"):
        err("S-10", "/rejection_reason", "must be non-null exactly when status is rejected")
    return errors


# ============================================================================================
# FR-035 conversion (INV-11), derived from SPEC_CONSTANTS only (R-17)
# ============================================================================================


def expected_value_in_cr(order: dict) -> Decimal | None:
    """INV-11's own conversion: None unless INR; else order_value × (unit factor ÷ crore
    factor), rounded half up to value_in_cr_decimals places, in exact decimal arithmetic."""
    if order.get("currency") != "INR":
        return None
    factors = SPEC_CONSTANTS["unit_factor"]
    multiplier = Decimal(factors[order["unit"]]) / Decimal(factors["crore"])
    quantum = Decimal(1).scaleb(-SPEC_CONSTANTS["value_in_cr_decimals"])
    exact = Decimal(str(order["order_value"])) * multiplier
    return exact.quantize(quantum, rounding=ROUND_HALF_UP)


def _value_in_cr_matches(actual, expected) -> bool:
    if expected is None:
        return actual is None
    return _is_number(actual) and Decimal(str(actual)) == expected


# ============================================================================================
# dataset gate DG-1 … DG-9 and binding (FR-024 … FR-026)
# ============================================================================================


class DatasetGateError(Exception):
    def __init__(self, rule: str, detail: str):
        super().__init__(f"{rule}: {detail}")
        self.rule = rule
        self.detail = detail


def _require(condition, rule, detail):
    if not condition:
        raise DatasetGateError(rule, detail)


def _dg1(data):
    rule = "DG-1"
    _require(isinstance(data, dict), rule, "the file is not a JSON object")
    _require(
        set(data) == {"dataset_version", "spec_ref", "cases"},
        rule,
        "top-level keys must be dataset_version, spec_ref, cases",
    )
    _require(_is_text(data["dataset_version"]) and _is_text(data["spec_ref"]), rule, "bad header")
    _require(isinstance(data["cases"], list), rule, "cases must be a list")
    case_keys = {
        "id",
        "title",
        "categories",
        "input",
        "ground_truth",
        "expected_properties",
        "covers",
        "provenance",
    }
    input_keys = {
        "text": {"kind", "text"},
        "base64": {"kind", "data"},
        "padded": {"kind", "text", "filler", "length"},
    }
    for i, case in enumerate(data["cases"]):
        where = f"case {i} ({case.get('id') if isinstance(case, dict) else '?'})"
        _require(isinstance(case, dict) and set(case) == case_keys, rule, f"{where}: keys")
        _require(
            isinstance(case["id"], str) and re.fullmatch(r"[A-Z][0-9]{2}", case["id"]),
            rule,
            f"{where}: id must match ^[A-Z][0-9]{{2}}$",
        )
        _require(_is_text(case["title"]), rule, f"{where}: title")
        categories = case["categories"]
        _require(isinstance(categories, list) and categories, rule, f"{where}: categories")
        unknown = [c for c in categories if c not in CATEGORIES]
        _require(not unknown, rule, f"{where}: unknown categories {unknown}")
        spec = case["input"]
        _require(isinstance(spec, dict) and spec.get("kind") in input_keys, rule, f"{where}: input")
        _require(set(spec) == input_keys[spec["kind"]], rule, f"{where}: input keys")
        if spec["kind"] == "base64":
            try:
                base64.b64decode(spec["data"], validate=True)
            except (binascii.Error, TypeError, ValueError):
                raise DatasetGateError(rule, f"{where}: base64 data does not decode") from None
        elif spec["kind"] == "padded":
            _require(
                isinstance(spec["text"], str)
                and _is_text(spec["filler"])
                and isinstance(spec["length"], int)
                and spec["length"] >= 0,
                rule,
                f"{where}: padded input",
            )
        else:
            _require(isinstance(spec["text"], str), rule, f"{where}: text input")
        _require(isinstance(case["ground_truth"], dict), rule, f"{where}: ground_truth")
        props = case["expected_properties"]
        _require(
            isinstance(props, dict)
            and set(props) == {"invariants", "rejection_reason", "injection", "checks"},
            rule,
            f"{where}: expected_properties keys",
        )
        _require(
            isinstance(props["invariants"], list)
            and all(inv in INV_IDS for inv in props["invariants"]),
            rule,
            f"{where}: invariants",
        )
        _require(
            isinstance(props["checks"], list) and all(isinstance(c, str) for c in props["checks"]),
            rule,
            f"{where}: checks",
        )
        injection = props["injection"]
        _require(
            injection is None
            or (
                isinstance(injection, dict)
                and set(injection) == {"counterpart_id", "forbidden_strings", "forbidden_numbers"}
                and isinstance(injection["forbidden_strings"], list)
                and isinstance(injection["forbidden_numbers"], list)
            ),
            rule,
            f"{where}: injection",
        )
        covers = case["covers"]
        _require(
            isinstance(covers, dict)
            and set(covers) == {"fr", "ac"}
            and isinstance(covers["fr"], list)
            and covers["fr"]
            and all(isinstance(x, str) and re.fullmatch(r"FR-\d{3}", x) for x in covers["fr"])
            and isinstance(covers["ac"], list)
            and all(isinstance(x, str) and re.fullmatch(r"AC-\d\.\d", x) for x in covers["ac"]),
            rule,
            f"{where}: covers must list FR and AC ids only, with at least one FR id",
        )
        provenance = case["provenance"]
        _require(
            isinstance(provenance, dict)
            and set(provenance) == {"kind", "note"}
            and provenance["kind"] in ("synthetic", "public")
            and _is_text(provenance["note"]),
            rule,
            f"{where}: provenance",
        )


def _dg2(data):
    cases = data["cases"]
    minimum = SPEC_CONSTANTS["min_cases"]
    _require(len(cases) >= minimum, "DG-2", f"{len(cases)} cases < {minimum} (FR-024)")
    ids = [c["id"] for c in cases]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    _require(not duplicates, "DG-2", f"duplicate ids {duplicates}")


def _dg3(data):
    cases = data["cases"]

    def members(category):
        return [c for c in cases if category in c["categories"]]

    def need(condition, detail):
        _require(condition, "DG-3", detail)

    normal = members("normal_single_order")
    need(len(normal) >= 3, "fewer than 3 normal_single_order cases")
    types = {
        c["ground_truth"]["order"].get("order_type")
        for c in normal
        if isinstance(c["ground_truth"].get("order"), dict)
    }
    need(len(types) >= 3, f"normal single orders span only {len(types)} order types")
    for category in ("unit_crore", "unit_lakh", "unit_million"):
        need(members(category), f"no {category} case")
    need(
        any(
            isinstance(c["ground_truth"].get("order"), dict)
            and c["ground_truth"]["order"].get("currency") in ("USD", "EUR")
            for c in members("unit_million")
        ),
        "no unit_million case in USD or EUR",
    )
    multiple = members("multiple_orders")
    need(len(multiple) >= 2, "fewer than 2 multiple_orders cases")
    need(
        any("multiple_orders_mixed_units" in c["categories"] for c in multiple),
        "no multiple_orders case with mixed units",
    )
    value, non_order = members("ambiguous_value"), members("ambiguous_non_order")
    need(value and non_order, "ambiguous wording needs an ambiguous_value and a non-order case")
    need(len({c["id"] for c in value + non_order}) >= 2, "fewer than 2 ambiguous cases")
    for category in (
        "missing_value",
        "missing_client",
        "non_order_results",
        "non_order_board_meeting",
        "malformed_empty",
        "malformed_whitespace",
        "malformed_garbled",
        "malformed_too_long",
        "injection_order",
        "injection_non_order",
    ):
        need(members(category), f"no {category} case")
    for case in cases:
        gt = case["ground_truth"]
        for category in case["categories"]:
            if category in CATEGORY_STATUS:
                need(
                    gt.get("status") == CATEGORY_STATUS[category],
                    f"{case['id']}: {category} needs status {CATEGORY_STATUS[category]}",
                )
            if category in CATEGORY_REASON:
                need(
                    gt.get("rejection_reason") == CATEGORY_REASON[category],
                    f"{case['id']}: {category} needs reason {CATEGORY_REASON[category]}",
                )
            if category == "injection_order":
                need(
                    gt.get("status") in ("extracted", "needs_clarification"),
                    f"{case['id']}: injection_order needs an order status",
                )
            if category == "injection_non_order":
                need(gt.get("status") == "not_an_order", f"{case['id']}: needs not_an_order")


def _dg9(data):
    orders = []
    for case in data["cases"]:
        for pointer, order, _ev in _orders(case["ground_truth"]):
            where = f"{case['id']}{pointer}"
            _require("value_in_cr" in order, "DG-9", f"{where}: no value_in_cr key")
            try:
                expected = expected_value_in_cr(order)
            except (KeyError, TypeError, ArithmeticError, ValueError) as exc:
                raise DatasetGateError("DG-9", f"{where}: cannot convert: {exc!r}") from None
            _require(
                _value_in_cr_matches(order["value_in_cr"], expected),
                "DG-9",
                f"{where}: value_in_cr {order['value_in_cr']!r} != FR-035 value {expected}",
            )
            orders.append(order)
    _require(any(o.get("currency") == "USD" for o in orders), "DG-9", "no USD order (FR-025)")
    for unit in ("lakh", "million"):
        _require(
            any(o.get("currency") == "INR" and o.get("unit") == unit for o in orders),
            "DG-9",
            f"no INR order in {unit} (FR-025 rev 3)",
        )


def _dg4(data):
    for case in data["cases"]:
        gt = case["ground_truth"]
        schema = [f"{e.code} {e.pointer}: {e.message}" for e in validators.check_output(gt)]
        structural = structural_check(gt)
        _require(
            not schema and not structural,
            "DG-4",
            f"{case['id']}: ground truth is not valid schema 1.0: {schema + structural}",
        )


def _dg5(data):
    by_id = {c["id"]: c for c in data["cases"]}
    for case in data["cases"]:
        injection = case["expected_properties"]["injection"]
        if injection is None:
            continue
        counterpart = by_id.get(injection["counterpart_id"])
        _require(counterpart is not None, "DG-5", f"{case['id']}: counterpart missing")
        _require(
            counterpart["ground_truth"].get("status") == case["ground_truth"].get("status"),
            "DG-5",
            f"{case['id']}: counterpart has a different ground-truth status",
        )
        _require(
            injection["forbidden_strings"] and injection["forbidden_numbers"],
            "DG-5",
            f"{case['id']}: forbidden_strings and forbidden_numbers must be non-empty",
        )


def _dg6(data):
    for case in data["cases"]:
        _require(
            case["expected_properties"]["rejection_reason"]
            == case["ground_truth"].get("rejection_reason"),
            "DG-6",
            f"{case['id']}: expected rejection_reason differs from the ground truth",
        )


def _dg7(data):
    for case in data["cases"]:
        count = len(_orders(case["ground_truth"]))
        _require(count <= 4, "DG-7", f"{case['id']}: {count} orders > 4 (P-3)")


def _dg8(data):
    for case in data["cases"]:
        listed = case["expected_properties"]["invariants"]
        expected = applicable_invariants(case, case["ground_truth"])
        _require(
            set(listed) == set(expected) and len(listed) == len(set(listed)),
            "DG-8",
            f"{case['id']}: invariants {sorted(listed)} != applicable {expected}",
        )


# DG-9 runs before DG-4 so that a value_in_cr error is reported as such.
_GATE = (
    ("DG-1", _dg1),
    ("DG-2", _dg2),
    ("DG-3", _dg3),
    ("DG-9", _dg9),
    ("DG-4", _dg4),
    ("DG-5", _dg5),
    ("DG-6", _dg6),
    ("DG-7", _dg7),
    ("DG-8", _dg8),
)


def load_dataset(path) -> tuple[dict, str]:
    """Enforce DG-1 … DG-9. Returns (dataset, SHA-256 of the raw bytes)."""
    raw = Path(path).read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DatasetGateError("DG-1", f"not valid UTF-8 JSON: {exc}") from None
    for rule, check in _GATE:
        try:
            check(data)
        except DatasetGateError:
            raise
        except (KeyError, TypeError, AttributeError, ValueError, IndexError) as exc:
            raise DatasetGateError(rule, f"malformed: {type(exc).__name__}: {exc}") from None
    return data, sha256


def bound_dataset(spec_path) -> tuple[str, str] | None:
    """FR-026 (rev 2): (dataset_version, sha256) of the last DATASET-BINDING line, or None."""
    try:
        text = Path(spec_path).read_text(encoding="utf-8")
    except OSError:
        return None
    bound = None
    for line in text.splitlines():
        match = BINDING_LINE.match(line)
        if match:
            bound = (match[1], match[2])
    return bound


# ============================================================================================
# layer 2 invariants INV-1 … INV-11 (FR-028), written for the runner alone
# ============================================================================================


@dataclass
class CaseContext:
    case: dict
    candidate: dict
    source: str
    model_called: bool
    counterpart: dict | None


def make_context(case, candidate, *, model_called=True, counterpart=None) -> CaseContext:
    source = expand_input(case["input"]).decode("utf-8", "replace")
    return CaseContext(case, candidate, source, model_called, counterpart)


def _join(problems):
    return "; ".join(problems) or None


def _inv1(ctx):
    problems = [
        f"{e.code} {e.pointer}: {e.message}" for e in validators.check_output(ctx.candidate)
    ]
    problems += structural_check(ctx.candidate)
    date_error = _date_error(ctx.candidate)
    if date_error:
        problems.append(date_error)
    return _join(problems)


def _inv2(ctx):
    source = _ws(ctx.source)
    return _join(
        [
            f"{pointer}: quote not in the source"
            for pointer, quote in _quotes(ctx.candidate)
            if not (isinstance(quote, str) and _ws(quote) in source)
        ]
    )


def _inv3(ctx):
    problems = []
    for pointer, order, evidence in _orders(ctx.candidate):
        value = order.get("order_value")
        if value is None:
            continue
        quote = evidence.get("order_value")
        if not isinstance(quote, str):
            problems.append(f"{pointer}: no order_value quote")
        elif not _is_number(value) or _canon_digits(value) not in _digits(quote):
            problems.append(f"{pointer}: digits of {value!r} not in {quote!r}")
    return _join(problems)


def _inv4(ctx):
    source = _ws(ctx.source)
    problems = []
    for pointer, order, evidence in _orders(ctx.candidate):
        name = order.get("client")
        if name is None:
            continue
        quote = evidence.get("client")
        if not isinstance(quote, str) or not isinstance(name, str):
            problems.append(f"{pointer}: no client quote")
        elif _ws(quote) not in source:
            problems.append(f"{pointer}: client quote not in the source")
        elif _ws(name).casefold() not in _ws(quote).casefold():
            problems.append(f"{pointer}: client {name!r} not in its quote {quote!r}")
    return _join(problems)


def _inv5(ctx):
    gt, cand = ctx.case["ground_truth"], ctx.candidate
    problems = []
    if cand.get("status") != gt["status"]:
        problems.append(f"status {cand.get('status')!r} != expected {gt['status']!r}")
    if gt["status"] == "rejected":
        if cand.get("rejection_reason") != gt["rejection_reason"]:
            problems.append(f"rejection_reason {cand.get('rejection_reason')!r} != expected")
        if ctx.model_called:
            problems.append("a model call was made for a rejected input")
    return _join(problems)


def _inv6(ctx):
    order = ctx.candidate.get("order")
    expected = (
        {f for f in REQUIRED_FIELDS if order.get(f) is None} if isinstance(order, dict) else set()
    )
    listed = ctx.candidate.get("missing_fields")
    actual = (
        set(listed)
        if isinstance(listed, list) and all(isinstance(x, str) for x in listed)
        else None
    )
    if actual != expected:
        return f"missing_fields {listed!r} != {sorted(expected)}"
    return None


def _walk(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield value


def _inv7(ctx):
    injection = ctx.case["expected_properties"]["injection"]
    problems = []
    if ctx.counterpart is None:
        problems.append("the clean counterpart is missing")
    elif ctx.candidate.get("status") != ctx.counterpart["ground_truth"]["status"]:
        problems.append("status differs from the clean counterpart's")
    values = list(_walk(ctx.candidate))
    texts = [_ws(v).casefold() for v in values if isinstance(v, str)]
    for forbidden in injection["forbidden_strings"]:
        needle = _ws(forbidden).casefold()
        if any(needle in text for text in texts):
            problems.append(f"injected value {forbidden!r} appears in the output")
    numbers = [v for v in values if _is_number(v)]
    for forbidden in injection["forbidden_numbers"]:
        if any(v == forbidden for v in numbers):
            problems.append(f"injected number {forbidden!r} appears in the output")
    return _join(problems)


def _inv8(ctx):
    cand = ctx.candidate
    problems = []
    evidence = cand.get("evidence") if isinstance(cand.get("evidence"), dict) else {}
    expected = {f for f in ("company", "announcement_date") if cand.get(f) is not None}
    if isinstance(cand.get("order"), dict):
        expected |= {f for f in ORDER_EVIDENCE_KEYS if cand["order"].get(f) is not None}
    if set(evidence) != expected:
        problems.append(f"/evidence keys {sorted(evidence)} != non-null fields {sorted(expected)}")
    for pointer, order, ev in _orders(cand):
        if pointer == "/order":
            continue
        wanted = {f for f in ADDITIONAL_EVIDENCE_KEYS if order.get(f) is not None}
        if set(ev) != wanted:
            problems.append(f"{pointer}/evidence keys {sorted(ev)} != {sorted(wanted)}")
    return _join(problems)


def _base_value(order) -> Decimal:
    factor = SPEC_CONSTANTS["unit_factor"][order["unit"]]
    rate = SPEC_CONSTANTS["fx"][order["currency"]]
    return Decimal(str(order["order_value"])) * Decimal(factor) * Decimal(rate)


def _inv9(ctx):
    rated = tuple(SPEC_CONSTANTS["fx"])
    entries = _orders(ctx.candidate)
    top = ctx.candidate.get("order") if isinstance(ctx.candidate.get("order"), dict) else None
    extras = [order for pointer, order, _ev in entries if pointer != "/order"]
    if top is None:
        return "additional orders without a top-level order" if extras else None
    problems = []
    for i, extra in enumerate(extras):
        if extra.get("currency") in rated and extra.get("order_value") is not None:  # (i)
            if top.get("currency") not in rated or top.get("order_value") is None:
                problems.append(f"(i) additional order {i} is valued but the top level is not")
            elif _base_value(top) < _base_value(extra):
                problems.append(f"(i) additional order {i} ranks above the top-level order")
    # (ii) never compares an `other` order: schema 1.0 cannot carry a convertible equivalent.
    if top.get("currency") == "other":  # (iii)
        valued = [o for _p, o, _e in entries if o.get("order_value") is not None]
        if len(valued) != 1:
            problems.append(
                "(iii) the top-level order is in `other` but is not the only valued one"
            )
    return _join(problems)


def _inv10(ctx):
    cand = ctx.candidate
    expected = {f for f in ("company", "announcement_date") if cand.get(f) is None}
    if isinstance(cand.get("order"), dict):
        expected |= {f for f in ("order_type", "execution_period") if cand["order"].get(f) is None}
    listed = cand.get("unstated_fields")
    actual = (
        set(listed)
        if isinstance(listed, list) and all(isinstance(x, str) for x in listed)
        else None
    )
    if actual != expected:
        return f"unstated_fields {listed!r} != {sorted(expected)}"
    return None


def _inv11(ctx):
    problems = []
    for pointer, order, _ev in _orders(ctx.candidate):
        if "value_in_cr" not in order:
            problems.append(f"{pointer}: no value_in_cr key")
            continue
        try:
            expected = expected_value_in_cr(order)
        except (KeyError, TypeError, ArithmeticError, ValueError) as exc:
            problems.append(f"{pointer}: cannot compute the FR-035 value: {exc!r}")
            continue
        if not _value_in_cr_matches(order["value_in_cr"], expected):
            problems.append(
                f"{pointer}: value_in_cr {order['value_in_cr']!r} != FR-035 value {expected}"
            )
    return _join(problems)


INVARIANTS = {
    "INV-1": _inv1,
    "INV-2": _inv2,
    "INV-3": _inv3,
    "INV-4": _inv4,
    "INV-5": _inv5,
    "INV-6": _inv6,
    "INV-7": _inv7,
    "INV-8": _inv8,
    "INV-9": _inv9,
    "INV-10": _inv10,
    "INV-11": _inv11,
}


def applicable_invariants(case, candidate) -> list[str]:
    """The spec's "Applies to" column, over the candidate and the ground truth (R-13)."""
    docs = [d for d in (candidate, case["ground_truth"]) if isinstance(d, dict)]

    def any_doc(predicate):
        return any(predicate(doc) for doc in docs)

    applicable = {"INV-1", "INV-5", "INV-6"}
    if any_doc(lambda d: bool(_quotes(d))):
        applicable.add("INV-2")
    if any_doc(lambda d: any(o.get("order_value") is not None for _p, o, _e in _orders(d))):
        applicable.add("INV-3")
    if any_doc(lambda d: any(o.get("client") is not None for _p, o, _e in _orders(d))):
        applicable.add("INV-4")
    if case["expected_properties"]["injection"] is not None:
        applicable.add("INV-7")
    if any_doc(lambda d: d.get("status") != "rejected"):
        applicable |= {"INV-8", "INV-10"}
    if any_doc(lambda d: isinstance(d.get("additional_orders"), list) and d["additional_orders"]):
        applicable.add("INV-9")
    if any_doc(lambda d: isinstance(d.get("order"), dict)):
        applicable.add("INV-11")
    return [inv for inv in INV_IDS if inv in applicable]


# ============================================================================================
# per-case scoring
# ============================================================================================


def _candidate(outcome):
    if isinstance(outcome, agent.Success):
        return outcome.result
    if isinstance(outcome, agent.ApplicationFailure):
        return outcome.candidate
    return None


def _model_called(outcome) -> bool:
    if isinstance(outcome, agent.Success):
        return bool(outcome.model_called)
    return bool(getattr(outcome, "attempts", []))


def _agent_errors(outcome) -> list[dict]:
    errors = getattr(outcome, "errors", None) or []
    out = []
    for error in errors:
        code = getattr(error, "code", None)
        layer = AGENT_CODE_LAYER.get(code, getattr(error, "layer", 1))
        out.append(
            {
                "code": code,
                "pointer": getattr(error, "pointer", ""),
                "message": getattr(error, "message", ""),
                "layer": layer,
            }
        )
    return out


def score_layer1(case, outcome) -> dict:
    """FR-027 (rev 2) items 1–5: candidate, schema file, structural check, calendar date,
    no agent layer-1 code."""
    candidate = _candidate(outcome)
    agent_l1 = [e for e in _agent_errors(outcome) if e["layer"] == 1]
    if candidate is None:
        return {
            "pass": False,
            "has_candidate": False,
            "schema_errors": [],
            "structural_errors": [],
            "date_error": None,
            "agent_errors": agent_l1,
            "checker_disagreement": False,
        }
    schema = [f"{e.code} {e.pointer}: {e.message}" for e in validators.check_output(candidate)]
    structural = structural_check(candidate)
    date_error = _date_error(candidate)
    return {
        "pass": not (schema or structural or date_error or agent_l1),
        "has_candidate": True,
        "schema_errors": schema,
        "structural_errors": structural,
        "date_error": date_error,
        "agent_errors": agent_l1,
        "checker_disagreement": bool(schema) != bool(structural),
    }


def score_layer2(case, outcome, counterpart=None) -> dict:
    """FR-028 (rev 2): candidate present, every applicable INV holds (runner's own code), and
    no agent layer-2 code (reading (a))."""
    candidate = _candidate(outcome)
    agent_l2 = [e for e in _agent_errors(outcome) if e["layer"] == 2]
    applicable = applicable_invariants(case, candidate)
    if candidate is None:
        return {
            "pass": False,
            "applicable": applicable,
            "failed": [{"inv": "INV-1", "detail": "no candidate (FR-028 item 1)"}],
            "agent_errors": agent_l2,
        }
    context = make_context(
        case, candidate, model_called=_model_called(outcome), counterpart=counterpart
    )
    failed = []
    for inv in applicable:
        try:
            detail = INVARIANTS[inv](context)
        except Exception as exc:  # a malformed candidate must fail, never crash the run
            detail = f"check raised {type(exc).__name__}: {exc}"
        if detail:
            failed.append({"inv": inv, "detail": detail})
    return {
        "pass": not failed and not agent_l2,
        "applicable": applicable,
        "failed": failed,
        "agent_errors": agent_l2,
    }


def _field(doc, name):
    if not isinstance(doc, dict):
        return None
    if name in ("company", "announcement_date"):
        return doc.get(name)
    if name == "additional_orders":
        extras = doc.get("additional_orders")
        return len(extras) if isinstance(extras, list) else None
    order = doc.get("order")
    return order.get(name) if isinstance(order, dict) else None


def _value_correct(candidate, gt) -> bool:
    expected, actual = _field(gt, "order_value"), _field(candidate, "order_value")
    if expected is None:
        return actual is None
    if not _is_number(actual) or _field(candidate, "currency") != _field(gt, "currency"):
        return False
    factors = SPEC_CONSTANTS["unit_factor"]
    unit_a, unit_e = _field(candidate, "unit"), _field(gt, "unit")
    if unit_a not in factors or unit_e not in factors:
        return False
    base_a = Decimal(str(actual)) * Decimal(factors[unit_a])
    base_e = Decimal(str(expected)) * Decimal(factors[unit_e])
    return abs(base_a - base_e) <= Decimal(str(SPEC_CONSTANTS["value_tolerance"])) * base_e


def _compare(field, candidate, gt):
    expected, actual = _field(gt, field), _field(candidate, field)
    if field == "order_value":
        return _value_correct(candidate, gt), "base units within value_tolerance, same currency"
    if expected is None:
        return actual is None, "null in ground truth: correct only if null"
    if field in ("company", "client"):
        same = isinstance(actual, str) and layer3_name(actual) == layer3_name(expected)
        return same, "FR-029 name normalisation"
    if field == "execution_period":
        return isinstance(actual, str) and _period(actual) == _period(expected), "normalised text"
    if field == "additional_orders":
        return actual == expected, "same count"
    return isinstance(actual, str) and actual == expected, "exact"


def score_layer3(case, candidate) -> dict | None:
    """FR-029 (rev 2): nine fields per extracted / needs_clarification case; no candidate scores
    0 of 9 (reading (c)). unstated_fields and value_in_cr are not compared."""
    gt = case["ground_truth"]
    if gt["status"] not in ("extracted", "needs_clarification"):
        return None
    fields = {}
    for field in LAYER3_FIELDS:
        if candidate is None:
            correct, rule = False, "no candidate: 0 of 9 (reading (c))"
        else:
            correct, rule = _compare(field, candidate, gt)
        fields[field] = {
            "expected": _field(gt, field),
            "actual": _field(candidate, field),
            "correct": bool(correct),
            "rule": rule,
        }
    correct_count = sum(1 for f in fields.values() if f["correct"])
    return {"fields": fields, "correct": correct_count, "compared": len(LAYER3_FIELDS)}


# ============================================================================================
# verdict (FR-031 rev 2), a pure function with no judge or binding input
# ============================================================================================


def verdict(pin_ok, case_summaries, layer3_score) -> tuple[str, str, str]:
    if not pin_ok:
        return (
            "INCONCLUSIVE",
            "1-pin-check",
            "The pin check failed, so the model and runner identity cannot be confirmed.",
        )
    processed = [s for s in case_summaries if s["processed"]]

    def listing(cases):
        return ", ".join(
            f"{s['case_id']} ({', '.join(s['checks']) or 'see feedback'})" for s in cases
        )

    l1_failed = [s for s in processed if not s["l1_pass"]]
    l2_failed = [s for s in processed if not s["l2_pass"]]
    if l1_failed or l2_failed:
        parts = []
        if l1_failed:
            parts.append(f"Layer 1 failed for {len(l1_failed)} case(s): {listing(l1_failed)}")
        if l2_failed:
            parts.append(f"Layer 2 failed for {len(l2_failed)} case(s): {listing(l2_failed)}")
        return "FAIL", "2-app-failure", "; ".join(parts) + "."
    unresolved = [s["case_id"] for s in case_summaries if not s["processed"]]
    if unresolved:
        return (
            "INCONCLUSIVE",
            "3-service-failure",
            f"{len(unresolved)} case(s) still have a service failure after retries: "
            f"{', '.join(unresolved)}.",
        )
    total = len(case_summaries)
    l1 = sum(1 for s in case_summaries if s["l1_pass"]) / total if total else 0.0
    l2 = sum(1 for s in case_summaries if s["l2_pass"]) / total if total else 0.0
    l3_met = layer3_score is not None and layer3_score >= SPEC_CONSTANTS["layer3_threshold"]
    if (
        l1 >= SPEC_CONSTANTS["layer1_threshold"]
        and l2 >= SPEC_CONSTANTS["layer2_threshold"]
        and l3_met
    ):
        return (
            "PASS",
            "4-thresholds-met",
            f"Layers 1 and 2 are at 100% and layer 3 is {layer3_score:.1%} "
            f"(threshold {SPEC_CONSTANTS['layer3_threshold']:.0%}).",
        )
    shown = "n/a" if layer3_score is None else f"{layer3_score:.1%}"
    return (
        "FAIL",
        "5-thresholds-not-met",
        f"Layer 3 is {shown}, below the {SPEC_CONSTANTS['layer3_threshold']:.0%} threshold.",
    )


# ============================================================================================
# environment and pin check (R-11; FR-031 step 1, reading (e))
# ============================================================================================


def _pip_freeze() -> list[str]:
    names = set()
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if name:
            names.add(f"{name}=={dist.version}")
    return sorted(names, key=str.lower)


def _git_head(start: Path) -> str | None:
    """git HEAD read from the .git directory (no subprocess)."""
    for directory in (start, *start.parents):
        git = directory / ".git"
        if not git.is_dir():
            continue
        try:
            head = (git / "HEAD").read_text(encoding="utf-8").strip()
            if not head.startswith("ref: "):
                return head
            ref = head[5:]
            if (git / ref).is_file():
                return (git / ref).read_text(encoding="utf-8").strip()
            packed = git / "packed-refs"
            if packed.is_file():
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        return line.split(" ", 1)[0]
        except OSError:
            return None
        return None
    return None


def check_environment(settings, transport) -> tuple[dict, dict]:
    """Collect the runner identity and check the five FR-031 step 1 conditions."""
    mismatches: list[str] = []
    base = settings.ollama_url.rstrip("/")

    def fetch(path, payload=None):
        try:
            if payload is None:
                return client.get_json(base + path, timeout=PIN_TIMEOUT_S, transport=transport)
            return client.post_json(
                base + path, payload, timeout=PIN_TIMEOUT_S, transport=transport
            )
        except client.ServiceError as exc:
            mismatches.append(f"request_failed: {path} {exc.kind}: {exc.detail}")
        except Exception as exc:  # the pins cannot be confirmed either way
            mismatches.append(f"request_failed: {path} exception: {type(exc).__name__}: {exc}")
        return None

    version = digest = quant = None
    reply = fetch("/api/version")
    if reply is not None:
        version = reply.get("version")
        if version != config.PINNED_RUNNER_VERSION:
            mismatches.append(
                f"ollama_version: installed {version!r} != pinned {config.PINNED_RUNNER_VERSION}"
            )
    reply = fetch("/api/tags")
    if reply is not None:
        models = reply.get("models") if isinstance(reply.get("models"), list) else []
        entry = next(
            (
                m
                for m in models
                if isinstance(m, dict) and config.PINNED_MODEL in (m.get("name"), m.get("model"))
            ),
            None,
        )
        if entry is None:
            mismatches.append(f"model_digest: tag {config.PINNED_MODEL} is not installed")
        else:
            digest = entry.get("digest")
            if not (isinstance(digest, str) and digest.startswith(config.PINNED_MODEL_DIGEST)):
                mismatches.append(
                    f"model_digest: installed {digest!r} does not start with pinned "
                    f"{config.PINNED_MODEL_DIGEST}"
                )
    reply = fetch("/api/show", {"model": config.PINNED_MODEL})
    if reply is not None:
        details = reply.get("details") if isinstance(reply.get("details"), dict) else {}
        quant = details.get("quantization_level")
        if quant != config.PINNED_QUANT:
            mismatches.append(f"quantization: installed {quant!r} != pinned {config.PINNED_QUANT}")
    env_mismatch = config.pin_mismatches(settings)
    mismatches += [f"env_mismatch: {m}" for m in env_mismatch]
    environment = {
        "ollama_url_host": urlsplit(settings.ollama_url).netloc,
        "ollama_version": version,
        "model": {
            "tag": config.PINNED_MODEL,
            "digest_pinned": config.PINNED_MODEL_DIGEST,
            "digest_installed": digest,
        },
        "runner": {
            "name": "ollama",
            "version_pinned": config.PINNED_RUNNER_VERSION,
            "version_installed": version,
        },
        "quantization_level": quant,
        "quantization_pinned": config.PINNED_QUANT,
        "env_mismatch": env_mismatch,
        "python_version": platform.python_version(),
        "pip_freeze": _pip_freeze(),
        "git_head": _git_head(ROOT),
        "platform": platform.platform(),
        "judge": {"url_host": urlsplit(settings.judge_url).netloc, "model": settings.judge_model},
    }
    return environment, {"ok": not mismatches, "mismatches": mismatches}


# ============================================================================================
# orchestration and writers (R-13, R-15; contracts/eval-results.md)
# ============================================================================================


@dataclass
class _RunnerError:
    """The runner's own EXC error (it does not import the agent's ValidationError)."""

    code: str
    pointer: str
    message: str
    layer: int


def _write_json(path: Path, obj) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def _iso(moment: datetime.datetime) -> str:
    return moment.astimezone(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _attempt_summary(attempt) -> dict:
    if hasattr(attempt, "to_dict"):
        return attempt.to_dict()
    return dict(attempt)


def _raw_attempt(attempt, bundle) -> dict:
    request = dict(getattr(attempt, "request", {}) or {})
    if bundle is not None:
        request.update(system=bundle.system, prompt=bundle.prompt)
    return {
        "n": attempt.n,
        "request": request,
        "response": {
            "http_status": attempt.http_status,
            "body": getattr(attempt, "response_body", None),
            "raw_text": attempt.raw_text,
        },
        "timing": {
            "started_at": attempt.started_at,
            "ended_at": attempt.ended_at,
            "elapsed_s": attempt.elapsed_s,
        },
        "outcome": attempt.outcome,
        "service_failure_kind": attempt.service_failure_kind,
        "error": attempt.error,
        "envelope": attempt.envelope,
    }


def _code_sha256() -> dict:
    files = {
        "src/order_agent/validators.py": Path(order_agent.__file__).with_name("validators.py"),
        ".harness/run_eval.py": Path(__file__),
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}


def _settings_record(settings) -> dict:
    return {
        "temperature": settings.temperature,
        "seed": settings.seed,
        "num_predict": settings.num_predict,
        "think": settings.think,
        "format": settings.format,
        "stream": False,
        "timeout_s": settings.timeout_s,
        "num_ctx_formula": config.NUM_CTX_FORMULA,
        "max_attempts": settings.max_attempts,
        "backoff_s": list(settings.backoff_s),
    }


def _judge_record(settings) -> dict:
    return {
        "url_host": urlsplit(settings.judge_url).netloc,
        "model": settings.judge_model,
        "temperature": 0,
        "max_tokens": config.JUDGE_MAX_TOKENS,
        "timeout_s": config.JUDGE_TIMEOUT_S,
        "disable_thinking": config.JUDGE_DISABLE_THINKING,
    }


def _new_run_dir(root: Path, stamp: str) -> tuple[str, Path]:
    runs = root / EVIDENCE_DIR / "eval-runs"
    run_id, n = stamp, 1
    while (runs / run_id).exists():
        n += 1
        run_id = f"{stamp}-{n}"
    (runs / run_id).mkdir(parents=True)
    return run_id, runs / run_id


def _checks(layer1, layer2, agent_errors) -> list[str]:
    checks = []
    for error in agent_errors:
        if error["code"] not in checks:
            checks.append(error["code"])
    if not layer1["pass"]:
        if not layer1["has_candidate"] and not checks:
            checks.append("L1-no-candidate")
        if layer1["schema_errors"]:
            checks.append("L1-schema")
        if layer1["structural_errors"]:
            checks.append("L1-structural")
        if layer1["date_error"]:
            checks.append("L1-date")
    if layer1["has_candidate"]:
        checks += [f["inv"] for f in layer2["failed"] if f["inv"] not in checks]
    return checks


def _feedback(record, case, run_id) -> dict:
    """FR-032, constitution VII: one structured record per failing case."""
    outcome = record["outcome_obj"]
    layers, failed = [], []
    layer1, layer2, layer3 = record["layer1"], record["layer2"], record["layer3"]
    if record["scored"]:
        if not layer1["pass"]:
            layers.append(1)
            failed += [{"id": "L1-schema", "detail": d} for d in layer1["schema_errors"]]
            failed += [{"id": "L1-structural", "detail": d} for d in layer1["structural_errors"]]
            if layer1["date_error"]:
                failed.append({"id": "L1-date", "detail": layer1["date_error"]})
            if not layer1["has_candidate"]:
                failed.append({"id": "L1-no-candidate", "detail": f"stage {record['stage']}"})
        if not layer2["pass"]:
            layers.append(2)
            failed += [{"id": f["inv"], "detail": f["detail"]} for f in layer2["failed"]]
        failed += [{"id": e["code"], "detail": e["message"]} for e in record["agent_errors"]]
        if (
            layer3 is not None
            and layer3["correct"] < layer3["compared"]
            and layer1["pass"]
            and layer2["pass"]
        ):
            layers.append(3)
        if layer3 is not None:
            failed += [
                {"id": f"L3:{name}", "detail": f"expected {f['expected']!r}, got {f['actual']!r}"}
                for name, f in layer3["fields"].items()
                if not f["correct"] and record["candidate"] is not None
            ]
    else:
        layers.append("service")
        failed.append({"id": "service", "detail": f"unresolved {outcome.last_kind}"})
    attempts = record["attempts"]
    raw_output = getattr(outcome, "raw_text", None)
    if raw_output is None and attempts:
        raw_output = attempts[-1].get("raw_text")
    if record["exception"]:
        exc = record["exception"]
        reason = f"The agent raised {exc['type']}: {exc['message']} while processing this case."
        raw_output = None
    elif not record["scored"]:
        reason = f"Unresolved model service failure ({outcome.last_kind}) after all attempts."
    elif 1 in layers or 2 in layers:
        reason = "Failed " + " and ".join(f"layer {n}" for n in layers if n in (1, 2)) + ": "
        reason += ", ".join(record["checks"]) + "."
    else:
        wrong = [n for n, f in layer3["fields"].items() if not f["correct"]]
        reason = f"Semantic miss only: wrong layer-3 field(s) {', '.join(wrong)}."
    return {
        "case_id": case["id"],
        "layers_failed": layers,
        "failed_checks": failed,
        "expected": case["ground_truth"],
        "actual": record["candidate"],
        "raw_model_output": raw_output,
        "parser_log": record["parser_log"],
        "agent_errors": record["agent_errors"],
        "reason": reason,
        "attempts": attempts,
        "run_id": run_id,
    }


def _case_record(case, outcome, exception, counterpart) -> dict:
    scored = not isinstance(outcome, agent.ServiceFailure)
    candidate = _candidate(outcome)
    layer1 = score_layer1(case, outcome)
    layer2 = score_layer2(case, outcome, counterpart)
    if not scored:
        layer1["pass"] = False
        layer2["pass"] = False
    layer3 = score_layer3(case, candidate)
    agent_errors = _agent_errors(outcome)
    if isinstance(outcome, agent.Success):
        kind = "success"
    elif isinstance(outcome, agent.ApplicationFailure):
        kind = "application_failure"
    else:
        kind = "service_failure"
    return {
        "case_id": case["id"],
        "categories": case["categories"],
        "covers": case["covers"],
        "outcome": kind,
        "stage": getattr(outcome, "stage", None),
        "exception": exception,
        "model_called": _model_called(outcome),
        "attempts": [_attempt_summary(a) for a in getattr(outcome, "attempts", [])],
        "candidate": candidate,
        "agent_errors": agent_errors,
        "parser_log": getattr(outcome, "parser_log", []) or [],
        "assembly_trace": getattr(outcome, "assembly_trace", None),
        "scored": scored,
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3,
        "judge": {"status": "not_applicable"},
        "checks": _checks(layer1, layer2, agent_errors),
        "outcome_obj": outcome,
    }


_PUBLIC_CASE_KEYS = (
    "case_id",
    "categories",
    "covers",
    "outcome",
    "stage",
    "exception",
    "model_called",
    "attempts",
    "candidate",
    "agent_errors",
    "parser_log",
    "assembly_trace",
    "scored",
    "layer1",
    "layer2",
    "layer3",
    "judge",
)


def _judge_case(settings, case, record, transport, sleep):
    source = expand_input(case["input"]).decode("utf-8", "replace")
    try:
        result = client.judge(
            settings, source, record["candidate"], transport=transport, sleep=sleep
        )
    except Exception as exc:  # second line of defence (R-12, U1)
        result = client.JudgeResult(
            "failed", None, None, "exception", f"{type(exc).__name__}: {exc}"
        )
    return result


def _results(run_id, records, pin_check, dataset_info, run_record, verdict_tuple, settings):
    by_id = {r["case_id"]: r for r in records}
    not_scored = [r["case_id"] for r in records if not r["scored"]]
    total = len(records)

    def layer_block(layer):
        passed = sum(1 for r in records if r[layer]["pass"])
        threshold = SPEC_CONSTANTS[f"{layer}_threshold"]
        score = passed / total if total else 0.0
        return {
            "passed": passed,
            "total": total,
            "score": score,
            "threshold": threshold,
            "met": score >= threshold,
            "failed_cases": [r["case_id"] for r in records if r["scored"] and not r[layer]["pass"]],
            "not_scored": not_scored,
        }

    layer1 = layer_block("layer1")
    layer1["checker_disagreements"] = [
        r["case_id"] for r in records if r["layer1"]["checker_disagreement"]
    ]
    layer2 = layer_block("layer2")
    layer2["by_invariant"] = {
        inv: {
            "applicable": sum(
                1 for r in records if r["scored"] and inv in r["layer2"]["applicable"]
            ),
            "failed": sum(
                1
                for r in records
                if r["scored"]
                and r["candidate"] is not None
                and any(f["inv"] == inv for f in r["layer2"]["failed"])
            ),
        }
        for inv in INV_IDS
    }
    layer2["by_agent_code"] = {
        code: sum(1 for r in records for e in r["agent_errors"] if e["code"] == code)
        for code in LAYER2_AGENT_CODES
    }
    l3_records = [r for r in records if r["layer3"] is not None]
    correct = sum(r["layer3"]["correct"] for r in l3_records)
    compared = sum(r["layer3"]["compared"] for r in l3_records)
    layer3_score = correct / compared if compared else None
    layer3 = {
        "correct": correct,
        "compared": compared,
        "score": layer3_score,
        "threshold": SPEC_CONSTANTS["layer3_threshold"],
        "met": layer3_score is not None and layer3_score >= SPEC_CONSTANTS["layer3_threshold"],
        "by_field": {
            field: {
                "correct": sum(1 for r in l3_records if r["layer3"]["fields"][field]["correct"]),
                "compared": len(l3_records),
            }
            for field in LAYER3_FIELDS
        },
        "cases": len(l3_records),
        "not_scored": [r["case_id"] for r in l3_records if not r["scored"]],
    }
    app_cases = [
        {
            "case_id": r["case_id"],
            "layers": [n for n, layer in ((1, "layer1"), (2, "layer2")) if not r[layer]["pass"]],
            "checks": r["checks"],
            "stage": r["stage"],
            "feedback": f"feedback/{r['case_id']}.json",
        }
        for r in records
        if r["scored"] and not (r["layer1"]["pass"] and r["layer2"]["pass"])
    ]
    misses = [
        {
            "case_id": r["case_id"],
            "fields": [n for n, f in r["layer3"]["fields"].items() if not f["correct"]],
            "feedback": f"feedback/{r['case_id']}.json",
        }
        for r in records
        if r["scored"]
        and r["layer1"]["pass"]
        and r["layer2"]["pass"]
        and r["layer3"] is not None
        and r["layer3"]["correct"] < r["layer3"]["compared"]
    ]
    failed_attempts = [
        {"case_id": r["case_id"], "n": a["n"], "kind": a["service_failure_kind"]}
        for r in records
        for a in r["attempts"]
        if a.get("outcome") == "service_failure"
    ]
    unresolved = [
        {"case_id": r["case_id"], "kind": r["outcome_obj"].last_kind}
        for r in records
        if not r["scored"]
    ]
    judged = [r for r in records if r["judge"]["status"] != "not_applicable"]
    ratings = [
        {
            "case_id": r["case_id"],
            "rating": r["judge"]["rating"],
            "rationale": r["judge"]["rationale"],
        }
        for r in judged
        if r["judge"]["status"] == "ok"
    ]
    judge_failures = [
        {"case_id": r["case_id"], "kind": r["judge"]["kind"]}
        for r in judged
        if r["judge"]["status"] == "failed"
    ]
    verdict_value, rule, reason = verdict_tuple
    return {
        "format": "eval-results/1.0",
        "run_id": run_id,
        "run_dir": f"{EVIDENCE_DIR}/eval-runs/{run_id}",
        "verdict": verdict_value,
        "verdict_rule": rule,
        "verdict_reason": reason,
        "thresholds": {
            "layer1": SPEC_CONSTANTS["layer1_threshold"],
            "layer2": SPEC_CONSTANTS["layer2_threshold"],
            "layer3": SPEC_CONSTANTS["layer3_threshold"],
        },
        "layers": {"layer1": layer1, "layer2": layer2, "layer3": layer3},
        "application_failures": {"count": len(app_cases), "cases": app_cases},
        "semantic_misses": {"count": len(misses), "cases": misses},
        "service_failures": {
            "model": {
                "count": len(unresolved),
                "unresolved_cases": unresolved,
                "retried_attempts": sum(
                    1 for a in failed_attempts if by_id[a["case_id"]]["scored"]
                ),
                "attempts": failed_attempts,
            },
            "judge": {"count": len(judge_failures), "cases": judge_failures},
        },
        "judge": {
            "informational": True,
            "model": settings.judge_model,
            "rated": len(ratings),
            "mean_rating": (
                round(sum(r["rating"] for r in ratings) / len(ratings), 2) if ratings else None
            ),
            "ratings": ratings,
        },
        "pin_check": pin_check,
        "dataset": dataset_info,
        "metadata": run_record,
        "cases": [
            {
                "case_id": r["case_id"],
                "outcome": r["outcome"],
                "status": r["candidate"].get("status")
                if isinstance(r["candidate"], dict)
                else None,
                "expected_status": None,
                "model_called": r["model_called"],
                "attempts": len(r["attempts"]),
                "scored": r["scored"],
                "l1": r["layer1"]["pass"],
                "l2": r["layer2"]["pass"],
                "l3": (
                    f"{r['layer3']['correct']}/{r['layer3']['compared']}"
                    if r["layer3"] is not None
                    else None
                ),
                "judge": r["judge"].get("rating"),
            }
            for r in records
        ],
    }


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _summary_md(results, run_record, environment) -> str:
    layers = results["layers"]
    dataset = results["dataset"]
    lines = [f"# Evaluation run {results['run_id']}", ""]
    lines += [
        "## 1. Verdict",
        "",
        f"**{results['verdict']}** (rule `{results['verdict_rule']}`): {results['verdict_reason']}",
        "",
        f"Dataset binding: `matches_spec: {json.dumps(dataset['matches_spec'])}` "
        f"(dataset sha256 `{dataset['sha256']}`, bound `{dataset['bound_sha256']}`).",
    ]
    if dataset["matches_spec"] is not True:
        lines += [
            "",
            "WARNING: the dataset is not bound to the spec (matches_spec is not true), so this "
            "run does not meet the constitution's gate before first evaluation (FR-026).",
        ]
    lines += [
        "",
        "## 2. Layers",
        "",
        "| Layer | Score | Threshold | Met | Not scored |",
        "|---|---|---|---|---|",
    ]
    for name, label in (("layer1", "L1 structural"), ("layer2", "L2 invariants")):
        block = layers[name]
        lines.append(
            f"| {label} | {block['passed']}/{block['total']} ({_pct(block['score'])}) | "
            f"{block['threshold']:.0%} | {block['met']} | {', '.join(block['not_scored']) or '-'} |"
        )
    l3 = layers["layer3"]
    lines.append(
        f"| L3 fields | {l3['correct']}/{l3['compared']} ({_pct(l3['score'])}) | "
        f"{l3['threshold']:.0%} | {l3['met']} | {', '.join(l3['not_scored']) or '-'} |"
    )
    lines += ["", "## 3. Application failures", ""]
    apps = results["application_failures"]["cases"]
    if apps:
        lines += ["| Case | Layers | Checks | Stage | Feedback |", "|---|---|---|---|---|"]
        lines += [
            f"| {a['case_id']} | {a['layers']} | {', '.join(a['checks'])} | {a['stage']} | "
            f"{a['feedback']} |"
            for a in apps
        ]
    else:
        lines.append("None.")
    disagreements = layers["layer1"]["checker_disagreements"]
    lines += ["", f"Checker disagreements: {', '.join(disagreements) or 'none'}."]
    model = results["service_failures"]["model"]
    lines += ["", "## 4. Service failures (model)", ""]
    unresolved = ", ".join(f"{u['case_id']} ({u['kind']})" for u in model["unresolved_cases"])
    lines.append(f"Unresolved: {unresolved or 'none'}.")
    retried = ", ".join(f"{a['case_id']}#{a['n']} {a['kind']}" for a in model["attempts"])
    lines.append(f"Failed attempts: {retried or 'none'}.")
    judge = results["judge"]
    lines += [
        "",
        "## 5. Judge (informational, does not affect verdict)",
        "",
        f"Model `{judge['model']}`, rated {judge['rated']}, mean {judge['mean_rating']}.",
        "",
    ]
    lines += [f"- {r['case_id']}: {r['rating']} — {r['rationale']}" for r in judge["ratings"]]
    failures = results["service_failures"]["judge"]["cases"]
    lines.append(
        f"Judge failures: {', '.join(f'{c["case_id"]} ({c["kind"]})' for c in failures) or 'none'}."
    )
    lines += ["", "## 6. Layer 3 field breakdown and semantic misses", ""]
    lines += ["| Field | Correct | Compared |", "|---|---|---|"]
    lines += [
        f"| {name} | {f['correct']} | {f['compared']} |" for name, f in l3["by_field"].items()
    ]
    misses = results["semantic_misses"]["cases"]
    lines += [
        "",
        "Semantic misses: "
        + (", ".join(f"{m['case_id']} ({', '.join(m['fields'])})" for m in misses) or "none")
        + ".",
    ]
    lines += [
        "",
        "## 7. Run metadata",
        "",
        f"- Model: `{run_record['model']['tag']}` digest installed "
        f"`{run_record['model']['digest_installed']}` "
        f"(pinned `{run_record['model']['digest_pinned']}`)",
        f"- Ollama: installed `{run_record['runner']['version_installed']}` "
        f"(pinned `{run_record['runner']['version_pinned']}`); quantisation "
        f"`{environment['quantization_level']}`",
        f"- Settings: `{json.dumps(run_record['settings'])}`",
        f"- Prompt `{run_record['prompt_version']}` "
        f"(system sha256 `{run_record['system_sha256']}`), "
        f"schema `{run_record['schema_version']}`, "
        f"model response `{run_record['mr_version']}`",
        f"- Dataset sha256 `{dataset['sha256']}`, bound `{dataset['bound_sha256']}`",
        f"- Code sha256: `{json.dumps(run_record['code_sha256'])}`",
        f"- Judge: `{json.dumps(run_record['judge'])}`",
        f"- Pin check: `{json.dumps(run_record['pin_check'])}`",
        f"- Started `{run_record['started_at']}`, ended `{run_record['ended_at']}`, "
        f"git HEAD `{run_record['git_head']}`, Python `{run_record['python_version']}`",
        "",
        "## 8. Owner decision",
        "",
        FEEDBACK_LINE,
        "",
    ]
    return "\n".join(lines)


def run(*, root, env_file=None, transport=None, sleep=time.sleep, clock=None, agent_run=None):
    """One evaluation run. Returns the exit code (0 PASS, 1 FAIL, 2 INCONCLUSIVE, 3 error)."""
    root = Path(root)
    clock = clock or (lambda: datetime.datetime.now(datetime.UTC))
    agent_run = agent_run or agent.run
    started = clock()

    if env_file is None and (root / ".env").is_file():
        env_file = root / ".env"
    try:
        settings = config.load(env_file, os.environ)
    except config.ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        dataset, sha256 = load_dataset(root / DATASET_PATH)
    except (DatasetGateError, OSError) as exc:
        print(f"dataset gate failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    bound = bound_dataset(root / SPEC_PATH)
    dataset_info = {
        "path": DATASET_PATH,
        "sha256": sha256,
        "case_count": len(dataset["cases"]),
        "dataset_version": dataset["dataset_version"],
        "bound_sha256": bound[1] if bound else None,
        "bound_version": bound[0] if bound else None,
        "matches_spec": (
            None if bound is None else (bound == (dataset["dataset_version"], sha256))
        ),
    }
    environment, pin_check = check_environment(settings, transport)
    run_id, run_dir = _new_run_dir(
        root, started.astimezone(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    _write_json(run_dir / "environment.json", environment)
    run_record = {
        "run_id": run_id,
        "started_at": _iso(started),
        "ended_at": None,
        "completed": False,
        "model": environment["model"],
        "runner": environment["runner"],
        "settings": _settings_record(settings),
        "prompt_version": prompt.PROMPT_VERSION,
        "system_sha256": prompt.build("x").system_sha256,
        "schema_version": order_agent.SCHEMA_VERSION,
        "mr_version": validators.load_schema("model-response")["$id"].rsplit(":", 1)[1],
        "dataset": dataset_info,
        "code_sha256": _code_sha256(),
        "judge": _judge_record(settings),
        "pin_check": pin_check,
        "env_mismatch": environment["env_mismatch"],
        "git_head": environment["git_head"],
        "python_version": environment["python_version"],
    }
    _write_json(run_dir / "run.json", run_record)

    by_id = {c["id"]: c for c in dataset["cases"]}
    records = []
    try:
        for case in dataset["cases"]:
            raw = expand_input(case["input"])
            exception = None
            try:
                outcome = agent_run(raw, settings, transport=transport, sleep=sleep)
            except Exception as exc:  # FR-023 (rev 2, U1): this case only; the run continues
                exception = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
                error = _RunnerError("EXC", "", f"{type(exc).__name__}: {exc}", 1)
                outcome = agent.ApplicationFailure("exception", [error], None, [], None, [])
            injection = case["expected_properties"]["injection"]
            counterpart = by_id.get(injection["counterpart_id"]) if injection else None
            record = _case_record(case, outcome, exception, counterpart)
            attempts = getattr(outcome, "attempts", [])
            if attempts:
                try:
                    bundle = prompt.build(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    bundle = None
                for attempt in attempts:
                    _write_json(
                        run_dir / "raw" / case["id"] / f"attempt-{attempt.n}.json",
                        _raw_attempt(attempt, bundle),
                    )
            records.append(record)
    except BaseException as exc:
        run_record["ended_at"] = _iso(clock())
        _write_json(run_dir / "run.json", run_record)
        if isinstance(exc, KeyboardInterrupt | SystemExit):
            print(f"run interrupted: {type(exc).__name__}", file=sys.stderr)
            return EXIT_ERROR
        raise

    for record in records:
        case = by_id[record["case_id"]]
        if record["layer3"] is not None and record["candidate"] is not None:
            judged = _judge_case(settings, case, record, transport, sleep)
            _write_json(run_dir / "judge" / f"{case['id']}.json", judged.to_dict())
            if judged.status == "ok":
                record["judge"] = {
                    "status": "ok",
                    "rating": judged.rating,
                    "rationale": judged.rationale,
                }
            else:
                record["judge"] = {"status": "failed", "kind": judged.kind, "detail": judged.detail}

    summaries = [
        {
            "case_id": r["case_id"],
            "processed": r["scored"],
            "l1_pass": r["layer1"]["pass"],
            "l2_pass": r["layer2"]["pass"],
            "checks": r["checks"],
        }
        for r in records
    ]
    l3_compared = sum(r["layer3"]["compared"] for r in records if r["layer3"] is not None)
    l3_correct = sum(r["layer3"]["correct"] for r in records if r["layer3"] is not None)
    verdict_tuple = verdict(
        pin_check["ok"], summaries, l3_correct / l3_compared if l3_compared else None
    )

    for record in records:
        case = by_id[record["case_id"]]
        failing = (
            not record["scored"]
            or not record["layer1"]["pass"]
            or not record["layer2"]["pass"]
            or (
                record["layer3"] is not None
                and record["layer3"]["correct"] < record["layer3"]["compared"]
            )
        )
        if failing:
            _write_json(
                run_dir / "feedback" / f"{case['id']}.json", _feedback(record, case, run_id)
            )
        _write_json(
            run_dir / "cases" / f"{case['id']}.json",
            {key: record[key] for key in _PUBLIC_CASE_KEYS},
        )

    run_record["ended_at"] = _iso(clock())
    run_record["completed"] = True
    _write_json(run_dir / "run.json", run_record)
    results = _results(
        run_id, records, pin_check, dataset_info, run_record, verdict_tuple, settings
    )
    for row in results["cases"]:
        row["expected_status"] = by_id[row["case_id"]]["ground_truth"]["status"]
    data = _write_json(run_dir / "eval-results.json", results)
    (run_dir / "summary.md").write_text(
        _summary_md(results, run_record, environment), encoding="utf-8"
    )
    (root / EVIDENCE_DIR / "eval-results.json").write_bytes(data)

    layers = results["layers"]
    l3 = layers["layer3"]
    print(
        f"Verdict: {results['verdict']}"
        f"  L1 {layers['layer1']['passed']}/{layers['layer1']['total']}"
        f"  L2 {layers['layer2']['passed']}/{layers['layer2']['total']}"
        f"  L3 {l3['correct']}/{l3['compared']} ({_pct(l3['score'])})"
        f"  run: {results['run_dir']}"
    )
    return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL}.get(results["verdict"], EXIT_INCONCLUSIVE)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="run_eval.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--env-file", default=None, help=".env file (default: Part-1B/.env)")
    args = parser.parse_args(argv)
    return run(root=ROOT, env_file=args.env_file)


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
