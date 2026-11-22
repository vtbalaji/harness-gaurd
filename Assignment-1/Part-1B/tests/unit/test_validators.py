"""Validators: JSON Schema subset, output contract, MR checks, post-validation, value_in_cr,
ranking (spec FR-001 … FR-015, FR-019, FR-035, INV-2/3/4/8/9/10/11; research.md R-1, R-5 … R-7,
R-17)."""

from __future__ import annotations

import copy

import pytest
from conftest import N01_TEXT, additional, build_mr, build_result, not_an_order, rejected

# ---------------------------------------------------------------------------------------------
# Schema part (T017): the R-1 keyword subset, one conforming and one non-conforming document each
# ---------------------------------------------------------------------------------------------

KEYWORD_CASES = [
    ("type-string", {"type": "string"}, "a", 1),
    ("type-list", {"type": ["string", "null"]}, None, 1),
    ("type-number-int", {"type": "number"}, 2, "2"),
    ("type-number-float", {"type": "number"}, 1.5, None),
    ("type-number-not-bool", {"type": "number"}, 0, True),
    ("type-integer", {"type": "integer"}, 3, 3.5),
    ("type-boolean", {"type": "boolean"}, False, 0),
    ("type-object", {"type": "object"}, {}, []),
    ("type-array", {"type": "array"}, [], {}),
    ("type-null", {"type": "null"}, None, False),
    ("enum", {"enum": ["a", None]}, None, "b"),
    ("enum-bool-is-not-1", {"enum": [1]}, 1, True),
    ("const", {"const": "1.0"}, "1.0", "1"),
    ("const-null", {"const": None}, None, 0),
    ("properties", {"properties": {"a": {"type": "string"}}}, {"a": "x"}, {"a": 1}),
    ("required", {"required": ["a"]}, {"a": 1}, {}),
    (
        "additionalProperties",
        {"properties": {"a": {}}, "additionalProperties": False},
        {"a": 1},
        {"a": 1, "b": 2},
    ),
    (
        "additionalProperties-schema",
        {"properties": {"a": {}}, "additionalProperties": {"type": "string"}},
        {"a": 1, "b": "x"},
        {"a": 1, "b": 2},
    ),
    ("items", {"items": {"type": "string"}}, ["a"], ["a", 1]),
    ("minItems", {"minItems": 1}, [1], []),
    ("maxItems", {"maxItems": 0}, [], [1]),
    ("uniqueItems", {"uniqueItems": True}, [1, True, "1"], [1, 1.0]),
    ("uniqueItems-objects", {"uniqueItems": True}, [{"a": 1}, {"a": 2}], [{"a": 1}, {"a": 1}]),
    ("minLength", {"minLength": 1}, "a", ""),
    ("minLength-code-points", {"minLength": 2}, "₹1", "₹"),
    ("pattern", {"pattern": "^[0-9]{4}$"}, "2026", "x2026"),
    ("pattern-no-trailing-newline", {"pattern": "^[0-9]{4}$"}, "2026", "2026\n"),
    ("pattern-unanchored", {"pattern": "[0-9]"}, "ab1", "ab"),
    ("exclusiveMinimum", {"exclusiveMinimum": 0}, 0.1, 0),
    ("maxProperties", {"maxProperties": 0}, {}, {"a": 1}),
    ("anyOf", {"anyOf": [{"type": "null"}, {"type": "string"}]}, None, 1),
    ("allOf", {"allOf": [{"type": "string"}, {"minLength": 2}]}, "ab", "a"),
    (
        "if-then",
        {"if": {"properties": {"s": {"const": "x"}}}, "then": {"required": ["y"]}},
        {"s": "x", "y": 1},
        {"s": "x"},
    ),
    (
        "if-not-matching",
        {"if": {"properties": {"s": {"const": "x"}}}, "then": {"required": ["y"]}},
        {"s": "z"},
        {"s": "x"},
    ),
    (
        "ref",
        {"$defs": {"q": {"type": "string"}}, "properties": {"a": {"$ref": "#/$defs/q"}}},
        {"a": "x"},
        {"a": 1},
    ),
]


@pytest.mark.parametrize(
    ("schema", "good", "bad"), [c[1:] for c in KEYWORD_CASES], ids=[c[0] for c in KEYWORD_CASES]
)
def test_r1_keyword_good_and_bad_documents(schema, good, bad):
    """FR-001, R-1: every supported keyword accepts a conforming and rejects a bad document."""
    from order_agent import validators

    assert validators.validate(good, schema) == []
    errors = validators.validate(bad, schema)
    assert errors, f"{bad!r} should fail {schema!r}"


def test_r1_type_checks_only_apply_to_matching_instance_types():
    """R-1: string/array/object/number keywords ignore instances of other types."""
    from order_agent import validators

    schema = {
        "minLength": 5,
        "pattern": "^x$",
        "minItems": 3,
        "maxItems": 0,
        "uniqueItems": True,
        "items": {"type": "string"},
        "exclusiveMinimum": 10,
        "maxProperties": 0,
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": False,
    }
    for instance in (None, True, False):
        assert validators.validate(instance, schema) == []
    assert validators.validate(10.5, schema) == []


