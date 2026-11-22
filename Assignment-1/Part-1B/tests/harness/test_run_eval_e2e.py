"""End-to-end runner check: `run_eval.run` over the real 28-case dataset with the **real**
`order_agent.agent.run` and fake transports only (rev 2, F1). It verifies FR-016, FR-022,
FR-023, FR-027 … FR-032, FR-035, AC-5.1, AC-5.3, AC-5.4, AC-5.5 and INV-11. No Ollama, no judge,
no network: the autouse socket block stays active."""

from __future__ import annotations

import copy
import datetime
import json
import re
import urllib.error

import pytest
from conftest import (
    DATASET_PATH,
    ENV_EXAMPLE_VALUES,
    SPEC_PATH,
    RoutingTransport,
    judge_body,
    load_run_eval,
    mr_from_ground_truth,
    ollama_envelope,
    pin_routes,
)

FIXED = datetime.datetime(2026, 11, 22, 11, 0, 0, tzinfo=datetime.UTC)
CASES = {c["id"]: c for c in json.loads(DATASET_PATH.read_text("utf-8"))["cases"]}
MARKER = re.compile(r"^<<<ANNOUNCEMENT id=([0-9a-f]{12})>>>")


def _text(case_id):
    run_eval = load_run_eval()
    return run_eval.expand_input(CASES[case_id]["input"]).decode("utf-8", "replace")


def _canned():
    """case id → canned mr-1 response built from the ground truth (no value_in_cr key).
    J01 gets N01's response and J02 gets R02's."""
    responses = {}
    for case_id, case in CASES.items():
        if case["ground_truth"]["status"] == "rejected":
            continue
        source_id = {"J01": "N01", "J02": "R02"}.get(case_id, case_id)
        source = CASES[source_id]
        responses[case_id] = mr_from_ground_truth(source["ground_truth"], _text(source_id))
    return responses


def _marker_index():
    from order_agent import prompt

    index = {}
    for case_id in CASES:
        index[prompt.build(_text(case_id)).marker_id] = case_id
    return index


class Model:
    """The /api/generate route: answers each case with its canned response, or an override
    (a dict MR, or an exception to raise). Records which cases reached the model."""

    def __init__(self, overrides=None):
        self.responses = _canned()
        self.responses.update({k: v for k, v in (overrides or {}).items() if isinstance(v, dict)})
        self.raises = {k: v for k, v in (overrides or {}).items() if isinstance(v, BaseException)}
        self.index = _marker_index()
        self.seen = []

    def __call__(self, method, url, payload):
        case_id = self.index[MARKER.match(payload["prompt"])[1]]
        self.seen.append(case_id)
        assert "value_in_cr" not in json.dumps(self.responses.get(case_id, {}))
        if case_id in self.raises:
            raise self.raises[case_id]
        return (200, ollama_envelope(json.dumps(self.responses[case_id], ensure_ascii=False)))


def _root(tmp_path):
    root = tmp_path / "root"
    (root / "evals").mkdir(parents=True)
    (root / "specs" / "001-order-extraction-agent").mkdir(parents=True)
    (root / "evals" / "dataset.json").write_bytes(DATASET_PATH.read_bytes())
    (root / "specs" / "001-order-extraction-agent" / "spec.md").write_bytes(SPEC_PATH.read_bytes())
    (root / "test.env").write_text(
        "".join(f"{k}={v}\n" for k, v in ENV_EXAMPLE_VALUES.items()), encoding="utf-8"
    )
    return root


def _e2e(tmp_path, overrides=None, judge=None):
    run_eval = load_run_eval()
    model = Model(overrides)
    routes = pin_routes()
    routes["/api/generate"] = model
    routes["/v1/chat/completions"] = judge if judge is not None else judge_body(5)
    transport = RoutingTransport(routes)
    root = _root(tmp_path)
    code = run_eval.run(
        root=root,
        env_file=root / "test.env",
        transport=transport,
        sleep=lambda _s: None,
        clock=lambda: FIXED,
    )
    run_dir = next((root / "evidence" / "eval-runs").iterdir())
    results = json.loads((run_dir / "eval-results.json").read_text("utf-8"))
    return code, results, run_dir, model, transport


