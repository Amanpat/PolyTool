"""RIS v1 evaluation gate — core type definitions."""

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
    """4-dimension scoring result from the LLM evaluator."""
    relevance: int
    novelty: int
    actionability: int
    credibility: int
    total: int
    epistemic_type: str
    summary: str
    key_findings: list
    eval_model: str

    @property
    def gate(self) -> str:
        """Gate decision derived from total score.

        GREEN (ACCEPT): >= 12/20
        YELLOW (REVIEW): 8-11/20
        RED (REJECT): < 8/20
        """
        if self.total >= 12:
            return "ACCEPT"
        elif self.total >= 8:
            return "REVIEW"
        else:
            return "REJECT"


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
}

SOURCE_FAMILY_GUIDANCE: dict[str, str] = {
    "academic": (
        "Academic/peer-reviewed source. Credibility floor is 3 unless methodology is "
        "clearly flawed. Weight empirical findings heavily."
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
