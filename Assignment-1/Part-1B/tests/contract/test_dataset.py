"""The evaluation dataset `evals/dataset.json` (spec FR-024, FR-025, FR-026, FR-035; data-model.md
DG-1 … DG-9). Checked independently of `.harness/run_eval.py`."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal

import pytest
from conftest import DATA_MODEL_PATH, DATASET_PATH, SPEC_PATH

CATEGORIES = {
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
}
CASE_KEYS = {
    "id",
    "title",
    "categories",
    "input",
    "ground_truth",
    "expected_properties",
    "covers",
    "provenance",
}
EXPECTED_PROPERTY_KEYS = {"invariants", "rejection_reason", "injection", "checks"}
TOP_FIELDS = (
    "company",
    "announcement_date",
    "order_value",
    "currency",
    "unit",
    "client",
    "order_type",
    "execution_period",
)
ORDER_FIELDS = ("order_value", "currency", "unit", "client", "order_type", "execution_period")
ADDITIONAL_EVIDENCE_FIELDS = ("order_value", "currency", "unit", "client")

# FR-009 unit factors, for this test's own FR-035 recomputation (no import from validators).
UNIT_FACTOR = {
    "crore": 10_000_000,
    "lakh": 100_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "thousand": 1_000,
    "absolute": 1,
}


def _dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _cases():
    return {case["id"]: case for case in _dataset()["cases"]}


def _ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _expand(input_spec) -> bytes:
    kind = input_spec["kind"]
    if kind == "text":
        return input_spec["text"].encode("utf-8")
    if kind == "base64":
        return base64.b64decode(input_spec["data"], validate=True)
    text = input_spec["text"]
    while len(text) < input_spec["length"]:
        text += input_spec["filler"]
    return text[: input_spec["length"]].encode("utf-8")


def _orders(gt):
    if gt["order"] is None:
        return []
    return [gt["order"], *gt["additional_orders"]]


def _expected_value_in_cr(order):
    if order["currency"] != "INR":
        return None
    multiplier = Decimal(UNIT_FACTOR[order["unit"]]) / Decimal(UNIT_FACTOR["crore"])
    exact = Decimal(str(order["order_value"])) * multiplier
    return exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _canon_digits(value):
    return format(Decimal(str(value)).normalize(), "f").replace(".", "").lstrip("-")


def _table_rows(text, heading_start):
    """Rows of the first Markdown table after the line starting with `heading_start`."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading_start))
    rows = []
    in_table = False
    for line in lines[start + 1 :]:
        if line.startswith("|"):
            in_table = True
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not set(cells[0]) <= set("-"):
                rows.append(cells)
        elif in_table:
            break
    return rows[1:]  # drop the header row


def _expand_ids(cell):
    ids = []
    for part in cell.split(","):
        part = part.strip()
        match = re.fullmatch(r"([A-Z])(\d{2})–[A-Z](\d{2})", part)
        if match:
            ids += [f"{match[1]}{n:02d}" for n in range(int(match[2]), int(match[3]) + 1)]
        else:
            ids.append(part)
    return ids


def _planned():
    rows = _table_rows(DATA_MODEL_PATH.read_text(encoding="utf-8"), "### Planned cases")
    planned = {}
    for row in rows:
        assert len(row) == 6, row
        planned[row[0]] = {
            "categories": [c.strip() for c in row[2].split(",")],
            "covers": set(re.findall(r"FR-\d{3}|AC-\d\.\d", row[4])),
        }
    return planned


def _planned_value_in_cr():
    rows = _table_rows(
        DATA_MODEL_PATH.read_text(encoding="utf-8"), "Ground-truth `value_in_cr` per case"
    )
    table = {}
    for case_cell, top_cell, extra_cell in rows:
        if top_cell.startswith("no order object"):
            value = None
        else:
            top = re.match(r"(null|\d+(?:\.\d+)?)", top_cell)
            assert top, f"unparseable top-level cell {top_cell!r}"
            extras = []
            if extra_cell != "—":
                for part in re.split(r",\s*(?![^()]*\))", extra_cell):
                    number = re.match(r"(null|\d+(?:\.\d+)?)", part.strip())
                    assert number, f"unparseable additional cell {extra_cell!r}"
                    extras.append(number[1])
            value = [top[1], *extras]
        for case_id in _expand_ids(case_cell):
            table[case_id] = value
    return table


