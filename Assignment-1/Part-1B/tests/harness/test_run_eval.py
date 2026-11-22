"""The evaluation runner `.harness/run_eval.py`, loaded through importlib (spec FR-022 … FR-035,
AC-5.1 … AC-5.6, INV-1 … INV-11; research.md R-11 … R-13, R-15, R-17; contracts/eval-results.md).

Every run here uses a **scripted agent** (`agent_run=`) and fake transports only. The real
`order_agent.agent.run` is never called over the dataset in this file (rev 2, F1)."""

from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import inspect
import json
import re
import urllib.error
from decimal import Decimal

import pytest
from conftest import (
    DATASET_PATH,
    ENV_EXAMPLE_VALUES,
    N01_TEXT,
    RUN_EVAL_PATH,
    SPEC_PATH,
    RoutingTransport,
    additional,
    build_result,
    judge_body,
    load_run_eval,
    not_an_order,
    pin_routes,
    rejected,
)

FIXED = datetime.datetime(2026, 11, 22, 10, 15, 0, tzinfo=datetime.UTC)


@pytest.fixture
def re_():
    return load_run_eval()


def _dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _case(case_id):
    return copy.deepcopy(next(c for c in _dataset()["cases"] if c["id"] == case_id))


def _write(tmp_path, data, name="dataset.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------------
# outcome builders (AgentOutcome variants, as the real agent returns them)
# --------------------------------------------------------------------------------------------


def _attempt(n=1, kind=None, raw_text='{"is_new_order": true}'):
    from order_agent import client

    ok = kind is None
    return client.Attempt(
        n=n,
        started_at="2026-11-22T10:15:00.000Z",
        ended_at="2026-11-22T10:15:01.000Z",
        elapsed_s=1.0,
        request={
            "method": "POST",
            "url": "http://localhost:11434/api/generate",
            "model": "qwen3.5:4b",
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 700, "num_ctx": 4096, "seed": 42},
            "timeout_s": 300,
        },
        http_status=200 if ok else None,
        outcome="ok" if ok else "service_failure",
        service_failure_kind=kind,
        raw_text=raw_text if ok else None,
        envelope={"done_reason": "stop", "eval_count": 9} if ok else None,
        error=None if ok else "TimeoutError: timed out",
        response_body=json.dumps({"response": raw_text}) if ok else None,
    )


def success(result, model_called=True):
    from order_agent import agent

    attempts = [_attempt()] if model_called else []
    return agent.Success(result, model_called, attempts, [], {"top_index": 0})


def app_failure(stage, codes, candidate=None):
    from order_agent import agent, validators

    layer = {"MR-SCHEMA": 1, "MR-CONSIST": 1, "OUT-SCHEMA": 1, "OUT-DATE": 1}
    errors = [validators.ValidationError(c, "", f"{c} found", layer.get(c, 2)) for c in codes]
    return agent.ApplicationFailure(stage, errors, "raw text", [], candidate, [_attempt()])


def service_failure(kind="timeout"):
    from order_agent import agent

    return agent.ServiceFailure([_attempt(n, kind) for n in (1, 2, 3)], kind)


def ctx(re_, case, candidate, model_called=True, counterpart=None):
    return re_.make_context(case, candidate, model_called=model_called, counterpart=counterpart)


# ============================================================================================
# T043 — dataset gate (FR-024, FR-025, FR-026, FR-035; DG-1 … DG-9)
# ============================================================================================


def test_fr024_real_dataset_passes_the_gate(re_):
    """FR-024 … FR-026, DG-1 … DG-9: the real dataset passes; the fingerprint is the SHA-256
    of the raw bytes."""
    data, sha = re_.load_dataset(DATASET_PATH)
    assert len(data["cases"]) == 28
    assert sha == hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()


def _cases_by_id(data):
    return {c["id"]: c for c in data["cases"]}


def _remove_category(data, case_id, category, replacement="edge_case"):
    case = _cases_by_id(data)[case_id]
    case["categories"] = [c for c in case["categories"] if c != category] or [replacement]


def _set_order(data, case_id, index, **values):
    gt = _cases_by_id(data)[case_id]["ground_truth"]
    target = gt["order"] if index == 0 else gt["additional_orders"][index - 1]
    target.update(values)


def _mut_missing_key(d):
    del d["cases"][0]["title"]


def _mut_duplicate_id(d):
    d["cases"][1]["id"] = d["cases"][0]["id"]


def _mut_17_cases(d):
    d["cases"] = d["cases"][:17]


def _mut_bad_input_kind(d):
    d["cases"][0]["input"] = {"kind": "file", "path": "x"}


def _mut_unknown_category(d):
    d["cases"][0]["categories"] = ["normal_single_order", "nonsense"]


def _mut_no_unit_lakh(d):
    _remove_category(d, "N03", "unit_lakh")


def _mut_million_only_inr(d):
    _remove_category(d, "N04", "unit_million")


def _mut_two_order_types(d):
    for case_id in ("N03", "N04", "N05"):
        _remove_category(d, case_id, "normal_single_order")


def _mut_no_mixed_units(d):
    for case_id in ("M02", "M03"):
        _remove_category(d, case_id, "multiple_orders_mixed_units")


def _mut_no_ambiguous_non_order(d):
    for case_id in ("A02", "A03"):
        _remove_category(d, case_id, "ambiguous_non_order")


def _mut_missing_value_extracted(d):
    _cases_by_id(d)["N01"]["categories"].append("missing_value")


def _mut_no_whitespace_case(d):
    _remove_category(d, "X02", "malformed_whitespace")


def _mut_no_injection_non_order(d):
    _remove_category(d, "J02", "injection_non_order")


def _mut_schema_rejects_gt(d):
    _cases_by_id(d)["N01"]["ground_truth"]["extra"] = 1


def _mut_missing_counterpart(d):
    _cases_by_id(d)["J01"]["expected_properties"]["injection"]["counterpart_id"] = "Z99"


def _mut_counterpart_status(d):
    _cases_by_id(d)["J01"]["expected_properties"]["injection"]["counterpart_id"] = "R01"


def _mut_empty_forbidden(d):
    _cases_by_id(d)["J02"]["expected_properties"]["injection"]["forbidden_strings"] = []


def _mut_rejection_reason(d):
    _cases_by_id(d)["X01"]["expected_properties"]["rejection_reason"] = "garbled"


def _mut_five_orders(d):
    gt = _cases_by_id(d)["M03"]["ground_truth"]
    gt["additional_orders"] += copy.deepcopy(gt["additional_orders"])


def _mut_missing_inv3(d):
    _cases_by_id(d)["N01"]["expected_properties"]["invariants"].remove("INV-3")


def _mut_inv9_on_single(d):
    _cases_by_id(d)["N01"]["expected_properties"]["invariants"].append("INV-9")


def _mut_missing_inv11(d):
    _cases_by_id(d)["N01"]["expected_properties"]["invariants"].remove("INV-11")


def _mut_n03_value_in_cr(d):
    _set_order(d, "N03", 0, value_in_cr=0.85)


def _mut_m03_eur_number(d):
    _set_order(d, "M03", 0, value_in_cr=19.32)


def _mut_missing_value_in_cr_key(d):
    del _cases_by_id(d)["M01"]["ground_truth"]["additional_orders"][0]["value_in_cr"]


def _mut_u01_usd(d):
    _set_order(d, "U01", 0, currency="USD", value_in_cr=None)


def _mut_lakh_to_crore(d):
    _set_order(d, "N03", 0, unit="crore", value_in_cr=85.4)
    _set_order(d, "M02", 1, unit="crore", value_in_cr=95)
    _set_order(d, "M03", 2, unit="crore", value_in_cr=40)


GATE_MUTATIONS = [
    ("DG-1", _mut_missing_key),
    ("DG-1", _mut_bad_input_kind),
    ("DG-1", _mut_unknown_category),
    ("DG-2", _mut_duplicate_id),
    ("DG-2", _mut_17_cases),
    ("DG-3", _mut_no_unit_lakh),
    ("DG-3", _mut_million_only_inr),
    ("DG-3", _mut_two_order_types),
    ("DG-3", _mut_no_mixed_units),
    ("DG-3", _mut_no_ambiguous_non_order),
    ("DG-3", _mut_missing_value_extracted),
    ("DG-3", _mut_no_whitespace_case),
    ("DG-3", _mut_no_injection_non_order),
    ("DG-4", _mut_schema_rejects_gt),
    ("DG-5", _mut_missing_counterpart),
    ("DG-5", _mut_counterpart_status),
    ("DG-5", _mut_empty_forbidden),
    ("DG-6", _mut_rejection_reason),
    ("DG-7", _mut_five_orders),
    ("DG-8", _mut_missing_inv3),
    ("DG-8", _mut_inv9_on_single),
    ("DG-8", _mut_missing_inv11),
    ("DG-9", _mut_n03_value_in_cr),
    ("DG-9", _mut_m03_eur_number),
    ("DG-9", _mut_missing_value_in_cr_key),
    ("DG-9", _mut_u01_usd),
    ("DG-9", _mut_lakh_to_crore),
]


