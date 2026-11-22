"""The guards on the real dataset (spec FR-016, FR-017 rev 2, U2; research.md R-3). Reads the
dataset only; no model is involved."""

from __future__ import annotations

import base64
import json

import pytest
from conftest import DATASET_PATH


def _expand(spec) -> bytes:
    """Expand an input exactly as run_eval does (text, base64, padded)."""
    if spec["kind"] == "text":
        return spec["text"].encode("utf-8")
    if spec["kind"] == "base64":
        return base64.b64decode(spec["data"], validate=True)
    text = spec["text"]
    while len(text) < spec["length"]:
        text += spec["filler"]
    return text[: spec["length"]].encode("utf-8")


CASES = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize(
    "case", [c for c in CASES if not c["id"].startswith("X")], ids=lambda c: c["id"]
)
def test_fr016_fr017_every_non_x_case_passes_the_guards(case):
    """FR-016, FR-017 (rev 2, U2): every case that is not an X-case passes the guards, including
    J02 with its Hindi instruction and every case with ₹, NBSP or other non-ASCII text."""
    from order_agent import guards

    result = guards.check(_expand(case["input"]))
    assert result.ok is True and result.rejection_reason is None, (case["id"], result.detail)


def test_fr017_x05_boundary_passes_confirmed_p1_4():
    """FR-017 (CONFIRMED P-1.4): X05, exactly 20,000 code points, passes the guards."""
    from order_agent import guards

    case = next(c for c in CASES if c["id"] == "X05")
    result = guards.check(_expand(case["input"]))
    assert result.ok is True, result.detail
    assert len(result.text) == 20_000


@pytest.mark.parametrize("case_id", ["X01", "X02", "X03", "X04"])
def test_fr016_x01_to_x04_give_their_ground_truth_reason(case_id):
    """FR-016, FR-017 (X04: CONFIRMED P-1.4): X01–X04 give exactly their ground-truth
    rejection_reason."""
    from order_agent import guards

    case = next(c for c in CASES if c["id"] == case_id)
    result = guards.check(_expand(case["input"]))
    expected = case["ground_truth"]["rejection_reason"]
    assert result.ok is False and result.rejection_reason == expected, (case_id, result.detail)
