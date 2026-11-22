"""Deterministic input guards, applied before any model call (spec FR-016, FR-017; R-3).

Rules in order; the first that fails decides the result:

1. zero bytes → `empty`;
2. not strict UTF-8 → `garbled` (rules 3–5 are defined on characters, FR-016 note rev 2);
3. only whitespace (Python's Unicode whitespace, NBSP included) → `whitespace_only`;
4. more than 20,000 code points → `too_long` (CONFIRMED P-1.4; exactly 20,000 is accepted);
5. `garbled` if (a) a Cc character other than tab, LF or CR is present, (b) fewer than 85% of
   the non-whitespace characters are recognised, or (c) there are fewer than 3 words.

Recognised: Unicode letters (L*), combining marks Mn and Mc (rev 2), numbers (N*),
punctuation (P*), currency symbols (Sc), and the ASCII symbols + < = > | ~ ^ `. A word is a
maximal run of L*/Mn/Mc characters with at least two L* characters (combining marks never split
a word and do not count as letters). The input is measured as received: no BOM stripping or
normalisation.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal

MAX_CHARS = 20000
RECOGNISED_MIN_RATIO = 0.85
MIN_WORDS = 3
_ALLOWED_CONTROLS = frozenset("\t\n\r")
_ASCII_SYMBOLS = frozenset("+<=>|~^`")


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    text: str | None
    rejection_reason: str | None
    detail: str


def is_recognised(ch: str) -> bool:
    """R-3 rule 5(b): L*, Mn, Mc, N*, P*, Sc or one of the listed ASCII symbols."""
    category = unicodedata.category(ch)
    return category[0] in ("L", "N", "P") or category in ("Mn", "Mc", "Sc") or ch in _ASCII_SYMBOLS


def count_words(text: str) -> int:
    """R-3 rule 5(c): maximal runs of L*/Mn/Mc with at least two L* characters."""
    words = letters = 0
    for ch in text + " ":
        category = unicodedata.category(ch)
        if category[0] == "L":
            letters += 1
        elif category in ("Mn", "Mc"):
            continue  # word-internal: never ends a word, not a letter
        else:
            if letters >= 2:
                words += 1
            letters = 0
    return words


def _reject(reason: str, detail: str) -> GuardResult:
    return GuardResult(False, None, reason, detail)


def check(raw: bytes) -> GuardResult:
    """Apply FR-016 rules 1–4 and the FR-017 garbled rules, in order."""
    if len(raw) == 0:
        return _reject("empty", "rule 1: the input has zero bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _reject("garbled", f"rule 2: not valid UTF-8 ({exc.reason} at byte {exc.start})")
    if text.isspace():
        return _reject("whitespace_only", "rule 3: the input contains only whitespace")
    if len(text) > MAX_CHARS:
        return _reject("too_long", f"rule 4: {len(text)} code points > {MAX_CHARS}")
    controls = sorted(
        {
            f"U+{ord(ch):04X}"
            for ch in text
            if unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROLS
        }
    )
    if controls:
        return _reject("garbled", f"rule 5a: control characters {', '.join(controls)}")
    visible = [ch for ch in text if not ch.isspace()]
    recognised = sum(1 for ch in visible if is_recognised(ch))
    # Exact comparison: 85 of 100 is exactly the threshold and passes (0.85 * 100 is not 85.0
    # in binary floating point).
    if recognised < Decimal(str(RECOGNISED_MIN_RATIO)) * len(visible):
        ratio = recognised / len(visible)
        return _reject("garbled", f"rule 5b: recognised ratio {ratio:.2f} < {RECOGNISED_MIN_RATIO}")
    words = count_words(text)
    if words < MIN_WORDS:
        return _reject("garbled", f"rule 5c: {words} words < {MIN_WORDS}")
    return GuardResult(True, text, None, f"accepted: {len(text)} code points, {words} words")
