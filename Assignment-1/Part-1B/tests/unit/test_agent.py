"""The agent pipeline with canned model responses (spec AC-1.x, AC-2.x, AC-3.5/3.6, AC-4.x,
FR-001, FR-019, FR-023, FR-035; data-model.md assembly rules A-1 … A-9)."""

from __future__ import annotations

import json
import urllib.error

import pytest
from conftest import N01_TEXT, FakeTransport, build_mr, ok_reply, ollama_envelope


def _run(settings, no_sleep, text, responses):
    from order_agent import agent

    transport = FakeTransport(responses)
    raw = text.encode("utf-8") if isinstance(text, str) else text
    outcome = agent.run(raw, settings, transport=transport, sleep=no_sleep)
    return outcome, transport


def _ok(settings, no_sleep, text, mr_obj):
    from order_agent import agent, validators

    outcome, transport = _run(settings, no_sleep, text, [ok_reply(mr_obj)])
    assert isinstance(outcome, agent.Success), getattr(outcome, "errors", outcome)
    assert validators.check_output(outcome.result) == []  # FR-001: every Success conforms
    return outcome, transport


# ------------------------------------------- US1 part (T033) -------------------------------------


def test_ac_1_1_n01_extracted_with_full_result(settings, no_sleep):
    """AC-1.1, A-3 … A-9, FR-035: the N01 text gives the full AC-1.1 result."""
    outcome, transport = _ok(settings, no_sleep, N01_TEXT, build_mr())
    result = outcome.result
    assert result == {
        "schema_version": "1.0",
        "status": "extracted",
        "company": "Example Transformers Limited",
        "announcement_date": "2026-11-20",
        "order": {
            "order_value": 1250.5,
            "currency": "INR",
            "unit": "crore",
            "value_in_cr": 1250.5,
            "client": "NTPC Limited",
            "order_type": "supply",
            "execution_period": "within 18 months",
        },
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
    assert "value_in_cr" not in result["evidence"]
    assert outcome.model_called is True
    assert len(outcome.attempts) == 1 and len(transport.calls) == 1
    assert outcome.parser_log == []
    assert outcome.assembly_trace["value_in_cr"] == [1250.5]


def test_ac_1_2_lakh_value_as_stated_and_value_in_cr(settings, no_sleep):
    """AC-1.2, FR-006, FR-035: 85.4 lakh stays 85.4; value_in_cr is 0.854."""
    text = N01_TEXT.replace("₹1,250.50 crore", "Rs. 85.40 lakh")
    mr = build_mr(order={"order_value": 85.4, "unit": "lakh", "value_quote": "Rs. 85.40 lakh"})
    order = _ok(settings, no_sleep, text, mr)[0].result["order"]
    assert (order["order_value"], order["unit"], order["value_in_cr"]) == (85.4, "lakh", 0.854)


@pytest.mark.parametrize(
    ("quote", "value", "currency"), [("USD 15 million", 15, "USD"), ("EUR 2.3 Mn", 2.3, "EUR")]
)
def test_ac_1_3_foreign_currency_export_value_in_cr_null(
    settings, no_sleep, quote, value, currency
):
    """AC-1.3, FR-035: USD/EUR million with export, value_in_cr null (no FX)."""
    text = N01_TEXT.replace("₹1,250.50 crore", quote).replace(
        "supply of transformers", "an export order for transformers"
    )
    mr = build_mr(
        order={"order_value": value, "currency": currency, "unit": "million", "value_quote": quote},
        order_type="export",
        order_type_quote="export order",
    )
    order = _ok(settings, no_sleep, text, mr)[0].result["order"]
    assert order["currency"] == currency and order["unit"] == "million"
    assert order["order_type"] == "export" and order["value_in_cr"] is None


def test_ac_1_6_inr_million_and_no_marker_crore(settings, no_sleep):
    """AC-1.6, FR-035 (rev 3): INR 48.5 million gives 4.85; "340 crore" with currency INR (no
    marker in the text, CONFIRMED P-2) passes post-validation with 340; a null value gives null."""
    text = N01_TEXT.replace("₹1,250.50 crore", "INR 48.5 million")
    mr = build_mr(order={"order_value": 48.5, "unit": "million", "value_quote": "INR 48.5 million"})
    order = _ok(settings, no_sleep, text, mr)[0].result["order"]
    assert (order["order_value"], order["unit"], order["value_in_cr"]) == (48.5, "million", 4.85)

    text = N01_TEXT.replace("₹1,250.50 crore", "340 crore")
    mr = build_mr(order={"order_value": 340, "value_quote": "340 crore"})
    order = _ok(settings, no_sleep, text, mr)[0].result["order"]
    assert (order["currency"], order["value_in_cr"]) == ("INR", 340)

    no_value = {"order_value": None, "currency": None, "unit": None, "value_quote": None}
    result = _ok(settings, no_sleep, N01_TEXT, build_mr(order=no_value))[0].result
    assert result["order"]["value_in_cr"] is None
    assert result["status"] == "needs_clarification"


def test_ac_1_4_dates_and_unstated_fields_confirmed_p5(settings, no_sleep):
    """AC-1.4, FR-004, FR-012 rev 2 (CONFIRMED P-5): a real date passes; 2026-02-30 is OUT-DATE;
    a null date has no evidence key and is listed in unstated_fields, and so is a null period."""
    from order_agent import agent

    assert _ok(settings, no_sleep, N01_TEXT, build_mr())[0].result["announcement_date"] == (
        "2026-11-20"
    )

    outcome, _ = _run(
        settings, no_sleep, N01_TEXT, [ok_reply(build_mr(announcement_date="2026-02-30"))]
    )
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "post_validation"
    assert [e.code for e in outcome.errors] == ["OUT-DATE"]

    mr = build_mr(announcement_date=None, announcement_date_quote=None)
    result = _ok(settings, no_sleep, N01_TEXT, mr)[0].result
    assert result["announcement_date"] is None and "announcement_date" not in result["evidence"]
    assert result["unstated_fields"] == ["announcement_date"]

    mr = build_mr(
        announcement_date=None,
        announcement_date_quote=None,
        execution_period=None,
        execution_period_quote=None,
    )
    result = _ok(settings, no_sleep, N01_TEXT, mr)[0].result
    assert result["unstated_fields"] == ["announcement_date", "execution_period"]


def test_ac_1_5_exchange_as_company_is_application_failure(settings, no_sleep):
    """AC-1.5, FR-003, G-5: an MR naming BSE Limited as company is an ApplicationFailure that
    carries the candidate and the raw text."""
    from order_agent import agent

    mr = build_mr(company="BSE Limited", company_quote="To, BSE Limited")
    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(mr)])
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "post_validation"
    assert [e.code for e in outcome.errors] == ["G-5"]
    assert outcome.candidate["company"] == "BSE Limited"
    assert json.loads(outcome.raw_text)["company"] == "BSE Limited"


