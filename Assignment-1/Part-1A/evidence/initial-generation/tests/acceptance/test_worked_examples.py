"""SC-004: worked examples, hand-computed from the spec FRs and cross-checked against
Assignment-1/GIS_REFERENCE.md (§3 ladders, §3.10 penalties, §4 total, labels, gating and
valuation). Each docstring shows the item-by-item computation; each test asserts every item's
points, the exact total, the final label and the valuation.
"""

import json
from pathlib import Path

from gis_scorer import score_snapshot

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "snapshots"

ITEM_ORDER = (
    "Piotroski F-Score",
    "Altman Z-Score",
    "Beneish M-Score",
    "EBITDA Growth",
    "Earnings Growth",
    "Revenue Growth",
    "Equity Growth",
    "Cash Flow Quality",
    "Net Profit Margin",
    "Operating Margin",
    "ROE",
    "ROCE",
    "Loss to Profit",
    "Profitability Sustainability",
    "Working Capital Efficiency",
    "Debt Reduction",
    "Current Ratio",
    "Debt to Equity",
)


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _item_points(result):
    items = [i for d in result.dimensions[:-1] for i in d.items]
    assert tuple(i.name for i in items) == ITEM_ORDER
    return [(i.earned, i.available) for i in items]


def _penalties(result):
    return [(p.name, p.earned) for p in result.dimensions[-1].items]


def test_sc004_example_1_full_max():
    """SC-004 example 1, full_max.json (FR-010 to FR-060, FR-050, FR-052):

    Forensic: Piotroski 9 >=8 -> 10/10; Altman 3.5 >2.99 -> 5/5; Beneish -2.5 <-2.22 -> 5/5.
    Growth: EBITDA 125 v 100 = 25% >=20 -> 8/8; earnings 125 v 100 = 25% >=20 -> 7/7.
    Revenue 130 v 100 = 30% >=25 -> 10/10.
    Financial health: equity 120 v 100 = 20% >15 -> 5/5; OCF/NP 1.6 >=1.5 -> 5/5.
    Profitability: NPM 16 >15 -> 3/3; OPM 21 >20 -> 4/4. Moat: ROE 18, ROCE 20 >=15 -> 5/5 each.
    Turnaround: NPM 16 > 0, previous -2 <= 0 -> 5/5; run [16,15,14,13] = 4 -> 2/2;
    dCCC 40-400 = -360 <=-300 -> 5/5; dD/E 0.3-0.9 = -0.6 <=-0.5 -> 3/3.
    Balance sheet: CR 2.5 >2.0 -> 5/5; D/E 0.3 <0.5 -> 5/5.
    No penalty (16 > 15 and 21 > 20). Raw 97/97 -> total 100 -> STRONG BUY; gate passes
    (ROE 18, Piotroski 9). Valuation P/E 11 -> 5, P/B 1.4 -> 3, PEG 0.9 -> 2 = 10.
    """
    result = score_snapshot(_load("full_max.json"))
    assert _item_points(result) == [
        (10, 10),
        (5, 5),
        (5, 5),
        (8, 8),
        (7, 7),
        (10, 10),
        (5, 5),
        (5, 5),
        (3, 3),
        (4, 4),
        (5, 5),
        (5, 5),
        (5, 5),
        (2, 2),
        (5, 5),
        (3, 3),
        (5, 5),
        (5, 5),
    ]
    assert _penalties(result) == []
    assert (result.raw_earned, result.raw_available, result.total) == (97, 97, 100)
    assert (result.label.pre_gate, result.label.final) == ("STRONG BUY", "STRONG BUY")
    assert result.valuation.score == 10


