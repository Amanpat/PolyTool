"""RIS v1 evaluation gate — document quality scoring and hard-stop filtering."""

from packages.research.evaluation.evaluator import DocumentEvaluator, evaluate_document
from packages.research.evaluation.hard_stops import check_hard_stops
from packages.research.evaluation.types import (
    EvalDocument,
    GateDecision,
    HardStopResult,
    ScoringResult,
)

__all__ = [
    "DocumentEvaluator",
    "evaluate_document",
    "EvalDocument",
    "GateDecision",
    "HardStopResult",
    "ScoringResult",
    "check_hard_stops",
]