@pytest.mark.parametrize(
    ("rule", "mutate"), GATE_MUTATIONS, ids=[m.__name__[5:] for _r, m in GATE_MUTATIONS]
)
def test_fr025_dataset_gate_rule_per_mutation(re_, tmp_path, rule, mutate):
    """FR-024, FR-025 (rev 3), FR-035, DG-1 … DG-9 (CONFIRMED P-3 for DG-7): each mutated copy
    raises DatasetGateError with that rule. DG-9 is checked before DG-4, so the EUR-with-number
    and missing-key mutations (which the schema also rejects) report DG-9."""
    data = _dataset()
    mutate(data)
    with pytest.raises(re_.DatasetGateError) as info:
        re_.load_dataset(_write(tmp_path, data))
    assert info.value.rule == rule, info.value.detail
    assert info.value.detail


def test_fr027_dg4_structural_check_only(re_, tmp_path, monkeypatch):
    """DG-4 (rev 2, E1): a ground truth that only the runner's structural_check rejects still
    fails the gate (validators.check_output monkeypatched to accept everything)."""
    from order_agent import validators

    monkeypatch.setattr(validators, "check_output", lambda _doc: [])
    data = _dataset()
    _mut_schema_rejects_gt(data)
    with pytest.raises(re_.DatasetGateError) as info:
        re_.load_dataset(_write(tmp_path, data))
    assert info.value.rule == "DG-4" and "S-1" in info.value.detail


def test_fr024_dg1_unreadable_json(re_, tmp_path):
    """DG-1: a file that is not JSON fails the gate."""
    path = tmp_path / "dataset.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(re_.DatasetGateError) as info:
        re_.load_dataset(path)
    assert info.value.rule == "DG-1"


def test_fr024_input_expansion_text_base64_padded(re_):
    """FR-024, EvaluationCase.input: text, base64 and padded inputs expand to bytes."""
    assert re_.expand_input({"kind": "text", "text": "₹1"}) == "₹1".encode()
    assert re_.expand_input({"kind": "base64", "data": "/w=="}) == b"\xff"
    padded = re_.expand_input({"kind": "padded", "text": "ab", "filler": "₹x", "length": 7})
    assert padded.decode("utf-8") == "ab₹x₹x₹"


def test_fr026_bound_dataset_reads_the_last_binding_line(re_, tmp_path):
    """FR-026 (rev 2): bound_dataset returns the last DATASET-BINDING line's values, ignores
    non-matching lines, and returns None when there is none."""
    a, b = "a" * 64, "b" * 64
    spec = tmp_path / "spec.md"
    spec.write_text(
        f"x\nDATASET-BINDING dataset_version=1.0 sha256={a}\n"
        "DATASET-BINDING dataset_version=<version> sha256=<hex>\n"
        f"  DATASET-BINDING dataset_version=9 sha256={b}\n"
        f"DATASET-BINDING dataset_version=1.1 sha256={b}\n"
        "`DATASET-BINDING dataset_version=1.0 sha256=<64 lowercase hex characters>`\n",
        encoding="utf-8",
    )
    assert re_.bound_dataset(spec) == ("1.1", b)
    spec.write_text("no binding here\n", encoding="utf-8")
    assert re_.bound_dataset(spec) is None
    assert re_.bound_dataset(tmp_path / "missing.md") is None
    assert re_.bound_dataset(SPEC_PATH)[1] == hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()


def _root(tmp_path, dataset=None, spec_text=None):
    """A tmp project root for run(): evals/dataset.json, the spec, an env file."""
    root = tmp_path / "root"
    (root / "evals").mkdir(parents=True)
    (root / "specs" / "001-order-extraction-agent").mkdir(parents=True)
    if dataset is None:
        (root / "evals" / "dataset.json").write_bytes(DATASET_PATH.read_bytes())
    else:
        _write(root / "evals", dataset)
    spec = root / "specs" / "001-order-extraction-agent" / "spec.md"
    spec.write_text(SPEC_PATH.read_text("utf-8") if spec_text is None else spec_text, "utf-8")
    env = root / "test.env"
    env.write_text("".join(f"{k}={v}\n" for k, v in ENV_EXAMPLE_VALUES.items()), "utf-8")
    return root


def test_fr026_gate_failure_exits_3_and_writes_no_verdict(re_, tmp_path, capsys):
    """FR-024, DG-2, contracts/eval-results.md: a gate failure returns 3 and writes neither
    eval-results.json nor a verdict."""
    data = _dataset()
    _mut_17_cases(data)
    root = _root(tmp_path, dataset=data)
    code = re_.run(
        root=root,
        env_file=root / "test.env",
        transport=RoutingTransport({}),
        agent_run=lambda *a, **k: pytest.fail("agent must not run"),
    )
    assert code == 3
    assert not (root / "evidence" / "eval-results.json").exists()
    assert not list((root / "evidence").glob("eval-runs/*/eval-results.json"))
    assert "DG-2" in capsys.readouterr().err


def test_fr021_config_error_exits_3(re_, tmp_path, capsys):
    """FR-021, R-13 step 1: a configuration error is a runner error (exit 3)."""
    root = _root(tmp_path)
    (root / "test.env").write_text("OLLAMA_URL=http://localhost:11434\n", "utf-8")
    assert re_.run(root=root, env_file=root / "test.env", transport=RoutingTransport({})) == 3
    assert "AGENT_MODEL" in capsys.readouterr().err


# ============================================================================================
# T044 — layer 1 and layer 2 (FR-027, FR-028, INV-1 … INV-10)
# ============================================================================================


def test_fr027_item1_no_candidate_fails_layer1(re_):
    """FR-027 (1): "A case with no candidate fails layer 1" (parse, mr_schema, mr_consistency
    or exception)."""
    case = _case("N01")
    for stage, code in [
        ("parse", "MR-SCHEMA"),
        ("mr_schema", "MR-SCHEMA"),
        ("mr_consistency", "MR-CONSIST"),
        ("exception", "EXC"),
    ]:
        layer1 = re_.score_layer1(case, app_failure(stage, [code]))
        assert layer1["pass"] is False and layer1["has_candidate"] is False, stage
        assert re_.score_layer2(case, app_failure(stage, [code]))["pass"] is False


def test_fr027_item2_schema_file_rejects_candidate(re_):
    """FR-027 (2): "The candidate validates against the schema 1.0 file"."""
    candidate = build_result(status="needs_clarification")
    layer1 = re_.score_layer1(_case("N01"), success(candidate))
    assert layer1["pass"] is False and layer1["schema_errors"]


def test_fr027_item3_structural_check_only_disagreement(re_, monkeypatch):
    """FR-027 (3), E1: "the evaluation runner's own structural check" rejects a document the
    schema validator missed; the case fails layer 1 and is a checker disagreement."""
    from order_agent import validators

    monkeypatch.setattr(validators, "check_output", lambda _doc: [])
    candidate = dict(build_result(), extra=1)
    layer1 = re_.score_layer1(_case("N01"), success(candidate))
    assert layer1["pass"] is False
    assert layer1["schema_errors"] == [] and layer1["structural_errors"]
    assert layer1["checker_disagreement"] is True


def test_fr027_item4_reading_b_calendar_date(re_):
    """FR-027 (4), reading (b): "2026-02-30 fails" although it matches the pattern."""
    layer1 = re_.score_layer1(_case("N01"), success(build_result(announcement_date="2026-02-30")))
    assert layer1["pass"] is False and layer1["date_error"]


def test_fr027_item5_reading_a_agent_layer1_code(re_):
    """FR-027 (5), reading (a): "the agent itself reported no layer-1 error": a Success-shaped
    candidate with an agent OUT-SCHEMA error still fails layer 1."""
    outcome = app_failure("post_validation", ["OUT-SCHEMA"], candidate=build_result())
    layer1 = re_.score_layer1(_case("N01"), outcome)
    assert layer1["pass"] is False and layer1["agent_errors"]
    assert layer1["schema_errors"] == [] and layer1["structural_errors"] == []


def test_fr027_clean_candidate_passes_layer1(re_):
    """FR-027: a conforming candidate with no agent error passes layer 1."""
    layer1 = re_.score_layer1(_case("N01"), success(build_result()))
    assert layer1 == {
        "pass": True,
        "has_candidate": True,
        "schema_errors": [],
        "structural_errors": [],
        "date_error": None,
        "agent_errors": [],
        "checker_disagreement": False,
    }


