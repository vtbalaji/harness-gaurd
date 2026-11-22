"""Schema contracts (spec FR-001, "Schema file pins (rev 2)"; research.md R-1, R-2, G1)."""

from __future__ import annotations

import hashlib
import json
import re

import pytest
from conftest import CONTRACTS_DIR, PROJECT_ROOT, SPEC_PATH

SCHEMA_NAMES = ("output", "model-response")

# research.md R-1, restated here independently of validators.py.
R1_ASSERTIONS = {
    "type",
    "enum",
    "const",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "pattern",
    "exclusiveMinimum",
    "maxProperties",
    "anyOf",
    "allOf",
    "if",
    "then",
    "$ref",
}
R1_ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description", "$comment"}

PIN_ROW = re.compile(
    r"^\|\s*`contracts/(?P<file>[\w.-]+)`\s*\|\s*`(?P<id>[^`]+)`\s*\|\s*(?P<hash>\S+)\s*\|\s*$"
)


def _files():
    for name in SCHEMA_NAMES:
        yield CONTRACTS_DIR / f"{name}.schema.json"
        yield PROJECT_ROOT / "schemas" / f"{name}.schema.json"


def _pin_table(spec_text):
    """Parse spec.md 'Schema file pins (rev 2)' into {$id: sha256}."""
    section = spec_text.split("#### Schema file pins (rev 2)", 1)[1].split("\n#### ", 1)[0]
    pins = {}
    for line in section.splitlines():
        match = PIN_ROW.match(line)
        if match:
            pins[match["id"]] = match["hash"]
    return pins


def _check_pin(path, pins):
    """Return a failure message, or None when the file's SHA-256 equals its version's pin."""
    data = path.read_bytes()
    schema_id = json.loads(data)["$id"]
    pinned = pins.get(schema_id)
    advice = (
        "a schema change needs a new version ($id) and a new pin row through a spec revision "
        "(spec 'Schema file pins (rev 2)', G1)"
    )
    if pinned is None:
        return f"{path.name}: no pin row for {schema_id}; {advice}"
    if pinned.startswith("PENDING-"):
        return f"{path.name}: pin for {schema_id} is still {pinned}; {advice}"
    actual = hashlib.sha256(data).hexdigest()
    if actual != pinned:
        return f"{path.name}: SHA-256 {actual} != pinned {pinned} for {schema_id}; {advice}"
    return None


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_fr001_runtime_schemas_byte_identical_to_contracts(name):
    """FR-001, R-2: schemas/*.json are byte-identical copies of contracts/*.json."""
    runtime = (PROJECT_ROOT / "schemas" / f"{name}.schema.json").read_bytes()
    design = (CONTRACTS_DIR / f"{name}.schema.json").read_bytes()
    assert runtime == design


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_fr001_schema_path_resolves_to_existing_file(name):
    """FR-001, R-2: validators.schema_path resolves the runtime schema files."""
    from order_agent import validators

    path = validators.schema_path(name)
    assert path.is_file()
    assert path.resolve() == (PROJECT_ROOT / "schemas" / f"{name}.schema.json").resolve()


def _walk(node, where, found):
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        found.append((where, key))
        if key == "properties" or key == "$defs":
            for sub_name, sub in value.items():
                _walk(sub, f"{where}/{key}/{sub_name}", found)
        elif key in ("items", "if", "then") or (
            key == "additionalProperties" and isinstance(value, dict)
        ):
            _walk(value, f"{where}/{key}", found)
        elif key in ("anyOf", "allOf"):
            for i, sub in enumerate(value):
                _walk(sub, f"{where}/{key}/{i}", found)


@pytest.mark.parametrize("name", SCHEMA_NAMES)
def test_r1_schemas_use_only_the_declared_keyword_subset(name):
    """FR-001, R-1: a recursive walk finds no keyword outside the assertion/annotation lists."""
    schema = json.loads((CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    found = []
    _walk(schema, "#", found)
    unknown = [(where, key) for where, key in found if key not in R1_ASSERTIONS | R1_ANNOTATIONS]
    assert unknown == []
    deepest = {
        "output": "#/$defs/additional_order/properties/evidence/properties/order_value",
        "model-response": "#/$defs/mr_order/properties/order_value",
    }[name]
    assert any(where == deepest for where, _key in found)  # the walk really descended


def test_fr001_output_schema_identity():
    """FR-001: output.schema.json has $id urn:order-agent:output:1.0 and schema_version "1.0"."""
    schema = json.loads((CONTRACTS_DIR / "output.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "urn:order-agent:output:1.0"
    assert schema["properties"]["schema_version"] == {"const": "1.0"}


@pytest.mark.parametrize("path", list(_files()), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_g1_schema_file_sha256_equals_spec_pin(path):
    """FR-001, Schema file pins (rev 2, G1): each file's SHA-256 equals its version's pin row."""
    pins = _pin_table(SPEC_PATH.read_text(encoding="utf-8"))
    assert set(pins) == {"urn:order-agent:output:1.0", "urn:order-agent:model-response:mr-1"}
    problem = _check_pin(path, pins)
    assert problem is None, problem


def test_g1_pin_check_fails_on_one_changed_byte(tmp_path):
    """Schema file pins (rev 2, G1): a mutated copy with the same $id fails the pin check."""
    pins = {
        "urn:order-agent:model-response:mr-1": hashlib.sha256(
            (CONTRACTS_DIR / "model-response.schema.json").read_bytes()
        ).hexdigest()
    }
    original = (CONTRACTS_DIR / "model-response.schema.json").read_bytes()
    assert _check_pin(CONTRACTS_DIR / "model-response.schema.json", pins) is None
    mutated = original.replace(b'"title": "Model', b'"title": "model', 1)
    assert mutated != original
    copy = tmp_path / "model-response.schema.json"
    copy.write_bytes(mutated)
    problem = _check_pin(copy, pins)
    assert problem is not None and "new version" in problem


def test_g1_pin_check_fails_on_pending_or_missing_row(tmp_path):
    """Schema file pins (rev 2, G1): a PENDING- value or a missing row fails."""
    path = CONTRACTS_DIR / "model-response.schema.json"
    pending = _check_pin(path, {"urn:order-agent:model-response:mr-1": "PENDING-T098"})
    assert pending is not None and "PENDING-T098" in pending
    missing = _check_pin(path, {})
    assert missing is not None and "no pin row" in missing


def test_g1_pin_table_parser_reads_markdown_rows():
    """Schema file pins (rev 2, G1): the parser reads `| file | $id | hash |` rows."""
    text = (
        "#### Schema file pins (rev 2)\n\n| File | Version (`$id`) | SHA-256 |\n|---|---|---|\n"
        "| `contracts/a.schema.json` | `urn:x:1` | " + "a" * 64 + " |\n\n#### Next\n"
        "| `contracts/b.schema.json` | `urn:y:1` | " + "b" * 64 + " |\n"
    )
    assert _pin_table(text) == {"urn:x:1": "a" * 64}
