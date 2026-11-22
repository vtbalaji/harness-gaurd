"""FR-001: the snapshot field schema and the validated Snapshot."""

import dataclasses
import json
from pathlib import Path

import pytest

from gis_scorer import snapshot

SNAPSHOT_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "001-gis-scorer"
    / "contracts"
    / "snapshot.schema.json"
)

# data-model.md §1 table order (30 fields).
EXPECTED_FIELDS = (
    "piotroski",
    "altman_z",
    "beneish_m",
    "revenue_12m",
    "revenue_prior_12m",
    "ebitda_12m",
    "ebitda_prior_12m",
    "net_profit_12m",
    "net_profit_prior_12m",
    "equity",
    "equity_prior",
    "debt_to_equity",
    "debt_to_equity_prior",
    "current_ratio",
    "ocf_to_net_profit",
    "net_profit_margin",
    "operating_margin",
    "net_profit_margin_year_ago",
    "operating_margin_year_ago",
    "previous_net_profit_margin",
    "roe",
    "roce",
    "recent_net_profit_margins",
    "ccc_days",
    "ccc_days_prior",
    "dso_days",
    "dso_days_prior",
    "pe",
    "pb",
    "peg",
)


def test_fr001_fields_are_the_30_named_metrics_in_order():
    """FR-001: FIELDS lists the 30 Key Entities metrics in data-model.md §1 order."""
    assert snapshot.FIELDS == EXPECTED_FIELDS
    assert len(snapshot.FIELDS) == 30


def test_fr001_fields_match_snapshot_schema_order():
    """FR-001: FIELDS has the same order as contracts/snapshot.schema.json."""
    schema = json.loads(SNAPSHOT_SCHEMA.read_text(encoding="utf-8"))
    assert tuple(schema["properties"]) == snapshot.FIELDS


def test_fr001_snapshot_attributes_follow_fields():
    """FR-001: the Snapshot dataclass has one attribute per field, in FIELDS order."""
    names = tuple(f.name for f in dataclasses.fields(snapshot.Snapshot))
    assert names == snapshot.FIELDS


def test_fr001_empty_snapshot_is_all_missing(empty_snapshot):
    """FR-001: every metric is optional; an empty snapshot validates with every value None."""
    validated = snapshot.validate(empty_snapshot)
    assert isinstance(validated, snapshot.Snapshot)
    for name in snapshot.FIELDS:
        assert getattr(validated, name) is None


def test_fr001_zero_and_negative_are_real_values():
    """FR-001: zero and negative values are kept as real values, not treated as missing."""
    validated = snapshot.validate({"roe": 0, "pe": 0, "altman_z": -1.5})
    assert validated.roe == 0
    assert validated.pe == 0
    assert validated.altman_z == -1.5
    assert validated.roce is None


def test_fr001_list_field_becomes_a_tuple():
    """FR-001: the quarterly-margin list is stored immutably as a tuple."""
    validated = snapshot.validate({"recent_net_profit_margins": [1, 2.5]})
    assert validated.recent_net_profit_margins == (1, 2.5)


def test_fr001_snapshot_is_frozen():
    """FR-001: the validated Snapshot is immutable."""
    validated = snapshot.validate({"roe": 5})
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated.roe = 6