def _num(text):
    return None if text == "null" else Decimal(text)


# ------------------------------------------ DG-1 / DG-2 ------------------------------------------


def test_fr024_dg1_file_format():
    """FR-024, DG-1: top-level keys and every EvaluationCase field with its stated type."""
    data = _dataset()
    assert set(data) == {"dataset_version", "spec_ref", "cases"}
    assert data["dataset_version"] == "1.0"
    assert data["spec_ref"] == "specs/001-order-extraction-agent/spec.md (rev 3, 2026-11-22)"
    for case in data["cases"]:
        assert set(case) == CASE_KEYS, case["id"]
        assert re.fullmatch(r"[A-Z][0-9]{2}", case["id"])
        assert isinstance(case["title"], str) and case["title"]
        assert case["categories"] and set(case["categories"]) <= CATEGORIES, case["id"]
        spec = case["input"]
        assert spec["kind"] in {"text", "base64", "padded"}
        expected_input_keys = {
            "text": {"kind", "text"},
            "base64": {"kind", "data"},
            "padded": {"kind", "text", "filler", "length"},
        }[spec["kind"]]
        assert set(spec) == expected_input_keys, case["id"]
        assert set(case["expected_properties"]) == EXPECTED_PROPERTY_KEYS, case["id"]
        props = case["expected_properties"]
        assert isinstance(props["invariants"], list)
        assert isinstance(props["checks"], list)
        assert all(isinstance(c, str) for c in props["checks"])
        assert set(case["covers"]) == {"fr", "ac"}


def test_fr024_dg2_at_least_18_unique_ids_exactly_the_planned_28():
    """FR-024, DG-2 (rev 3): ≥ 18 cases, unique ids, exactly the 28 planned ids incl. U01."""
    ids = [case["id"] for case in _dataset()["cases"]]
    assert len(ids) >= 18
    assert len(ids) == len(set(ids))
    assert set(ids) == set(_planned())
    assert len(ids) == 28 and "U01" in ids


def test_fr024_categories_match_the_plan():
    """FR-025: each case carries the categories of the data-model.md Planned cases table."""
    planned = _planned()
    for case_id, case in _cases().items():
        assert case["categories"] == planned[case_id]["categories"], case_id


# --------------------------------------------- DG-9 ----------------------------------------------


def test_fr035_dg9a_value_in_cr_equals_table_and_own_recomputation():
    """FR-035 (rev 3), DG-9 (a): every ground-truth order has value_in_cr equal to the data-model
    table and to this test's own half-up Decimal recomputation; null for non-INR."""
    table = _planned_value_in_cr()
    for case_id, case in _cases().items():
        orders = _orders(case["ground_truth"])
        planned = table[case_id]
        if planned is None:
            assert orders == [], case_id
            continue
        if case_id == "X05":
            assert planned[0] != "null", "X05 row must be fixed by T029"
        assert len(orders) == len(planned), case_id
        for order, cell in zip(orders, planned, strict=True):
            assert "value_in_cr" in order, case_id
            actual = order["value_in_cr"]
            expected = _expected_value_in_cr(order)
            if expected is None:
                assert actual is None, case_id
            else:
                assert isinstance(actual, (int, float)) and not isinstance(actual, bool)
                assert Decimal(str(actual)) == expected, (case_id, actual, expected)
            assert _num(cell) == (None if actual is None else Decimal(str(actual))), case_id


def test_fr035_dg9b_coverage_usd_inr_lakh_inr_million():
    """FR-025 (rev 3 sentence), DG-9 (b): a USD order, an INR lakh order, an INR million order."""
    orders = [o for case in _cases().values() for o in _orders(case["ground_truth"])]
    assert any(o["currency"] == "USD" for o in orders)
    assert any(o["currency"] == "INR" and o["unit"] == "lakh" for o in orders)
    assert any(o["currency"] == "INR" and o["unit"] == "million" for o in orders)


# --------------------------------------------- DG-3 ----------------------------------------------

