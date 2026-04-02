"""RIS Phase 3 — per-family deterministic feature extraction.

Provides extract_features(doc) which dispatches to a per-family extractor
based on the document's source_type. All extraction is pure text/regex —
no network calls, no LLM dependencies.

Families:
- academic     : arxiv, ssrn, book
- github       : github repos
- blog         : blog posts
- news         : news articles
- forum_social : reddit, twitter, youtube
- manual       : manual/unknown (default)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from packages.research.evaluation.types import EvalDocument, SOURCE_FAMILIES

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"10\.\d{4,}/\S+")
_ARXIV_RE = re.compile(r"arxiv[:\s]*\d{4}\.\d{4,5}", re.IGNORECASE)
_SSRN_RE = re.compile(r"ssrn[:\s]*\d{6,}", re.IGNORECASE)
_BYLINE_RE = re.compile(
    r"(?:^|\n)\s*(?:by|written by|author[:\s])\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+",
    re.IGNORECASE | re.MULTILINE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n")
_BLOCKQUOTE_RE = re.compile(r"^>", re.MULTILINE)
_PERCENTAGE_RE = re.compile(r"\d+(?:\.\d+)?%")
_DOLLAR_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
_DATE_LIKE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b"
    r"|"
    r"\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_SCREENSHOT_RE = re.compile(r"\b(?:screenshot|image|img|photo|pic)\b", re.IGNORECASE)
_DATA_CHART_RE = re.compile(r"\b(?:data|chart|graph|table|figure)\b", re.IGNORECASE)

_METHODOLOGY_KEYWORDS = [
    "regression",
    "p-value",
    "sample size",
    "dataset",
    "experiment",
    "methodology",
    "control group",
    "confidence interval",
    "hypothesis test",
]


# ---------------------------------------------------------------------------
# FamilyFeatures dataclass
# ---------------------------------------------------------------------------


@dataclass
class FamilyFeatures:
    """Structured features extracted from a document, keyed by source family.

    Attributes:
        family: Source family label (e.g., "academic", "github", "blog").
        features: Dictionary of feature name -> value (bool, int, float, None).
        confidence_signals: Human-readable list of signals that indicate
            document quality/credibility for this family.
    """

    family: str
    features: dict[str, Any] = field(default_factory=dict)
    confidence_signals: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-family extractors
# ---------------------------------------------------------------------------


def _extract_academic(doc: EvalDocument) -> tuple[dict[str, Any], list[str]]:
    """Extract features for academic sources (arxiv, ssrn, book)."""
    body = doc.body or ""

    has_doi = bool(_DOI_RE.search(body))
    has_arxiv_id = bool(_ARXIV_RE.search(body))
    has_ssrn_id = bool(_SSRN_RE.search(body))

    body_lower = body.lower()
    methodology_cues = sum(1 for kw in _METHODOLOGY_KEYWORDS if kw in body_lower)

    has_known_author = bool(doc.author and doc.author.lower() not in {"unknown", "", "none"})
    has_publish_date = bool(doc.source_publish_date)

    features: dict[str, Any] = {
        "has_doi": has_doi,
        "has_arxiv_id": has_arxiv_id,
        "has_ssrn_id": has_ssrn_id,
        "methodology_cues": methodology_cues,
        "has_known_author": has_known_author,
        "has_publish_date": has_publish_date,
    }

    signals: list[str] = []
    if has_doi:
        signals.append("has_doi")
    if has_arxiv_id:
        signals.append("has_arxiv_id")
    if has_ssrn_id:
        signals.append("has_ssrn_id")
    if methodology_cues >= 2:
        signals.append(f"methodology_cues:{methodology_cues}")
    if has_known_author:
        signals.append("has_known_author")
    if has_publish_date:
        signals.append("has_publish_date")

    return features, signals


def _extract_github(doc: EvalDocument) -> tuple[dict[str, Any], list[str]]:
    """Extract features for GitHub repository sources."""
    body = doc.body or ""
    meta = doc.metadata or {}

    stars: Optional[int] = meta.get("stars", None)
    forks: Optional[int] = meta.get("forks", None)
    commit_recency: Optional[str] = meta.get("commit_recency", None)

    body_lower = body.lower()
    has_readme_mention = "readme" in body_lower
    has_license_mention = "license" in body_lower

    features: dict[str, Any] = {
        "stars": stars,
        "forks": forks,
        "has_readme_mention": has_readme_mention,
        "has_license_mention": has_license_mention,
        "commit_recency": commit_recency,
    }

    signals: list[str] = []
    if stars is not None and stars > 0:
        signals.append(f"stars:{stars}")
    if forks is not None and forks > 0:
        signals.append(f"forks:{forks}")
    if has_readme_mention:
        signals.append("has_readme_mention")
    if has_license_mention:
        signals.append("has_license_mention")
    if commit_recency:
        signals.append(f"commit_recency:{commit_recency}")

    return features, signals


def _extract_blog_news(doc: EvalDocument) -> tuple[dict[str, Any], list[str]]:
    """Extract features for blog and news sources."""
    body = doc.body or ""

    has_byline = bool(_BYLINE_RE.search(body))
    has_date = bool(doc.source_publish_date or _DATE_LIKE_RE.search(body))
    heading_count = len(_HEADING_RE.findall(body))
    paragraph_count = len(_PARAGRAPH_BREAK_RE.split(body.strip()))
    has_blockquote = bool(_BLOCKQUOTE_RE.search(body))

    features: dict[str, Any] = {
        "has_byline": has_byline,
        "has_date": has_date,
        "heading_count": heading_count,
        "paragraph_count": paragraph_count,
        "has_blockquote": has_blockquote,
    }

    signals: list[str] = []
    if has_byline:
        signals.append("has_byline")
    if has_date:
        signals.append("has_date")
    if heading_count > 0:
        signals.append(f"heading_count:{heading_count}")
    if paragraph_count > 1:
        signals.append(f"paragraph_count:{paragraph_count}")

    return features, signals


def _extract_forum_social(doc: EvalDocument) -> tuple[dict[str, Any], list[str]]:
    """Extract features for forum and social media sources."""
    body = doc.body or ""
    meta = doc.metadata or {}

    has_screenshot = bool(_SCREENSHOT_RE.search(body))
    has_data_mention = bool(_DATA_CHART_RE.search(body))
    reply_count: Optional[int] = meta.get("reply_count", None)

    # Specificity markers: percentages, dollar amounts
    specificity_markers = len(_PERCENTAGE_RE.findall(body)) + len(_DOLLAR_RE.findall(body))

    features: dict[str, Any] = {
        "has_screenshot": has_screenshot,
        "has_data_mention": has_data_mention,
        "reply_count": reply_count,
        "specificity_markers": specificity_markers,
    }

    signals: list[str] = []
    if has_data_mention:
        signals.append("has_data_mention")
    if specificity_markers > 0:
        signals.append(f"specificity_markers:{specificity_markers}")
    if reply_count is not None and reply_count > 0:
        signals.append(f"reply_count:{reply_count}")
    if has_screenshot:
        signals.append("has_screenshot")

    return features, signals


def _extract_default(doc: EvalDocument) -> tuple[dict[str, Any], list[str]]:
    """Extract minimal features for manual/unknown sources."""
    body = doc.body or ""

    words = body.split()
    has_url = "http://" in body or "https://" in body

    features: dict[str, Any] = {
        "body_length": len(body),
        "word_count": len(words),
        "has_url": has_url,
    }

    signals: list[str] = []
    if has_url:
        signals.append("has_url")
    if len(words) > 100:
        signals.append(f"word_count:{len(words)}")

    return features, signals


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_FAMILY_EXTRACTORS = {
    "academic": _extract_academic,
    "book_foundational": _extract_academic,
    "github": _extract_github,
    "blog": _extract_blog_news,
    "news": _extract_blog_news,
    "forum_social": _extract_forum_social,
    "dossier_report": _extract_default,
    "manual": _extract_default,
}


def extract_features(doc: EvalDocument) -> FamilyFeatures:
    """Extract per-family deterministic features from a document.

    Looks up the source family from SOURCE_FAMILIES, dispatches to the
    appropriate extractor, and returns a FamilyFeatures dataclass.

    All extraction is pure text/regex. No network calls.

    Args:
        doc: The document to extract features from.

    Returns:
        FamilyFeatures with family label, feature dict, and confidence signals.
    """
    family = SOURCE_FAMILIES.get(doc.source_type, "manual")
    extractor = _FAMILY_EXTRACTORS.get(family, _extract_default)
    features, signals = extractor(doc)
    return FamilyFeatures(family=family, features=features, confidence_signals=signals)