def test_sc004_example_2_sparse():
    """SC-004 example 2, sparse.json {"net_profit_margin": 12, "roe": 0} (FR-001, FR-051):

    NPM 12 >10 -> 2/3; ROE 0 is a real value -> 0/5 (the reference would treat a stored 0 as
    missing: a recorded deviation, spec Assumptions). Every other item is "No data" 0/0.
    Raw 2/8 = 25. Piotroski, Altman and Beneish all missing -> SUSPICIOUS. Valuation 0.
    """
    result = score_snapshot(_load("sparse.json"))
    points = _item_points(result)
    assert points[ITEM_ORDER.index("Net Profit Margin")] == (2, 3)
    assert points[ITEM_ORDER.index("ROE")] == (0, 5)
    assert sum(a for _, a in points) == 8
    assert (result.raw_earned, result.raw_available, result.total) == (2, 8, 25)
    assert result.label.final == "SUSPICIOUS"
    assert result.label.reasons == ("Piotroski, Altman Z and Beneish M all missing",)
    assert result.valuation.score == 0


def test_sc004_example_3_empty():
    """SC-004 example 3, empty.json {} (FR-050, FR-051):

    Nothing is available: every item 0/0, raw 0/0 -> total 0 (reference §4: 0 when raw_max is
    0). NPM missing and all forensic inputs missing -> SUSPICIOUS with both reasons.
    Valuation 0.
    """
    result = score_snapshot(_load("empty.json"))
    assert _item_points(result) == [(0, 0)] * 18
    assert (result.raw_earned, result.raw_available, result.total) == (0, 0, 0)
    assert result.label.final == "SUSPICIOUS"
    assert result.label.reasons == (
        "Net profit margin missing",
        "Piotroski, Altman Z and Beneish M all missing",
    )
    assert result.valuation.score == 0


def test_sc004_example_4_buy_band_with_roe_10_is_held():
    """SC-004 example 4, a BUY-band company with ROE 10 (FR-052, FR-054):

    Forensic: Piotroski 7 >=6 -> 7; Altman 2.2 >=1.81 -> 3; Beneish -2.0 <=-1.78 -> 2 (12/20).
    Growth: EBITDA 112 v 100 = 12% >=10 -> 4/8; earnings 108 v 100 = 8% >=5 -> 3/7.
    Revenue 118 v 100 = 18% >=15 -> 7/10.
    Financial health: equity 112 v 100 = 12% >=10 -> 3/5; OCF/NP 1.1 >=1.0 -> 4/5.
    Profitability: NPM 12 >10 -> 2/3; OPM 18 >15 -> 3/4.
    Moat: ROE 10 >=8 -> 2/5; ROCE 14 >=12 -> 3/5.
    Turnaround: previous NPM 11 > 0 -> 0/5; run [12,11,10,9,8] = 5 -> 2/2;
    dCCC 60-80 = -20 <0 -> 1, dDSO 45-52 = -7 <=-5 -> 2, best -> 2/5;
    dD/E 0.8-1.1 = -0.3 <=-0.2 -> 2/3.
    Balance sheet: CR 1.8 >=1.5 -> 3/5; D/E 0.8 <=1.0 -> 3/5.
    No penalty (all growth > 0; NPM 12 > 11). Raw 55/97 = 56.7 -> 57 -> BUY; the gate fails on
    ROE below 12% -> HOLD (reference §4 display gating). Valuation P/E 20 -> 2, P/B 2.5 -> 2,
    PEG 1.2 -> 1 = 5.
    """
    raw = {
        "piotroski": 7,
        "altman_z": 2.2,
        "beneish_m": -2.0,
        "revenue_12m": 118,
        "revenue_prior_12m": 100,
        "ebitda_12m": 112,
        "ebitda_prior_12m": 100,
        "net_profit_12m": 108,
        "net_profit_prior_12m": 100,
        "equity": 112,
        "equity_prior": 100,
        "debt_to_equity": 0.8,
        "debt_to_equity_prior": 1.1,
        "current_ratio": 1.8,
        "ocf_to_net_profit": 1.1,
        "net_profit_margin": 12,
        "operating_margin": 18,
        "net_profit_margin_year_ago": 11,
        "operating_margin_year_ago": 17,
        "previous_net_profit_margin": 11,
        "roe": 10,
        "roce": 14,
        "recent_net_profit_margins": [12, 11, 10, 9, 8],
        "ccc_days": 60,
        "ccc_days_prior": 80,
        "dso_days": 45,
        "dso_days_prior": 52,
        "pe": 20,
        "pb": 2.5,
        "peg": 1.2,
    }
    result = score_snapshot(raw)
    assert _item_points(result) == [
        (7, 10),
        (3, 5),
        (2, 5),
        (4, 8),
        (3, 7),
        (7, 10),
        (3, 5),
        (4, 5),
        (2, 3),
        (3, 4),
        (2, 5),
        (3, 5),
        (0, 5),
        (2, 2),
        (2, 5),
        (2, 3),
        (3, 5),
        (3, 5),
    ]
    assert _penalties(result) == []
    assert (result.raw_earned, result.raw_available, result.total) == (55, 97, 57)
    assert (result.label.pre_gate, result.label.final) == ("BUY", "HOLD")
    assert result.label.reasons == ("Total 57 >= 55: BUY", "ROE below 12%")
    assert result.valuation.score == 5


