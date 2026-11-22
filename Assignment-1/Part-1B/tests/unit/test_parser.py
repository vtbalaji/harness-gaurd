"""Parser clean-up rules PC-1 … PC-3 only (spec FR-019; research.md R-8)."""

from __future__ import annotations

import pytest

OBJ = '{"is_new_order": true, "currency": "INR"}'


def _rules(log):
    return [entry["rule"] for entry in log]


def test_fr019_plain_object_parses_with_empty_log():
    """FR-019, R-8: valid JSON needs no clean-up, so nothing is logged."""
    from order_agent import parser

    obj, log = parser.parse(OBJ)
    assert obj == {"is_new_order": True, "currency": "INR"}
    assert log == []


def test_fr019_pc1_strips_surrounding_whitespace_and_logs_it():
    """FR-019, R-8 PC-1: surrounding whitespace is stripped and logged."""
    from order_agent import parser

    obj, log = parser.parse("\n  " + OBJ + " \n")
    assert obj["currency"] == "INR"
    assert _rules(log) == ["PC-1"]


@pytest.mark.parametrize("opener", ["```", "```json", "```json  "])
def test_fr019_pc2_removes_exactly_one_whole_text_fence(opener):
    """FR-019, R-8 PC-2: one whole-text ``` or ```json fence is removed and logged."""
    from order_agent import parser

    obj, log = parser.parse(f"{opener}\n{OBJ}\n```")
    assert obj["is_new_order"] is True
    assert _rules(log) == ["PC-2"]


def test_fr019_pc1_and_pc2_both_logged_in_order():
    """FR-019, R-8: PC-1 then PC-2, each logged because each changed the text."""
    from order_agent import parser

    _obj, log = parser.parse(f"  ```json\n{OBJ}\n```\n")
    assert _rules(log) == ["PC-1", "PC-2"]
    assert all(entry["detail"] for entry in log)


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("Here is the JSON: " + OBJ, "PC-3"),
        (OBJ + " Hope this helps.", "PC-3"),
        ('{"a": 1,}', "PC-3"),
        ('{"is_new_order": true, "orders": [{"order_value": 12', "PC-3"),
        ("[1, 2]", "PC-3"),
        ('"just a string"', "PC-3"),
        (f"```json\n{OBJ}\n```\n```json\n{OBJ}\n```", "PC-2"),
        (f"```json\n{OBJ}\n```\nHope this helps.", "PC-3"),
        ('{"a": NaN}', "PC-3"),
        ('{"a": 1, "a": 2}', "PC-3"),
        ("", "PC-3"),
    ],
    ids=[
        "prose-before",
        "prose-after",
        "trailing-comma",
        "truncated",
        "top-level-array",
        "top-level-string",
        "two-fences",
        "fence-with-trailing-prose",
        "nan-constant",
        "duplicate-key",
        "empty",
    ],
)
def test_fr019_unparseable_text_raises_parse_error_without_repair(text, rule):
    """FR-019, R-8: no repair; the failing rule is reported and the text is left unchanged."""
    from order_agent import parser

    with pytest.raises(parser.ParseError) as info:
        parser.parse(text)
    assert info.value.rule == rule
    assert info.value.message
    assert rule in str(info.value)


def test_fr019_no_value_or_key_case_is_changed():
    """FR-019, R-8: "INR" stays "INR" and "inr" stays "inr" (no case-folding)."""
    from order_agent import parser

    obj, _log = parser.parse('{"Currency": "inr", "currency": "INR"}')
    assert obj == {"Currency": "inr", "currency": "INR"}
