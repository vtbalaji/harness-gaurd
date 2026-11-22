"""FR-030, FR-070: dimension grouping, order and subtotals."""

from gis_scorer.result import LabelDecision, Valuation
from gis_scorer.scoring import score_snapshot

DIMENSION_NAMES = [
    "Forensic Quality",
    "Growth",
    "Revenue Quality",
    "Financial Health",
    "Profitability",
    "Competitive Moat",
    "Turnaround",
    "Balance Sheet",
    "Penalties",
]

# data-model.md §3 item catalogue, in FR-030 order: (dimension, [(item name, FR id), ...]).
CATALOGUE = [
    (
        "Forensic Quality",
        [
            ("Piotroski F-Score", "FR-010"),
            ("Altman Z-Score", "FR-011"),
            ("Beneish M-Score", "FR-012"),
        ],
    ),
    ("Growth", [("EBITDA Growth", "FR-014"), ("Earnings Growth", "FR-015")]),
    ("Revenue Quality", [("Revenue Growth", "FR-016")]),
    ("Financial Health", [("Equity Growth", "FR-017"), ("Cash Flow Quality", "FR-018")]),
    ("Profitability", [("Net Profit Margin", "FR-019"), ("Operating Margin", "FR-020")]),
    ("Competitive Moat", [("ROE", "FR-021"), ("ROCE", "FR-021")]),
    (
        "Turnaround",
        [
            ("Loss to Profit", "FR-022"),
            ("Profitability Sustainability", "FR-023"),
            ("Working Capital Efficiency", "FR-024"),
            ("Debt Reduction", "FR-025"),
        ],
    ),
    ("Balance Sheet", [("Current Ratio", "FR-026"), ("Debt to Equity", "FR-027")]),
    ("Penalties", []),
]


def test_fr030_nine_dimensions_in_order(max_snapshot):
    """FR-030: exactly 9 dimensions, named and ordered as FR-030 lists them."""
    result = score_snapshot(max_snapshot())
    assert [d.name for d in result.dimensions] == DIMENSION_NAMES


def test_fr030_items_follow_the_catalogue_order(max_snapshot):
    """FR-030: each dimension holds its catalogue items in order, each with its FR id."""
    result = score_snapshot(max_snapshot())
    actual = [(d.name, [(i.name, i.requirement) for i in d.items]) for d in result.dimensions]
    assert actual == CATALOGUE


def test_fr030_subtotals_are_item_sums(max_snapshot):
    """FR-030: each dimension's earned/available equals the sum over its items."""
    result = score_snapshot(max_snapshot())
    for dimension in result.dimensions:
        assert dimension.earned == sum(i.earned for i in dimension.items)
        assert dimension.available == sum(i.available for i in dimension.items)


def test_fr030_max_snapshot_subtotals(max_snapshot):
    """FR-030: full_max subtotals are 20, 15, 10, 10, 7, 10, 15, 10 and Penalties 0 of 0."""
    result = score_snapshot(max_snapshot())
    subtotals = [(d.earned, d.available) for d in result.dimensions]
    assert subtotals == [
        (20, 20),
        (15, 15),
        (10, 10),
        (10, 10),
        (7, 7),
        (10, 10),
        (15, 15),
        (10, 10),
        (0, 0),
    ]
    assert result.dimensions[-1].items == ()


def test_fr070_result_carries_every_part(max_snapshot):
    """FR-070: the result has total, max 100, raw earned/available, label and valuation."""
    result = score_snapshot(max_snapshot())
    assert result.max == 100
    assert result.raw_earned == 97
    assert result.raw_available == 97
    assert result.total == 100
    assert isinstance(result.label, LabelDecision)
    assert isinstance(result.valuation, Valuation)
    assert [p.name for p in result.valuation.parts] == ["P/E", "P/B", "PEG"]