def test_r1_unsupported_keyword_raises():
    """R-1: a keyword outside the declared subset raises UnsupportedKeyword."""
    from order_agent import validators

    with pytest.raises(validators.UnsupportedKeyword, match="minimum"):
        validators.validate(1, {"minimum": 0})
    with pytest.raises(validators.UnsupportedKeyword, match="patternProperties"):
        validators.validate({}, {"properties": {"a": {"patternProperties": {}}}})


def test_r1_non_local_ref_is_unsupported():
    """R-1: only local `#/...` references are supported."""
    from order_agent import validators

    with pytest.raises(validators.UnsupportedKeyword, match=r"\$ref"):
        validators.validate(1, {"$ref": "https://example.com/s.json"})


def test_r1_errors_carry_pointer_keyword_message_and_are_all_collected():
    """R-1: errors are (pointer, keyword, message), and every error is collected."""
    from order_agent import validators

    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "array", "items": {"type": "string"}},
            "c~/d": {"type": "string"},
        },
        "required": ["z"],
    }
    errors = validators.validate({"a": 1, "b": ["x", 2], "c~/d": 3}, schema)
    found = {(e.pointer, e.keyword) for e in errors}
    assert found == {("/a", "type"), ("/b/1", "type"), ("/c~0~1d", "type"), ("", "required")}
    assert all(e.message for e in errors)


def test_r1_annotations_are_ignored():
    """R-1: $schema, $id, $defs, title, description and $comment are annotations only."""
    from order_agent import validators

    schema = {
        "$schema": "x",
        "$id": "urn:x",
        "title": "t",
        "description": "d",
        "$comment": "c",
        "$defs": {"unused": {"type": "string"}},
    }
    assert validators.validate(5, schema) == []


# ----------------------------------- output.schema.json ------------------------------------


def _codes(errors):
    return [e.code for e in errors]


def test_fr001_ac_1_1_result_validates():
    """FR-001, AC-1.1: the AC-1.1 result (value_in_cr 1250.5) conforms to schema 1.0."""
    from order_agent import validators

    assert validators.check_output(build_result()) == []


@pytest.mark.parametrize(
    "result",
    [
        build_result(missing_fields=["client"]),
        build_result(status="needs_clarification"),
        not_an_order(order=build_result()["order"]),
        not_an_order(additional_orders=[additional()]),
        not_an_order(missing_fields=["client"]),
        dict(rejected("empty"), evidence={"company": "x"}),
        rejected(None),
        dict(rejected("empty"), company="X Limited"),
        dict(build_result(), rejection_reason="empty"),
    ],
    ids=[
        "extracted-with-missing",
        "needs-clarification-without-missing",
        "not-an-order-with-order",
        "not-an-order-with-additional",
        "not-an-order-with-missing",
        "rejected-with-evidence",
        "rejected-without-reason",
        "rejected-with-company",
        "extracted-with-rejection-reason",
    ],
)
def test_fr015_status_shapes_are_enforced(result):
    """FR-015: each status-dependent shape is enforced by the schema file."""
    from order_agent import validators

    assert "OUT-SCHEMA" in _codes(validators.check_output(result))


def test_fr006_value_triplet_enforced():
    """FR-006: order_value null with currency set fails (null iff)."""
    from order_agent import validators

    result = build_result(
        order={"order_value": None, "value_in_cr": None},
        status="needs_clarification",
        missing_fields=["order_value"],
    )
    assert "OUT-SCHEMA" in _codes(validators.check_output(result))
    ok = build_result(
        order={"order_value": None, "currency": None, "unit": None, "value_in_cr": None},
        status="needs_clarification",
        missing_fields=["order_value"],
    )
    assert validators.check_output(ok) == []


def test_fr001_unknown_top_level_key_and_missing_unstated_fields_fail():
    """FR-001: no other top-level fields; unstated_fields is required (rev 2)."""
    from order_agent import validators

    assert "OUT-SCHEMA" in _codes(validators.check_output(dict(build_result(), extra=1)))
    missing = build_result()
    del missing["unstated_fields"]
    assert "OUT-SCHEMA" in _codes(validators.check_output(missing))


def test_fr002_status_outside_enum_fails():
    """FR-002: status must be one of the four values."""
    from order_agent import validators

    assert "OUT-SCHEMA" in _codes(validators.check_output(build_result(status="order")))