def _case_file(run_dir, case_id):
    return json.loads((run_dir / "cases" / f"{case_id}.json").read_text("utf-8"))


def test_ac_5_1_clean_end_to_end_run_passes(tmp_path):
    """AC-5.1, FR-016, FR-027 … FR-029, FR-035, INV-11: with the real agent and canned responses
    built from the ground truth, X01–X04 make no model call, exactly 24 generate calls are made,
    every case passes layers 1 and 2 (the agent's A-9 reproduces every ground-truth
    value_in_cr), layer 3 is 162/162, and the verdict is PASS (exit 0)."""
    code, results, run_dir, model, transport = _e2e(tmp_path)
    assert code == 0, results["verdict_reason"]
    assert results["verdict"] == "PASS"
    assert len(transport.urls("/api/generate")) == 24
    assert sorted(model.seen) == sorted(c for c in CASES if c not in {"X01", "X02", "X03", "X04"})
    for case_id in ("X01", "X02", "X03", "X04"):
        assert not (run_dir / "raw" / case_id).exists()
        assert _case_file(run_dir, case_id)["model_called"] is False
    layers = results["layers"]
    assert (layers["layer1"]["passed"], layers["layer2"]["passed"]) == (28, 28)
    assert (layers["layer3"]["correct"], layers["layer3"]["compared"]) == (162, 162)
    assert results["semantic_misses"]["count"] == 0
    assert results["application_failures"]["count"] == 0
    for case_id, case in CASES.items():
        candidate = _case_file(run_dir, case_id)["candidate"]
        assert candidate == case["ground_truth"], case_id


def test_fr010_variant_a_ungrounded_client_quote_fails(tmp_path):
    """FR-010, INV-2, G-1, AC-5.5: N01's response with an ungrounded client quote → FAIL (exit 1)
    and a feedback record for N01."""
    bad = copy.deepcopy(_canned()["N01"])
    bad["orders"][0].update(client="NTPC Ltd", client_quote="NTPC Ltd")
    code, results, run_dir, _model, _transport = _e2e(tmp_path, {"N01": bad})
    assert code == 1 and results["verdict"] == "FAIL"
    failures = {c["case_id"]: c for c in results["application_failures"]["cases"]}
    assert set(failures) == {"N01"}
    assert "G-1" in failures["N01"]["checks"] and "INV-2" in failures["N01"]["checks"]
    feedback = json.loads((run_dir / "feedback" / "N01.json").read_text("utf-8"))
    assert feedback["case_id"] == "N01" and 2 in feedback["layers_failed"]
    assert feedback["raw_model_output"] and "NTPC Ltd" in feedback["raw_model_output"]


def test_fr023_ac_5_3_variant_b_unresolved_connection_loss_is_inconclusive(tmp_path):
    """FR-023, AC-5.3: N04 gets ConnectionResetError on every attempt (connection_lost) →
    INCONCLUSIVE (exit 2); N04 is in every layer's not_scored and not an application failure."""
    code, results, run_dir, model, _transport = _e2e(
        tmp_path, {"N04": ConnectionResetError(54, "reset")}
    )
    assert code == 2 and results["verdict_rule"] == "3-service-failure"
    assert model.seen.count("N04") == 3
    for layer in ("layer1", "layer2", "layer3"):
        assert results["layers"][layer]["not_scored"] == ["N04"]
    assert results["application_failures"]["count"] == 0
    assert results["service_failures"]["model"]["unresolved_cases"] == [
        {"case_id": "N04", "kind": "connection_lost"}
    ]
    assert len(list((run_dir / "raw" / "N04").iterdir())) == 3