def test_fr010_ungrounded_client_quote_fails_g1(settings, no_sleep):
    """FR-010, INV-2, G-1: an ungrounded client quote is an ApplicationFailure."""
    from order_agent import agent

    mr = build_mr(order={"client": "NTPC Ltd", "client_quote": "NTPC Ltd"})
    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(mr)])
    assert isinstance(outcome, agent.ApplicationFailure)
    assert "G-1" in [e.code for e in outcome.errors]


def test_fr023_non_json_is_parse_failure_after_one_attempt(settings, no_sleep):
    """FR-019, FR-023: non-JSON text is an ApplicationFailure (parse) and is never retried."""
    from order_agent import agent

    outcome, transport = _run(
        settings, no_sleep, N01_TEXT, [(200, ollama_envelope("Sure! Here is the data."))]
    )
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "parse" and outcome.candidate is None
    assert outcome.errors[0].code == "MR-SCHEMA" and "PC-3" in outcome.errors[0].message
    assert outcome.raw_text == "Sure! Here is the data."
    assert len(transport.calls) == 1 and len(outcome.attempts) == 1 and no_sleep.calls == []


def test_fr019_lowercase_currency_is_mr_schema_not_coerced(settings, no_sleep):
    """FR-019: "inr" gives MR-SCHEMA, never a coerced value."""
    from order_agent import agent

    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(build_mr(order={"currency": "inr"}))])
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "mr_schema" and outcome.candidate is None
    assert {e.code for e in outcome.errors} == {"MR-SCHEMA"}