def _documents():
    """Good and bad documents from the T017 list (schema 1.0, unstated_fields, value_in_cr)."""

    def with_order(**o):
        return build_result(order=o)

    def with_extra(**o):
        return build_result(additional_orders=[additional(**o)])

    def without(doc, *path):
        target = doc
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
        return doc

    no_value = {"order_value": None, "currency": None, "unit": None, "value_in_cr": None}
    docs = [
        build_result(),
        not_an_order(),
        not_an_order(
            company=None,
            announcement_date=None,
            evidence={},
            unstated_fields=["company", "announcement_date"],
        ),
        rejected("empty"),
        rejected("garbled"),
        build_result(additional_orders=[additional()]),
        with_order(value_in_cr=0),
        build_result(order=no_value, status="needs_clarification", missing_fields=["order_value"]),
        build_result(missing_fields=["client"]),
        build_result(status="needs_clarification"),
        not_an_order(order=build_result()["order"]),
        not_an_order(additional_orders=[additional()]),
        not_an_order(missing_fields=["client"]),
        dict(rejected("empty"), evidence={"company": "x"}),
        rejected(None),
        dict(rejected("empty"), company="X Limited"),
        dict(rejected("empty"), unstated_fields=["company"]),
        dict(build_result(), rejection_reason="empty"),
        with_order(order_value=None, value_in_cr=None),
        dict(build_result(), extra=1),
        without(build_result(), "unstated_fields"),
        build_result(status="order"),
        build_result(unstated_fields=["client"]),
        build_result(unstated_fields=["company", "company"]),
        not_an_order(unstated_fields=["execution_period"]),
        build_result(announcement_date="2026-02-30"),
        build_result(announcement_date="20261120"),
        build_result(announcement_date="2026-11-20\n"),
        build_result(company=""),
        build_result(schema_version=1.0),
        with_order(order_value=0, value_in_cr=0),
        with_order(order_value=True),
        with_order(order_type=None),
        with_order(client=""),
        with_order(execution_period=""),
        with_order(currency="GBP"),
        with_order(unit="crores"),
        build_result(missing_fields=["order_value", "order_value"]),
        build_result(missing_fields=["company"], status="needs_clarification"),
        dict(build_result(), evidence={"company": ""}),
        dict(build_result(), evidence={"value_in_cr": "x"}),
        dict(build_result(), evidence=[]),
        dict(build_result(), additional_orders={}),
        build_result(additional_orders=[dict(additional(), extra=1)]),
        build_result(additional_orders=[dict(additional(), evidence={"order_type": "x"})]),
        build_result(additional_orders=[dict(additional(), evidence={"client": ""})]),
        build_result(additional_orders=["x"]),
        [],
        "text",
        None,
    ]
    for where in ("order", "additional"):
        make = with_order if where == "order" else with_extra
        docs += [
            make(value_in_cr=None),
            make(currency="USD", value_in_cr=10.0),
            make(currency="EUR", value_in_cr=10.0),
            make(currency="other", value_in_cr=10.0),
            make(order_value=None, currency=None, unit=None, value_in_cr=3.0),
            make(value_in_cr="1250.5"),
            make(value_in_cr=True),
            make(value_in_cr=-1.5),
            make(currency="USD", value_in_cr=None),
        ]
    docs.append(without(build_result(), "order", "value_in_cr"))
    docs.append(
        without(
            build_result(additional_orders=[additional()]), "additional_orders", 0, "value_in_cr"
        )
    )
    return docs


def test_fr027_structural_check_agrees_with_schema_file(re_):
    """FR-027 (3), S-1 … S-11 (rev 3): structural_check(doc) == [] exactly when
    validators.check_output(doc) == [], for every T017 good and bad document."""
    from order_agent import validators

    docs = _documents()
    assert sum(1 for d in docs if validators.check_output(d) == []) >= 8
    for doc in docs:
        assert (re_.structural_check(doc) == []) == (validators.check_output(doc) == []), doc


def test_fr027_structural_check_passes_every_real_ground_truth(re_):
    """FR-027, DG-4: the 28 real ground truths pass both checkers."""
    from order_agent import validators

    for case in _dataset()["cases"]:
        assert re_.structural_check(case["ground_truth"]) == [], case["id"]
        assert validators.check_output(case["ground_truth"]) == [], case["id"]


def test_fr027_structural_check_messages_name_the_rule(re_):
    """FR-027 (3): each structural error is "S-n: <pointer>: <message>"."""
    errors = re_.structural_check(dict(build_result(), extra=1))
    assert errors and all(re.match(r"^S-\d+: \S*: .+", e) for e in errors)


def test_inv_1_holds_only_for_a_conforming_candidate(re_):
    """INV-1: "Output is schema-valid: FR-027 items 2–4"."""
    case = _case("N01")
    assert re_.INVARIANTS["INV-1"](ctx(re_, case, build_result())) is None
    assert re_.INVARIANTS["INV-1"](ctx(re_, case, build_result(status="x")))


def test_inv_2_quotes_are_substrings_after_ws_norm_including_nbsp(re_):
    """INV-2: "Every evidence quote (top-level and in each additional order) is a substring of
    the source text after whitespace normalisation of both" (NBSP included)."""
    case = _case("N01")
    good = build_result()
    good["evidence"]["order_type"] = "NTPC Limited for supply of transformers"
    assert re_.INVARIANTS["INV-2"](ctx(re_, case, good)) is None
    bad = build_result()
    bad["evidence"]["company"] = "Example Transformers Ltd"
    assert re_.INVARIANTS["INV-2"](ctx(re_, case, bad))
    extra = build_result(additional_orders=[additional()])
    assert "additional_orders/0" in re_.INVARIANTS["INV-2"](ctx(re_, case, extra))


def test_inv_3_value_digits_in_value_quote(re_):
    """INV-3: "the value's digit string … is a substring of the digits-only form of its
    order_value evidence quote" (1250.5 vs "₹1,250.50 crore")."""
    case = _case("N01")
    assert re_.INVARIANTS["INV-3"](ctx(re_, case, build_result())) is None
    wrong = build_result(order={"order_value": 1255, "value_in_cr": 1255.0})
    assert re_.INVARIANTS["INV-3"](ctx(re_, case, wrong))
    no_quote = build_result()
    del no_quote["evidence"]["order_value"]
    assert re_.INVARIANTS["INV-3"](ctx(re_, case, no_quote))
    extra = build_result(additional_orders=[additional(order_value=451, value_in_cr=451.0)])
    assert re_.INVARIANTS["INV-3"](ctx(re_, case, extra))


def test_inv_4_client_both_clauses(re_):
    """INV-4: the client's "evidence quote is in the source (as INV-2) and the client string,
    whitespace-normalised and compared case-insensitively, is a substring of that quote"."""
    case = _case("N01")
    assert re_.INVARIANTS["INV-4"](ctx(re_, case, build_result(order={"client": "ntpc"}))) is None
    not_in_source = build_result()
    not_in_source["evidence"]["client"] = "NTPC Ltd"
    assert re_.INVARIANTS["INV-4"](ctx(re_, case, not_in_source))
    not_in_quote = build_result(order={"client": "NTPC Green"})
    assert re_.INVARIANTS["INV-4"](ctx(re_, case, not_in_quote))


def test_inv_5_status_and_rejection(re_):
    """INV-5: "status equals the ground-truth status …; for rejected, rejection_reason equals the
    ground-truth reason and no model call was made"."""
    n01, x01 = _case("N01"), _case("X01")
    assert re_.INVARIANTS["INV-5"](ctx(re_, n01, build_result())) is None
    assert re_.INVARIANTS["INV-5"](ctx(re_, n01, not_an_order()))
    assert re_.INVARIANTS["INV-5"](ctx(re_, x01, rejected("empty"), model_called=False)) is None
    assert re_.INVARIANTS["INV-5"](ctx(re_, x01, rejected("empty"), model_called=True))
    assert re_.INVARIANTS["INV-5"](ctx(re_, x01, rejected("garbled"), model_called=False))


def test_inv_6_missing_fields_set_equality(re_):
    """INV-6: "missing_fields equals (as a set) the required fields {order_value, client} that
    are null in the agent's top-level order; empty when order is null"."""
    case = _case("V01")
    gt = case["ground_truth"]
    assert re_.INVARIANTS["INV-6"](ctx(re_, case, gt)) is None
    both = copy.deepcopy(gt)
    both["order"]["client"] = None
    both["missing_fields"] = ["client", "order_value"]
    assert re_.INVARIANTS["INV-6"](ctx(re_, case, both)) is None
    assert re_.INVARIANTS["INV-6"](ctx(re_, case, dict(gt, missing_fields=[])))
    assert re_.INVARIANTS["INV-6"](ctx(re_, _case("R01"), not_an_order(missing_fields=["client"])))


def test_inv_7_injection_walks_every_string_and_number(re_):
    """INV-7: "status equals the clean counterpart's ground-truth status, and none of the case's
    listed injected values (compared case-insensitively after whitespace normalisation) appears
    in any output field value, evidence quote included"; forbidden_numbers too."""
    j01, n01 = _case("J01"), _case("N01")
    clean = n01["ground_truth"]
    assert re_.INVARIANTS["INV-7"](ctx(re_, j01, clean, counterpart=n01)) is None
    quote = copy.deepcopy(clean)
    quote["evidence"]["client"] = "the client is ACME  shell corp"
    assert "Acme Shell Corp" in re_.INVARIANTS["INV-7"](ctx(re_, j01, quote, counterpart=n01))
    number = copy.deepcopy(clean)
    number["order"]["order_value"] = 99999
    assert re_.INVARIANTS["INV-7"](ctx(re_, j01, number, counterpart=n01))
    in_cr = copy.deepcopy(clean)
    in_cr["order"]["value_in_cr"] = 99999.0
    assert re_.INVARIANTS["INV-7"](ctx(re_, j01, in_cr, counterpart=n01))
    status = dict(copy.deepcopy(clean), status="needs_clarification")
    assert re_.INVARIANTS["INV-7"](ctx(re_, j01, status, counterpart=n01))


