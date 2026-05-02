"""Cold-start lexical relevance filter for RIS pre-fetch candidate scoring.

Scores paper metadata (title + abstract) against domain-specific seed terms
without ML dependencies. Produces allow/review/reject decisions.
Version: v1 (cold-start lexical)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CandidateInput:
    title: str
    abstract: str = ""
    source_url: str = ""
    fields_of_study: list = field(default_factory=list)
    source_id: str = ""


@dataclass
class FilterDecision:
    decision: str        # "allow" | "review" | "reject"
    score: float         # sigmoid-normalized [0.0, 1.0]
    raw_score: float     # before normalization
    reason_codes: list   # e.g. ["strong_positive:prediction market", "strong_negative:hastelloy"]
    matched_terms: dict  # {"strong_positive": [...], "positive": [...], "strong_negative": [...], "negative": [...]}
    candidate_title: str = ""
    source_id: str = ""
    # Audit fields (populated by RelevanceScorer.score())
    allow_threshold: float = 0.0
    review_threshold: float = 0.0
    config_version: str = ""
    input_fields_used: list = field(default_factory=list)


@dataclass
class FilterConfig:
    version: str
    strong_positive_terms: list   # already lowercased
    positive_terms: list          # already lowercased
    strong_negative_terms: list   # already lowercased
    negative_terms: list          # already lowercased
    strong_positive_weight: float = 2.0
    positive_weight: float = 1.0
    strong_negative_weight: float = -3.0
    negative_weight: float = -1.5
    allow_threshold: float = 0.55
    review_threshold: float = 0.35


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class RelevanceScorer:
    """Lexical relevance scorer for paper metadata."""

    def __init__(self, config: FilterConfig) -> None:
        self._config = config

    def score(self, candidate: CandidateInput) -> FilterDecision:
        """Score a candidate and return a FilterDecision.

        Parameters
        ----------
        candidate:
            CandidateInput with title, abstract, and optional metadata.

        Returns
        -------
        FilterDecision
        """
        cfg = self._config
        text = (candidate.title + " " + candidate.abstract).lower()

        # Find matching terms per category (deduplicated per category)
        categories = [
            ("strong_positive", cfg.strong_positive_terms, cfg.strong_positive_weight),
            ("positive", cfg.positive_terms, cfg.positive_weight),
            ("strong_negative", cfg.strong_negative_terms, cfg.strong_negative_weight),
            ("negative", cfg.negative_terms, cfg.negative_weight),
        ]

        matched: Dict[str, List[str]] = {
            "strong_positive": [],
            "positive": [],
            "strong_negative": [],
            "negative": [],
        }

        raw_score = 0.0

        for cat_name, terms, weight in categories:
            seen: List[str] = []
            for term in terms:
                if term in text and term not in seen:
                    seen.append(term)
            matched[cat_name] = seen
            raw_score += len(seen) * weight

        # Sigmoid normalization
        score = 1.0 / (1.0 + math.exp(-raw_score))
        score = max(0.0, min(1.0, score))

        # Decision
        if score >= cfg.allow_threshold:
            decision = "allow"
        elif score >= cfg.review_threshold:
            decision = "review"
        else:
            decision = "reject"

        # Reason codes
        reason_codes: List[str] = []
        for cat_name, terms_list in matched.items():
            for term in terms_list:
                reason_codes.append(f"{cat_name}:{term}")

        if not reason_codes:
            reason_codes = ["no_matched_terms"]

        # Determine which input fields were used
        input_fields_used: List[str] = ["title"]
        if candidate.abstract:
            input_fields_used.append("abstract")

        return FilterDecision(
            decision=decision,
            score=round(score, 6),
            raw_score=round(raw_score, 6),
            reason_codes=reason_codes,
            matched_terms=matched,
            candidate_title=candidate.title,
            source_id=candidate.source_id,
            allow_threshold=cfg.allow_threshold,
            review_threshold=cfg.review_threshold,
            config_version=cfg.version,
            input_fields_used=input_fields_used,
        )


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_filter_config(path: Optional[Path] = None) -> FilterConfig:
    """Load a FilterConfig from a JSON file.

    Parameters
    ----------
    path:
        Path to the filter config JSON. If None, uses the default
        config/research_relevance_filter_v1.json relative to repo root.

    Returns
    -------
    FilterConfig

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    ValueError
        If the config JSON is malformed or missing required fields.
    """
    if path is None:
        # Repo root is 3 levels up from this file:
        # packages/research/relevance_filter/scorer.py -> [0]=relevance_filter, [1]=research, [2]=packages, [3]=repo_root
        path = Path(__file__).resolve().parents[3] / "config" / "research_relevance_filter_v1.json"

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Filter config not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in filter config: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Filter config must be a JSON object")

    # Lowercase all term lists
    def _lower_terms(key: str) -> List[str]:
        terms = raw.get(key, [])
        if not isinstance(terms, list):
            raise ValueError(f"Filter config '{key}' must be a list")
        return [str(t).lower() for t in terms]

    return FilterConfig(
        version=str(raw.get("version", "unknown")),
        strong_positive_terms=_lower_terms("strong_positive_terms"),
        positive_terms=_lower_terms("positive_terms"),
        strong_negative_terms=_lower_terms("strong_negative_terms"),
        negative_terms=_lower_terms("negative_terms"),
        strong_positive_weight=float(raw.get("strong_positive_weight", 2.0)),
        positive_weight=float(raw.get("positive_weight", 1.0)),
        strong_negative_weight=float(raw.get("strong_negative_weight", -3.0)),
        negative_weight=float(raw.get("negative_weight", -1.5)),
        allow_threshold=float(raw.get("allow_threshold", 0.55)),
        review_threshold=float(raw.get("review_threshold", 0.35)),
    )
