"""RIS Phase 4 — metadata normalization and canonical ID extraction.

Provides:
- NormalizedMetadata: structured metadata output
- canonicalize_url(url) -> str
- extract_canonical_ids(text, url) -> dict
- normalize_metadata(raw, source_family) -> NormalizedMetadata

All functions are pure (no I/O, no network calls).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# Compiled patterns (consistent with feature_extraction.py)
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"10\.\d{4,}/\S+")
_ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})", re.IGNORECASE)
_SSRN_RE = re.compile(r"ssrn[:\s]*(\d{6,})", re.IGNORECASE)
_GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([^/\s]+/[^/\s#?]+)"
)

# ArXiv URL patterns: /abs/YYMM.NNNNN or /pdf/YYMM.NNNNN
_ARXIV_URL_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")

# GitHub URL stripping: remove /tree/... /blob/... /commit/... suffixes
_GITHUB_SUFFIX_RE = re.compile(
    r"(https?://github\.com/[^/]+/[^/]+)(?:/(?:tree|blob|commit|releases|issues|pull|actions|wiki)[/\S]*)?$"
)

# Known news domains (subset; extend as needed)
_NEWS_DOMAINS = frozenset({
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "nytimes.com",
    "theguardian.com",
    "bbc.com",
    "bbc.co.uk",
    "apnews.com",
    "axios.com",
    "politico.com",
    "cnbc.com",
    "cnn.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "arstechnica.com",
    "coindesk.com",
    "cointelegraph.com",
    "decrypt.co",
    "theblock.co",
})


# ---------------------------------------------------------------------------
# NormalizedMetadata
# ---------------------------------------------------------------------------


@dataclass
class NormalizedMetadata:
    """Structured metadata produced by normalize_metadata().

    Attributes
    ----------
    canonical_url:
        Normalized, fragment-free, trailing-slash-free URL.
    title:
        Document title (from raw dict, may be empty string).
    author:
        Document author or "unknown".
    publish_date:
        ISO-8601 publication date string, or None.
    source_family:
        Source-family label (e.g. "academic", "github", "blog").
    source_type:
        Specific source type (e.g. "arxiv", "ssrn", "github", "blog", "news").
    canonical_ids:
        Dict of identifier type -> value. Possible keys:
        doi, arxiv_id, ssrn_id, repo_url.
    publisher:
        Publisher name, or None.
    raw_metadata:
        Original raw dict passed to normalize_metadata().
    """

    canonical_url: str
    title: str
    author: str
    publish_date: Optional[str]
    source_family: str
    source_type: str
    canonical_ids: dict = field(default_factory=dict)
    publisher: Optional[str] = None
    raw_metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------


def canonicalize_url(url: str) -> str:
    """Normalize a URL for dedup and canonical-ID purposes.

    Transformations applied:
    - Lowercase scheme and host
    - Strip URL fragment (#...)
    - Strip trailing slash from path
    - Normalize arXiv /pdf/ URLs to /abs/ form
    - Strip GitHub tree/blob/commit suffixes to repo root

    Non-HTTP schemes (e.g. ``internal://``) are returned as-is without
    modification — they are already canonical stable identifiers.

    Parameters
    ----------
    url:
        Raw URL string.

    Returns
    -------
    str
        Canonical URL.
    """
    # Pass through non-HTTP(S) URLs unchanged (e.g. internal:// book identifiers)
    url_lower = url.lower()
    if not url_lower.startswith("http://") and not url_lower.startswith("https://"):
        return url

    # Apply GitHub suffix stripping first (handles https/http)
    github_match = _GITHUB_SUFFIX_RE.match(url)
    if github_match:
        url = github_match.group(1)

    parsed = urlparse(url)

    # Lowercase scheme and netloc (host)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path

    # Normalize arXiv PDF -> abs
    if "arxiv.org" in netloc and path.startswith("/pdf/"):
        path = path.replace("/pdf/", "/abs/", 1)

    # Strip trailing slash from path (but not root "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Strip trailing slash after arXiv/GitHub normalization
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Rebuild without fragment; keep query only if present
    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))

    # Strip trailing slash one final time (urlunparse may reintroduce one)
    if normalized.endswith("/") and normalized.count("/") > 2:
        normalized = normalized.rstrip("/")

    return normalized


# ---------------------------------------------------------------------------
# Canonical ID extraction
# ---------------------------------------------------------------------------


def extract_canonical_ids(text: str, url: str) -> dict:
    """Extract canonical identifiers from text and URL.

    Extracts:
    - doi: DOI (10.NNNN/...)
    - arxiv_id: arXiv paper ID (YYMM.NNNNN)
    - ssrn_id: SSRN paper ID (ssrn:NNNNNN)
    - repo_url: GitHub repo URL (github.com/owner/repo)

    Parameters
    ----------
    text:
        Document body text to search.
    url:
        Source URL (also searched for IDs).

    Returns
    -------
    dict
        Dictionary with optional keys: doi, arxiv_id, ssrn_id, repo_url.
    """
    combined = (text or "") + " " + (url or "")
    result: dict = {}

    # DOI: 10.NNNN/...
    doi_match = _DOI_RE.search(combined)
    if doi_match:
        result["doi"] = doi_match.group(0).rstrip(".,;)")

    # arXiv ID: from URL path or body text
    arxiv_url_match = _ARXIV_URL_ID_RE.search(url or "")
    if arxiv_url_match:
        result["arxiv_id"] = arxiv_url_match.group(1)
    else:
        arxiv_body_match = _ARXIV_RE.search(combined)
        if arxiv_body_match:
            result["arxiv_id"] = arxiv_body_match.group(1)

    # SSRN ID
    ssrn_match = _SSRN_RE.search(combined)
    if ssrn_match:
        result["ssrn_id"] = ssrn_match.group(1)

    # GitHub repo URL: from URL or text
    github_url_match = _GITHUB_REPO_RE.search(url or "")
    if github_url_match:
        result["repo_url"] = "https://github.com/" + github_url_match.group(1)
    else:
        github_text_match = _GITHUB_REPO_RE.search(text or "")
        if github_text_match:
            result["repo_url"] = "https://github.com/" + github_text_match.group(1)

    return result


# ---------------------------------------------------------------------------
# Source type inference
# ---------------------------------------------------------------------------


def _infer_source_type(url: str, source_family: str) -> str:
    """Infer specific source_type from URL and source_family."""
    url_lower = url.lower() if url else ""

    if source_family == "academic":
        if "arxiv.org" in url_lower:
            return "arxiv"
        if "ssrn.com" in url_lower:
            return "ssrn"
        return "book"

    if source_family == "github":
        return "github"

    if source_family in ("blog", "news"):
        # Check if host matches a known news domain
        try:
            host = urlparse(url_lower).netloc.lstrip("www.")
        except Exception:
            host = ""
        if any(nd in host for nd in _NEWS_DOMAINS):
            return "news"
        return "blog"

    return source_family


# ---------------------------------------------------------------------------
# normalize_metadata
# ---------------------------------------------------------------------------


def normalize_metadata(raw: dict, source_family: str) -> NormalizedMetadata:
    """Build NormalizedMetadata from a raw source dict.

    Family-specific field mapping:
    - academic: url, title, abstract/body_text, authors (list), published_date
    - github:   repo_url, readme_text, description, stars, forks, last_commit_date
    - blog/news: url, title, body_text, author, published_date, publisher

    Parameters
    ----------
    raw:
        Raw source dict (as produced by a scraper or fixture).
    source_family:
        One of "academic", "github", "blog", "news".

    Returns
    -------
    NormalizedMetadata
    """
    if source_family == "github":
        url = raw.get("repo_url", "")
    else:
        url = raw.get("url", "")

    canonical_url = canonicalize_url(url) if url else ""
    source_type = _infer_source_type(url, source_family)

    # Build combined text for canonical ID extraction
    body_text = raw.get("body_text", raw.get("abstract", raw.get("readme_text", "")))
    canonical_ids = extract_canonical_ids(str(body_text), url)

    # Author
    if source_family == "academic":
        authors = raw.get("authors", [])
        if isinstance(authors, list):
            author = ", ".join(str(a) for a in authors) if authors else "unknown"
        else:
            author = str(authors) if authors else "unknown"
    else:
        author = raw.get("author", "unknown") or "unknown"

    title = raw.get("title", raw.get("description", "")) or ""
    publish_date = raw.get("published_date", raw.get("last_commit_date", None))
    publisher = raw.get("publisher", None)

    return NormalizedMetadata(
        canonical_url=canonical_url,
        title=title,
        author=author,
        publish_date=publish_date,
        source_family=source_family,
        source_type=source_type,
        canonical_ids=canonical_ids,
        publisher=publisher,
        raw_metadata=raw,
    )