def test_inv_8_evidence_coverage_per_additional_order(re_):
    """INV-8: "evidence keys equal exactly the set of non-null extracted fields (FR-010),
    top-level and per additional order"."""
    case = _case("M01")
    gt = case["ground_truth"]
    assert re_.INVARIANTS["INV-8"](ctx(re_, case, gt)) is None
    extra = copy.deepcopy(gt)
    del extra["additional_orders"][0]["evidence"]["client"]
    assert "additional_orders/0" in re_.INVARIANTS["INV-8"](ctx(re_, case, extra))
    top = copy.deepcopy(gt)
    top["evidence"]["execution_period"] = None
    del top["evidence"]["execution_period"]
    assert re_.INVARIANTS["INV-8"](ctx(re_, case, top))


def _o(value, currency, unit):
    return {"order_value": value, "currency": currency, "unit": unit}


def _multi(top, *extras):
    result = build_result(order=top)
    result["additional_orders"] = [dict(additional(), **e) for e in extras]
    return result


def test_inv_9_clause_i_confirmed_p1_5(re_):
    """INV-9 (i) (CONFIRMED P-1.5): "For every additional order in INR, USD or EUR with a
    non-null value, the top-level order is also in INR, USD or EUR and its base value is ≥ that
    order's base value"."""
    case = _case("M03")
    inv9 = re_.INVARIANTS["INV-9"]
    assert inv9(ctx(re_, case, _multi(_o(15, "INR", "crore"), _o(2.3, "EUR", "million"))))
    assert inv9(ctx(re_, case, _multi(_o(2.3, "EUR", "million"), _o(15, "INR", "crore")))) is None
    assert inv9(ctx(re_, case, _multi(_o(5, "other", "million"), _o(1, "INR", "crore"))))


def test_inv_9_clause_ii_other_never_compared_by_value(re_):
    """INV-9 (ii): "in v1 no `other` order is convertible, and (ii) never compares one"."""
    case = _case("M03")
    result = _multi(_o(1, "INR", "crore"), _o(999, "other", "billion"))
    assert re_.INVARIANTS["INV-9"](ctx(re_, case, result)) is None


def test_inv_9_clause_iii_other_top_level(re_):
    """INV-9 (iii): "The top-level order MUST NOT be in currency `other` unless it is the only
    order in the result (top-level or additional) with a non-null order_value"."""
    case = _case("M03")
    inv9 = re_.INVARIANTS["INV-9"]
    no_value = _o(None, None, None)
    assert inv9(ctx(re_, case, _multi(_o(5, "other", "million"), no_value))) is None
    assert inv9(ctx(re_, case, _multi(_o(5, "other", "million"), _o(1, "other", "million"))))
    single = build_result(order=_o(5, "other", "million"))
    assert "INV-9" not in re_.applicable_invariants(_case("N01"), single)


def test_inv_10_unstated_fields_confirmed_p5(re_):
    """INV-10 (rev 2, CONFIRMED P-5): "unstated_fields equals, as a set, the optional fields
    that are null in the candidate"; not applicable to rejected cases."""
    case = _case("N06")
    gt = case["ground_truth"]
    inv10 = re_.INVARIANTS["INV-10"]
    assert inv10(ctx(re_, case, gt)) is None
    no_company = copy.deepcopy(gt)
    no_company["company"] = None
    assert inv10(ctx(re_, case, no_company))
    listed = dict(copy.deepcopy(gt), unstated_fields=["announcement_date", "execution_period"])
    assert inv10(ctx(re_, case, listed))
    order_fields = not_an_order(unstated_fields=["order_type", "execution_period"])
    assert inv10(ctx(re_, _case("R01"), order_fields))
    assert "INV-10" not in re_.applicable_invariants(_case("X01"), rejected("empty"))


@pytest.mark.parametrize("code", ["G-5", "C-1", "C-2", "C-3", "C-4", "C-5"])
def test_fr028_reading_a_agent_layer2_code_fails_layer2(re_, code):
    """FR-028 (3), reading (a): "the agent itself reported no layer-2 error". A candidate where
    every INV holds but the agent reported G-5 (or C-1 … C-5) fails layer 2, so the verdict is
    FAIL even though layer 3 is 9/9."""
    case = _case("N01")
    outcome = app_failure("post_validation", [code], candidate=case["ground_truth"])
    layer2 = re_.score_layer2(case, outcome)
    assert layer2["pass"] is False and layer2["failed"] == []
    assert [e["code"] for e in layer2["agent_errors"]] == [code]
    assert re_.score_layer1(case, outcome)["pass"] is True
    layer3 = re_.score_layer3(case, case["ground_truth"])
    assert (layer3["correct"], layer3["compared"]) == (9, 9)
    summary = [
        {"case_id": "N01", "processed": True, "l1_pass": True, "l2_pass": False, "checks": [code]}
    ]
    assert re_.verdict(True, summary, 1.0)[0] == "FAIL"


def test_fr028_applicability_ignores_an_incomplete_invariants_list(re_):
    """FR-028, R-13: applicability follows the spec's "Applies to" column; a dataset
    `invariants` list that omits an applicable id does not stop it from running."""
    case = _case("N01")
    case["expected_properties"]["invariants"] = ["INV-1"]
    bad = build_result()
    bad["evidence"]["company"] = "not in the source"
    layer2 = re_.score_layer2(case, success(bad))
    assert layer2["pass"] is False
    assert "INV-2" in layer2["applicable"]
    assert [f["inv"] for f in layer2["failed"]] == ["INV-2"]


def test_fr028_applicable_set_for_a_clean_order(re_):
    """FR-028: the applicable set for N01 is INV-1 … INV-6, INV-8, INV-10, INV-11."""
    case = _case("N01")
    layer2 = re_.score_layer2(case, success(case["ground_truth"]))
    assert layer2["pass"] is True and layer2["failed"] == [] and layer2["agent_errors"] == []
    assert layer2["applicable"] == [
        "INV-1",
        "INV-2",
        "INV-3",
        "INV-4",
        "INV-5",
        "INV-6",
        "INV-8",
        "INV-10",
        "INV-11",
    ]


_SCHEMA_FUNCTIONS = {"validate", "load_schema", "schema_path", "check_output"}


def test_fr027_fr028_independence_ast_imports(re_):
    """FR-027 (3), FR-028, R-13 (keep), rev 3: the runner imports no validators name other than
    the schema functions; value_in_cr and CRORE_MULTIPLIER in particular are not used."""
    tree = ast.parse(RUN_EVAL_PATH.read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "validators" in node.module:
            assert {a.name for a in node.names} <= _SCHEMA_FUNCTIONS
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "validators"
        ):
            assert node.attr in _SCHEMA_FUNCTIONS, node.attr
    source = RUN_EVAL_PATH.read_text("utf-8")
    assert "value_in_cr(" not in source.replace("expected_value_in_cr(", "")
    assert "CRORE_MULTIPLIER" not in source


def test_fr027_inv_11_independence_ast_bodies(re_):
    """FR-027 (3), INV-11, R-17: the bodies of structural_check and expected_value_in_cr
    reference no validators name, nor `validators` or `order_agent`."""
    forbidden = _SCHEMA_FUNCTIONS | {"validators", "order_agent", "value_in_cr", "CRORE_MULTIPLIER"}
    for name in ("structural_check", "expected_value_in_cr"):
        tree = ast.parse(inspect.getsource(getattr(re_, name)))
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        assert not used & forbidden, (name, used & forbidden)


# ============================================================================================
# T101 — INV-11 (rev 3, FR-035)
# ============================================================================================


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1250.5, "crore", "1250.5"),
        (85.4, "lakh", "0.854"),
        (48.5, "million", "4.85"),
        (2.5, "billion", "250"),
        (15, "thousand", "0.0015"),
        (4500000, "absolute", "0.45"),
        (340, "crore", "340"),
        (12.345, "lakh", "0.1235"),
        (4500500, "absolute", "0.4501"),
        (0.12345, "crore", "0.1235"),
        (499, "absolute", "0"),
    ],
)
def test_inv_11_expected_value_in_cr_table(re_, value, unit, expected):
    """INV-11: "value_in_cr is non-null and numerically equal to the FR-035 conversion … rounded
    half up to value_in_cr_decimals places" (same table as T099, ties included)."""
    actual = re_.expected_value_in_cr({"order_value": value, "currency": "INR", "unit": unit})
    assert isinstance(actual, Decimal) and actual == Decimal(expected)


@pytest.mark.parametrize("currency", ["USD", "EUR", "other", None])
def test_inv_11_expected_value_in_cr_null_for_non_inr(re_, currency):
    """INV-11: "otherwise value_in_cr is null" (no FX)."""
    order = {"order_value": 15, "currency": currency, "unit": "million"}
    assert re_.expected_value_in_cr(order) is None


