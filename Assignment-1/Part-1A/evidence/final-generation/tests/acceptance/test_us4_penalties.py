"""User Story 4 - Penalties for a deteriorating business (US4-AS1 ... US4-AS4)."""

from gis_scorer import score_snapshot


def _penalties(result):
    return [(p.name, p.earned) for p in result.dimensions[-1].items]


def _item(result, name):
    return next(i for d in result.dimensions for i in d.items if i.name == name)


def test_us4_as1_revenue_decline_is_penalised(max_snapshot):
    """US4-AS1: revenue growth -2% -> 'Revenue Declining' -5 and growth 0 of 10 (FR-016/040)."""
    result = score_snapshot(max_snapshot(revenue_12m=98, revenue_prior_12m=100))
    assert _item(result, "Revenue Growth").value == -2.0
    assert ("Revenue Declining", -5) in _penalties(result)
    revenue = _item(result, "Revenue Growth")
    assert (revenue.earned, revenue.available) == (0, 10)


def test_us4_as2_two_sided_margin_compression(max_snapshot):
    """US4-AS2: NPM 8 vs 9 and OPM 12 vs 13 -> 'Margin Compression' -3 (FR-043)."""
    raw = max_snapshot(
        net_profit_margin=8,
        net_profit_margin_year_ago=9,
        operating_margin=12,
        operating_margin_year_ago=13,
    )
    assert ("Margin Compression", -3) in _penalties(score_snapshot(raw))


def test_us4_as3_one_sided_margin_drop_is_not_compression(max_snapshot):
    """US4-AS3: only the net margin below its year-ago value -> no Margin Compression (FR-043)."""
    raw = max_snapshot(
        net_profit_margin=8,
        net_profit_margin_year_ago=9,
        operating_margin=14,
        operating_margin_year_ago=13,
    )
    assert "Margin Compression" not in [name for name, _ in _penalties(score_snapshot(raw))]


def test_us4_as4_penalties_below_zero_give_total_zero():
    """US4-AS4: penalties push raw points to -15 of 25 -> total 0, never negative (FR-050).

    Revenue, EBITDA and net profit all fall 10% (FR-040, FR-041, FR-042): each growth item
    earns 0 and each decline costs 5, so raw is -15 of 10 + 8 + 7 = 25.
    """
    raw = {
        "revenue_12m": 90,
        "revenue_prior_12m": 100,
        "ebitda_12m": 90,
        "ebitda_prior_12m": 100,
        "net_profit_12m": 90,
        "net_profit_prior_12m": 100,
    }
    result = score_snapshot(raw)
    assert (result.raw_earned, result.raw_available) == (-15, 25)
    assert result.total == 0
