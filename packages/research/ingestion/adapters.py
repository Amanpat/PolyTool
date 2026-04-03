"""RIS Phase 4 — source adapters.

Provides the SourceAdapter ABC and three concrete adapter implementations:
- AcademicAdapter: arXiv, SSRN, book/preprint sources
- GithubAdapter: GitHub repository sources
- BlogNewsAdapter: Blog posts and news articles

Each adapter:
1. Normalizes metadata via normalize.py
2. Caches the raw payload if a RawSourceCache is provided
3. Returns an ExtractedDocument ready for the ingestion pipeline

ADAPTER_REGISTRY maps source_family -> adapter class.
get_adapter(family) returns a fresh adapter instance.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from packages.research.ingestion.extractors import ExtractedDocument
from packages.research.ingestion.normalize import (
    NormalizedMetadata,
    normalize_metadata,
    canonicalize_url,
    _infer_source_type,
    _NEWS_DOMAINS,
)
from packages.research.ingestion.source_cache import RawSourceCache, make_source_id

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# SourceAdapter ABC
# ---------------------------------------------------------------------------


class SourceAdapter(ABC):
    """Abstract base class for external-source adapters.

    An adapter converts a raw source dict (as produced by a scraper or
    loaded from a fixture) into an ExtractedDocument.  Optionally caches
    the raw payload on disk before any processing.
    """

    @abstractmethod
    def adapt(
        self,
        raw_source: dict,
        cache: Optional[RawSourceCache] = None,
    ) -> ExtractedDocument:
        """Convert *raw_source* to an ExtractedDocument.

        Parameters
        ----------
        raw_source:
            The original source dict. Structure is family-specific.
        cache:
            If provided, the raw payload is written to disk before any
            processing.

        Returns
        -------
        ExtractedDocument
        """
        ...

    def _cache_if_provided(
        self,
        raw_source: dict,
        source_id: str,
        source_family: str,
        cache: Optional[RawSourceCache],
    ) -> None:
        if cache is not None:
            cache.cache_raw(source_id, raw_source, source_family)


# ---------------------------------------------------------------------------
# AcademicAdapter
# ---------------------------------------------------------------------------


class AcademicAdapter(SourceAdapter):
    """Adapter for academic/preprint sources (arXiv, SSRN, book).

    Expected raw_source keys:
    - url (str): Paper URL
    - title (str): Paper title
    - abstract (str): Paper abstract
    - authors (list[str], optional): Author list
    - published_date (str, optional): ISO-8601 date
    - body_text (str, optional): Full paper body if available
    """

    def adapt(
        self,
        raw_source: dict,
        cache: Optional[RawSourceCache] = None,
    ) -> ExtractedDocument:
        url = raw_source.get("url", "")
        title = raw_source.get("title", "Unknown Paper")
        abstract = raw_source.get("abstract", "")
        body_text = raw_source.get("body_text", "")
        authors = raw_source.get("authors", [])
        published_date = raw_source.get("published_date", None)

        # Build body: prefer body_text, fall back to abstract
        body = body_text if body_text else abstract
        if not body:
            body = title  # last-resort fallback

        # Normalize metadata
        meta: NormalizedMetadata = normalize_metadata(raw_source, "academic")

        # Build source_id from canonical URL for cache keying
        canonical_url = meta.canonical_url or url
        source_id = make_source_id(canonical_url) if canonical_url else make_source_id(title)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, "academic", cache)

        # Build author string
        if isinstance(authors, list):
            author = ", ".join(str(a) for a in authors) if authors else "unknown"
        else:
            author = str(authors) if authors else "unknown"

        metadata = {
            "canonical_ids": meta.canonical_ids,
            "source_type": meta.source_type,
            "publisher": meta.publisher,
            "abstract": abstract[:500] if abstract else "",
        }

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=canonical_url or url or "internal://academic",
            source_family="academic",
            author=author,
            publish_date=published_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# GithubAdapter
# ---------------------------------------------------------------------------


class GithubAdapter(SourceAdapter):
    """Adapter for GitHub repository sources.

    Expected raw_source keys:
    - repo_url (str): Full repository URL
    - readme_text (str): README content
    - description (str, optional): Repository description
    - stars (int, optional): Star count
    - forks (int, optional): Fork count
    - license (str, optional): License name
    - last_commit_date (str, optional): ISO date of last commit
    """

    def adapt(
        self,
        raw_source: dict,
        cache: Optional[RawSourceCache] = None,
    ) -> ExtractedDocument:
        repo_url = raw_source.get("repo_url", "")
        readme_text = raw_source.get("readme_text", "")
        description = raw_source.get("description", "")
        stars = raw_source.get("stars", None)
        forks = raw_source.get("forks", None)
        license_name = raw_source.get("license", None)
        last_commit_date = raw_source.get("last_commit_date", None)

        # Normalize metadata
        meta: NormalizedMetadata = normalize_metadata(raw_source, "github")

        canonical_url = meta.canonical_url or repo_url
        source_id = make_source_id(canonical_url) if canonical_url else make_source_id(repo_url)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, "github", cache)

        # Build title from URL: last two path segments (owner/repo)
        if canonical_url:
            parts = canonical_url.rstrip("/").split("/")
            title = "/".join(parts[-2:]) if len(parts) >= 2 else canonical_url
        else:
            title = description or repo_url

        # Body: readme + description
        body_parts = []
        if readme_text:
            body_parts.append(readme_text)
        if description:
            body_parts.append(f"\nDescription: {description}")
        body = "\n\n".join(body_parts) if body_parts else description or repo_url

        # commit_recency: last_commit_date as string
        commit_recency = last_commit_date

        metadata = {
            "canonical_ids": meta.canonical_ids,
            "source_type": "github",
            "stars": stars,
            "forks": forks,
            "license": license_name,
            "commit_recency": commit_recency,
        }

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=canonical_url or repo_url or "internal://github",
            source_family="github",
            author="unknown",
            publish_date=last_commit_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# BlogNewsAdapter
# ---------------------------------------------------------------------------


class BlogNewsAdapter(SourceAdapter):
    """Adapter for blog posts and news articles.

    Expected raw_source keys:
    - url (str): Article URL
    - title (str): Article title
    - body_text (str): Full article body
    - author (str, optional): Author name
    - published_date (str, optional): ISO-8601 date
    - publisher (str, optional): Publisher name

    Source-type heuristic: if the URL host matches a known news domain ->
    source_type="news"; otherwise source_type="blog".
    """

    def adapt(
        self,
        raw_source: dict,
        cache: Optional[RawSourceCache] = None,
    ) -> ExtractedDocument:
        from urllib.parse import urlparse

        url = raw_source.get("url", "")
        title = raw_source.get("title", "")
        body_text = raw_source.get("body_text", "")
        author = raw_source.get("author", "unknown") or "unknown"
        published_date = raw_source.get("published_date", None)
        publisher = raw_source.get("publisher", None)

        # Determine source_type via news-domain heuristic
        try:
            host = urlparse(url.lower()).netloc.lstrip("www.")
        except Exception:
            host = ""
        is_news = any(nd in host for nd in _NEWS_DOMAINS)
        source_type = "news" if is_news else "blog"
        source_family = source_type  # "news" or "blog" are both valid source_families

        # Normalize metadata
        meta: NormalizedMetadata = normalize_metadata(raw_source, source_family)

        canonical_url = meta.canonical_url or url
        source_id = make_source_id(canonical_url) if canonical_url else make_source_id(title)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, source_family, cache)

        body = body_text or title

        metadata = {
            "canonical_ids": meta.canonical_ids,
            "source_type": source_type,
            "publisher": publisher,
        }

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=canonical_url or url or "internal://blog",
            source_family=source_family,
            author=author,
            publish_date=published_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# BookAdapter
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Slugify *text* for use in canonical_url paths.

    Lowercases text, replaces non-alphanumeric characters (except underscore)
    with underscores, strips leading/trailing underscores, and collapses
    consecutive underscores.
    """
    slug = re.sub(r"[^\w]", "_", text.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "root"


class BookAdapter(SourceAdapter):
    """Adapter for curated book content ingestion.

    Books do not have a live fetcher.  Raw source dicts are supplied manually
    (e.g. via ``research-ingest --from-adapter --source-family book``) or
    loaded from a structured fixture.

    Expected raw_source keys:
    - title (str): Book title
    - authors (str or list[str]): Author(s)
    - book_id (str): Stable book identifier (e.g. "market_microstructure_theory")
    - chapter (str, optional): Chapter name/label
    - section (str, optional): Section name/label (used if chapter absent)
    - body_text (str): Chapter/section body text
    - published_date (str, optional): ISO-8601 publication date

    Identity is stable: canonical_url = "internal://book/{book_id}/{chapter_or_section_slug}"
    where chapter_or_section_slug = slugify(chapter or section or "root").
    """

    def adapt(
        self,
        raw_source: dict,
        cache: Optional[RawSourceCache] = None,
    ) -> ExtractedDocument:
        title = raw_source.get("title", "Unknown Book")
        authors_raw = raw_source.get("authors", [])
        book_id = raw_source.get("book_id", "")
        chapter = raw_source.get("chapter", None)
        section = raw_source.get("section", None)
        body_text = raw_source.get("body_text", "")
        published_date = raw_source.get("published_date", None)

        # Determine chapter/section slug for stable canonical URL
        chapter_or_section = chapter or section or "root"
        slug = _slugify(chapter_or_section)

        canonical_url = f"internal://book/{book_id}/{slug}"

        # Build author string
        if isinstance(authors_raw, list):
            author = ", ".join(str(a) for a in authors_raw) if authors_raw else "unknown"
        else:
            author = str(authors_raw) if authors_raw else "unknown"

        # Source ID from canonical URL
        source_id = make_source_id(canonical_url)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, "book", cache)

        metadata = {
            "canonical_ids": {"book_id": book_id} if book_id else {},
            "source_type": "book",
            "chapter": chapter,
            "section": section,
        }

        return ExtractedDocument(
            title=title,
            body=body_text or title,
            source_url=canonical_url,
            source_family="book",
            author=author,
            publish_date=published_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# RedditAdapter
# ---------------------------------------------------------------------------


class RedditAdapter(SourceAdapter):
    """Adapter for Reddit post sources.

    Expected raw_source keys:
    - url (str): Reddit post URL
    - title (str): Post title
    - body_text (str, optional): Post body / self-text
    - author (str): Post author username
    - published_date (str, optional): ISO-8601 date
    - subreddit (str): Subreddit name
    - score (int, optional): Post score (upvotes)
    - num_comments (int, optional): Total comment count
    - top_comments (list[str], optional): Top comment texts

    Body is assembled as::

        {title}

        {body_text}

        --- Top Comments ---

        {comment_1}
        {comment_2}
        ...

    The ``--- Top Comments ---`` block is omitted when ``top_comments`` is
    empty or absent.
    """

    def adapt(
        self,
        raw_source: dict,
        cache=None,
    ) -> ExtractedDocument:
        url = raw_source.get("url", "")
        title = raw_source.get("title", "")
        body_text = raw_source.get("body_text", "") or ""
        author = raw_source.get("author", "unknown") or "unknown"
        published_date = raw_source.get("published_date", None)
        subreddit = raw_source.get("subreddit", "")
        score = raw_source.get("score", None)
        num_comments = raw_source.get("num_comments", None)
        top_comments = raw_source.get("top_comments", []) or []

        # Normalize metadata
        meta: NormalizedMetadata = normalize_metadata(raw_source, "reddit")

        canonical_url = meta.canonical_url or url
        source_id = make_source_id(canonical_url) if canonical_url else make_source_id(title)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, "reddit", cache)

        # Build body
        parts = []
        if title:
            parts.append(title)
        if body_text:
            parts.append(body_text)
        if top_comments:
            parts.append("--- Top Comments ---")
            for comment in top_comments:
                if comment and comment.strip():
                    parts.append(comment.strip())
        body = "\n\n".join(parts) if parts else title or ""

        metadata = {
            "subreddit": subreddit,
            "score": score,
            "num_comments": num_comments,
            "canonical_ids": meta.canonical_ids,
            "source_type": "reddit",
        }

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=canonical_url or url or "internal://reddit",
            source_family="reddit",
            author=author,
            publish_date=published_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# YouTubeAdapter