STATUS_BY_CATEGORY = {
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
REASON_BY_CATEGORY = {
    "malformed_empty": "empty",
    "malformed_whitespace": "whitespace_only",
    "malformed_garbled": "garbled",
    "malformed_too_long": "too_long",
}


def _in(category):
    return [c for c in _cases().values() if category in c["categories"]]


def test_fr025_dg3_minimum_counts_per_category():
    """FR-025, DG-3 (rev 2): every row of the full enumeration in data-model.md DG-3."""
    normal = _in("normal_single_order")
    assert len(normal) >= 3
    assert len({c["ground_truth"]["order"]["order_type"] for c in normal}) >= 3
    for unit in ("unit_crore", "unit_lakh", "unit_million"):
        assert len(_in(unit)) >= 1, unit
    assert any(
        c["ground_truth"]["order"]["currency"] in {"USD", "EUR"} for c in _in("unit_million")
    )
    assert len(_in("multiple_orders")) >= 2
    assert any("multiple_orders_mixed_units" in c["categories"] for c in _in("multiple_orders"))
    assert len(_in("ambiguous_value")) >= 1 and len(_in("ambiguous_non_order")) >= 1
    assert len({c["id"] for c in _in("ambiguous_value") + _in("ambiguous_non_order")}) >= 2
    assert len(_in("missing_value")) >= 1 and len(_in("missing_client")) >= 1
    assert len(_in("non_order_results")) >= 1 and len(_in("non_order_board_meeting")) >= 1
    for category in REASON_BY_CATEGORY:
        assert len(_in(category)) >= 1, category
    assert len(_in("injection_order")) >= 1 and len(_in("injection_non_order")) >= 1


def test_fr025_dg3_expected_status_per_category():
    """FR-025 "Expected status" column, DG-3: each category's cases have the stated status."""
    cases = _cases()
    for case in cases.values():
        gt = case["ground_truth"]
        for category in case["categories"]:
            if category in STATUS_BY_CATEGORY:
                assert gt["status"] == STATUS_BY_CATEGORY[category], (case["id"], category)
            if category in REASON_BY_CATEGORY:
                assert gt["rejection_reason"] == REASON_BY_CATEGORY[category], case["id"]
            if category == "injection_order":
                counterpart = cases[case["expected_properties"]["injection"]["counterpart_id"]]
                assert counterpart["ground_truth"]["status"] in {"extracted", "needs_clarification"}
                assert gt["status"] == counterpart["ground_truth"]["status"]
            if category == "injection_non_order":
                assert gt["status"] == "not_an_order"


# ---------------------------------------- DG-4 … DG-8 ---------------------------------------------


def test_fr001_dg4_every_ground_truth_validates_against_schema():
    """FR-001, DG-4: every ground truth passes the schema file via validators.check_output."""
    from order_agent import validators

    for case_id, case in _cases().items():
        assert validators.check_output(case["ground_truth"]) == [], case_id


def _applicable_invariants(case):
    gt = case["ground_truth"]
    orders = _orders(gt)
    quotes = list(gt["evidence"].values()) + [
        q for o in gt["additional_orders"] for q in o["evidence"].values()
    ]
    applicable = {"INV-1", "INV-5", "INV-6"}
    if quotes:
        applicable.add("INV-2")
    if any(o["order_value"] is not None for o in orders):
        applicable.add("INV-3")
    if any(o["client"] is not None for o in orders):
        applicable.add("INV-4")
    if case["expected_properties"]["injection"] is not None:
        applicable.add("INV-7")
    if gt["status"] != "rejected":
        applicable |= {"INV-8", "INV-10"}
    if gt["additional_orders"]:
        applicable.add("INV-9")
    if gt["order"] is not None:
        applicable.add("INV-11")
    return applicable


def test_fr028_dg8_invariants_list_equals_applicable_set():
    """FR-028, DG-8 (rev 2, L4; rev 3 INV-11): `invariants` equals the applicable set."""
    for case_id, case in _cases().items():
        listed = case["expected_properties"]["invariants"]
        assert len(listed) == len(set(listed)), case_id
        assert set(listed) == _applicable_invariants(case), case_id


def test_fr012_inv10_unstated_fields_follow_a8():
    """FR-012 rev 2, INV-10 rule, A-8 (CONFIRMED P-5): unstated_fields derived from the nulls."""
    for case_id, case in _cases().items():
        gt = case["ground_truth"]
        if gt["status"] == "rejected":
            expected = []
        else:
            expected = [f for f in ("company", "announcement_date") if gt[f] is None]
            if gt["order"] is not None:
                expected += [
                    f for f in ("order_type", "execution_period") if gt["order"][f] is None
                ]
        assert gt["unstated_fields"] == expected, case_id


def test_fr018_dg5_injection_counterparts_and_forbidden_values():
    """FR-018, INV-7, DG-5: counterparts exist with the same status; forbidden lists non-empty."""
    cases = _cases()
    injected = [c for c in cases.values() if c["expected_properties"]["injection"] is not None]
    assert {c["id"] for c in injected} == {"J01", "J02"}
    for case in injected:
        injection = case["expected_properties"]["injection"]
        assert set(injection) == {"counterpart_id", "forbidden_strings", "forbidden_numbers"}
        counterpart = cases[injection["counterpart_id"]]
        assert counterpart["ground_truth"] == case["ground_truth"], case["id"]
        assert injection["forbidden_strings"] and injection["forbidden_numbers"]
        text = _expand(case["input"]).decode("utf-8")
        clean = _expand(counterpart["input"]).decode("utf-8")
        for forbidden in injection["forbidden_strings"]:
            assert forbidden in text and forbidden not in clean, (case["id"], forbidden)
    assert cases["J01"]["expected_properties"]["injection"]["counterpart_id"] == "N01"
    assert cases["J02"]["expected_properties"]["injection"]["counterpart_id"] == "R02"


def test_fr016_dg6_rejection_reason_consistent():
    """FR-016, DG-6: expected_properties.rejection_reason equals the ground-truth reason."""
    for case_id, case in _cases().items():
        assert (
            case["expected_properties"]["rejection_reason"]
            == case["ground_truth"]["rejection_reason"]
        ), case_id


def test_fr009_dg7_no_case_has_more_than_4_orders():
    """FR-009 (rev 3), DG-7 (CONFIRMED P-3): no ground truth has more than 4 orders."""
    for case_id, case in _cases().items():
        assert len(_orders(case["ground_truth"])) <= 4, case_id


# --------------------------------------------- covers ---------------------------------------------


def _spec_ids():
    text = SPEC_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"\*\*(FR-\d{3})\*\*", text)), set(
        re.findall(r"\*\*(AC-\d\.\d)\*\*", text)
    )


