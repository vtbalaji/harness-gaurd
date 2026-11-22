"""FR-001, FR-002: strict snapshot validation, rules V1-V9 (data-model.md §1, research R-05)."""

import math

import pytest

from gis_scorer import FieldError, SnapshotValidationError, score_snapshot
from gis_scorer.snapshot import validate


def _errors(raw):
    with pytest.raises(SnapshotValidationError) as info:
        validate(raw)
    return [(e.field, e.message) for e in info.value.errors]


# --- V1 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [pytest.param([], id="fr002_v1_list"), pytest.param("x", id="fr002_v1_string")],
)
def test_fr002_v1_non_mapping_is_rejected(raw):
    """FR-002 V1: a snapshot that is not a mapping is rejected as <snapshot>."""
    assert _errors(raw) == [("<snapshot>", "must be an object with string keys")]


def test_fr002_v1_non_string_key_is_rejected():
    """FR-002 V1: a non-str key is rejected as <snapshot>; string keys are still checked."""
    assert _errors({1: 2, "roe": "x"}) == [
        ("<snapshot>", "must be an object with string keys"),
        ("roe", "must be a number"),
    ]


# --- V2 ---------------------------------------------------------------------------------------


def test_fr002_v2_unknown_fields_sorted_by_name():
    """FR-002 V2: unknown fields are each reported as 'unknown field', sorted by name."""
    assert _errors({"zzz": 1, "aaa": 2, "roe": 5}) == [
        ("aaa", "unknown field"),
        ("zzz", "unknown field"),
    ]


# --- V3 / V4 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("12", id="fr002_v3_string"),
        pytest.param({}, id="fr002_v3_object"),
        pytest.param([1], id="fr002_v3_list_in_scalar_field"),
    ],
)
def test_fr002_v3_non_number_is_rejected(value):
    """FR-002 V3: a string, object or list in a scalar field -> 'must be a number'."""
    assert _errors({"roe": value}) == [("roe", "must be a number")]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(math.nan, id="fr002_v4_nan"),
        pytest.param(math.inf, id="fr002_v4_pos_inf"),
        pytest.param(-math.inf, id="fr002_v4_neg_inf"),
    ],
)
def test_fr002_v4_non_finite_is_rejected(value):
    """FR-002 V4: NaN and +/-infinity -> 'must be finite'."""
    assert _errors({"altman_z": value}) == [("altman_z", "must be finite")]


def test_fr002_v4_integer_beyond_float_range_is_rejected():
    """FR-002 V4: an integer too large for a float cannot be scored -> 'must be finite'."""
    assert _errors({"revenue_12m": 10**400}) == [("revenue_12m", "must be finite")]


# --- V5 Piotroski -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(10, id="fr002_v5_above_9"),
        pytest.param(-1, id="fr002_v5_below_0"),
        pytest.param(6.5, id="fr002_v5_not_integral"),
    ],
)
def test_fr002_v5_piotroski_out_of_range(value):
    """FR-002 V5: Piotroski must be an integer from 0 to 9."""
    assert _errors({"piotroski": value}) == [("piotroski", "must be an integer from 0 to 9")]


@pytest.mark.parametrize("value", [0, 9])
def test_fr002_v5_piotroski_range_ends_accepted(value):
    """FR-002 V5: Piotroski 0 and 9 are inside the range."""
    assert validate({"piotroski": value}).piotroski == value


def test_fr002_r02_integral_float_piotroski_is_normalised_to_int():
    """FR-002, R-02: Piotroski 6.0 is accepted and reported as the int 6."""
    snap = validate({"piotroski": 6.0})
    assert snap.piotroski == 6
    assert type(snap.piotroski) is int
    item = score_snapshot({"piotroski": 6.0}).dimensions[0].items[0]
    assert item.value == 6
    assert type(item.value) is int


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("roe", True, id="fr002_r02_bool_true_scalar"),
        pytest.param("roe", False, id="fr002_r02_bool_false_scalar"),
        pytest.param("piotroski", True, id="fr002_r02_bool_piotroski"),
    ],
)
def test_fr002_r02_booleans_are_not_numbers(field, value):
    """FR-002, R-02: booleans are rejected as 'must be a number' (also in piotroski)."""
    assert _errors({field: value}) == [(field, "must be a number")]


def test_fr002_r02_boolean_list_element_is_not_a_number():
    """FR-002, R-02: a boolean inside recent_net_profit_margins is 'must be a number'."""
    assert _errors({"recent_net_profit_margins": [1, False]}) == [
        ("recent_net_profit_margins[1]", "must be a number")
    ]


# --- V6 current ratio -------------------------------------------------------------------------


def test_fr002_v6_negative_current_ratio_rejected():
    """FR-002 V6: current_ratio -0.01 -> 'must be >= 0'."""
    assert _errors({"current_ratio": -0.01}) == [("current_ratio", "must be >= 0")]


def test_fr002_v6_zero_current_ratio_accepted():
    """FR-002 V6, FR-001: current_ratio 0 is a real value and accepted."""
    assert validate({"current_ratio": 0}).current_ratio == 0