@pytest.mark.parametrize(
    ("result", "ok"),
    [
        (build_result(unstated_fields=["client"]), False),
        (build_result(unstated_fields=["company", "company"]), False),
        (dict(rejected("empty"), unstated_fields=["company"]), False),
        (not_an_order(unstated_fields=["execution_period"]), False),
        (
            not_an_order(
                company=None,
                announcement_date=None,
                evidence={},
                unstated_fields=["company", "announcement_date"],
            ),
            True,
        ),
    ],
    ids=["unknown-item", "duplicate", "rejected-non-empty", "not-an-order-order-field", "ok"],
)
def test_fr012_fr015_unstated_fields_schema_rules(result, ok):
    """FR-012, FR-015 (rev 2, CONFIRMED P-5): unstated_fields items, uniqueness and shapes."""
    from order_agent import validators

    errors = validators.check_output(result)
    assert (errors == []) is ok, errors


def _with_order(order_overrides, where):
    """A result whose top-level order (where='order') or one additional order is changed."""
    result = build_result()
    if where == "order":
        result["order"].update(order_overrides)
        for key, value in order_overrides.items():
            if value is _DELETE:
                del result["order"][key]
    else:
        entry = additional(**order_overrides)
        for key, value in order_overrides.items():
            if value is _DELETE:
                del entry[key]
        result["additional_orders"] = [entry]
    return result


_DELETE = object()


@pytest.mark.parametrize("where", ["order", "additional"])
@pytest.mark.parametrize(
    "overrides",
    [
        {"value_in_cr": _DELETE},
        {"value_in_cr": None},
        {"currency": "USD", "value_in_cr": 10.0},
        {"currency": "EUR", "value_in_cr": 10.0},
        {"currency": "other", "value_in_cr": 10.0},
        {"order_value": None, "currency": None, "unit": None, "value_in_cr": 3.0},
        {"value_in_cr": "1250.5"},
        {"value_in_cr": True},
    ],
    ids=[
        "missing",
        "inr-null",
        "usd-number",
        "eur-number",
        "other-number",
        "null-value-number",
        "string",
        "bool",
    ],
)
def test_fr035_value_in_cr_schema_shape_failures(overrides, where):
    """FR-005, FR-009, FR-035 (rev 3): value_in_cr is required and a number iff currency is INR."""
    from order_agent import validators

    result = _with_order(overrides, where)
    if where == "order" and overrides.get("order_value", 1) is None:
        result.update(status="needs_clarification", missing_fields=["order_value"])
    if where == "additional" and overrides.get("order_value", 1) is None:
        result["additional_orders"][0]["evidence"] = {"client": "Y Limited"}
    assert "OUT-SCHEMA" in _codes(validators.check_output(result))


@pytest.mark.parametrize("where", ["order", "additional"])
def test_fr035_value_in_cr_zero_and_number_pass_schema(where):
    """FR-035 (rev 3): 0 for INR passes the schema; the exact value is INV-11, not the schema."""
    from order_agent import validators

    assert validators.check_output(_with_order({"value_in_cr": 0}, where)) == []
    assert validators.check_output(_with_order({"value_in_cr": 1250.5}, where)) == []


def test_fr035_value_in_cr_has_no_evidence_key():
    """FR-010, FR-035 (rev 3): an evidence key value_in_cr fails, top-level and additional."""
    from order_agent import validators

    top = build_result()
    top["evidence"]["value_in_cr"] = "₹1,250.50 crore"
    assert "OUT-SCHEMA" in _codes(validators.check_output(top))
    extra = build_result(additional_orders=[additional()])
    extra["additional_orders"][0]["evidence"]["value_in_cr"] = "₹450 crore"
    assert "OUT-SCHEMA" in _codes(validators.check_output(extra))


def test_fr004_check_output_out_date_layer_1():
    """FR-004: a calendar-invalid date is OUT-DATE (layer 1); a real date passes."""
    from order_agent import validators

    bad = validators.check_output(build_result(announcement_date="2026-02-30"))
    assert [(e.code, e.layer) for e in bad] == [("OUT-DATE", 1)]
    assert validators.check_output(build_result(announcement_date="2026-11-20")) == []


def test_fr004_compact_date_is_schema_error_not_out_date():
    """FR-004: "20261120" breaks the pattern (OUT-SCHEMA); OUT-DATE needs the pattern first."""
    from order_agent import validators

    errors = validators.check_output(build_result(announcement_date="20261120"))
    assert _codes(errors) == ["OUT-SCHEMA"]


def test_fr001_check_output_returns_validation_errors_with_layer():
    """FR-001, FR-028 code table: every item is a ValidationError(code, pointer, message, layer)."""
    from order_agent import validators

    errors = validators.check_output(dict(build_result(), extra=1, status="x"))
    assert len(errors) >= 2
    for error in errors:
        assert isinstance(error, validators.ValidationError)
        assert error.code == "OUT-SCHEMA" and error.layer == 1
        assert isinstance(error.pointer, str) and error.message


def test_fr001_check_output_non_object_is_schema_error():
    """FR-001: a non-object document fails OUT-SCHEMA and does not crash."""
    from order_agent import validators

    assert _codes(validators.check_output([])) == ["OUT-SCHEMA"]