def test_fr024_covers_maps_to_fr_and_ac_ids_from_the_plan():
    """FR-024 (rev 2, L2): covers holds spec FR/AC ids only, equal to the plan's Covers cell
    (plus AC-4.3 for single-order cases); every AC-1.1 … AC-4.3 is covered."""
    fr_ids, ac_ids = _spec_ids()
    planned = _planned()
    covered = set()
    for case_id, case in _cases().items():
        covers = case["covers"]
        assert covers["fr"], case_id
        for fr in covers["fr"]:
            assert re.fullmatch(r"FR-\d{3}", fr) and fr in fr_ids, (case_id, fr)
        for ac in covers["ac"]:
            assert re.fullmatch(r"AC-\d\.\d", ac) and ac in ac_ids, (case_id, ac)
        expected = set(planned[case_id]["covers"])
        gt = case["ground_truth"]
        if gt["order"] is not None and not gt["additional_orders"]:
            expected.add("AC-4.3")
        assert set(covers["fr"]) | set(covers["ac"]) == expected, case_id
        assert len(covers["fr"]) == len(set(covers["fr"]))
        assert len(covers["ac"]) == len(set(covers["ac"]))
        covered |= set(covers["ac"])
    required = {
        f"AC-{s}.{n}" for s, last in ((1, 6), (2, 6), (3, 6), (4, 3)) for n in range(1, last + 1)
    }
    assert required <= covered


def test_fr024_provenance_is_synthetic_or_public_with_note():
    """FR-024: provenance kind is synthetic or public, with a non-empty note."""
    for case_id, case in _cases().items():
        assert set(case["provenance"]) == {"kind", "note"}
        assert case["provenance"]["kind"] in {"synthetic", "public"}, case_id
        assert case["provenance"]["note"].strip(), case_id


# ---------------------------------------- self-consistency ----------------------------------------


def _non_null_top_fields(gt):
    fields = {f for f in ("company", "announcement_date") if gt[f] is not None}
    if gt["order"] is not None:
        fields |= {f for f in ORDER_FIELDS if gt["order"][f] is not None}
    return fields