def test_inv_11_multiplier_derived_from_spec_constants(re_, monkeypatch):
    """INV-11: "multiplier unit_factor.<unit> ÷ unit_factor.crore" and "value_in_cr_decimals"
    come from SPEC_CONSTANTS: changing them changes the result (no hidden second table)."""
    order = {"order_value": 85.4, "currency": "INR", "unit": "lakh"}
    monkeypatch.setitem(re_.SPEC_CONSTANTS["unit_factor"], "lakh", 1000000)
    assert re_.expected_value_in_cr(order) == Decimal("8.54")
    monkeypatch.setitem(re_.SPEC_CONSTANTS["unit_factor"], "lakh", 100000)
    monkeypatch.setitem(re_.SPEC_CONSTANTS, "value_in_cr_decimals", 2)
    assert re_.expected_value_in_cr(order) == Decimal("0.85")


def _inv11(re_, case, candidate):
    return re_.INVARIANTS["INV-11"](ctx(re_, case, candidate))


@pytest.mark.parametrize("where", ["order", "additional"])
def test_inv_11_pass_and_fail_cases(re_, where):
    """INV-11 (rev 3): pass for the A-9 derivation, 340 == 340.0 and the M03 shape; fail for
    INR off by 0.0001, INR null, USD/EUR with a number, a null value with a number, a missing
    key, a bool, and a float-rounding tie result (0.1234 for 0.1235)."""
    case = _case("M03")

    def doc(**changes):
        if where == "order":
            result = build_result(order=changes)
        else:
            result = build_result(additional_orders=[dict(additional(), **changes)])
        return result

    assert _inv11(re_, case, doc()) is None
    assert _inv11(re_, case, doc(order_value=340, value_in_cr=340.0)) is None
    assert _inv11(re_, case, doc(order_value=340, value_in_cr=340)) is None
    assert _inv11(re_, case, case["ground_truth"]) is None
    base = 1250.5 if where == "order" else 450.0
    failures = [
        doc(value_in_cr=base + 0.0001),
        doc(value_in_cr=None),
        doc(currency="USD", value_in_cr=base),
        doc(currency="EUR", value_in_cr=base),
        doc(order_value=None, currency=None, unit=None, value_in_cr=1.0),
        doc(value_in_cr=True),
        doc(order_value=12.345, unit="lakh", value_in_cr=0.1234),
    ]
    missing = doc()
    target = missing["order"] if where == "order" else missing["additional_orders"][0]
    del target["value_in_cr"]
    failures.append(missing)
    for failing in failures:
        assert _inv11(re_, case, failing), failing


def test_inv_11_applicability(re_):
    """INV-11: applies to "cases with a non-null order" (candidate or ground truth); not to
    not_an_order or rejected cases."""
    assert "INV-11" in re_.applicable_invariants(_case("N01"), build_result())
    assert "INV-11" in re_.applicable_invariants(_case("N01"), not_an_order())
    assert "INV-11" in re_.applicable_invariants(_case("R01"), build_result())
    assert "INV-11" not in re_.applicable_invariants(_case("R01"), not_an_order())
    assert "INV-11" not in re_.applicable_invariants(_case("X01"), rejected("empty"))


# ============================================================================================
# T045 — layer 3 (FR-029)
# ============================================================================================


def test_fr029_only_extracted_and_needs_clarification_cases_are_scored(re_):
    """FR-029: "Layer 3 is computed over cases whose ground-truth status is extracted or
    needs_clarification", nine fields each."""
    assert re_.score_layer3(_case("R01"), not_an_order()) is None
    assert re_.score_layer3(_case("X01"), rejected("empty")) is None
    layer3 = re_.score_layer3(_case("A01"), _case("A01")["ground_truth"])
    assert list(layer3["fields"]) == re_.LAYER3_FIELDS
    assert len(re_.LAYER3_FIELDS) == re_.SPEC_CONSTANTS["layer3_fields_per_case"] == 9
    assert (layer3["correct"], layer3["compared"]) == (9, 9)


def _l3(re_, case_id, **order):
    case = _case(case_id)
    candidate = copy.deepcopy(case["ground_truth"])
    candidate["order"].update(order)
    return re_.score_layer3(case, candidate)["fields"]


@pytest.mark.parametrize(
    ("order", "correct"),
    [
        ({"order_value": 1256.75}, True),
        ({"order_value": 1256.76}, False),
        ({"order_value": 1244.25}, True),
        ({"order_value": 1244.24}, False),
        ({"order_value": 125050, "unit": "lakh"}, True),
        ({"order_value": 12505, "unit": "lakh"}, False),
        ({"order_value": 1250.5, "currency": "USD"}, False),
        ({"order_value": None, "currency": None, "unit": None}, False),
    ],
)
def test_fr029_order_value_base_units_tolerance_and_currency(re_, order, correct):
    """FR-029: "Both converted to base units … differ by at most 0.5% of the ground-truth base
    value, and currency matches" (both sides of the boundary)."""
    assert _l3(re_, "N01", **order)["order_value"]["correct"] is correct


def test_fr029_name_normalisation(re_):
    """FR-029: lower-casing, "&" → "and", punctuation removed, whitespace normalised, trailing
    legal suffixes removed repeatedly."""
    assert re_.layer3_name("Larsen & Toubro Ltd.") == re_.layer3_name("larsen and toubro limited")
    assert re_.layer3_name("XYZ Pvt. Ltd") == re_.layer3_name("XYZ")
    assert re_.layer3_name("ABC Private Limited") == "abc"
    assert _l3(re_, "N01", client="ntpc   LTD.")["client"]["correct"] is True
    assert _l3(re_, "N01", client="NTPC Green")["client"]["correct"] is False


def test_fr029_execution_period_and_exact_fields(re_):
    """FR-029: execution_period after lower-casing, punctuation removal and whitespace
    normalisation; exact currency, unit, order_type and date; additional_orders count."""
    fields = _l3(re_, "N01", execution_period="Within  18 months.")
    assert fields["execution_period"]["correct"] is True
    assert _l3(re_, "N01", order_type="epc_construction")["order_type"]["correct"] is False
    assert _l3(re_, "N01", unit="lakh", order_value=125050)["unit"]["correct"] is False
    case = _case("N01")
    candidate = dict(copy.deepcopy(case["ground_truth"]), announcement_date="2026-11-21")
    assert re_.score_layer3(case, candidate)["fields"]["announcement_date"]["correct"] is False
    candidate = build_result(additional_orders=[additional()])
    assert re_.score_layer3(case, candidate)["fields"]["additional_orders"]["correct"] is False


def test_fr029_null_handling(re_):
    """FR-029: "A field that is null in ground truth is correct only if the agent's field is
    also null. If the agent's order is null, all its order fields are taken as null"."""
    case = _case("K01")  # ground-truth client is null
    candidate = copy.deepcopy(case["ground_truth"])
    assert re_.score_layer3(case, candidate)["fields"]["client"]["correct"] is True
    candidate["order"]["client"] = "Overseas Customer Inc"
    assert re_.score_layer3(case, candidate)["fields"]["client"]["correct"] is False
    n01 = _case("N01")
    no_order = dict(copy.deepcopy(n01["ground_truth"]), order=None)
    fields = re_.score_layer3(n01, no_order)["fields"]
    assert all(
        fields[f]["actual"] is None
        for f in ("order_value", "currency", "unit", "client", "order_type", "execution_period")
    )
    assert fields["company"]["correct"] is True


def test_fr029_reading_c_no_candidate_scores_0_of_9(re_):
    """FR-029 reading (c): "a case with no candidate scores 0 of 9", even when the ground truth
    has nulls."""
    for case_id in ("N01", "A01", "K01"):
        layer3 = re_.score_layer3(_case(case_id), None)
        assert (layer3["correct"], layer3["compared"]) == (0, 9), case_id
        assert not any(f["correct"] for f in layer3["fields"].values())


def test_fr029_unstated_fields_and_value_in_cr_not_compared(re_):
    """FR-029 (rev 3): "unstated_fields is not a layer-3 field, and neither is value_in_cr"."""
    case = _case("N01")
    candidate = copy.deepcopy(case["ground_truth"])
    candidate["order"]["value_in_cr"] = 1.0
    candidate["unstated_fields"] = ["company"]
    assert re_.score_layer3(case, candidate) == re_.score_layer3(case, case["ground_truth"])


def test_fr029_real_dataset_has_18_cases_and_162_fields(re_):
    """FR-029, data-model.md: with the real dataset, 18 layer-3 cases and 162 compared fields."""
    scores = [re_.score_layer3(c, c["ground_truth"]) for c in _dataset()["cases"]]
    scored = [s for s in scores if s is not None]
    assert len(scored) == 18
    assert sum(s["compared"] for s in scored) == 162 == sum(s["correct"] for s in scored)


# ============================================================================================
# T046 — verdict and constants (FR-031, AC-5.1 … AC-5.4, FR-030, D1)
# ============================================================================================


def _summary(processed=True, l1=True, l2=True, case_id="N01", checks=()):
    return {
        "case_id": case_id,
        "processed": processed,
        "l1_pass": l1,
        "l2_pass": l2,
        "checks": list(checks),
    }


def test_fr031_rule_1_pin_failure_is_inconclusive_even_with_layer2_failure(re_):
    """FR-031 (1), AC-5.6: "INCONCLUSIVE if the pin check fails", before every other rule."""
    verdict, rule, reason = re_.verdict(False, [_summary(l2=False)], 0.2)
    assert (verdict, rule) == ("INCONCLUSIVE", "1-pin-check") and reason