def test_sc004_example_5_declining_company_rounds_into_sell():
    """SC-004 example 5, a declining company with penalties (FR-040, FR-041, FR-050, FR-052):

    Forensic: Piotroski 6 -> 7; Altman 2.5 -> 3; Beneish -2.5 -> 5 (15/20).
    Growth: EBITDA 100 v 100 = 0% -> 0/8 (no penalty: 0 is not < 0); earnings 90 v 100 = -10%
    -> 0/7. Revenue 95 v 100 = -5% -> 0/10.
    Financial health: equity 103 v 100 = 3% >0 -> 1/5; OCF/NP 0.9 >=0.8 -> 3/5.
    Profitability: NPM 8 >0 -> 1/3; OPM 12 >10 -> 2/4. Moat: ROE 13 >=12 -> 3; ROCE 11 >=8 -> 2.
    Turnaround: previous NPM 9 > 0 -> 0/5; run [8,9,7,-2] = 3 -> 1/2;
    dCCC +10 and dDSO +5 -> 0/5; dD/E 0.7-0.6 = +0.1 -> 0/3.
    Balance sheet: CR 1.6 >=1.5 -> 3/5; D/E 0.7 <=1.0 -> 3/5.
    Items 34; penalties Revenue Declining -5, Earnings Declining -5; no Margin Compression
    (OPM 12 > 11). Raw 24/97 = 24.74 -> 25 -> SELL. Valuation P/E 14 -> 3, P/B 1.8 -> 2,
    PEG 1.6 -> 0 = 5.
    """
    raw = {
        "piotroski": 6,
        "altman_z": 2.5,
        "beneish_m": -2.5,
        "revenue_12m": 95,
        "revenue_prior_12m": 100,
        "ebitda_12m": 100,
        "ebitda_prior_12m": 100,
        "net_profit_12m": 90,
        "net_profit_prior_12m": 100,
        "equity": 103,
        "equity_prior": 100,
        "debt_to_equity": 0.7,
        "debt_to_equity_prior": 0.6,
        "current_ratio": 1.6,
        "ocf_to_net_profit": 0.9,
        "net_profit_margin": 8,
        "operating_margin": 12,
        "net_profit_margin_year_ago": 9,
        "operating_margin_year_ago": 11,
        "previous_net_profit_margin": 9,
        "roe": 13,
        "roce": 11,
        "recent_net_profit_margins": [8, 9, 7, -2],
        "ccc_days": 100,
        "ccc_days_prior": 90,
        "dso_days": 55,
        "dso_days_prior": 50,
        "pe": 14,
        "pb": 1.8,
        "peg": 1.6,
    }
    result = score_snapshot(raw)
    assert _item_points(result) == [
        (7, 10),
        (3, 5),
        (5, 5),
        (0, 8),
        (0, 7),
        (0, 10),
        (1, 5),
        (3, 5),
        (1, 3),
        (2, 4),
        (3, 5),
        (2, 5),
        (0, 5),
        (1, 2),
        (0, 5),
        (0, 3),
        (3, 5),
        (3, 5),
    ]
    assert _penalties(result) == [("Revenue Declining", -5), ("Earnings Declining", -5)]
    assert (result.raw_earned, result.raw_available, result.total) == (24, 97, 25)
    assert (result.label.pre_gate, result.label.final) == ("SELL", "SELL")
    assert result.label.reasons == ("Total 25 >= 25: SELL",)
    assert result.valuation.score == 5


