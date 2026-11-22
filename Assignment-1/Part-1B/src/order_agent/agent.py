"""The extraction pipeline and the deterministic assembly (data-model.md Pipeline states,
assembly rules A-1 … A-9; research.md R-5).

guards → prompt → client.generate → parser → check_mr → assemble → post_validate → outcome.
Assembly never creates or alters an extracted value; the one computed value is the declared
derived field `value_in_cr` (A-9, spec FR-035).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import client, guards, parser, prompt, validators
from .config import Settings
from .validators import ValidationError


@dataclass
class Success:
    result: dict
    model_called: bool
    attempts: list = field(default_factory=list)
    parser_log: list = field(default_factory=list)
    assembly_trace: dict = field(default_factory=dict)


@dataclass
class ApplicationFailure:
    stage: str  # parse | mr_schema | mr_consistency | post_validation (runner only: exception)
    errors: list[ValidationError]
    raw_text: str | None
    parser_log: list
    candidate: dict | None
    attempts: list


@dataclass
class ServiceFailure:
    attempts: list
    last_kind: str | None


AgentOutcome = Success | ApplicationFailure | ServiceFailure


def _top_evidence(mr: dict, top: dict | None) -> dict:
    """A-4 for the top level, in the FR-010 field order; a key only for a non-null field."""
    evidence = {}
    if mr["company"] is not None:
        evidence["company"] = mr["company_quote"]
    if mr["announcement_date"] is not None:
        evidence["announcement_date"] = mr["announcement_date_quote"]
    if top is not None:
        if top["order_value"] is not None:
            for key in ("order_value", "currency", "unit"):
                evidence[key] = top["value_quote"]
        if top["client"] is not None:
            evidence["client"] = top["client_quote"]
        if mr["order_type"] is not None:
            evidence["order_type"] = mr["order_type_quote"]
        if mr["execution_period"] is not None:
            evidence["execution_period"] = mr["execution_period_quote"]
    return evidence


def _additional(entry: dict) -> dict:
    """A-4 restricted to the four keys, plus A-9."""
    evidence = {}
    if entry["order_value"] is not None:
        for key in ("order_value", "currency", "unit"):
            evidence[key] = entry["value_quote"]
    if entry["client"] is not None:
        evidence["client"] = entry["client_quote"]
    return {
        "order_value": entry["order_value"],
        "currency": entry["currency"],
        "unit": entry["unit"],
        "value_in_cr": validators.value_in_cr(
            entry["order_value"], entry["currency"], entry["unit"]
        ),
        "client": entry["client"],
        "evidence": evidence,
    }


def _result(status, company, date, order, additional, evidence, missing) -> dict:
    result = {
        "schema_version": "1.0",  # A-7
        "status": status,
        "company": company,
        "announcement_date": date,
        "order": order,
        "additional_orders": additional,
        "evidence": evidence,
        "missing_fields": missing,
        "unstated_fields": [],
        "rejection_reason": None,  # A-7
    }
    result["unstated_fields"] = validators.expected_unstated_fields(result)  # A-8
    return result


def _rank(orders: list[dict]):
    """A-2 (R-6): validators.rank picks the top-level order; the ranking keys go to the trace
    as JSON-safe values. Ranking never reads value_in_cr (A-9 runs on each order afterwards)."""
    top_index, extra_indices = validators.rank(orders)
    keys = [
        [group, str(-key) if key else "0"] for group, key in map(validators.ranking_key, orders)
    ]
    return top_index, extra_indices, keys


def assemble(mr: dict) -> tuple[dict, dict]:
    """Turn a validated model response into a schema-1.0 result (A-1 … A-9)."""
    if not mr["is_new_order"]:  # A-1: not a new order; only company and date are reported
        result = _result(
            "not_an_order",
            mr["company"],
            mr["announcement_date"],
            None,
            [],
            _top_evidence(mr, None),
            [],
        )
        return result, {"is_new_order": False, "value_in_cr": []}
    orders = mr["orders"]
    top_index, extra_indices, keys = _rank(orders)  # A-2
    top = orders[top_index]
    order = {  # A-3, A-9
        "order_value": top["order_value"],
        "currency": top["currency"],
        "unit": top["unit"],
        "value_in_cr": validators.value_in_cr(top["order_value"], top["currency"], top["unit"]),
        "client": top["client"],
        "order_type": mr["order_type"],
        "execution_period": mr["execution_period"],
    }
    additional = [_additional(orders[i]) for i in extra_indices]
    missing = [f for f in validators.REQUIRED_ORDER_FIELDS if order[f] is None]  # A-5
    status = "needs_clarification" if missing else "extracted"  # A-6
    result = _result(
        status,
        mr["company"],
        mr["announcement_date"],
        order,
        additional,
        _top_evidence(mr, top),
        missing,
    )
    trace = {
        "ranking_keys": keys,
        "top_index": top_index,
        "additional_indices": extra_indices,
        "value_in_cr": [order["value_in_cr"], *(a["value_in_cr"] for a in additional)],
    }
    return result, trace


def rejected_result(reason: str) -> dict:
    """The FR-015 rejected shape, built in code (nothing was read, so nothing is unstated)."""
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


def run(raw: bytes, settings: Settings, *, transport=None, sleep=None) -> AgentOutcome:
    """One announcement in, one AgentOutcome out (contracts/cli.md library entry point)."""
    guard = guards.check(raw)
    if not guard.ok:  # FR-016: a rejected input never reaches the model
        return Success(
            result=rejected_result(guard.rejection_reason),
            model_called=False,
            attempts=[],
            parser_log=[],
            assembly_trace={"guard": guard.detail},
        )
    bundle = prompt.build(guard.text)
    generated = client.generate(
        settings, bundle.system, bundle.prompt, transport=transport, sleep=sleep or time.sleep
    )
    if not generated.ok:
        return ServiceFailure(attempts=generated.attempts, last_kind=generated.last_kind)
    raw_text = generated.raw_text
    try:
        mr, log = parser.parse(raw_text)
    except parser.ParseError as exc:
        error = ValidationError("MR-SCHEMA", "", str(exc), 1)
        return ApplicationFailure("parse", [error], raw_text, exc.log, None, generated.attempts)
    errors = validators.check_mr(mr)
    if errors:
        stage = "mr_schema" if any(e.code == "MR-SCHEMA" for e in errors) else "mr_consistency"
        return ApplicationFailure(stage, errors, raw_text, log, None, generated.attempts)
    result, trace = assemble(mr)
    errors = validators.post_validate(guard.text, result)
    if errors:
        return ApplicationFailure(
            "post_validation", errors, raw_text, log, result, generated.attempts
        )
    return Success(result, True, generated.attempts, log, trace)