# ---------------------------------------------------------------------------


class YouTubeAdapter(SourceAdapter):
    """Adapter for YouTube video sources.

    Expected raw_source keys:
    - url (str): YouTube video URL
    - title (str): Video title
    - transcript_text (str): Raw VTT transcript or plain transcript text
    - channel (str): Channel name
    - published_date (str, optional): ISO-8601 date
    - duration_seconds (int, optional): Video duration in seconds
    - view_count (int, optional): View count

    Body is produced by ``clean_transcript(transcript_text)`` from fetchers.py.
    """

    def adapt(
        self,
        raw_source: dict,
        cache=None,
    ) -> ExtractedDocument:
        from packages.research.ingestion.fetchers import clean_transcript

        url = raw_source.get("url", "")
        title = raw_source.get("title", "")
        transcript_text = raw_source.get("transcript_text", "") or ""
        channel = raw_source.get("channel", "unknown") or "unknown"
        published_date = raw_source.get("published_date", None)
        duration_seconds = raw_source.get("duration_seconds", None)
        view_count = raw_source.get("view_count", None)

        # Normalize metadata
        meta: NormalizedMetadata = normalize_metadata(raw_source, "youtube")

        canonical_url = meta.canonical_url or url
        source_id = make_source_id(canonical_url) if canonical_url else make_source_id(title)

        # Cache raw payload
        self._cache_if_provided(raw_source, source_id, "youtube", cache)

        # Clean transcript
        body = clean_transcript(transcript_text)
        if not body:
            body = title or ""

        metadata = {
            "duration_seconds": duration_seconds,
            "view_count": view_count,
            "channel": channel,
            "canonical_ids": meta.canonical_ids,
            "source_type": "youtube",
        }

        return ExtractedDocument(
            title=title,
            body=body,
            source_url=canonical_url or url or "internal://youtube",
            source_family="youtube",
            author=channel,
            publish_date=published_date,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, type[SourceAdapter]] = {
    "academic": AcademicAdapter,
    "github": GithubAdapter,
    "blog": BlogNewsAdapter,
    "news": BlogNewsAdapter,
    "book": BookAdapter,
    "reddit": RedditAdapter,
    "youtube": YouTubeAdapter,
}


def get_adapter(family: str) -> SourceAdapter:
    """Return a fresh adapter instance for *family*.

    Parameters
    ----------
    family:
        Source-family key (e.g. "academic", "github", "blog", "news").

    Returns
    -------
    SourceAdapter

    Raises
    ------
    KeyError
        If *family* is not in ADAPTER_REGISTRY.
    """
    cls = ADAPTER_REGISTRY[family]
    return cls()