def test_sc004_example_6_collapsing_company_is_clamped_to_zero():
    """SC-004 example 6, a collapsing company (FR-018, FR-040 to FR-043, FR-050):

    Forensic: Piotroski 3 >=2 -> 2; Altman 1.5 -> 0; Beneish -1.5 -> 0 (2/20).
    Growth: EBITDA 85 v 100 = -15% -> 0/8; earnings 70 v 100 = -30% -> 0/7.
    Revenue 92 v 100 = -8% -> 0/10.
    Financial health: equity 98 v 100 = -2% -> 0/5; OCF/NP -0.2 with TTM profit 70 > 0 -> -3/5.
    Profitability: NPM 4 -> 1/3; OPM 7 -> 1/4. Moat: ROE 5 -> 1/5; ROCE 6 -> 1/5.
    Turnaround: previous NPM 6 > 0 -> 0/5; run [4,6,-1,5] = 2 -> 1/2;
    dCCC +20, dDSO +10 -> 0/5; dD/E 1.6-1.2 = +0.4 -> 0/3.
    Balance sheet: CR 0.9 -> 0/5; D/E 1.6 <=2.0 -> 1/5.
    Items 5; penalties -5 -5 -5 and Margin Compression -3 (4 < 6 and 7 < 9) = -18.
    Raw -13/97 -> clamped to 0 -> STRONG SELL (reference §4 clamp). Valuation P/E 35 -> 1,
    P/B 0.9 -> 3, PEG 2.5 -> 0 = 4.
    """
    raw = {
        "piotroski": 3,
        "altman_z": 1.5,
        "beneish_m": -1.5,
        "revenue_12m": 92,
        "revenue_prior_12m": 100,
        "ebitda_12m": 85,
        "ebitda_prior_12m": 100,
        "net_profit_12m": 70,
        "net_profit_prior_12m": 100,
        "equity": 98,
        "equity_prior": 100,
        "debt_to_equity": 1.6,
        "debt_to_equity_prior": 1.2,
        "current_ratio": 0.9,
        "ocf_to_net_profit": -0.2,
        "net_profit_margin": 4,
        "operating_margin": 7,
        "net_profit_margin_year_ago": 6,
        "operating_margin_year_ago": 9,
        "previous_net_profit_margin": 6,
        "roe": 5,
        "roce": 6,
        "recent_net_profit_margins": [4, 6, -1, 5],
        "ccc_days": 120,
        "ccc_days_prior": 100,
        "dso_days": 70,
        "dso_days_prior": 60,
        "pe": 35,
        "pb": 0.9,
        "peg": 2.5,
    }
    result = score_snapshot(raw)
    assert _item_points(result) == [
        (2, 10),
        (0, 5),
        (0, 5),
        (0, 8),
        (0, 7),
        (0, 10),
        (0, 5),
        (-3, 5),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 5),
        (0, 5),
        (1, 2),
        (0, 5),
        (0, 3),
        (0, 5),
        (1, 5),
    ]
    assert _penalties(result) == [
        ("Revenue Declining", -5),
        ("Earnings Declining", -5),
        ("EBITDA Declining", -5),
        ("Margin Compression", -3),
    ]
    assert (result.raw_earned, result.raw_available, result.total) == (-13, 97, 0)
    assert (result.label.pre_gate, result.label.final) == ("STRONG SELL", "STRONG SELL")
    assert result.label.reasons == ("Total 0 < 25: STRONG SELL",)
    assert result.valuation.score == 4


