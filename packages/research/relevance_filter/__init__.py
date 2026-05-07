"""Relevance filter for RIS pre-fetch candidate scoring (lexical + SVM)."""

from packages.research.relevance_filter.scorer import (
    CandidateInput,
    FilterConfig,
    FilterDecision,
    RelevanceScorer,
    load_filter_config,
)
from packages.research.relevance_filter.queue_store import (
    ReviewQueueStore,
    LabelStore,
    candidate_id_from_url,
)
from packages.research.relevance_filter.svm_scorer import (
    SvmModelLoadError,
    SvmRuntimeConfig,
    SvmRelevanceScorer,
)
from packages.research.relevance_filter.svm_training import SvmMissingDepsError

__all__ = [
    "CandidateInput",
    "FilterConfig",
    "FilterDecision",
    "RelevanceScorer",
    "load_filter_config",
    "ReviewQueueStore",
    "LabelStore",
    "candidate_id_from_url",
    "SvmRuntimeConfig",
    "SvmRelevanceScorer",
    "SvmModelLoadError",
    "SvmMissingDepsError",
]