def test_fr019_mc2_break_is_mr_consistency(settings, no_sleep):
    """FR-019, MC-2: a value without its quote gives mr_consistency."""
    from order_agent import agent

    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(build_mr(company_quote=None))])
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "mr_consistency"
    assert {e.code for e in outcome.errors} == {"MR-CONSIST"}


def test_fr023_three_unreachable_attempts_give_service_failure(settings, no_sleep):
    """FR-023: three URLErrors give a ServiceFailure with 3 attempts, last_kind unreachable."""
    from order_agent import agent

    errors = [urllib.error.URLError(ConnectionRefusedError(61, "refused")) for _ in range(3)]
    outcome, transport = _run(settings, no_sleep, N01_TEXT, errors)
    assert isinstance(outcome, agent.ServiceFailure)
    assert len(outcome.attempts) == 3 and outcome.last_kind == "unreachable"
    assert no_sleep.calls == [5, 10] and len(transport.calls) == 3


def test_fr019_parser_log_is_carried_on_success(settings, no_sleep):
    """FR-019, R-8: a fenced response is accepted and the PC-2 clean-up is logged."""
    fenced = "```json\n" + json.dumps(build_mr(), ensure_ascii=False) + "\n```"
    outcome, _ = _run(settings, no_sleep, N01_TEXT, [(200, ollama_envelope(fenced))])
    assert [entry["rule"] for entry in outcome.parser_log] == ["PC-2"]


# ------------------------------------------ triage part (T060, US2) ------------------------------

RESULTS_TEXT = (
    "Date: 12/05/2027\n"
    "Sub: Outcome of Board Meeting - Financial Results\n"
    "The Board of Directors of Lotus Fabrics Limited approved the audited financial results for "
    "the year. The order book stood at ₹310 crore and order inflow was ₹95 crore.\n"
)
NON_ORDER = {
    "is_new_order": False,
    "company": "Lotus Fabrics Limited",
    "company_quote": "Board of Directors of Lotus Fabrics Limited",
    "announcement_date": "2027-05-12",
    "announcement_date_quote": "Date: 12/05/2027",
    "order_type": None,
    "order_type_quote": None,
    "execution_period": None,
    "execution_period_quote": None,
    "orders": [],
}
NO_VALUE = {"order_value": None, "currency": None, "unit": None, "value_quote": None}
NO_CLIENT = {"client": None, "client_quote": None}


def test_ac_2_1_ac_2_2_non_order_shape(settings, no_sleep):
    """AC-2.1, AC-2.2, FR-013, FR-015, A-1: is_new_order false gives not_an_order with order
    null, no additional orders, empty missing/unstated fields, evidence only for company/date."""
    outcome, _ = _ok(settings, no_sleep, RESULTS_TEXT, dict(NON_ORDER))
    assert outcome.result == {
        "schema_version": "1.0",
        "status": "not_an_order",
        "company": "Lotus Fabrics Limited",
        "announcement_date": "2027-05-12",
        "order": None,
        "additional_orders": [],
        "evidence": {
            "company": "Board of Directors of Lotus Fabrics Limited",
            "announcement_date": "Date: 12/05/2027",
        },
        "missing_fields": [],
        "unstated_fields": [],
        "rejection_reason": None,
    }
    assert outcome.model_called is True


