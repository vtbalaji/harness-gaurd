"""Constitution III / SC-006 traceability: every FR and acceptance scenario has a test.

research.md R-12. The ids in scope come from the GIS_TRACE_SCOPE environment variable
(comma-separated tokens from SCOPE_TABLE, mirroring tasks.md "Traceability scope"). Unset
means the full scope: every FR id and every USn-ASm scenario in spec.md.
"""

import ast
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "specs" / "001-gis-scorer" / "spec.md"
TESTS_DIR = ROOT / "tests"
THIS_FILE = Path(__file__).resolve()


def _frs(*numbers):
    return frozenset(f"FR-{n:03d}" for n in numbers)


def _scenarios(story, count):
    return frozenset(f"US{story}-AS{m}" for m in range(1, count + 1))


# tasks.md, Conventions, "Traceability scope" table.
SCOPE_TABLE = {
    "foundation": (_frs(1, 70, 71), frozenset()),
    "US1": (_frs(3, *range(10, 28), 30, 44, 50, 52), _scenarios(1, 5)),
    "US2": (_frs(2, 51), _scenarios(2, 4)),
    "US3": (_frs(53, 54, 55), _scenarios(3, 5)),
    "US4": (_frs(40, 41, 42, 43), _scenarios(4, 4)),
    "US5": (_frs(60), _scenarios(5, 3)),
    "US6": (_frs(72), _scenarios(6, 2)),
}

_STORY_HEADING = re.compile(r"^###\s+User Story\s+(\d+)\b")
_NUMBERED_ITEM = re.compile(r"^(\d+)\.\s")


def spec_text():
    return SPEC_PATH.read_text(encoding="utf-8")


def spec_fr_ids(text):
    return frozenset(re.findall(r"FR-\d{3}", text))


def spec_scenario_ids(text):
    """Every numbered list item under a 'User Story n' heading's Acceptance Scenarios."""
    ids = set()
    story = None
    in_scenarios = False
    for line in text.splitlines():
        heading = _STORY_HEADING.match(line)
        if heading:
            story = int(heading.group(1))
            in_scenarios = False
            continue
        if line.startswith("#"):
            story = None
            in_scenarios = False
            continue
        if story is not None and line.strip().startswith("**Acceptance Scenarios**"):
            in_scenarios = True
            continue
        item = _NUMBERED_ITEM.match(line)
        if story is not None and in_scenarios and item:
            ids.add(f"US{story}-AS{int(item.group(1))}")
    return frozenset(ids)


def collect_test_texts():
    """(name, docstring) for every test function under tests/, excluding this file."""
    found = []
    for path in sorted(TESTS_DIR.rglob("*.py")):
        if path.resolve() == THIS_FILE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            is_func = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            if is_func and node.name.startswith("test"):
                found.append((node.name, ast.get_docstring(node) or ""))
    return found


def is_cited(identifier, tests):
    """True when a test function name (frNNN / usN_asM) or docstring cites the id."""
    if identifier.startswith("FR-"):
        number = identifier[3:]
        name_pattern = re.compile(rf"fr{number}(?!\d)")
        doc_pattern = re.compile(rf"FR-{number}(?!\d)")
    else:
        story, scenario = identifier.split("-")
        name_pattern = re.compile(rf"{story.lower()}_{scenario.lower()}(?!\d)")
        doc_pattern = re.compile(rf"{re.escape(identifier)}(?!\d)")
    return any(name_pattern.search(name) or doc_pattern.search(doc) for name, doc in tests)


def scope_ids(raw_scope, text):
    """The FR and scenario ids expected for a GIS_TRACE_SCOPE value (None = full scope)."""
    if raw_scope is None or not raw_scope.strip():
        return spec_fr_ids(text) | spec_scenario_ids(text)
    expected = set()
    for token in (t.strip() for t in raw_scope.split(",")):
        if token not in SCOPE_TABLE:
            raise ValueError(f"unknown GIS_TRACE_SCOPE token: {token!r}")
        frs, scenarios = SCOPE_TABLE[token]
        expected |= frs | scenarios
    return frozenset(expected)


def test_traceability_scope_table_matches_spec_fr_ids():
    """SC-006, Constitution III: the scope table's FR ids are exactly the FR ids in spec.md."""
    text = spec_text()
    table_frs = frozenset().union(*(frs for frs, _ in SCOPE_TABLE.values()))
    assert table_frs == spec_fr_ids(text)


def test_traceability_scope_table_matches_spec_scenarios():
    """SC-006, Constitution III: the scope table's scenarios are exactly those in spec.md."""
    text = spec_text()
    table_scenarios = frozenset().union(*(sc for _, sc in SCOPE_TABLE.values()))
    assert table_scenarios == spec_scenario_ids(text)


def test_traceability_unknown_scope_token_fails():
    """SC-006: an unknown GIS_TRACE_SCOPE token is an error, never silently ignored."""
    with pytest.raises(ValueError, match="unknown GIS_TRACE_SCOPE token"):
        scope_ids("foundation,US9", spec_text())


def _fr_constant_names():
    """Module-level names in src/gis_scorer/*.py that carry an FR id (FRxxx_*)."""
    names = []
    for path in sorted((ROOT / "src" / "gis_scorer").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else []
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and re.search(r"FR\d{3}_", target.id):
                    names.append((path.name, target.id))
    return names


def test_traceability_sc006_every_fr_constant_traces_to_a_spec_fr():
    """SC-006, Constitution II: every FRxxx_* constant names an FR id that exists in spec.md."""
    spec_frs = spec_fr_ids(spec_text())
    constants = _fr_constant_names()
    assert constants, "no FRxxx_* constants found"
    unknown = [
        (module, name)
        for module, name in constants
        for number in re.findall(r"FR(\d{3})", name)
        if f"FR-{number}" not in spec_frs
    ]
    assert unknown == []


def test_traceability_sc006_constants_exist_for_scoring_rules():
    """SC-006: the scoring rules are encoded as FR constants in rules, scoring and valuation."""
    modules = {module for module, _ in _fr_constant_names()}
    assert {"rules.py", "scoring.py", "valuation.py"} <= modules


@pytest.mark.parametrize("tag", ["R-01", "R-02"])
def test_traceability_confirmed_decisions_are_tagged(tag):
    """SC-006: the confirmed R-01 / R-02 decisions are each covered by a tagged test docstring."""
    assert any(tag in doc for _, doc in collect_test_texts())


def test_traceability_every_id_in_scope_is_cited_by_a_test():
    """SC-006, Constitution III: each FR / USn-ASm in scope is cited by a test name or docstring."""
    text = spec_text()
    expected = scope_ids(os.environ.get("GIS_TRACE_SCOPE"), text)
    tests = collect_test_texts()
    missing = sorted(i for i in expected if not is_cited(i, tests))
    assert missing == [], f"ids not cited by any test: {missing}"