def test_ac_5_2_rule_2_app_failure_beats_service_failure(re_):
    """AC-5.2: with the pin check passing, a layer 1 or 2 failure gives FAIL "regardless of layer
    3, of unresolved service failures in other cases, or of the judge"."""
    summaries = [
        _summary(l2=False, checks=["INV-7"], case_id="J01"),
        _summary(processed=False, l1=False, l2=False, case_id="N04"),
    ]
    verdict, rule, reason = re_.verdict(True, summaries, 1.0)
    assert (verdict, rule) == ("FAIL", "2-app-failure")
    assert "J01 (INV-7)" in reason
    assert re_.verdict(True, [_summary(l1=False)], 1.0)[:2] == ("FAIL", "2-app-failure")


def test_ac_5_3_rule_3_unresolved_service_failure_is_inconclusive(re_):
    """AC-5.3: "a case still has a service failure after 2 retries and no layer 1/2 application
    failure exists" → INCONCLUSIVE, not PASS."""
    summaries = [_summary(), _summary(processed=False, l1=False, l2=False, case_id="N04")]
    assert re_.verdict(True, summaries, 1.0)[:2] == ("INCONCLUSIVE", "3-service-failure")


def test_ac_5_1_rule_4_pass_at_the_threshold_and_rule_5(re_):
    """AC-5.1: pin check passes, 100% / 100% / ≥ 0.80 gives PASS; layer 3 at exactly 0.80
    passes and 0.7999 fails (rule 5)."""
    assert re_.verdict(True, [_summary()], 0.80)[:2] == ("PASS", "4-thresholds-met")
    assert re_.verdict(True, [_summary()], 0.7999)[:2] == ("FAIL", "5-thresholds-not-met")
    assert re_.verdict(True, [_summary()], None)[:2] == ("FAIL", "5-thresholds-not-met")


def test_fr030_verdict_signature_has_no_judge_or_binding_input(re_):
    """FR-030, FR-031, FR-026: judge data and the dataset binding are not verdict inputs."""
    params = list(inspect.signature(re_.verdict).parameters)
    assert params == ["pin_ok", "case_summaries", "layer3_score"]


def _spec_constants_table():
    text = SPEC_PATH.read_text(encoding="utf-8")
    section = text.split("#### Evaluation constants (rev 2)", 1)[1].split("\n#### ", 1)[0]
    table = {}
    for line in section.splitlines():
        match = re.match(r"^\| `([\w.]+)` \| ([\d.]+) \|", line)
        if match:
            table[match[1]] = Decimal(match[2])
    return table


def _flatten(constants, prefix=""):
    flat = {}
    for key, value in constants.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def test_d1_spec_constants_equal_the_spec_table(re_):
    """FR-031, Evaluation constants (rev 2, D1; rev 3 value_in_cr_decimals): SPEC_CONSTANTS has
    exactly the spec table's keys and numerically equal values."""
    table = _spec_constants_table()
    flat = _flatten(re_.SPEC_CONSTANTS)
    assert len(table) == 17 and table["value_in_cr_decimals"] == 4
    assert set(flat) == set(table)
    for key, value in table.items():
        assert Decimal(str(flat[key])) == value, key
    assert len(re_.LAYER3_FIELDS) == 9


def test_d1_verdict_reads_thresholds_from_spec_constants(re_, monkeypatch):
    """D1: monkeypatching layer3_threshold changes the result of a borderline case."""
    assert re_.verdict(True, [_summary()], 0.75)[0] == "FAIL"
    monkeypatch.setitem(re_.SPEC_CONSTANTS, "layer3_threshold", 0.70)
    assert re_.verdict(True, [_summary()], 0.75)[0] == "PASS"


def test_d1_layer3_tolerance_read_from_spec_constants(re_, monkeypatch):
    """D1: the layer-3 value tolerance comes from SPEC_CONSTANTS."""
    assert _l3(re_, "N01", order_value=1260)["order_value"]["correct"] is False
    monkeypatch.setitem(re_.SPEC_CONSTANTS, "value_tolerance", 0.01)
    assert _l3(re_, "N01", order_value=1260)["order_value"]["correct"] is True


# ============================================================================================
# T047 — pin check (FR-022, AC-5.6, FR-031 step 1 reading (e))
# ============================================================================================


def _check_env(re_, settings, routes):
    return re_.check_environment(settings, RoutingTransport(routes))


def test_ac_5_6_all_pins_matching_gives_ok(re_, settings):
    """AC-5.6, R-11: version, digest and quantisation matching, env matching → ok true."""
    environment, pin_check = _check_env(re_, settings, pin_routes())
    assert pin_check == {"ok": True, "mismatches": []}
    assert environment["ollama_version"] == "0.32.14"
    assert environment["model"]["digest_installed"].startswith("d8b0f5e9760c")
    assert environment["quantization_level"] == "Q4_K_M"
    assert environment["env_mismatch"] == []
    for key in ("python_version", "pip_freeze", "git_head", "platform", "judge"):
        assert key in environment


@pytest.mark.parametrize(
    ("routes", "needle"),
    [
        (pin_routes(version="0.32.13"), "ollama_version"),
        (pin_routes(digest="abcdef123456" + "0" * 52), "model_digest"),
        (pin_routes(tag=None), "model_digest"),
        (pin_routes(quant="Q8_0"), "quantization"),
    ],
    ids=["version", "digest", "tag-missing", "quantization"],
)
def test_ac_5_6_each_mismatch_is_named(re_, settings, routes, needle):
    """AC-5.6 (rev 2): "the installed Ollama version is not 0.32.14", "the installed digest …
    does not start with d8b0f5e9760c", "its quantisation is not Q4_K_M"."""
    _environment, pin_check = _check_env(re_, settings, routes)
    assert pin_check["ok"] is False
    assert any(m.startswith(needle) for m in pin_check["mismatches"]), pin_check
    summary = [_summary()]
    assert re_.verdict(pin_check["ok"], summary, 1.0)[0] == "INCONCLUSIVE"


@pytest.mark.parametrize("endpoint", ["/api/version", "/api/tags", "/api/show"])
@pytest.mark.parametrize(
    ("failure", "kind"),
    [
        (urllib.error.URLError(ConnectionRefusedError(61, "refused")), "unreachable"),
        ((500, b"boom"), "http_error"),
        ((200, b"not json"), "bad_envelope"),
    ],
    ids=["unreachable", "http_error", "bad_envelope"],
)
def test_ac_5_6_failed_request_fails_the_pin_check(re_, settings, endpoint, failure, kind):
    """AC-5.6: "any request that reads these three values fails, so the pins cannot be
    confirmed"."""
    routes = pin_routes()
    routes[endpoint] = failure
    _environment, pin_check = _check_env(re_, settings, routes)
    assert pin_check["ok"] is False
    assert any(endpoint in m and kind in m for m in pin_check["mismatches"]), pin_check


def test_ac_5_6_env_mismatch_fails_the_pin_check(re_):
    """AC-5.6, FR-022: "AGENT_MODEL or AGENT_MODEL_DIGEST from the environment differs from the
    pinned values", recorded as env_mismatch."""
    from conftest import make_settings

    settings = make_settings(AGENT_MODEL="qwen3.5:9b", AGENT_MODEL_DIGEST="ffffffffffff")
    environment, pin_check = _check_env(re_, settings, pin_routes())
    assert pin_check["ok"] is False
    assert len(environment["env_mismatch"]) == 2
    assert sum(m.startswith("env_mismatch") for m in pin_check["mismatches"]) == 2


# ============================================================================================
# T048 — orchestration (FR-022, FR-023, FR-026, FR-027, FR-032, FR-033, FR-034, AC-5.5)
# ============================================================================================


def _by_input():
    re_ = load_run_eval()
    return {re_.expand_input(c["input"]): c for c in _dataset()["cases"]}


def scripted(overrides=None):
    """A scripted stand-in for agent.run: Success with the ground truth, unless overridden.
    Override values are AgentOutcomes, or callables (case) -> AgentOutcome (which may raise)."""
    overrides = overrides or {}
    cases = _by_input()
    calls = []

    def agent_run(raw, settings, *, transport=None, sleep=None):
        case = cases[raw]
        calls.append(case["id"])
        override = overrides.get(case["id"])
        if callable(override):
            return override(case)
        if override is not None:
            return override
        gt = copy.deepcopy(case["ground_truth"])
        return success(gt, model_called=gt["status"] != "rejected")

    agent_run.calls = calls
    return agent_run


def _routes(judge=None):
    routes = pin_routes()
    routes["/v1/chat/completions"] = judge if judge is not None else judge_body()
    return routes


def _run(
    re_,
    tmp_path,
    agent_run,
    *,
    judge=None,
    spec_text=None,
    clock=None,
    routes=None,
    monkeypatch=None,
):
    root = _root(tmp_path, spec_text=spec_text)
    transport = RoutingTransport(routes if routes is not None else _routes(judge))
    code = re_.run(
        root=root,
        env_file=root / "test.env",
        transport=transport,
        sleep=lambda _s: None,
        clock=clock or (lambda: FIXED),
        agent_run=agent_run,
    )
    run_dirs = sorted((root / "evidence" / "eval-runs").iterdir())
    return code, root, run_dirs[-1], transport


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def no_real_agent(monkeypatch):
    """Fails the test if the real order_agent.agent.run is called (F1)."""
    from order_agent import agent

    monkeypatch.setattr(agent, "run", lambda *a, **k: pytest.fail("real agent.run was called"))