def test_fr015_non_order_with_null_company_and_date_confirmed_p5(settings, no_sleep):
    """FR-015, FR-012 rev 2 (CONFIRMED P-5): a not_an_order with a null company and date is
    valid and lists exactly ["company", "announcement_date"], never order_type/period."""
    mr = dict(
        NON_ORDER,
        company=None,
        company_quote=None,
        announcement_date=None,
        announcement_date_quote=None,
    )
    result = _ok(settings, no_sleep, RESULTS_TEXT, mr)[0].result
    assert result["unstated_fields"] == ["company", "announcement_date"]
    assert result["evidence"] == {}


def test_ac_2_3_value_null_needs_clarification(settings, no_sleep):
    """AC-2.3, FR-011, FR-014: value null gives needs_clarification, currency/unit null and
    missing_fields ["order_value"]."""
    result = _ok(settings, no_sleep, N01_TEXT, build_mr(order=NO_VALUE))[0].result
    assert result["status"] == "needs_clarification"
    order = result["order"]
    assert (order["order_value"], order["currency"], order["unit"]) == (None, None, None)
    assert result["missing_fields"] == ["order_value"]
    assert not {"order_value", "currency", "unit"} & set(result["evidence"])


def test_ac_2_4_unnamed_client_confirmed_p1_2(settings, no_sleep):
    """AC-2.4 (CONFIRMED P-1.2): client null gives missing_fields ["client"]."""
    result = _ok(settings, no_sleep, N01_TEXT, build_mr(order=NO_CLIENT))[0].result
    assert result["status"] == "needs_clarification" and result["missing_fields"] == ["client"]
    assert "client" not in result["evidence"]


def test_fr011_both_missing_in_fixed_order(settings, no_sleep):
    """FR-011, A-5: both null give ["order_value", "client"] in that fixed order."""
    result = _ok(settings, no_sleep, N01_TEXT, build_mr(order=dict(NO_VALUE, **NO_CLIENT)))[0]
    assert result.result["missing_fields"] == ["order_value", "client"]


def test_ac_2_5_range_value_confirmed_p1_3(settings, no_sleep):
    """AC-2.5 (CONFIRMED P-1.3): a range-value MR (value null) gives needs_clarification."""
    text = N01_TEXT.replace("₹1,250.50 crore", "in the range of ₹1,200–1,300 crore")
    result = _ok(settings, no_sleep, text, build_mr(order=NO_VALUE))[0].result
    assert result["status"] == "needs_clarification"
    assert "order_value" in result["missing_fields"]


@pytest.mark.parametrize(
    "sentence",
    [
        "Lotus Fabrics Limited has emerged as the L1 bidder for a tender of ₹40 crore.",
        "Lotus Fabrics Limited has signed an MoU with a state government.",
    ],
)
def test_ac_2_6_l1_bidder_and_mou_confirmed_p1_1(settings, no_sleep, sentence):
    """AC-2.6 (CONFIRMED P-1.1): an L1/MoU MR with is_new_order false gives not_an_order."""
    text = "Date: 12/05/2027\n" + sentence + "\nBoard of Directors of Lotus Fabrics Limited\n"
    result = _ok(settings, no_sleep, text, dict(NON_ORDER))[0].result
    assert result["status"] == "not_an_order" and result["order"] is None


def test_fr019_mc1_break_is_mr_consistency(settings, no_sleep):
    """FR-019, MC-1: is_new_order false with orders is ApplicationFailure mr_consistency."""
    from order_agent import agent

    mr = dict(NON_ORDER, orders=build_mr()["orders"])
    outcome, _ = _run(settings, no_sleep, RESULTS_TEXT, [ok_reply(mr)])
    assert isinstance(outcome, agent.ApplicationFailure)
    assert outcome.stage == "mr_consistency" and outcome.candidate is None


