"""Shared snapshot builders for the GIS Scorer tests.

No production code is imported here, so every fixture is usable before the
implementation exists (test-first, Constitution III).
"""

import copy

import pytest

# quickstart.md `full_max.json`: every item at its maximum (97/97 available),
# valuation 10, no Margin Compression.
_FULL_MAX_VALUES = {
    "piotroski": 9,
    "altman_z": 3.5,
    "beneish_m": -2.5,
    "revenue_12m": 130,
    "revenue_prior_12m": 100,
    "ebitda_12m": 125,
    "ebitda_prior_12m": 100,
    "net_profit_12m": 125,
    "net_profit_prior_12m": 100,
    "equity": 120,
    "equity_prior": 100,
    "debt_to_equity": 0.3,
    "debt_to_equity_prior": 0.9,
    "current_ratio": 2.5,
    "ocf_to_net_profit": 1.6,
    "net_profit_margin": 16,
    "operating_margin": 21,
    "net_profit_margin_year_ago": 15,
    "operating_margin_year_ago": 20,
    "previous_net_profit_margin": -2,
    "roe": 18,
    "roce": 20,
    "recent_net_profit_margins": [16, 15, 14, 13],
    "ccc_days": 40,
    "ccc_days_prior": 400,
    "dso_days": 30,
    "dso_days_prior": 75,
    "pe": 11,
    "pb": 1.4,
    "peg": 0.9,
}


@pytest.fixture
def full_max_values():
    """A fresh copy of the quickstart.md full_max.json values."""
    return copy.deepcopy(_FULL_MAX_VALUES)


@pytest.fixture
def max_snapshot():
    """Factory: max_snapshot(*drop, **overrides) -> a fresh full_max dict.

    Keys named in `drop` are removed, then `overrides` are applied.
    """

    def build(*drop, **overrides):
        values = copy.deepcopy(_FULL_MAX_VALUES)
        for key in drop:
            del values[key]
        values.update(overrides)
        return values

    return build


@pytest.fixture
def empty_snapshot():
    """A snapshot with no inputs at all."""
    return {}