# --- V7 / V8 / V9 quarterly margins -----------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [pytest.param(5, id="fr002_v7_number"), pytest.param("abc", id="fr002_v7_string")],
)
def test_fr002_v7_list_field_must_be_a_list(value):
    """FR-002 V7: recent_net_profit_margins that is not a list -> 'must be a list of numbers'."""
    assert _errors({"recent_net_profit_margins": value}) == [
        ("recent_net_profit_margins", "must be a list of numbers")
    ]


def test_fr002_v8_list_longer_than_8_rejected():
    """FR-002 V8: nine quarterly margins -> 'must have at most 8 elements'."""
    assert _errors({"recent_net_profit_margins": [1] * 9}) == [
        ("recent_net_profit_margins", "must have at most 8 elements")
    ]


def test_fr002_v8_eight_elements_accepted():
    """FR-002 V8: exactly eight quarterly margins are accepted (as a tuple)."""
    assert validate({"recent_net_profit_margins": [1] * 8}).recent_net_profit_margins == (1,) * 8


@pytest.mark.parametrize(
    ("element", "message"),
    [
        pytest.param("a", "must be a number", id="fr002_v9_string_element"),
        pytest.param(math.nan, "must be finite", id="fr002_v9_nan_element"),
    ],
)
def test_fr002_v9_bad_element_named_by_index(element, message):
    """FR-002 V9: a bad element is reported as recent_net_profit_margins[i]."""
    assert _errors({"recent_net_profit_margins": [1, 2, element]}) == [
        ("recent_net_profit_margins[2]", message)
    ]


def test_fr002_v8_v9_field_error_comes_before_element_errors():
    """FR-002 V8, V9: the field's own error comes first, then element errors in index order."""
    margins = [1, "a", 3, math.inf, 5, 6, 7, 8, 9]
    assert _errors({"recent_net_profit_margins": margins}) == [
        ("recent_net_profit_margins", "must have at most 8 elements"),
        ("recent_net_profit_margins[1]", "must be a number"),
        ("recent_net_profit_margins[3]", "must be finite"),
    ]


def test_fr001_r01_null_list_elements_are_kept():
    """FR-001, R-01: a null element in recent_net_profit_margins is kept as a missing quarter."""
    assert validate({"recent_net_profit_margins": [None, 5]}).recent_net_profit_margins == (
        None,
        5,
    )


def test_fr001_tuple_list_field_accepted():
    """FR-001: a tuple is accepted for the quarterly-margin list."""
    assert validate({"recent_net_profit_margins": (1, 2)}).recent_net_profit_margins == (1, 2)


# --- Collection, ordering and the error object ------------------------------------------------


def test_fr002_all_problems_collected_in_fixed_order():
    """FR-002: every problem is in one error: V1, then unknown keys, then schema order."""
    raw = {
        2: 0,
        "zzz": 1,
        "peg": "x",
        "recent_net_profit_margins": [1, "b"],
        "current_ratio": -1,
        "piotroski": 6.5,
        "aaa": 0,
        "roce": math.nan,
        "ccc_days": True,
    }
    assert _errors(raw) == [
        ("<snapshot>", "must be an object with string keys"),
        ("aaa", "unknown field"),
        ("zzz", "unknown field"),
        ("piotroski", "must be an integer from 0 to 9"),
        ("current_ratio", "must be >= 0"),
        ("roce", "must be finite"),
        ("recent_net_profit_margins[1]", "must be a number"),
        ("ccc_days", "must be a number"),
        ("peg", "must be a number"),
    ]


def test_fr002_error_text_is_one_line_per_problem():
    """FR-002: str(error) is one 'field: message' line per error."""
    with pytest.raises(SnapshotValidationError) as info:
        validate({"zzz": 1, "piotroski": 11})
    assert str(info.value) == "zzz: unknown field\npiotroski: must be an integer from 0 to 9"


def test_fr002_error_is_a_value_error_with_field_errors():
    """FR-002: SnapshotValidationError is a ValueError whose .errors is a non-empty tuple."""
    with pytest.raises(ValueError) as info:
        validate({"roe": "x"})
    error = info.value
    assert isinstance(error, SnapshotValidationError)
    assert error.errors == (FieldError(field="roe", message="must be a number"),)


def test_fr002_error_requires_at_least_one_field_error():
    """FR-002 (data-model.md §8): a SnapshotValidationError is never empty."""
    with pytest.raises(ValueError, match="at least one"):
        SnapshotValidationError([])


def test_fr002_score_snapshot_raises_and_returns_nothing():
    """FR-002: score_snapshot refuses an invalid snapshot; no partial result is produced."""
    outcome = []
    with pytest.raises(SnapshotValidationError):
        outcome.append(score_snapshot({"piotroski": 11, "roe": 18}))
    assert outcome == []


def test_fr001_r01_explicit_null_equals_absent():
    """FR-001, R-01: an explicit None is the same as an absent field."""
    assert validate({"roe": None}) == validate({})
    assert score_snapshot({"roe": None}) == score_snapshot({})


def test_fr001_input_values_echoed_as_given():
    """FR-001: valid values are kept exactly, including zero and negatives."""
    snap = validate({"altman_z": -1.5, "pe": 0, "roe": 12.25})
    assert (snap.altman_z, snap.pe, snap.roe) == (-1.5, 0, 12.25)