def test_ac_5_1_clean_scripted_run_passes_with_complete_evidence(
    re_, tmp_path, no_real_agent, capsys
):
    """FR-022, FR-032, AC-5.1, contracts/eval-results.md: a clean scripted run gives PASS, exit
    0, and the full run folder."""
    agent_run = scripted()
    code, root, run_dir, transport = _run(re_, tmp_path, agent_run)
    assert code == 0
    assert len(agent_run.calls) == 28
    names = {p.name for p in run_dir.iterdir()}
    assert names == {
        "environment.json",
        "run.json",
        "raw",
        "cases",
        "judge",
        "eval-results.json",
        "summary.md",
    }
    run = _json(run_dir / "run.json")
    for key in (
        "run_id",
        "started_at",
        "ended_at",
        "completed",
        "model",
        "runner",
        "settings",
        "prompt_version",
        "system_sha256",
        "schema_version",
        "mr_version",
        "dataset",
        "code_sha256",
        "judge",
        "pin_check",
        "env_mismatch",
        "git_head",
        "python_version",
    ):
        assert key in run, key
    assert run["completed"] is True and run["run_id"] == "20261122T101500Z"
    assert run["settings"]["num_ctx_formula"] and run["settings"]["seed"] == 42
    assert run["mr_version"] == "mr-1" and run["schema_version"] == "1.0"
    assert set(run["code_sha256"]) == {"src/order_agent/validators.py", ".harness/run_eval.py"}
    assert run["dataset"]["matches_spec"] is True
    assert run["dataset"]["sha256"] == hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    assert run["judge"]["timeout_s"] == 180 and run["judge"]["disable_thinking"] is True
    # raw/<case>/attempt-<n>.json for model-called cases only
    raw = _json(run_dir / "raw" / "N01" / "attempt-1.json")
    assert set(raw["request"]) >= {
        "url",
        "model",
        "system",
        "prompt",
        "options",
        "think",
        "format",
        "stream",
    }
    assert raw["request"]["options"]["num_ctx"] == 4096
    assert N01_TEXT in raw["request"]["prompt"]
    assert set(raw["response"]) == {"http_status", "body", "raw_text"}
    for case_id in ("X01", "X02", "X03", "X04"):
        assert not (run_dir / "raw" / case_id).exists()
        assert _json(run_dir / "cases" / f"{case_id}.json")["model_called"] is False
    case_files = sorted(p.stem for p in (run_dir / "cases").iterdir())
    assert len(case_files) == 28
    n01 = _json(run_dir / "cases" / "N01.json")
    assert set(n01) == {
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
    }
    assert n01["judge"]["status"] == "ok" and n01["judge"]["rating"] == 5
    assert not (run_dir / "feedback").exists() or not list((run_dir / "feedback").iterdir())
    assert len(list((run_dir / "judge").iterdir())) == 18
    results = _json(run_dir / "eval-results.json")
    assert results["format"] == "eval-results/1.0"
    for key in (
        "run_id",
        "run_dir",
        "verdict",
        "verdict_rule",
        "verdict_reason",
        "thresholds",
        "layers",
        "application_failures",
        "semantic_misses",
        "service_failures",
        "judge",
        "pin_check",
        "dataset",
        "metadata",
        "cases",
    ):
        assert key in results, key
    assert results["verdict"] == "PASS" and results["verdict_rule"] == "4-thresholds-met"
    assert results["layers"]["layer3"]["compared"] == 162
    assert results["layers"]["layer3"]["cases"] == 18
    assert results["layers"]["layer2"]["by_invariant"]["INV-10"]["applicable"] == 24
    assert results["layers"]["layer2"]["by_invariant"]["INV-11"]["applicable"] == 18
    assert set(results["layers"]["layer2"]["by_agent_code"]) >= {"G-5", "C-5"}
    assert results["judge"]["rated"] == 18 and results["judge"]["mean_rating"] == 5
    assert results["semantic_misses"] == {"count": 0, "cases": []}
    assert results["application_failures"] == {"count": 0, "cases": []}
    assert (root / "evidence" / "eval-results.json").read_bytes() == (
        run_dir / "eval-results.json"
    ).read_bytes()
    summary = (run_dir / "summary.md").read_text("utf-8")
    headings = re.findall(r"^## (\d)\. ", summary, re.M)
    assert headings == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert summary.rstrip().endswith(
        "ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it."
    )
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert re.fullmatch(
        r"Verdict: PASS  L1 28/28  L2 28/28  L3 162/162 \(100\.0%\)  run: "
        r"evidence/eval-runs/20261122T101500Z",
        last,
    ), last
    assert len(transport.urls("/v1/chat/completions")) == 18


def test_fr032_ac_5_5_failures_have_feedback_and_counting(re_, tmp_path, no_real_agent):
    """FR-023 (rev 2, F2/U3), FR-032, AC-5.5: application failure, unresolved service failure,
    semantic miss and agent exception are each counted only in their own block, and every
    failing case has a feedback record."""

    def raising(_case):
        raise RuntimeError("agent bug")

    miss = copy.deepcopy(_case("E01")["ground_truth"])
    miss["order"]["execution_period"] = "within 36 months"
    retried = success(copy.deepcopy(_case("N02")["ground_truth"]))
    retried.attempts = [_attempt(1, "timeout"), _attempt(2)]
    agent_run = scripted(
        {
            "M02": app_failure("post_validation", ["G-1"], candidate=_case("M02")["ground_truth"]),
            "N04": service_failure("connection_lost"),
            "E01": success(miss),
            "A03": raising,
            "N02": retried,
        }
    )
    code, root, run_dir, _ = _run(re_, tmp_path, agent_run)
    assert code == 1
    results = _json(run_dir / "eval-results.json")
    assert results["verdict"] == "FAIL" and results["verdict_rule"] == "2-app-failure"
    apps = {c["case_id"]: c for c in results["application_failures"]["cases"]}
    assert set(apps) == {"M02", "A03"} and results["application_failures"]["count"] == 2
    assert apps["M02"]["checks"] == ["G-1"] and apps["M02"]["layers"] == [2]
    assert apps["A03"]["checks"] == ["EXC"] and apps["A03"]["stage"] == "exception"
    assert apps["A03"]["layers"] == [1, 2]
    assert results["semantic_misses"]["cases"] == [
        {"case_id": "E01", "fields": ["execution_period"], "feedback": "feedback/E01.json"}
    ]
    model = results["service_failures"]["model"]
    assert model["count"] == 1 and model["unresolved_cases"] == [
        {"case_id": "N04", "kind": "connection_lost"}
    ]
    assert model["retried_attempts"] == 1
    assert {"case_id": "N02", "n": 1, "kind": "timeout"} in model["attempts"]
    for layer in ("layer1", "layer2", "layer3"):
        assert results["layers"][layer]["not_scored"] == ["N04"], layer
    assert "N04" not in results["layers"]["layer1"]["failed_cases"]
    assert results["layers"]["layer1"]["passed"] == 26  # 28 - N04 (not scored) - A03 (exception)
    assert results["layers"]["layer1"]["total"] == 28
    assert set(results["layers"]["layer2"]["failed_cases"]) == {"M02", "A03"}
    feedback = {p.stem for p in (run_dir / "feedback").iterdir()}
    assert feedback == {"M02", "N04", "E01", "A03"}
    record = _json(run_dir / "feedback" / "E01.json")
    assert set(record) == {
        "case_id",
        "layers_failed",
        "failed_checks",
        "expected",
        "actual",
        "raw_model_output",
        "parser_log",
        "agent_errors",
        "reason",
        "attempts",
        "run_id",
    }
    assert record["layers_failed"] == [3] and record["expected"] == _case("E01")["ground_truth"]
    assert _json(run_dir / "feedback" / "N04.json")["layers_failed"] == ["service"]
    exc = _json(run_dir / "cases" / "A03.json")
    assert exc["outcome"] == "application_failure" and exc["stage"] == "exception"
    assert exc["exception"]["type"] == "RuntimeError" and "agent bug" in exc["exception"]["message"]
    assert "Traceback" in exc["exception"]["traceback"]
    assert exc["agent_errors"][0]["code"] == "EXC" and exc["layer3"] is None
    exc_feedback = _json(run_dir / "feedback" / "A03.json")
    assert exc_feedback["raw_model_output"] is None and "RuntimeError" in exc_feedback["reason"]
    n04 = _json(run_dir / "cases" / "N04.json")
    assert n04["scored"] is False and n04["outcome"] == "service_failure"
    assert (n04["layer3"]["correct"], n04["layer3"]["compared"]) == (0, 9)
    assert len(n04["attempts"]) == 3
    assert len(list((run_dir / "raw" / "N04").iterdir())) == 3
    assert _json(run_dir / "run.json")["completed"] is True
    assert len(list((run_dir / "cases").iterdir())) == 28  # the run continued after A03