# ---------------------------------- guard and injection part (T068, US3) -------------------------


def _dataset_case(case_id):
    from conftest import DATASET_PATH

    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    return next(c for c in data["cases"] if c["id"] == case_id)


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"", "empty"),
        (b" \n\t \xc2\xa0", "whitespace_only"),
        (b"a" * 20001, "too_long"),
        (b"\xff\xfe\x00garbage", "garbled"),
        ("�� ╔══╗ ab ��".encode(), "garbled"),
    ],
    ids=["ac-3-1", "ac-3-2", "ac-3-3", "ac-3-4-undecodable", "ac-3-4-ratio"],
)
def test_ac_3_1_to_3_4_rejected_without_model_call(settings, no_sleep, raw, reason):
    """AC-3.1 … AC-3.4, FR-016: a rejected input gives Success with the FR-015 rejected shape
    (unstated_fields []), the right reason, model_called false, no attempts and no call."""
    from order_agent import agent, validators

    outcome, transport = _run(settings, no_sleep, raw, [])
    assert isinstance(outcome, agent.Success)
    assert outcome.result == {
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
    assert validators.check_output(outcome.result) == []
    assert outcome.model_called is False and outcome.attempts == [] and transport.calls == []
    assert outcome.assembly_trace["guard"]


def test_fr015_rejected_result_builder():
    """FR-015: agent.rejected_result builds the rejected shape in code."""
    from order_agent import agent

    assert agent.rejected_result("too_long")["rejection_reason"] == "too_long"
    assert agent.rejected_result("too_long")["unstated_fields"] == []


def test_ac_3_5_injected_order_text_gives_the_clean_result(settings, no_sleep):
    """AC-3.5, FR-018: J01 (N01 plus injected instructions) with the clean canned MR gives a
    result equal to the clean run's."""
    clean = _ok(settings, no_sleep, N01_TEXT, build_mr())[0].result
    injected_text = _dataset_case("J01")["input"]["text"]
    injected = _ok(settings, no_sleep, injected_text, build_mr())[0].result
    assert injected == clean


def test_ac_3_5_injected_values_not_in_the_source_fail_grounding(settings, no_sleep):
    """AC-3.5, FR-018, FR-019: an MR that uses the injected "Acme Shell Corp" / 99999 against
    the clean source fails G-1 (client quote) and G-2 (value digits)."""
    from order_agent import agent

    mr = build_mr(
        order={"client": "Acme Shell Corp", "client_quote": "Acme Shell Corp", "order_value": 99999}
    )
    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(mr)])
    assert isinstance(outcome, agent.ApplicationFailure)
    codes = {e.code for e in outcome.errors}
    assert {"G-1", "G-2"} <= codes


def test_ac_3_5_model_cannot_set_status_directly(settings, no_sleep):
    """AC-3.5, FR-019: an MR with an extra "status" key fails MR-SCHEMA."""
    from order_agent import agent

    outcome, _ = _run(settings, no_sleep, N01_TEXT, [ok_reply(build_mr(status="extracted"))])
    assert isinstance(outcome, agent.ApplicationFailure) and outcome.stage == "mr_schema"


def test_ac_3_6_injected_non_order_status_comes_from_is_new_order(settings, no_sleep):
    """AC-3.6, FR-018, A-1/A-6: for J02 (a board meeting with an injected order), status is
    derived only from is_new_order."""
    case = _dataset_case("J02")
    gt = case["ground_truth"]
    mr = {
        "is_new_order": False,
        "company": gt["company"],
        "company_quote": gt["evidence"]["company"],
        "announcement_date": gt["announcement_date"],
        "announcement_date_quote": gt["evidence"]["announcement_date"],
        "order_type": None,
        "order_type_quote": None,
        "execution_period": None,
        "execution_period_quote": None,
        "orders": [],
    }
    result = _ok(settings, no_sleep, case["input"]["text"], mr)[0].result
    assert result == gt


