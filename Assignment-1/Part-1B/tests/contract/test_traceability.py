"""Traceability: every spec id is exercised by a named test (research.md R-14; tasks.md T083).

Reads spec.md and every test function's name and docstring under tests/ (this file excluded).
"""

from __future__ import annotations

import ast
import json
import re

from conftest import DATASET_PATH, PROJECT_ROOT, SPEC_PATH

TESTS_DIR = PROJECT_ROOT / "tests"
AGENT_CODES = [
    "MR-SCHEMA",
    "MR-CONSIST",
    "OUT-SCHEMA",
    "OUT-DATE",
    *(f"G-{n}" for n in range(1, 6)),
    *(f"C-{n}" for n in range(1, 6)),
]
OWNER_IDS = ["P-1.1", "P-1.2", "P-1.3", "P-1.4", "P-1.5", "P-2", "P-3", "P-4", "P-5"]


def _tests():
    """(file, name, docstring) for every test function outside this file."""
    found = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.name == "test_traceability.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                found.append((path.name, node.name, ast.get_docstring(node) or ""))
    return found


def _spec_ids():
    text = SPEC_PATH.read_text(encoding="utf-8")
    frs = sorted(set(re.findall(r"\*\*(FR-\d{3})\*\*", text)))
    acs = sorted(set(re.findall(r"\*\*(AC-\d\.\d)\*\*", text)))
    invs = sorted(set(re.findall(r"^\s*\|\s*(INV-\d+)\s*\|", text, re.M)), key=lambda i: int(i[4:]))
    return frs, acs, invs


def _pattern(spec_id):
    """`FR-016` matches fr016 / fr_016 / FR-016; `AC-3.1` matches ac_3_1 / AC-3.1; `INV-7`
    matches inv_7 / INV-7 but not INV-70; case-insensitive, with -, . and _ equivalent."""
    prefix, number = spec_id.lower().split("-", 1)
    parts = number.split(".")
    body = "_?" + "_".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![a-z0-9]){prefix}{body}(?![0-9])")


def _normalise(text):
    return re.sub(r"[-.]", "_", text.lower())


def test_spec_ids_are_complete():
    """The id lists parsed from spec.md are complete: FR-001 … FR-035, AC-1.1 … AC-5.6 (with
    AC-1.6, rev 3) and INV-1 … INV-11 (rev 3)."""
    frs, acs, invs = _spec_ids()
    assert frs == [f"FR-{n:03d}" for n in range(1, 36)]
    assert "AC-1.6" in acs and "AC-5.6" in acs and len(acs) == 27
    assert invs == [f"INV-{n}" for n in range(1, 12)]


def test_every_fr_ac_inv_id_is_named_by_a_test():
    """FR-001 … FR-035, AC-1.1 … AC-5.6 and INV-1 … INV-11 each appear in at least one test
    function name or docstring."""
    texts = [_normalise(f"{name} {doc}") for _file, name, doc in _tests()]
    frs, acs, invs = _spec_ids()
    missing = [i for i in frs + acs + invs if not any(_pattern(i).search(t) for t in texts)]
    assert missing == []


def test_every_agent_code_is_cited_by_a_test_docstring():
    """Spec FR-028 code table: every agent code MR-SCHEMA … C-5 appears in a test docstring."""
    docs = [doc for _file, _name, doc in _tests()]
    missing = [
        code
        for code in AGENT_CODES
        if not any(re.search(rf"(?<![A-Za-z0-9-]){re.escape(code)}(?![0-9])", d) for d in docs)
    ]
    assert missing == []


def _cited(doc):
    return {m[0] for m in re.finditer(r"(?<![A-Za-z])P-[1-5](?:\.[1-5])?(?![0-9.])", doc)} & set(
        OWNER_IDS
    )


def test_owner_decisions_carry_the_confirmed_tag():
    """Every test docstring that cites P-1.1 … P-1.5, P-2, P-3, P-4 or P-5 carries the literal
    `CONFIRMED P-n` tag; no test docstring and no dataset case says PROVISIONAL (all owner
    decisions confirmed 2026-11-22)."""
    untagged = []
    for file, name, doc in _tests():
        for owner_id in _cited(doc):
            if f"CONFIRMED {owner_id}" not in doc:
                untagged.append((file, name, owner_id))
        assert "PROVISIONAL" not in doc, name
    assert untagged == []
    assert "PROVISIONAL" not in DATASET_PATH.read_text(encoding="utf-8")
    cited = {i for _f, _n, doc in _tests() for i in _cited(doc)}
    assert cited == set(OWNER_IDS)
    json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def test_pattern_matching_rules():
    """The id matcher treats -, . and _ alike, ignores case and respects number boundaries."""
    assert _pattern("FR-016").search(_normalise("test_fr016_guard"))
    assert _pattern("AC-3.1").search(_normalise("test_ac_3_1_empty"))
    assert _pattern("AC-3.1").search(_normalise("AC-3.1: empty"))
    assert _pattern("INV-7").search(_normalise("test_inv_7_x"))
    assert not _pattern("INV-1").search(_normalise("INV-10 only"))
    assert not _pattern("FR-001").search(_normalise("FR-0012"))