def test_ac_5_4_variant_c_unreachable_judge_still_passes(tmp_path):
    """AC-5.4, FR-030: the judge unreachable for every case → the verdict is still PASS."""
    judge = urllib.error.URLError(ConnectionRefusedError(61, "refused"))
    code, results, _run_dir, _model, _transport = _e2e(tmp_path, judge=judge)
    assert code == 0 and results["verdict"] == "PASS"
    assert results["service_failures"]["judge"]["count"] == 18


def test_fr009_variant_d_ranking_done_by_the_agent(tmp_path):
    """FR-009, INV-9: the M02 response puts ₹95 lakh first and ₹1.2 crore second; the agent's
    ranking makes 1.2 crore the top-level order and INV-9 holds."""
    mr = copy.deepcopy(_canned()["M02"])
    mr["orders"].sort(key=lambda o: o["unit"] != "lakh")  # 95 lakh first
    assert mr["orders"][0]["unit"] == "lakh"
    code, results, run_dir, _model, _transport = _e2e(tmp_path, {"M02": mr})
    assert code == 0
    m02 = _case_file(run_dir, "M02")
    assert m02["candidate"]["order"]["order_value"] == 1.2
    assert m02["assembly_trace"]["top_index"] == 1
    assert "INV-9" in m02["layer2"]["applicable"] and m02["layer2"]["pass"] is True


def test_ac_5_5_variant_e_semantic_miss_only(tmp_path):
    """FR-023 (F2), AC-5.5: a wrong E01 execution_period is a semantic miss only; PASS stays PASS
    while layer 3 ≥ 0.80, and E01 has a feedback record."""
    mr = copy.deepcopy(_canned()["E01"])
    mr["execution_period"] = "within 26 months"
    code, results, run_dir, _model, _transport = _e2e(tmp_path, {"E01": mr})
    assert code == 0 and results["verdict"] == "PASS"
    assert results["semantic_misses"]["cases"] == [
        {"case_id": "E01", "fields": ["execution_period"], "feedback": "feedback/E01.json"}
    ]
    assert results["application_failures"]["count"] == 0
    assert results["layers"]["layer3"]["correct"] == 161
    assert (run_dir / "feedback" / "E01.json").exists()


def test_inv_11_variant_f_runner_catches_a_shared_conversion_bug(tmp_path, monkeypatch):
    """INV-11, FR-035 (rev 3): with order_agent.validators.value_in_cr monkeypatched to skip the
    lakh multiplier, the agent's own C-5 shares the function and stays silent, but the runner's
    independent INV-11 fails N03 → FAIL (exit 1), N03 listed with INV-11; layer 3 stays
    162/162."""
    from order_agent import validators

    real = validators.value_in_cr

    def buggy(order_value, currency, unit):
        if currency == "INR" and unit == "lakh":
            return float(order_value)
        return real(order_value, currency, unit)

    monkeypatch.setattr(validators, "value_in_cr", buggy)
    code, results, _run_dir, _model, _transport = _e2e(tmp_path)
    assert code == 1 and results["verdict"] == "FAIL"
    failures = {c["case_id"]: c["checks"] for c in results["application_failures"]["cases"]}
    assert failures["N03"] == ["INV-11"]
    assert set(failures) == {"N03", "M02", "M03"}  # every case with an INR lakh order
    assert (results["layers"]["layer3"]["correct"], results["layers"]["layer3"]["compared"]) == (
        162,
        162,
    )


@pytest.mark.parametrize("case_id", ["X01", "X02", "X03", "X04"])
def test_fr016_rejected_cases_never_reach_the_transport(tmp_path, case_id):
    """FR-016, AC-3.1 … AC-3.4: the guard cases make no transport call at all."""
    run_eval = load_run_eval()
    from conftest import FakeTransport, make_settings

    from order_agent import agent

    transport = FakeTransport([])
    raw = run_eval.expand_input(CASES[case_id]["input"])
    outcome = agent.run(raw, make_settings(), transport=transport, sleep=lambda _s: None)
    assert outcome.result == CASES[case_id]["ground_truth"]
    assert transport.calls == []