# ----------------------------------------- multi-order part (T076, US4) --------------------------

MULTI_TEXT = (
    "Date: 01.06.2027\n"
    "Sub: Receipt of orders\n"
    "Orion Infra Limited has received orders aggregating ₹1,250 crore: ₹450 crore from Yamuna "
    "Projects Limited and ₹800 crore from Xenon Power Limited, for construction works, to be "
    "completed within 30 months. It has also received ₹95 lakh from Pune Municipal Corporation "
    "and ₹1.2 crore from Thane Municipal Corporation, an order from Lagos Grid Company of EUR "
    "2.3 Mn, ₹15 crore from Indian Oil Corporation Limited, ₹40 lakh from Gujarat Industrial "
    "Development Corporation and an order of undisclosed value from Surat Municipal "
    "Corporation.\n"
    "For Orion Infra Limited\n"
)


def _o(value, currency, unit, quote, client):
    return {
        "order_value": value,
        "currency": currency,
        "unit": unit,
        "client": client,
        "value_quote": quote,
        "client_quote": client,
    }


Y450 = _o(450, "INR", "crore", "₹450 crore", "Yamuna Projects Limited")
X800 = _o(800, "INR", "crore", "₹800 crore", "Xenon Power Limited")
L95 = _o(95, "INR", "lakh", "₹95 lakh", "Pune Municipal Corporation")
C12 = _o(1.2, "INR", "crore", "₹1.2 crore", "Thane Municipal Corporation")
E23 = _o(2.3, "EUR", "million", "EUR 2.3 Mn", "Lagos Grid Company")
C15 = _o(15, "INR", "crore", "₹15 crore", "Indian Oil Corporation Limited")
L40 = _o(40, "INR", "lakh", "₹40 lakh", "Gujarat Industrial Development Corporation")
NOVAL = _o(None, None, None, None, "Surat Municipal Corporation")


def _multi(settings, no_sleep, orders, **overrides):
    mr = build_mr(
        company="Orion Infra Limited",
        company_quote="Orion Infra Limited has received orders",
        announcement_date="2027-06-01",
        announcement_date_quote="Date: 01.06.2027",
        order_type="epc_construction",
        order_type_quote="construction works",
        execution_period="within 30 months",
        execution_period_quote="to be completed within 30 months",
        orders=orders,
        **overrides,
    )
    return _ok(settings, no_sleep, MULTI_TEXT, mr)[0]


def test_ac_4_1_largest_order_is_top_level(settings, no_sleep):
    """AC-4.1, FR-009, FR-010, FR-035: ₹450 crore (Y) then ₹800 crore (X) gives a top-level
    ₹800 crore from X and one additional order (₹450 crore, Y) with its own evidence (no
    value_in_cr key); value_in_cr is 800 and 450."""
    result = _multi(settings, no_sleep, [Y450, X800]).result
    assert (
        result["order"]["order_value"] == 800 and result["order"]["client"] == "Xenon Power Limited"
    )
    assert result["order"]["value_in_cr"] == 800
    assert result["evidence"]["order_value"] == "₹800 crore"
    assert result["additional_orders"] == [
        {
            "order_value": 450,
            "currency": "INR",
            "unit": "crore",
            "value_in_cr": 450,
            "client": "Yamuna Projects Limited",
            "evidence": {
                "order_value": "₹450 crore",
                "currency": "₹450 crore",
                "unit": "₹450 crore",
                "client": "Yamuna Projects Limited",
            },
        }
    ]


def test_ac_4_2_lakh_and_crore_ranking(settings, no_sleep):
    """AC-4.2, FR-035: 95 lakh then 1.2 crore gives a top-level 1.2 crore (value_in_cr 1.2), with
    the additional order at 0.95."""
    result = _multi(settings, no_sleep, [L95, C12]).result
    assert (result["order"]["order_value"], result["order"]["value_in_cr"]) == (1.2, 1.2)
    assert [a["value_in_cr"] for a in result["additional_orders"]] == [0.95]


