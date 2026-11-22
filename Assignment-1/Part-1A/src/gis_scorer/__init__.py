"""GIS Scorer: deterministic General Investor Score for one company snapshot."""

from gis_scorer.result import ScoreResult
from gis_scorer.scoring import score_snapshot
from gis_scorer.snapshot import FieldError, SnapshotValidationError

__version__ = "0.1.0"

__all__ = [
    "FieldError",
    "ScoreResult",
    "SnapshotValidationError",
    "__version__",
    "score_snapshot",
]