def test_fr010_ground_truth_evidence_is_grounded_and_complete():
    """FR-010, INV-2/3/4/8 rules: evidence keys equal the non-null fields, quotes are substrings
    of the input after whitespace normalisation, value digits are in the value quote."""
    for case_id, case in _cases().items():
        if case["input"]["kind"] == "base64":
            continue
        source = _ws(_expand(case["input"]).decode("utf-8"))
        gt = case["ground_truth"]
        assert set(gt["evidence"]) == _non_null_top_fields(gt), case_id
        entries = [(gt["order"], gt["evidence"])] if gt["order"] else []
        for extra in gt["additional_orders"]:
            assert set(extra["evidence"]) == {
                f for f in ADDITIONAL_EVIDENCE_FIELDS if extra[f] is not None
            }, case_id
            entries.append((extra, extra["evidence"]))
        quotes = list(gt["evidence"].values()) + [
            q for extra in gt["additional_orders"] for q in extra["evidence"].values()
        ]
        for quote in quotes:
            assert _ws(quote) in source, (case_id, quote)
        for order, evidence in entries:
            if order["order_value"] is not None:
                digits = re.sub(r"[^0-9]", "", evidence["order_value"])
                assert _canon_digits(order["order_value"]) in digits, case_id
            if order["client"] is not None:
                assert _ws(order["client"]).casefold() in _ws(evidence["client"]).casefold()


def test_fr017_padded_inputs_expand_to_exact_length():
    """FR-017 (CONFIRMED P-1.4): X04 expands to 20,001 code points and X05 to 20,000."""
    cases = _cases()
    assert len(_expand(cases["X04"]["input"]).decode("utf-8")) == 20_001
    assert len(_expand(cases["X05"]["input"]).decode("utf-8")) == 20_000
    assert cases["X04"]["input"]["text"] == cases["X05"]["input"]["text"]
    assert cases["X04"]["input"]["filler"] == cases["X05"]["input"]["filler"]
    filler = cases["X05"]["input"]["filler"]
    assert not re.search(r"[0-9]", filler)


def test_owner_decision_cases_carry_confirmed_notes():
    """owner_decision cases carry a CONFIRMED P-n note; N05 is not owner_decision and carries
    CONFIRMED P-2 (rev 3); no case still carries a provisional tag."""
    cases = _cases()
    for case_id, case in cases.items():
        notes = " ".join(case["expected_properties"]["checks"])
        if "owner_decision" in case["categories"]:
            assert re.search(r"CONFIRMED P-\d", notes), case_id
        assert "PROVISIONAL" not in json.dumps(case), case_id
    assert "owner_decision" not in cases["N05"]["categories"]
    assert "CONFIRMED P-2" in " ".join(cases["N05"]["expected_properties"]["checks"])


def test_fr026_fingerprint_stable_across_reads():
    """FR-026: the SHA-256 of the raw dataset bytes is stable across two reads."""
    first = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    second = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    assert first == second and len(first) == 64


@pytest.mark.parametrize("case_id", ["N01", "J01"])
def test_ac_1_1_n01_text_is_the_quickstart_text(case_id):
    """AC-1.1: N01 (and the start of J01) is the quickstart.md §3 announcement."""
    from conftest import N01_TEXT

    assert _cases()[case_id]["input"]["text"].startswith(N01_TEXT)


BINDING = re.compile(r"^DATASET-BINDING dataset_version=(\S+) sha256=([0-9a-f]{64})$")


def test_fr026_dataset_bound_to_spec():
    """FR-026 (rev 2, C1): the last whole `DATASET-BINDING` line in spec.md names this file's
    dataset_version and the SHA-256 of its raw bytes. Any unbound edit to evals/dataset.json,
    ground truth included, fails here, so run_all.sh will not evaluate an unbound dataset."""
    matches = [BINDING.match(line) for line in SPEC_PATH.read_text(encoding="utf-8").splitlines()]
    bindings = [m for m in matches if m]
    assert bindings, "spec.md has no DATASET-BINDING line (task T093 writes it)"
    version, sha256 = bindings[-1].groups()
    assert sha256 == hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(), (
        "evals/dataset.json differs from the bound fingerprint: a dataset change needs a new "
        "dated spec revision with a new DATASET-BINDING line (FR-026)"
    )
    assert version == _dataset()["dataset_version"]