def test_sc004_example_7_turnaround_with_capped_growth_is_hold():
    """SC-004 example 7, a turnaround with capped growth in the HOLD band (FR-013 to FR-016,
    FR-022, FR-044, FR-052):

    Forensic: Piotroski 5 >=4 -> 4; Altman 2.0 >=1.81 -> 3; Beneish -2.0 <=-1.78 -> 2 (9/20).
    Growth: EBITDA 30 v -10 (prior <= 0) -> capped 4/8; earnings 25 v 5 (> 4 x 5) -> capped 3/7.
    Revenue 140 v 100 = 40% >=25 -> 10/10.
    Financial health: equity 105 v 100 = 5% >=5 -> 2/5; OCF/NP 1.2 >=1.0 -> 4/5.
    Profitability: NPM 3 -> 1/3; OPM 9 -> 1/4. Moat: ROE 9 -> 2/5; ROCE 10 -> 2/5.
    Turnaround: NPM 3 > 0 with previous -4 <= 0 -> 5/5; run [3,-4,-6] = 1 -> 0/2;
    dCCC 70-110 = -40 <=-30 -> 2, dDSO 50-58 = -8 <=-5 -> 2, best -> 2/5;
    dD/E 1.2-1.9 = -0.7 <=-0.5 -> 3/3.
    Balance sheet: CR 1.2 >=1.0 -> 1/5; D/E 1.2 <=2.0 -> 1/5.
    No penalty: capped growth never triggers a decline penalty (FR-044), and NPM 3 > -2.
    Raw 50/97 = 51.5 -> 52 -> HOLD (no gating below BUY). Valuation P/E 30 -> 1, P/B 2.2 -> 2,
    PEG 0.8 -> 2 = 5.
    """
    raw = {
        "piotroski": 5,
        "altman_z": 2.0,
        "beneish_m": -2.0,
        "revenue_12m": 140,
        "revenue_prior_12m": 100,
        "ebitda_12m": 30,
        "ebitda_prior_12m": -10,
        "net_profit_12m": 25,
        "net_profit_prior_12m": 5,
        "equity": 105,
        "equity_prior": 100,
        "debt_to_equity": 1.2,
        "debt_to_equity_prior": 1.9,
        "current_ratio": 1.2,
        "ocf_to_net_profit": 1.2,
        "net_profit_margin": 3,
        "operating_margin": 9,
        "net_profit_margin_year_ago": -2,
        "operating_margin_year_ago": 5,
        "previous_net_profit_margin": -4,
        "roe": 9,
        "roce": 10,
        "recent_net_profit_margins": [3, -4, -6],
        "ccc_days": 70,
        "ccc_days_prior": 110,
        "dso_days": 50,
        "dso_days_prior": 58,
        "pe": 30,
        "pb": 2.2,
        "peg": 0.8,
    }
    result = score_snapshot(raw)
    assert _item_points(result) == [
        (4, 10),
        (3, 5),
        (2, 5),
        (4, 8),
        (3, 7),
        (10, 10),
        (2, 5),
        (4, 5),
        (1, 3),
        (1, 4),
        (2, 5),
        (2, 5),
        (5, 5),
        (0, 2),
        (2, 5),
        (3, 3),
        (1, 5),
        (1, 5),
    ]
    growth = result.dimensions[1].items
    assert [i.status for i in growth] == ["capped", "capped"]
    assert _penalties(result) == []
    assert (result.raw_earned, result.raw_available, result.total) == (50, 97, 52)
    assert (result.label.pre_gate, result.label.final) == ("HOLD", "HOLD")
    assert result.valuation.score == 5