def test_r1_load_schema_returns_independent_copies():
    """R-2: callers cannot corrupt the cached schema."""
    from order_agent import validators

    first = validators.load_schema("output")
    first["properties"] = {}
    assert validators.load_schema("output")["properties"] != {}
    assert copy.deepcopy(validators.load_schema("model-response"))["$id"].endswith("mr-1")
    assert validators.MR_VERSION == "mr-1"


# ---------------------------------------------------------------------------------------------
# MR and post-validation part (T032): check_mr, G-1 … G-5, C-1, C-3, C-4, helpers
# ---------------------------------------------------------------------------------------------

NBSP = " "


def _post(result, source=N01_TEXT):
    from order_agent import validators

    return validators.post_validate(source, result)


def test_fr019_check_mr_accepts_a_valid_model_response():
    """FR-019, R-5: a valid mr-1 response has no MR-SCHEMA or MR-CONSIST error."""
    from order_agent import validators

    assert validators.check_mr(build_mr()) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(extra=1),
        lambda m: m["orders"][0].update(currency="inr"),
        lambda m: m["orders"][0].update(order_value="1250.5"),
        lambda m: m["orders"][0].update(order_value=0),
        lambda m: m["orders"][0].update(order_value=-5),
        lambda m: m.pop("execution_period_quote"),
        lambda m: m["orders"][0].update(value_in_cr=1250.5),
        lambda m: m.update(is_new_order="yes"),
        lambda m: m.update(company=""),
    ],
    ids=[
        "extra-key",
        "lowercase-inr",
        "value-as-string",
        "value-zero",
        "value-negative",
        "missing-key",
        "mr-order-with-value_in_cr",
        "bool-as-string",
        "empty-string",
    ],
)
def test_fr019_check_mr_schema_strictness(mutate):
    """FR-019, R-5: MR-SCHEMA (layer 1) for every strictness break, never coerced. An MR order
    carrying value_in_cr fails too: the model cannot supply it (FR-035 rev 3)."""
    from order_agent import validators

    mr = build_mr()
    mutate(mr)
    errors = validators.check_mr(mr)
    assert errors and {e.code for e in errors} == {"MR-SCHEMA"}
    assert all(e.layer == 1 for e in errors)


@pytest.mark.parametrize(
    ("field", "quote"),
    [
        ("company", "company_quote"),
        ("announcement_date", "announcement_date_quote"),
        ("order_type", "order_type_quote"),
        ("execution_period", "execution_period_quote"),
    ],
)
def test_fr006_mc2_value_and_quote_pairs(field, quote):
    """FR-006, FR-010, MC-2: a value and its quote are both null or both non-null."""
    from order_agent import validators

    without_quote = build_mr(**{quote: None})
    without_value = build_mr(**{field: None})
    for mr in (without_quote, without_value):
        errors = validators.check_mr(mr)
        codes = {e.code for e in errors}
        assert codes == {"MR-CONSIST"}, (field, errors)
        assert any(e.pointer in (f"/{field}", f"/{quote}") for e in errors)


def test_fr006_mc2_client_and_client_quote_pair():
    """FR-006, MC-2: client and client_quote pair, per order."""
    from order_agent import validators

    for order in ({"client_quote": None}, {"client": None}):
        errors = validators.check_mr(build_mr(order=order))
        assert [e.code for e in errors] == ["MR-CONSIST"]
        assert errors[0].pointer.startswith("/orders/0/")


@pytest.mark.parametrize(
    "order",
    [
        {"currency": None},
        {"unit": None},
        {"value_quote": None},
        {"order_value": None},
        {"order_value": None, "currency": None, "unit": None},
    ],
    ids=["currency-null", "unit-null", "quote-null", "value-null", "only-quote-left"],
)
def test_fr006_mc3_value_triplet(order):
    """FR-006, MC-3: currency, unit and value_quote are null iff order_value is null."""
    from order_agent import validators

    errors = validators.check_mr(build_mr(order=order))
    assert errors and {e.code for e in errors} == {"MR-CONSIST"}


def test_fr006_mc3_all_value_fields_null_is_consistent():
    """FR-006, FR-012, MC-3: an order with no value (all four null) is consistent."""
    from order_agent import validators

    order = {"order_value": None, "currency": None, "unit": None, "value_quote": None}
    assert validators.check_mr(build_mr(order=order)) == []


def test_fr019_check_mr_reports_schema_before_consistency():
    """FR-019: MR-SCHEMA errors are reported alone; consistency is checked on a valid shape."""
    from order_agent import validators

    mr = build_mr(company=None, extra=1)
    assert {e.code for e in validators.check_mr(mr)} == {"MR-SCHEMA"}
    assert {e.code for e in validators.check_mr([])} == {"MR-SCHEMA"}


def test_fr001_post_validate_accepts_the_ac_1_1_result():
    """FR-001, FR-010, INV-2/3/4/8: the AC-1.1 result for N01 passes every check."""
    assert _post(build_result()) == []


