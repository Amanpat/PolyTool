"""RIS evaluation gate — document quality scoring and hard-stop filtering.

Phase 3 additions: per-family feature extraction, near-duplicate detection,
structured eval artifact persistence, and enhanced calibration analytics.
"""

from packages.research.evaluation.evaluator import DocumentEvaluator, evaluate_document
from packages.research.evaluation.hard_stops import check_hard_stops
from packages.research.evaluation.types import (
    EvalDocument,
    GateDecision,
    HardStopResult,
    ScoringResult,
)
from packages.research.evaluation.feature_extraction import extract_features, FamilyFeatures
from packages.research.evaluation.dedup import (
    check_near_duplicate,
    NearDuplicateResult,
    compute_content_hash,
    compute_shingles,
    jaccard_similarity,
)
from packages.research.evaluation.artifacts import (
    EvalArtifact,
    persist_eval_artifact,
    load_eval_artifacts,
)

__all__ = [
    # Core evaluator
    "DocumentEvaluator",
    "evaluate_document",
    # Types
    "EvalDocument",
    "GateDecision",
    "HardStopResult",
    "ScoringResult",
    # Hard stops
    "check_hard_stops",
    # Feature extraction
    "extract_features",
    "FamilyFeatures",
    # Dedup
    "check_near_duplicate",
    "NearDuplicateResult",
    "compute_content_hash",
    "compute_shingles",
    "jaccard_similarity",
    # Artifacts
    "EvalArtifact",
    "persist_eval_artifact",
    "load_eval_artifacts",
]
