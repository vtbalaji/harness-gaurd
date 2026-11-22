"""Model-output parser: the documented clean-up rules PC-1 … PC-3 and nothing else.

Spec FR-019; research.md R-8. Each rule that changes the text is logged. There is no other
repair: no trailing-comma fixes, no cutting JSON out of prose, no completing truncated output and
no case changes. A failure raises `ParseError(rule, message)`.
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(?P<body>.*?)\r?\n?```\Z", re.DOTALL)


class ParseError(Exception):
    """The raw model text could not be turned into a JSON object."""

    def __init__(self, rule: str, message: str, log: list[dict] | None = None):
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message
        self.log = list(log or [])


def _reject_constant(name: str):
    raise ValueError(f"{name} is not valid JSON")


def _object_without_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def parse(raw_text: str) -> tuple[dict, list[dict]]:
    """Apply PC-1, PC-2 and PC-3 in order. Returns `(object, log)`."""
    log: list[dict] = []
    text = raw_text

    # PC-1: strip leading and trailing whitespace.
    stripped = text.strip()
    if stripped != text:
        log.append({"rule": "PC-1", "detail": "removed surrounding whitespace"})
        text = stripped

    # PC-2: remove one Markdown code fence that wraps the whole text.
    fence = _FENCE.fullmatch(text)
    if fence:
        body = fence["body"]
        if "```" in body:
            raise ParseError(
                "PC-2", "more than one code fence; refusing to guess which to use", log
            )
        log.append({"rule": "PC-2", "detail": "removed a whole-text Markdown code fence"})
        text = body

    # PC-3: the text must be exactly one JSON object.
    try:
        obj = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except ValueError as exc:
        raise ParseError("PC-3", f"not valid JSON: {exc}", log) from None
    if not isinstance(obj, dict):
        kind = type(obj).__name__
        raise ParseError("PC-3", f"top-level JSON value is {kind}, not an object", log)
    return obj, log