def test_fr010_inv_2_g1_quote_not_in_source_fails():
    """FR-010, INV-2, G-1: a quote that is not a substring of the source fails (layer 2)."""
    result = build_result()
    result["evidence"]["company"] = "Example Transformers Ltd has received"
    errors = _post(result)
    assert [(e.code, e.layer, e.pointer) for e in errors] == [("G-1", 2, "/evidence/company")]


def test_fr010_inv_2_g1_whitespace_normalisation_nbsp_and_newline():
    """FR-010, INV-2, G-1: NBSP and newline differences pass after ws_norm."""
    source = N01_TEXT.replace("₹1,250.50 crore", "₹1,250.50" + NBSP + "crore")
    result = build_result()
    result["evidence"]["order_type"] = "NTPC Limited for supply of transformers"
    assert "for\nsupply" in source
    assert _post(result, source) == []


def test_inv_3_g2_value_digits_in_value_quote():
    """INV-3, G-2: 1250.5 vs "₹1,250.50 crore" passes; 1255 fails."""
    assert _post(build_result()) == []
    result = build_result(order={"order_value": 1255, "value_in_cr": 1255.0})
    assert [e.code for e in _post(result)] == ["G-2"]


def test_inv_4_g3_client_contained_case_insensitively_in_quote():
    """INV-4 (second clause), G-3: the client must be contained in its client quote."""
    assert _post(build_result(order={"client": "ntpc limited"})) == []
    assert _post(build_result(order={"client": "NTPC"})) == []
    result = build_result(order={"client": "NTPC Limited Corp"})
    assert [e.code for e in _post(result)] == ["G-3"]


def test_fr010_inv_8_g4_evidence_keys_exactly_the_non_null_fields():
    """FR-010, INV-8, G-4: a missing or an extra evidence key fails."""
    missing = build_result()
    del missing["evidence"]["execution_period"]
    assert "G-4" in [e.code for e in _post(missing)]
    extra = build_result(order={"execution_period": None}, unstated_fields=["execution_period"])
    assert [e.code for e in _post(extra)] == ["G-4"]


@pytest.mark.parametrize(
    "name",
    [
        "BSE Limited",
        "B.S.E. Ltd",
        "BSE Ltd",
        "National Stock Exchange of India Limited",
        "NSE",
        "SEBI",
        "Securities and Exchange Board of India",
    ],
)
def test_fr003_ac_1_5_g5_exchange_or_regulator_is_never_a_party(name):
    """FR-003, AC-1.5, G-5: company or client equal to an exchange/regulator fails (layer 2)."""
    as_company = _post(build_result(company=name))
    assert [(e.code, e.layer) for e in as_company if e.code == "G-5"] == [("G-5", 2)]
    as_client = _post(build_result(order={"client": name}))
    assert "G-5" in [e.code for e in as_client]
    extra = build_result(additional_orders=[additional(client=name)])
    assert "G-5" in [e.code for e in _post(extra)]


def test_fr003_g5_names_that_merely_contain_an_exchange_pass():
    """FR-003, G-5: the match is on the whole normalised name, not a substring."""
    from order_agent import validators

    assert validators.name_norm("NSE Infra Projects Limited") not in validators.EXCHANGE_DENYLIST
    assert validators.name_norm("BSE Limited") in validators.EXCHANGE_DENYLIST


def test_fr011_c1_missing_fields_must_match_the_order():
    """FR-011, C-1: missing_fields inconsistent with the top-level order fails."""
    codes = [e.code for e in _post(build_result(missing_fields=["client"]))]
    assert "C-1" in codes
    no_order = dict(not_an_order(), missing_fields=["client"])
    assert "C-1" in [e.code for e in _post(no_order)]


def test_fr014_c3_status_must_follow_the_order():
    """FR-014, C-3: a status inconsistent with the order's required fields fails."""
    codes = [e.code for e in _post(build_result(status="needs_clarification"))]
    assert "C-3" in codes
    order_null = build_result(order=None, status="extracted", unstated_fields=[])
    order_null["evidence"] = {
        k: v for k, v in order_null["evidence"].items() if k in ("company", "announcement_date")
    }
    assert "C-3" in [e.code for e in _post(order_null)]
    assert _post(not_an_order()) == []
    assert _post(rejected("empty")) == []


def test_fr012_inv_10_c4_unstated_fields_confirmed_p5():
    """FR-012 rev 2, INV-10, C-4 (CONFIRMED P-5): unstated_fields equals the A-8 derivation."""
    no_company = build_result(company=None)
    del no_company["evidence"]["company"]
    assert [e.code for e in _post(no_company)] == ["C-4"]
    no_company["unstated_fields"] = ["company"]
    assert _post(no_company) == []
    listed = build_result(unstated_fields=["execution_period"])
    assert [e.code for e in _post(listed)] == ["C-4"]
    assert _post(rejected("empty")) == []


