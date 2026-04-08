"""RIS evaluation gate -- core type definitions.

Phase 2 additions (weighted composite gate):
- ScoringResult.composite_score: weighted composite (rel*0.30 + nov*0.25 + act*0.25 + cred*0.20)
- ScoringResult.simple_sum_score: diagnostic-only sum of all 4 dimensions (same as total)
- ScoringResult.priority_tier: priority tier string (priority_1..priority_4)
- ScoringResult.reject_reason: set to "scorer_failure" or "floor_failure" when applicable
- ScoringResult.gate: now uses weighted composite + per-dimension floor + priority tier
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalDocument:
    """A document submitted for evaluation through the RIS quality gate."""
    doc_id: str
    title: str
    author: str
    source_type: str
    source_url: str
    source_publish_date: Optional[str]
    body: str
    metadata: dict = field(default_factory=dict)


@dataclass
class HardStopResult:
    """Result of hard-stop pre-screening before LLM scoring."""
    passed: bool
    reason: Optional[str] = None
    stop_type: Optional[str] = None


@dataclass
class ScoringResult:
    """4-dimension scoring result from the LLM evaluator.

    Phase 2 gate contract:
    - gate is determined by weighted composite score + per-dimension floor + priority tier.
    - simple_sum_score (= total) is retained as a diagnostic field only.
    - Any scorer failure (reject_reason="scorer_failure") immediately returns REJECT.
    - Floor failures (reject_reason will be set by gate property) return REJECT
      unless the tier is floor-waived (priority_1).
    """
    relevance: int
    novelty: int
    actionability: int
    credibility: int
    total: int
    epistemic_type: str
    summary: str
    key_findings: list
    eval_model: str

    # Phase 2 fields
    composite_score: float = 0.0
    priority_tier: str = "priority_3"
    reject_reason: Optional[str] = None

    @property
    def simple_sum_score(self) -> int:
        """Diagnostic alias for total score. Never drives gate decisions."""
        return self.total

    @property
    def gate(self) -> str:
        """Gate decision: ACCEPT | REVIEW | REJECT.

        Phase 2 logic (replaces simple sum threshold):
        1. scorer_failure -> always REJECT
        2. Floor check (skipped for floor-waived tiers like priority_1):
           - relevance < floor -> REJECT
           - credibility < floor -> REJECT
        3. Composite score vs priority threshold:
           - composite >= threshold -> ACCEPT
           - else -> REVIEW
        """
        # Immediate reject on scorer failure
        if self.reject_reason == "scorer_failure":
            return "REJECT"

        # Import config lazily to avoid circular imports and allow test isolation
        from packages.research.evaluation.config import get_eval_config
        cfg = get_eval_config()

        # Floor check (skip for floor-waived tiers)
        if self.priority_tier not in cfg.floor_waive_tiers:
            for dim, floor_val in cfg.floors.items():
                if getattr(self, dim, 0) < floor_val:
                    return "REJECT"

        # Threshold check
        threshold = cfg.thresholds.get(self.priority_tier, cfg.thresholds.get("priority_3", 3.2))
        if self.composite_score >= threshold:
            return "ACCEPT"
        return "REVIEW"


@dataclass
class GateDecision:
    """Final gate decision for a document."""
    gate: str  # ACCEPT | REVIEW | REJECT
    scores: Optional[ScoringResult]
    hard_stop: Optional[HardStopResult]
    doc_id: str
    timestamp: str


# ---------------------------------------------------------------------------
# Source-family mappings
# ---------------------------------------------------------------------------

SOURCE_FAMILIES: dict[str, str] = {
    "arxiv": "academic",
    "ssrn": "academic",
    "book": "academic",
    "reddit": "forum_social",
    "twitter": "forum_social",
    "youtube": "forum_social",
    "github": "github",
    "blog": "blog",
    "news": "news",
    "dossier": "dossier_report",
    "manual": "manual",
    # Internal document types -- map to book_foundational (null half-life, timeless)
    "reference_doc": "book_foundational",
    "roadmap": "book_foundational",
}

# SOURCE_FAMILY_OFFSETS is the designated extension point for data-driven
# per-family score adjustments. It is intentionally empty until calibration
# artifacts accumulate enough signal to justify non-zero offsets.
#
# Expected shape when populated:
#   {"academic": {"credibility": 1}, "forum_social": {"credibility": -1}}
#
# Do NOT populate this by hand -- derive offsets from eval_artifacts.jsonl
# once >= 50 entries across >= 3 families are available.
SOURCE_FAMILY_OFFSETS: dict[str, dict[str, int]] = {}

SOURCE_FAMILY_GUIDANCE: dict[str, str] = {
    "academic": (
        "Academic/peer-reviewed source. Credibility floor is 3 unless methodology is "
        "clearly flawed. Weight empirical findings heavily."
    ),
    "book_foundational": (
        "Internal architecture reference or foundational strategy document. Null freshness "
        "decay (timeless). Credibility is 4-5 by default. Score novelty based on whether "
        "the specific finding or design decision is already captured in the knowledge store."
    ),
    "forum_social": (
        "Community source. Credibility ceiling is 3 unless the author provides verifiable "
        "data or on-chain evidence. Look past conversational filler for core insight."
    ),
    "github": (
        "Open-source practitioner source. Credibility 3-4 if repo has evidence of real "
        "usage. Score actionability high if code is directly adaptable."
    ),
    "blog": (
        "Blog/essay source. Credibility depends on author track record and evidence "
        "quality. Score novelty relative to existing knowledge base."
    ),
    "dossier_report": (
        "Internal analysis report. High relevance by default. Score novelty based on "
        "whether findings are already captured."
    ),
    "manual": (
        "Manually submitted content. Apply standard rubric without source-type bias."
    ),
    "news": (
        "News article. Credibility depends on outlet reputation. Actionability is usually "
        "low unless it contains market-moving data."
    ),
}
