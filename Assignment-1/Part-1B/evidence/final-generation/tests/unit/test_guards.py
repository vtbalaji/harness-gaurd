"""Deterministic input guards (spec FR-016, FR-017, AC-3.1 … AC-3.4; research.md R-3)."""

from __future__ import annotations

import pytest

NBSP = " "
FFFD = "�"
BOM = "﻿"
READABLE = "Example Transformers Limited has received an order worth ₹1,250.50 crore."


def _check(text_or_bytes):
    from order_agent import guards

    raw = text_or_bytes if isinstance(text_or_bytes, bytes) else text_or_bytes.encode("utf-8")
    return guards.check(raw)


def _reason(text_or_bytes):
    return _check(text_or_bytes).rejection_reason


def test_ac_3_1_empty_input():
    """AC-3.1, FR-016 rule 1: b"" gives `empty`."""
    result = _check(b"")
    assert (result.ok, result.rejection_reason, result.text) == (False, "empty", None)


def test_fr016_invalid_utf8_is_garbled():
    """FR-016 note (rev 2), FR-017: undecodable bytes give `garbled`, before rules 2 and 3."""
    assert _reason(b"\xff\xfe\x00garbage") == "garbled"
    assert _reason(b" " * 30000 + b"\xff") == "garbled"


@pytest.mark.parametrize("text", [" \t\n ", NBSP, " \r\n" + NBSP + "  "])
def test_ac_3_2_whitespace_only(text):
    """AC-3.2, FR-016 rule 2: only whitespace (NBSP included) gives `whitespace_only`."""
    assert _reason(text) == "whitespace_only"


def _sized(n):
    base = "Order of ₹ crore from Indian Railways received today. "
    return (base * (n // len(base) + 1))[:n]


def test_ac_3_3_length_limit_counts_code_points_confirmed_p1_4():
    """AC-3.3, FR-017 (CONFIRMED P-1.4): 20,000 code points of multi-byte text are accepted and
    20,001 give `too_long`; the limit counts code points, not bytes."""
    from order_agent import guards

    accepted = _sized(20_000)
    assert len(accepted) == 20_000 and len(accepted.encode("utf-8")) > 20_000
    assert _check(accepted).ok is True
    assert _reason(_sized(20_001)) == "too_long"
    assert guards.MAX_CHARS == 20000


def test_fr016_rule_order_too_long_before_garbled():
    """FR-016: rules apply in order, so 20,001 garbled characters give `too_long`."""
    assert _reason(FFFD * 20_001) == "too_long"


@pytest.mark.parametrize("control", ["\x00", "\x07", "\x1b"])
def test_ac_3_4_control_characters_are_garbled(control):
    """AC-3.4, FR-017: Cc characters other than tab, LF and CR give `garbled`."""
    result = _check(READABLE + control)
    assert result.rejection_reason == "garbled" and "control" in result.detail


def test_fr017_tab_lf_cr_are_accepted():
    """FR-017: tab, line feed and carriage return are allowed."""
    assert _check("Line one\tcol\r\nLine two\nwith several words").ok is True


def test_fr017_recognised_ratio_boundary_85_percent():
    """FR-017: 100 non-whitespace characters with exactly 85 recognised pass; 84 fail."""
    passing = " ".join(["aaaaa"] * 17) + " " + FFFD * 15
    failing = " ".join(["aaaaa"] * 16 + ["aaaa"]) + " " + FFFD * 16
    assert sum(not c.isspace() for c in passing) == 100
    assert sum(not c.isspace() for c in failing) == 100
    assert _check(passing).ok is True
    result = _check(failing)
    assert result.rejection_reason == "garbled" and "0.84" in result.detail


def test_fr017_recognised_character_classes():
    """FR-017, R-3: So (box drawing), Cf (BOM) and Me (U+20DD) are unrecognised; Sc (₹), letters,
    digits, punctuation, Mn, Mc and the ASCII symbols + < = > | ~ ^ ` are recognised."""
    from order_agent import guards

    for ch in "═■░" + BOM + "⃝" + "":
        assert guards.is_recognised(ch) is False, repr(ch)
    for ch in "₹$aZ9٣.,;:-()[]{}\"'/+<=>|~^`" + "िे्" + "ह":
        assert guards.is_recognised(ch) is True, repr(ch)
    assert _check("Order value ₹ + < = > | ~ ^ ` noted here").ok is True
    assert _reason("abc def ghi " + "═" * 10) == "garbled"
    assert _reason(BOM + BOM + "abc def ghi") == "garbled"


def test_fr017_at_least_three_words_of_two_letters():
    """FR-017: exactly 3 words of 2+ letters pass, 2 fail, and single letters are not words."""
    assert _check("ab cd ef").ok is True
    result = _check("ab cd")
    assert result.rejection_reason == "garbled" and "words" in result.detail
    assert _reason("ab cd e f g h") == "garbled"
    assert _check("12 345 67, ab cd ef").ok is True


def test_fr017_combining_marks_are_word_internal_u2():
    """FR-017 (rev 2, U2): Mn/Mc marks are recognised and word-internal; a Hindi sentence passes;
    "किया" is one word; one letter plus marks is not a word; Me is unrecognised."""
    from order_agent import guards

    assert _check("कंपनी को ऑर्डर मिला है").ok is True
    assert guards.count_words("किया") == 1
    assert guards.count_words("कि") == 0
    assert guards.count_words("कंपनी को ऑर्डर मिला है") == 3
    assert guards.count_words("ab-cd ef") == 3
    assert guards.is_recognised("⃝") is False


def test_fr017_readable_text_with_pdf_noise_passes():
    """FR-017: readable text with a few stray symbols from PDF conversion is accepted."""
    noisy = READABLE + " ■ " + FFFD + " Page 1 of 2 ░"
    assert _check(noisy).ok is True


def test_fr017_detail_and_constants():
    """FR-016, FR-017: detail explains the rule; the constants are the spec's."""
    from order_agent import guards

    assert guards.MAX_CHARS == 20000
    assert guards.RECOGNISED_MIN_RATIO == 0.85
    assert guards.MIN_WORDS == 3
    ok = _check(READABLE)
    assert (ok.ok, ok.rejection_reason, ok.text) == (True, None, READABLE) and ok.detail
    for raw in (b"", b"  ", ("a b " * 6000).encode(), b"\xff", (FFFD * 50).encode()):
        result = _check(raw)
        assert result.ok is False and result.detail and result.text is None


def test_fr017_no_bom_stripping_or_normalisation():
    """FR-017, R-3: the input is measured as received; the text is returned unchanged."""
    text = "Order received from Indian Railways today\r\n"
    assert _check(text).text == text