def test_fr019_post_validate_collects_every_error_with_its_layer():
    """FR-019, FR-028 code table: every error is collected, each with its spec layer."""
    result = build_result(
        company="SEBI", announcement_date="2026-02-30", unstated_fields=["execution_period"]
    )
    result["evidence"]["client"] = "not in the source"
    by_code = {e.code: e.layer for e in _post(result)}
    assert by_code == {"OUT-DATE": 1, "G-1": 2, "G-3": 2, "G-5": 2, "C-4": 2}


def test_fr019_post_validate_survives_a_malformed_result():
    """FR-019: a schema-broken result yields errors, never an exception."""
    broken = build_result(order={"order_value": "x", "client": 5}, evidence=[])
    assert "OUT-SCHEMA" in [e.code for e in _post(broken)]
    assert _post("not a dict")
    assert _post({})


def test_inv_3_helpers_canon_digits_digits_only_ws_norm_name_norm():
    """INV-2, INV-3, FR-029 helpers: canon_digits, digits_only, ws_norm, name_norm."""
    from order_agent import validators

    assert validators.canon_digits(1250.5) == "12505"
    assert validators.canon_digits(4500000) == "4500000"
    assert validators.canon_digits(12.50) == "125"
    assert validators.canon_digits(1e7) == "10000000"
    assert validators.digits_only("₹1,250.50 crore") == "125050"
    assert validators.ws_norm(" a" + NBSP + NBSP + "b\n\tc ") == "a b c"
    assert validators.name_norm("Larsen & Toubro Ltd.") == "larsen and toubro"
    assert validators.name_norm("XYZ Pvt. Ltd") == "xyz"
    assert validators.name_norm("B.S.E. Ltd") == "bse"


# ---------------------------------------------------------------------------------------------
# value_in_cr part (T099, rev 3): FR-035 conversion and C-5 (research.md R-17)
# ---------------------------------------------------------------------------------------------


def test_fr035_crore_multiplier_is_exactly_the_owner_list():
    """FR-035: the crore multipliers are exactly the owner's decimal strings."""
    from order_agent import validators

    assert validators.CRORE_MULTIPLIER == {
        "crore": "1",
        "lakh": "0.01",
        "million": "0.1",
        "billion": "100",
        "thousand": "0.0001",
        "absolute": "0.0000001",
    }


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1250.5, "crore", 1250.5),
        (85.4, "lakh", 0.854),
        (48.5, "million", 4.85),
        (2.5, "billion", 250.0),
        (15, "thousand", 0.0015),
        (4500000, "absolute", 0.45),
        (340, "crore", 340.0),
    ],
)
def test_fr035_value_in_cr_inr_conversion_per_unit(value, unit, expected):
    """FR-035, AC-1.1, AC-1.2, AC-1.6: INR amounts in crore; 340 crore with no currency
    marker is INR (CONFIRMED P-2)."""
    from order_agent import validators

    actual = validators.value_in_cr(value, "INR", unit)
    assert actual == expected
    assert type(actual) is float


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (12.345, "lakh", 0.1235),
        (0.12345, "crore", 0.1235),
        (4500500, "absolute", 0.4501),
        (1.23456, "crore", 1.2346),
        (1.23454, "crore", 1.2345),
        (500, "absolute", 0.0001),
        (499, "absolute", 0.0),
    ],
)
def test_fr035_value_in_cr_rounds_half_up_to_4_places(value, unit, expected):
    """FR-035: exact decimal arithmetic, rounded half up to 4 places (these ties differ under
    half-even); an INR amount below ₹500 gives 0 (spec Edge Cases)."""
    from order_agent import validators

    assert validators.value_in_cr(value, "INR", unit) == expected


def test_fr035_value_in_cr_uses_decimal_half_up_and_no_builtin_round():
    """FR-035: no binary floating-point rounding: no `round`, and Decimal + ROUND_HALF_UP."""
    import ast
    import inspect

    from order_agent import validators

    tree = ast.parse(inspect.getsource(validators.value_in_cr))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    calls = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "round" not in calls
    assert {"Decimal", "ROUND_HALF_UP"} <= names


@pytest.mark.parametrize("currency", ["USD", "EUR", "other"])
@pytest.mark.parametrize("unit", ["crore", "lakh", "million", "billion", "thousand", "absolute"])
def test_fr035_ac_1_3_non_inr_is_never_converted(currency, unit):
    """FR-035, AC-1.3: USD, EUR and other give None for every unit (no FX conversion)."""
    from order_agent import validators

    assert validators.value_in_cr(15, currency, unit) is None


def test_fr035_null_value_gives_null():
    """FR-035: a null value with a null currency gives None."""
    from order_agent import validators

    assert validators.value_in_cr(None, None, None) is None
    assert validators.value_in_cr(None, "INR", None) is None


SOURCE_WITH_Y = N01_TEXT + "Also ₹450 crore from Y Limited.\n"


