"""SC-005: 10,000 snapshots are scored in under 5 seconds (timing lives only in this test)."""

import time

from gis_scorer import score_snapshot


def test_sc005_10000_snapshots_under_5_seconds(max_snapshot):
    """SC-005 (FR-003 inputs varied deterministically): 10,000 scores in < 5 s."""
    snapshots = []
    for i in range(10_000):
        snapshots.append(
            max_snapshot(
                piotroski=i % 10,
                revenue_12m=50 + (i % 400),
                roe=(i % 30) - 5,
                current_ratio=(i % 40) / 10,
                pe=(i % 70) - 10,
            )
        )
    start = time.perf_counter()
    totals = [score_snapshot(s).total for s in snapshots]
    elapsed = time.perf_counter() - start
    assert len(totals) == 10_000
    assert all(0 <= t <= 100 for t in totals)
    assert elapsed < 5.0, f"10,000 scores took {elapsed:.2f} s"