def test_fr035_value_in_cr_stays_with_its_order_after_ranking_confirmed_p1_5(settings, no_sleep):
    """FR-009, FR-035 (rev 3), CONFIRMED P-1.5: ₹15 crore, EUR 2.3 Mn, ₹40 lakh gives a top-level
    EUR order (value_in_cr null) and additional orders 15 and 0.4, each value with its own order."""
    result = _multi(settings, no_sleep, [C15, E23, L40]).result
    assert result["order"]["currency"] == "EUR" and result["order"]["value_in_cr"] is None
    extras = result["additional_orders"]
    assert [(a["order_value"], a["value_in_cr"]) for a in extras] == [(15, 15), (40, 0.4)]


def test_ac_4_3_single_order_has_no_additional_orders(settings, no_sleep):
    """AC-4.3: a single order gives additional_orders []."""
    assert _multi(settings, no_sleep, [X800]).result["additional_orders"] == []


def test_fr009_no_value_order_comes_last(settings, no_sleep):
    """FR-009: three orders including one with no value put the no-value order last."""
    result = _multi(settings, no_sleep, [NOVAL, L95, X800]).result
    assert result["order"]["order_value"] == 800
    assert [a["client"] for a in result["additional_orders"]] == [
        "Pune Municipal Corporation",
        "Surat Municipal Corporation",
    ]
    assert result["additional_orders"][1]["evidence"] == {"client": "Surat Municipal Corporation"}


def test_fr009_order_type_and_period_come_from_the_mr(settings, no_sleep):
    """A-3: order_type and execution_period of the top-level order come from the MR."""
    order = _multi(settings, no_sleep, [Y450, X800]).result["order"]
    assert (order["order_type"], order["execution_period"]) == (
        "epc_construction",
        "within 30 months",
    )


def test_fr010_additional_order_grounding(settings, no_sleep):
    """FR-010, INV-2/3, G-1/G-2: an additional order's ungrounded quote fails G-1 and its digit
    mismatch fails G-2."""
    from order_agent import agent

    for bad, code in [
        (dict(Y450, client="Yamuna Ltd", client_quote="Yamuna Ltd"), "G-1"),
        (dict(Y450, order_value=455), "G-2"),
    ]:
        mr = build_mr(
            company="Orion Infra Limited",
            company_quote="Orion Infra Limited has received orders",
            orders=[bad, X800],
            order_type_quote="construction works",
            execution_period_quote="to be completed within 30 months",
            announcement_date="2027-06-01",
            announcement_date_quote="Date: 01.06.2027",
        )
        outcome, _ = _run(settings, no_sleep, MULTI_TEXT, [ok_reply(mr)])
        assert isinstance(outcome, agent.ApplicationFailure)
        assert code in [e.code for e in outcome.errors]
        assert any(e.pointer.startswith("/additional_orders/0") for e in outcome.errors)


def test_fr009_assembly_trace_records_ranking(settings, no_sleep):
    """FR-009, data-model.md assembly trace: ranking keys, top index, additional indices and the
    value_in_cr of each order."""
    trace = _multi(settings, no_sleep, [NOVAL, L95, X800]).assembly_trace
    assert trace["top_index"] == 2 and trace["additional_indices"] == [1, 0]
    assert len(trace["ranking_keys"]) == 3
    assert trace["value_in_cr"] == [800, 0.95, None]
    json.dumps(trace)  # JSON-serialisable for the evidence files


def test_fr009_four_orders_accepted_without_a_count_guard_confirmed_p3(settings, no_sleep):
    """FR-009 (rev 3, CONFIRMED P-3): 4 orders are accepted; there is no count guard."""
    result = _multi(settings, no_sleep, [C15, E23, L40, L95]).result
    assert len(result["additional_orders"]) == 3