def test_fr035_c5_a9_derivation_passes_on_order_and_additional():
    """FR-035, C-5: the A-9 derivation passes, and C-5 adds no evidence requirement (G-4)."""
    result = build_result(additional_orders=[additional()])
    assert _post(result, SOURCE_WITH_Y) == []


@pytest.mark.parametrize("where", ["order", "additional"])
@pytest.mark.parametrize(
    "overrides",
    [{"value_in_cr": "off"}, {"currency": "USD", "value_in_cr": "keep"}, {"value_in_cr": None}],
    ids=["off-by-0.0001", "usd-with-number", "inr-null"],
)
def test_fr035_c5_wrong_value_in_cr_fails_layer_2(where, overrides):
    """FR-035, C-5 (layer 2): an INR value off by 0.0001, a USD order with a number, or an INR
    order with null fails C-5, on the top-level order and on an additional order."""
    base = 1250.5 if where == "order" else 450.0
    changes = dict(overrides)
    if changes["value_in_cr"] == "off":
        changes["value_in_cr"] = base + 0.0001
    elif changes["value_in_cr"] == "keep":
        changes["value_in_cr"] = base
    if where == "order":
        result = build_result(order=changes)
    else:
        result = build_result(additional_orders=[additional(**changes)])
    c5 = [e for e in _post(result, SOURCE_WITH_Y) if e.code == "C-5"]
    assert len(c5) == 1 and c5[0].layer == 2
    assert c5[0].pointer.startswith("/order/" if where == "order" else "/additional_orders/0/")


def test_fr035_c5_missing_key_is_left_to_out_schema():
    """FR-035, C-5: a missing value_in_cr key is reported by OUT-SCHEMA, not C-5."""
    result = build_result()
    del result["order"]["value_in_cr"]
    codes = [e.code for e in _post(result)]
    assert "OUT-SCHEMA" in codes and "C-5" not in codes


# ---------------------------------------------------------------------------------------------
# MC-1 part (T059, US2): the is_new_order rules (FR-005, FR-015; R-5)
# ---------------------------------------------------------------------------------------------

NOT_ORDER = {
    "is_new_order": False,
    "orders": [],
    "order_type": None,
    "order_type_quote": None,
    "execution_period": None,
    "execution_period_quote": None,
}


def test_fr015_mc1_valid_non_order_response():
    """FR-005, FR-015, MC-1: is_new_order false with company/date only is consistent."""
    from order_agent import validators

    assert validators.check_mr(build_mr(**NOT_ORDER)) == []


@pytest.mark.parametrize(
    "overrides",
    [
        dict(NOT_ORDER, orders=build_mr()["orders"]),
        dict(NOT_ORDER, order_type="supply", order_type_quote="supply of transformers"),
        dict(
            NOT_ORDER,
            execution_period="within 18 months",
            execution_period_quote="to be executed within 18 months",
        ),
        {"orders": []},
        {"order_type": None, "order_type_quote": None},
    ],
    ids=[
        "false-with-orders",
        "false-with-order-type",
        "false-with-period",
        "true-without-orders",
        "true-without-order-type",
    ],
)
def test_fr005_fr015_mc1_breaks_are_mr_consist(overrides):
    """FR-005, FR-015, MC-1: each break of the is_new_order rules is MR-CONSIST (never
    repaired)."""
    from order_agent import validators

    errors = validators.check_mr(build_mr(**overrides))
    assert errors and {e.code for e in errors} == {"MR-CONSIST"}
    assert any("MC-1" in e.message for e in errors)


def test_fr012_mc1_order_with_neither_value_nor_client_is_valid():
    """FR-012, MC-1: an order entry with neither a value nor a client is one entry with nulls."""
    from order_agent import validators

    empty = {
        "order_value": None,
        "currency": None,
        "unit": None,
        "client": None,
        "value_quote": None,
        "client_quote": None,
    }
    assert validators.check_mr(build_mr(orders=[empty])) == []


def test_fr011_fr014_c1_c3_hold_for_needs_clarification():
    """FR-011, FR-014: C-1 and C-3 hold for a needs_clarification result."""
    result = build_result(
        order={"client": None},
        status="needs_clarification",
        missing_fields=["client"],
    )
    del result["evidence"]["client"]
    assert _post(result) == []
    wrong = dict(result, missing_fields=["order_value"])
    assert "C-1" in [e.code for e in _post(wrong)]


# ---------------------------------------------------------------------------------------------
# ranking part (T075, US4): FR-009, INV-9, C-2 (research.md R-6, CONFIRMED P-1.5)
# ---------------------------------------------------------------------------------------------


def _ord(value, currency, unit, **extra):
    return {"order_value": value, "currency": currency, "unit": unit, **extra}


NONE = _ord(None, None, None)


