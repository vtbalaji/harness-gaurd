"""FR-070, FR-071: the result model, its key order and its JSON form."""

import dataclasses
import json
from pathlib import Path

import pytest

from gis_scorer.result import (
    LABELS,
    STATUSES,
    Dimension,
    LabelDecision,
    ScoreItem,
    ScoreResult,
    Valuation,
    ValuationPart,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "specs" / "001-gis-scorer" / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "result.schema.json"


def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _sample_result():
    item_plain = ScoreItem(
        name="Piotroski F-Score",
        requirement="FR-010",
        value=9,
        earned=10,
        available=10,
        status="scored",
        reason=">= 8",
    )
    item_object = ScoreItem(
        name="Loss to Profit",
        requirement="FR-022",
        value=(("net_profit_margin", 16), ("previous_net_profit_margin", -2)),
        earned=5,
        available=5,
        status="scored",
        reason="current > 0 and previous <= 0",
    )
    item_none = ScoreItem(
        name="Altman Z-Score",
        requirement="FR-011",
        value=None,
        earned=0,
        available=0,
        status="no_data",
        reason="No data",
    )
    dims = (
        Dimension(name="Forensic Quality", earned=10, available=10, items=(item_plain, item_none)),
        Dimension(name="Turnaround", earned=5, available=5, items=(item_object,)),
    )
    label = LabelDecision(
        pre_gate="STRONG BUY", final="HOLD", reasons=("Total 100 >= 70: STRONG BUY", "ROE missing")
    )
    parts = (
        ValuationPart(
            name="P/E", requirement="FR-060", value=11, points=5, available=5, reason="< 12"
        ),
        ValuationPart(
            name="P/B", requirement="FR-060", value=1.4, points=3, available=3, reason="< 1.5"
        ),
        ValuationPart(
            name="PEG", requirement="FR-060", value=None, points=0, available=2, reason="No data"
        ),
    )
    valuation = Valuation(score=8, max=10, parts=parts)
    return ScoreResult(
        total=100,
        max=100,
        raw_earned=15,
        raw_available=15,
        dimensions=dims,
        label=label,
        valuation=valuation,
    )


def _walk_types(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            assert type(key) is str
            yield from _walk_types(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk_types(inner)
    else:
        yield type(value)


def test_fr070_result_entities_are_frozen():
    """FR-070: every result entity is an immutable (frozen) dataclass."""
    result = _sample_result()
    targets = [
        result,
        result.dimensions[0],
        result.dimensions[0].items[0],
        result.label,
        result.valuation,
        result.valuation.parts[0],
    ]
    for target in targets:
        assert dataclasses.is_dataclass(target)
        field_name = dataclasses.fields(target)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(target, field_name, None)


def test_fr070_status_and_label_value_sets():
    """FR-070: the status and label enums match contracts/result.schema.json."""
    schema = _schema()
    assert list(STATUSES) == schema["$defs"]["item"]["properties"]["status"]["enum"]
    assert list(LABELS) == schema["$defs"]["labelValue"]["enum"]


def test_fr070_fr071_to_dict_key_order_matches_schema_at_every_level():
    """FR-070, FR-071: to_dict() key order equals the schema property order at every level."""
    schema = _schema()
    data = _sample_result().to_dict()
    assert list(data) == list(schema["properties"])
    dimension = data["dimensions"][0]
    assert list(dimension) == list(schema["$defs"]["dimension"]["properties"])
    assert list(dimension["items"][0]) == list(schema["$defs"]["item"]["properties"])
    assert list(data["label"]) == list(schema["properties"]["label"]["properties"])
    valuation_schema = schema["properties"]["valuation"]
    assert list(data["valuation"]) == list(valuation_schema["properties"])
    part_props = valuation_schema["properties"]["parts"]["items"]["properties"]
    assert list(data["valuation"]["parts"][0]) == list(part_props)


def test_fr070_to_dict_values():
    """FR-070: to_dict() carries every value; object values become dicts in their given order."""
    data = _sample_result().to_dict()
    assert data["total"] == 100
    assert data["max"] == 100
    assert data["raw_earned"] == 15
    assert data["raw_available"] == 15
    assert [d["name"] for d in data["dimensions"]] == ["Forensic Quality", "Turnaround"]
    first = data["dimensions"][0]["items"][0]
    assert first == {
        "name": "Piotroski F-Score",
        "requirement": "FR-010",
        "value": 9,
        "earned": 10,
        "available": 10,
        "status": "scored",
        "reason": ">= 8",
    }
    obj_value = data["dimensions"][1]["items"][0]["value"]
    assert obj_value == {"net_profit_margin": 16, "previous_net_profit_margin": -2}
    assert list(obj_value) == ["net_profit_margin", "previous_net_profit_margin"]
    assert data["dimensions"][0]["items"][1]["value"] is None
    assert data["label"] == {
        "pre_gate": "STRONG BUY",
        "final": "HOLD",
        "reasons": ["Total 100 >= 70: STRONG BUY", "ROE missing"],
    }
    assert data["valuation"]["score"] == 8
    assert data["valuation"]["max"] == 10
    assert data["valuation"]["parts"][2] == {
        "name": "PEG",
        "requirement": "FR-060",
        "value": None,
        "points": 0,
        "available": 2,
        "reason": "No data",
    }


def test_fr071_to_dict_contains_only_plain_json_types():
    """FR-071: to_dict() holds only dict/list/str/int/float/None (tuples become lists)."""
    data = _sample_result().to_dict()
    allowed = {str, int, float, type(None)}
    assert set(_walk_types(data)) <= allowed


def test_fr071_to_json_is_the_fixed_dumps_form():
    """FR-071: to_json() is json.dumps(to_dict()) with the R-06 options, plus a newline."""
    result = _sample_result()
    expected = json.dumps(result.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    assert result.to_json() == expected
    assert result.to_json().endswith("}\n")


def test_fr071_equal_results_serialise_identically():
    """FR-071: two equal results compare equal and serialise byte-identically."""
    assert _sample_result() == _sample_result()
    assert _sample_result().to_json() == _sample_result().to_json()