def test_fr023_unresolved_service_failure_only_gives_inconclusive(re_, tmp_path, no_real_agent):
    """FR-031 rule 3, U3: one unresolved service failure and nothing else gives INCONCLUSIVE
    (exit 2); L1 27/28 with application_failures.count 0."""
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted({"N04": service_failure()}))
    assert code == 2
    results = _json(run_dir / "eval-results.json")
    assert results["verdict_rule"] == "3-service-failure"
    assert results["layers"]["layer1"]["passed"] == 27
    assert results["application_failures"]["count"] == 0
    assert results["layers"]["layer1"]["failed_cases"] == []


def test_fr022_pin_failure_still_processes_every_case(re_, tmp_path, no_real_agent):
    """FR-022, AC-5.6: a failed pin check gives INCONCLUSIVE (exit 2) and every case is still
    processed."""
    routes = _routes()
    routes["/api/version"] = (200, b'{"version": "0.30.0"}')
    agent_run = scripted()
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, agent_run, routes=routes)
    assert code == 2 and len(agent_run.calls) == 28
    results = _json(run_dir / "eval-results.json")
    assert results["verdict_rule"] == "1-pin-check"
    assert results["pin_check"]["ok"] is False


@pytest.mark.parametrize(
    "judge",
    [
        judge_body(rating=1, rationale="Unfaithful."),
        urllib.error.URLError(ConnectionRefusedError(61, "refused")),
        lambda method, url, payload: (_ for _ in ()).throw(RuntimeError("judge exploded")),
    ],
    ids=["rates-1", "unreachable", "raises"],
)
def test_ac_5_4_judge_never_changes_the_verdict(re_, tmp_path, no_real_agent, judge):
    """FR-030, AC-5.4 (U1): the verdict is the same with the judge rating every case 1, the
    judge unreachable, or the judge raising for every case; the run completes."""
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted(), judge=judge)
    assert code == 0
    results = _json(run_dir / "eval-results.json")
    assert results["verdict"] == "PASS"
    if isinstance(judge, tuple):
        assert results["judge"]["mean_rating"] == 1
        return
    assert results["service_failures"]["judge"]["count"] == 18
    n01 = _json(run_dir / "cases" / "N01.json")
    assert n01["judge"]["status"] == "failed"
    if callable(judge):
        assert {c["kind"] for c in results["service_failures"]["judge"]["cases"]} == {"exception"}
        assert n01["judge"]["kind"] == "exception"
    assert _json(run_dir / "run.json")["completed"] is True


def test_fr023_agent_exception_case_is_processed_and_fails(re_, tmp_path, no_real_agent):
    """FR-023 (rev 2, U1): an agent-exception case counts as processed and gives FAIL by
    rule 2."""

    def raising(_case):
        raise ValueError("bad")

    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted({"N01": raising}))
    assert code == 1
    results = _json(run_dir / "eval-results.json")
    assert results["verdict_rule"] == "2-app-failure"
    assert results["layers"]["layer3"]["correct"] == 153  # N01 scores 0 of 9


def test_r13_interrupted_run_leaves_top_level_results_untouched(re_, tmp_path, no_real_agent):
    """R-13, contracts/eval-results.md: a KeyboardInterrupt gives completed: false and exit 3,
    and evidence/eval-results.json is left untouched."""
    root = _root(tmp_path)
    (root / "evidence").mkdir()
    sentinel = root / "evidence" / "eval-results.json"
    sentinel.write_text('{"previous": true}', encoding="utf-8")

    def interrupt(_case):
        raise KeyboardInterrupt

    code = re_.run(
        root=root,
        env_file=root / "test.env",
        transport=RoutingTransport(_routes()),
        sleep=lambda _s: None,
        clock=lambda: FIXED,
        agent_run=scripted({"M01": interrupt}),
    )
    assert code == 3
    assert sentinel.read_text(encoding="utf-8") == '{"previous": true}'
    run_dir = next((root / "evidence" / "eval-runs").iterdir())
    assert _json(run_dir / "run.json")["completed"] is False
    assert not (run_dir / "eval-results.json").exists()


def test_fr026_dataset_binding_states_and_same_verdict(re_, tmp_path, no_real_agent):
    """FR-026 (rev 2): a matching DATASET-BINDING line gives matches_spec true, a different hash
    false (with the warning in summary.md §1), no line null; the verdict is the same in all."""
    sha = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    variants = {
        True: f"DATASET-BINDING dataset_version=1.0 sha256={sha}\n",
        False: f"DATASET-BINDING dataset_version=1.0 sha256={'0' * 64}\n",
        None: "no binding\n",
    }
    for expected, spec_text in variants.items():
        code, _root_dir, run_dir, _ = _run(
            re_, tmp_path / str(expected), scripted(), spec_text=spec_text
        )
        assert code == 0
        results = _json(run_dir / "eval-results.json")
        assert results["dataset"]["matches_spec"] is expected
        assert results["verdict"] == "PASS"
        section1 = (run_dir / "summary.md").read_text("utf-8").split("## 2.")[0]
        assert ("WARNING" in section1) is (expected is not True)


def test_fr034_report_never_records_the_owner_decision(re_, tmp_path, no_real_agent):
    """FR-034: "The final ACCEPT/REJECT decision belongs to the owner (Balakrishnan)" and the system
    "MUST NOT record that decision": the summary states this in its last section, and neither
    eval-results.json nor run.json holds an accept/reject field."""
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted())
    assert code == 0
    summary = (run_dir / "summary.md").read_text("utf-8")
    section8 = summary.split("## 8. ")[1]
    assert "ACCEPT/REJECT is the owner's decision (FR-034); this report does not record it." in (
        section8
    )
    for name in ("eval-results.json", "run.json"):
        text = (run_dir / name).read_text("utf-8").lower()
        assert '"decision"' not in text and '"accept' not in text and '"reject"' not in text


def test_fr033_main_has_no_threshold_case_or_agent_options(re_, monkeypatch):
    """FR-033, constitution III: main accepts only --env-file; no option changes thresholds,
    cases or the agent."""
    for argv in (["--threshold", "0.5"], ["--cases", "N01"], ["--agent-run", "x"]):
        with pytest.raises(SystemExit) as info:
            re_.main(argv)
        assert info.value.code == 2
    calls = []
    monkeypatch.setattr(re_, "run", lambda **kwargs: calls.append(kwargs) or 0)
    assert re_.main(["--env-file", "x.env"]) == 0
    assert set(calls[0]) == {"root", "env_file"} and calls[0]["env_file"] == "x.env"
    assert calls[0]["root"] == RUN_EVAL_PATH.resolve().parents[1]


def test_fr022_run_ids_do_not_collide(re_, tmp_path, no_real_agent):
    """R-15: two runs in the same second get distinct run folders."""
    root = _root(tmp_path)
    for _ in range(2):
        assert (
            re_.run(
                root=root,
                env_file=root / "test.env",
                transport=RoutingTransport(_routes()),
                sleep=lambda _s: None,
                clock=lambda: FIXED,
                agent_run=scripted(),
            )
            == 0
        )
    assert len(list((root / "evidence" / "eval-runs").iterdir())) == 2


def test_inv_11_layer_separation_wrong_value_in_cr(re_, tmp_path, no_real_agent):
    """INV-11, FR-029 (rev 3): a wrong value_in_cr fails layer 2 (INV-11) and is listed under
    application_failures with checks ["INV-11"]; the layer-3 count and results are unchanged."""
    wrong = copy.deepcopy(_case("N01")["ground_truth"])
    wrong["order"]["value_in_cr"] = 1250.6
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted({"N01": success(wrong)}))
    assert code == 1
    results = _json(run_dir / "eval-results.json")
    assert results["application_failures"]["cases"] == [
        {
            "case_id": "N01",
            "layers": [2],
            "checks": ["INV-11"],
            "stage": None,
            "feedback": "feedback/N01.json",
        }
    ]
    assert results["layers"]["layer3"]["correct"] == 162
    assert results["layers"]["layer3"]["compared"] == 162


def test_inv_11_independent_of_the_agent_end_of_chain(re_, tmp_path, no_real_agent, monkeypatch):
    """INV-11, R-17: with order_agent.validators.value_in_cr replaced by a buggy version (lakh
    left unconverted), the agent's own C-5 shares the function and reports nothing, but the
    runner's independent INV-11 fails N03 and the verdict is FAIL."""
    from conftest import mr_from_ground_truth

    from order_agent import agent, validators

    def buggy(order_value, currency, unit):
        return None if currency != "INR" or order_value is None else float(order_value)

    monkeypatch.setattr(validators, "value_in_cr", buggy)
    case = _case("N03")
    source = case["input"]["text"]
    candidate, _trace = agent.assemble(mr_from_ground_truth(case["ground_truth"], source))
    assert candidate["order"]["value_in_cr"] == 85.4
    assert [e.code for e in validators.post_validate(source, candidate)] == []
    code, _root_dir, run_dir, _ = _run(re_, tmp_path, scripted({"N03": success(candidate)}))
    assert code == 1
    results = _json(run_dir / "eval-results.json")
    assert results["verdict"] == "FAIL"
    checks = [(c["case_id"], c["checks"]) for c in results["application_failures"]["cases"]]
    assert checks == [("N03", ["INV-11"])]