@pytest.mark.parametrize(
    ("unit", "factor"),
    [
        ("crore", 10**7),
        ("lakh", 10**5),
        ("million", 10**6),
        ("billion", 10**9),
        ("thousand", 10**3),
        ("absolute", 1),
    ],
)
@pytest.mark.parametrize(("currency", "fx"), [("INR", 1), ("USD", 84), ("EUR", 90)])
def test_fr009_base_value_unit_factors_and_fx_confirmed_p1_5(unit, factor, currency, fx):
    """FR-009, R-6 (CONFIRMED P-1.5): base value = value × unit factor × FX (INR 1, USD 84,
    EUR 90)."""
    from decimal import Decimal

    from order_agent import validators

    assert validators.base_value(_ord(2, currency, unit)) == Decimal(2 * factor * fx)
    assert validators.base_value(_ord(2, "other", unit)) is None
    assert validators.base_value(NONE) is None


def test_ac_4_2_ranking_across_units_and_currencies():
    """AC-4.2, FR-009: ₹1.2 crore ranks above ₹95 lakh; EUR 2.3 Mn (2.07e8) above ₹15 crore."""
    from order_agent import validators

    key = validators.ranking_key
    assert key(_ord(1.2, "INR", "crore")) < key(_ord(95, "INR", "lakh"))
    assert key(_ord(2.3, "EUR", "million")) < key(_ord(15, "INR", "crore"))
    assert validators.rank([_ord(95, "INR", "lakh"), _ord(1.2, "INR", "crore")]) == (1, [0])


def test_fr009_ties_go_to_the_first_stated_order():
    """FR-009: ties go to the first-stated order."""
    from order_agent import validators

    assert validators.rank([_ord(1, "INR", "crore"), _ord(100, "INR", "lakh")]) == (0, [1])
    assert validators.rank([_ord(100, "INR", "lakh"), _ord(1, "INR", "crore")]) == (0, [1])


def test_fr009_other_currency_and_no_value_ordering():
    """FR-009, R-6: an `other` order ranks after every valued INR/USD/EUR order and before the
    no-value orders, which come last; additional orders are valued ones in appearance order,
    then no-value ones in appearance order."""
    from order_agent import validators

    orders = [NONE, _ord(5, "other", "million"), _ord(1, "INR", "crore"), _ord(3, "USD", "million")]
    assert validators.rank(orders) == (3, [1, 2, 0])
    key = validators.ranking_key
    assert key(orders[2]) < key(orders[1]) < key(orders[0])
    assert validators.rank([NONE, _ord(9, "INR", "lakh"), NONE, _ord(1, "INR", "crore")]) == (
        3,
        [1, 0, 2],
    )


def test_fr009_two_valued_other_orders_keep_appearance_order():
    """FR-009, spec Edge Cases: with two valued `other` orders, rank still returns appearance
    order (out of scope for v1; C-2 reports it, see below)."""
    from order_agent import validators

    assert validators.rank([_ord(5, "other", "million"), _ord(9, "other", "million")]) == (0, [1])


def _ranked(top, *extras):
    result = build_result(order=dict(top, value_in_cr=None))
    result["additional_orders"] = [dict(additional(), **dict(e, value_in_cr=None)) for e in extras]
    return result


def _c2(result):
    from order_agent import validators

    return [e for e in validators.post_validate(N01_TEXT, result) if e.code == "C-2"]


def test_inv_9_c2_top_level_must_rank_first():
    """INV-9 (i), C-2 (layer 2): the top-level order ranking below an additional order fails."""
    assert _c2(_ranked(_ord(15, "EUR", "million"), _ord(2.3, "USD", "million"))) == []
    errors = _c2(_ranked(_ord(15, "INR", "crore"), _ord(2.3, "EUR", "million")))
    assert len(errors) == 1 and errors[0].layer == 2


def test_inv_9_c2_other_currency_clauses():
    """INV-9 (rev 2) via C-2: (i) a top-level `other` order with a valued INR/USD/EUR additional
    order fails; (iii) a top-level `other` order with a no-value additional order passes, and
    with a second valued `other` order fails."""
    assert _c2(_ranked(_ord(5, "other", "million"), _ord(1, "INR", "crore")))
    assert _c2(_ranked(_ord(5, "other", "million"), NONE)) == []
    assert _c2(_ranked(_ord(5, "other", "million"), _ord(9, "other", "million")))
    assert _c2(_ranked(_ord(1, "INR", "crore"), _ord(999, "other", "billion"))) == []


def test_fr035_ranking_never_reads_value_in_cr():
    """FR-009, FR-035 (rev 3): ranking_key ignores value_in_cr, so FX ranking stays separate
    from the crore conversion."""
    from order_agent import validators

    plain = [_ord(95, "INR", "lakh"), _ord(1.2, "INR", "crore")]
    wrong = [dict(plain[0], value_in_cr=999.0), dict(plain[1], value_in_cr=0.0)]
    assert validators.rank(plain) == validators.rank(wrong) == (1, [0])
    assert [validators.ranking_key(o) for o in plain] == [validators.ranking_key(o) for o in wrong]
