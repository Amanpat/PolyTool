"""RIS Layer 4 — Multi-source academic candidate harvesters.

Provides metadata-only discovery across multiple academic sources:
  - ArxivHarvester             arXiv Atom API  (backfill + monitoring)
  - SemanticScholarHarvester   S2 Graph API v1 (primary aggregator)
  - CrossrefHarvester          Crossref REST API (DOI resolution/enrichment)
  - OpenReviewHarvester        OpenReview API v2 (ML conferences)

Deferred sources (see FEATURE-ris-l4-multisource-academic-harvesters.md):
  - SSRN: requires session/cookie redirect handling; community scrapers are brittle
  - NBER: HTML-based; the ledwindra/nber reference scraper was last updated 2021-2022

All harvesters:
  - Return list[AcademicCandidate] — metadata only (no PDF download, no Marker)
  - Accept injectable _http_fn(url, timeout, headers) -> bytes for offline testing
  - Use stdlib-only dependencies (no extra packages required)

HARVESTER_REGISTRY maps name -> class.  get_harvester(name) returns instances.

Deduplication: dedup_candidates() matches on any canonical ID, with URL fallback:
  arxiv_id, doi, s2_paper_id, openreview_id, source_url

Candidates feed into CandidateInput / RelevanceScorer / ReviewQueueStore
without modification.  No paper becomes RAG-ready until it passes through
the L1 Marker queue.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP helper (stdlib only)
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 15


def _default_urlopen(url: str, timeout: int, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise HarvestError(f"HTTP {exc.code} {exc.reason} for {url}") from exc
    except urllib.error.URLError as exc:
        raise HarvestError(f"URL error for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HarvestError(f"Timeout fetching {url}") from exc
    except Exception as exc:
        raise HarvestError(f"Error fetching {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HarvestError(Exception):
    """Raised when a harvester cannot retrieve or parse results."""


# ---------------------------------------------------------------------------
# AcademicCandidate
# ---------------------------------------------------------------------------


@dataclass
class AcademicCandidate:
    """Normalized metadata-only record from any academic source.

    Compatible with CandidateInput (title, abstract, source_url, fields_of_study)
    and ReviewQueueStore.enqueue() (source_url, title, abstract, canonical_ids).

    No PDF is downloaded.  No Marker is called.
    A candidate may flow through L3 relevance scoring and into the review queue,
    but it does not become RAG-ready until it passes through the L1 Marker queue.
    """

    source_url: str
    title: str
    abstract: str
    authors: list[str]
    published_date: Optional[str]  # YYYY-MM-DD or None
    source_name: str               # "arxiv" | "semantic_scholar" | "crossref" | "openreview"
    canonical_ids: dict = field(default_factory=dict)  # arxiv_id, doi, s2_paper_id, ...
    fields_of_study: list[str] = field(default_factory=list)

    def to_review_queue_record(self, decision: str, score: float, raw_score: float,
                                reason_codes: list, matched_terms: dict,
                                allow_threshold: float, review_threshold: float,
                                config_version: str) -> dict:
        """Build a dict compatible with ReviewQueueStore.enqueue()."""
        candidate_id = hashlib.sha256(self.source_url.encode("utf-8")).hexdigest()
        return {
            "candidate_id": candidate_id,
            "source_url": self.source_url,
            "title": self.title,
            "abstract": self.abstract,
            "score": score,
            "raw_score": raw_score,
            "decision": decision,
            "reason_codes": reason_codes,
            "matched_terms": matched_terms,
            "allow_threshold": allow_threshold,
            "review_threshold": review_threshold,
            "config_version": config_version,
            "canonical_ids": self.canonical_ids,
            "source_name": self.source_name,
            "authors": self.authors,
            "published_date": self.published_date,
            "fields_of_study": self.fields_of_study,
        }


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

_DEDUP_KEYS = ("arxiv_id", "doi", "s2_paper_id", "openreview_id")


def _normalise_dedup_value(key: str, value: object) -> Optional[str]:
    """Return a stable comparable canonical-ID value, or None."""
    text = str(value or "").strip()
    if not text:
        return None
    if key == "doi":
        text = text.removeprefix("https://doi.org/")
        text = text.removeprefix("http://doi.org/")
        text = text.removeprefix("doi:")
        return text.lower()
    return text


def _dedup_keys(candidate: AcademicCandidate) -> list[str]:
    """Return every canonical-ID dedup key for *candidate*."""
    keys: list[str] = []
    for key in _DEDUP_KEYS:
        val = _normalise_dedup_value(key, candidate.canonical_ids.get(key))
        if val:
            keys.append(f"{key}:{val}")
    if not keys:
        keys.append(f"url:{candidate.source_url.strip().lower()}")
    return keys


def dedup_candidates(candidates: list[AcademicCandidate]) -> list[AcademicCandidate]:
    """Remove duplicate candidates across sources.

    Any shared canonical ID is treated as a duplicate.  The first occurrence of
    each paper is kept; later duplicates are dropped, but their IDs are still
    remembered so transitive aliases are caught.  Input order is preserved for
    non-duplicates.
    """
    seen: set[str] = set()
    result: list[AcademicCandidate] = []
    for c in candidates:
        keys = _dedup_keys(c)
        if seen.intersection(keys):
            seen.update(keys)
            continue
        seen.update(keys)
        result.append(c)
    return result


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class AcademicHarvesterBase(ABC):
    """Abstract base for metadata-only academic harvesters.

    Subclasses implement search() which returns AcademicCandidate records
    without downloading PDFs or calling Marker.

    Parameters
    ----------
    timeout:
        HTTP request timeout in seconds.
    _http_fn:
        Injectable HTTP function for offline testing.
        Signature: (url: str, timeout: int, headers: dict) -> bytes
    """

    # Capability flags for the source matrix (read-only, set per subclass)
    METADATA_ONLY: bool = True
    PDF_URL_CAPABLE: bool = False  # Can provide direct PDF URL
    BACKFILL_MODE: bool = True     # Can query historical date ranges
    MONITORING_MODE: bool = True   # Can query for "new since date"
    AUTH_REQUIRED: bool = False    # Requires API key / session

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        _http_fn: Optional[Callable] = None,
    ) -> None:
        self._timeout = timeout
        self._http_fn = _http_fn if _http_fn is not None else _default_urlopen

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[AcademicCandidate]:
        """Search for papers matching *query*.

        Parameters
        ----------
        query:
            Topic/keyword search string.
        max_results:
            Maximum number of candidates to return.

        Returns
        -------
        list[AcademicCandidate]
            Empty list on no results or recoverable error.

        Raises
        ------
        HarvestError
            On unrecoverable network or parse failure.
        """
        ...

    def search_since(self, query: str, since_date: str,
                     max_results: int = 20) -> list[AcademicCandidate]:
        """Search for papers published on or after *since_date* (YYYY-MM-DD).

        Default implementation delegates to search() and filters by date.
        Subclasses may override for source-native date filtering.
        """
        results = self.search(query, max_results=max_results * 2)
        filtered = [c for c in results
                    if c.published_date and c.published_date >= since_date]
        return filtered[:max_results]


# ---------------------------------------------------------------------------
# ArXiv harvester
# ---------------------------------------------------------------------------

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ARXIV_URL_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
_ARXIV_ID_FROM_URL_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")


class ArxivHarvester(AcademicHarvesterBase):
    """Metadata-only arXiv search using the Atom API.

    Does NOT download PDFs or call Marker.  For full PDF extraction,
    use LiveAcademicFetcher (L0/L1 path).

    Capability: backfill (search by topic), monitoring (search_since by date).
    """

    PDF_URL_CAPABLE = True  # arXiv PDFs are at https://arxiv.org/pdf/{id}.pdf

    def search(self, query: str, max_results: int = 20) -> list[AcademicCandidate]:
        encoded = urllib.parse.quote_plus(query)
        api_url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query=all:{encoded}&max_results={max_results}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        try:
            xml_bytes = self._http_fn(api_url, self._timeout, {})
        except HarvestError as exc:
            _logger.warning("ArxivHarvester: search failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            _logger.warning("ArxivHarvester: XML parse error: %s", exc)
            return []

        candidates: list[AcademicCandidate] = []
        for entry in root.findall("atom:entry", _ATOM_NS):
            title_el = entry.find("atom:title", _ATOM_NS)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""

            summary_el = entry.find("atom:summary", _ATOM_NS)
            abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

            authors = [
                name_el.text.strip()
                for author_el in entry.findall("atom:author", _ATOM_NS)
                for name_el in [author_el.find("atom:name", _ATOM_NS)]
                if name_el is not None and name_el.text
            ]

            published_el = entry.find("atom:published", _ATOM_NS)
            published_date = None
            if published_el is not None and published_el.text:
                published_date = published_el.text[:10]

            id_el = entry.find("atom:id", _ATOM_NS)
            canonical_url = ""
            arxiv_id = None
            if id_el is not None and id_el.text:
                raw_id = id_el.text.strip()
                id_match = _ARXIV_URL_ID_RE.search(raw_id)
                if id_match:
                    arxiv_id = id_match.group(1)
                    canonical_url = f"https://arxiv.org/abs/{arxiv_id}"
                else:
                    canonical_url = raw_id

            if not canonical_url:
                continue

            canonical_ids: dict = {}
            if arxiv_id:
                canonical_ids["arxiv_id"] = arxiv_id

            candidates.append(AcademicCandidate(
                source_url=canonical_url,
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=published_date,
                source_name="arxiv",
                canonical_ids=canonical_ids,
            ))

        return candidates

    def search_since(self, query: str, since_date: str,
                     max_results: int = 20) -> list[AcademicCandidate]:
        """Use native arXiv date-range search (submittedDate filter)."""
        # arXiv submittedDate filter format: YYYYMMDDHHMMSS
        since_compact = since_date.replace("-", "") + "000000"
        encoded_query = urllib.parse.quote_plus(query)
        api_url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query=all:{encoded_query}+AND+submittedDate:[{since_compact}+TO+99991231235959]"
            f"&max_results={max_results}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        try:
            xml_bytes = self._http_fn(api_url, self._timeout, {})
        except HarvestError as exc:
            _logger.warning("ArxivHarvester: search_since failed: %s", exc)
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            _logger.warning("ArxivHarvester: XML parse error: %s", exc)
            return []

        # Reuse the entry parsing from search() by building a pseudo feed
        # (simpler: just call search() and filter; the date filter in the URL
        # handles it for large queries, but we also post-filter for correctness)
        candidates: list[AcademicCandidate] = []
        for entry in root.findall("atom:entry", _ATOM_NS):
            title_el = entry.find("atom:title", _ATOM_NS)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            summary_el = entry.find("atom:summary", _ATOM_NS)
            abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
            authors = [
                name_el.text.strip()
                for author_el in entry.findall("atom:author", _ATOM_NS)
                for name_el in [author_el.find("atom:name", _ATOM_NS)]
                if name_el is not None and name_el.text
            ]
            published_el = entry.find("atom:published", _ATOM_NS)
            published_date = None
            if published_el is not None and published_el.text:
                published_date = published_el.text[:10]
            id_el = entry.find("atom:id", _ATOM_NS)
            canonical_url = ""
            arxiv_id = None
            if id_el is not None and id_el.text:
                raw_id = id_el.text.strip()
                id_match = _ARXIV_URL_ID_RE.search(raw_id)
                if id_match:
                    arxiv_id = id_match.group(1)
                    canonical_url = f"https://arxiv.org/abs/{arxiv_id}"
                else:
                    canonical_url = raw_id
            if not canonical_url:
                continue
            canonical_ids: dict = {}
            if arxiv_id:
                canonical_ids["arxiv_id"] = arxiv_id
            if published_date and published_date >= since_date:
                candidates.append(AcademicCandidate(
                    source_url=canonical_url,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    published_date=published_date,
                    source_name="arxiv",
                    canonical_ids=canonical_ids,
                ))
        return candidates


# ---------------------------------------------------------------------------
# Semantic Scholar harvester
# ---------------------------------------------------------------------------

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "title,abstract,authors,year,publicationDate,externalIds,fieldsOfStudy,openAccessPdf"


class SemanticScholarHarvester(AcademicHarvesterBase):
    """Metadata harvester using the Semantic Scholar Graph API v1.

    No API key required for basic search (100 req/5 min unauthenticated).
    Optionally accepts an S2_API_KEY for higher rate limits (1 req/s).

    Returns candidates with arxiv_id and doi in canonical_ids when available.
    openAccessPdf field is captured in canonical_ids["s2_pdf_url"] when present.
    """

    PDF_URL_CAPABLE = True   # openAccessPdf field when available

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = _DEFAULT_TIMEOUT,
        _http_fn: Optional[Callable] = None,
    ) -> None:
        import os as _os
        super().__init__(timeout=timeout, _http_fn=_http_fn)
        self._api_key = api_key or _os.environ.get("S2_API_KEY")

    def _headers(self) -> dict:
        h: dict = {"User-Agent": "PolyTool-RIS/1.0"}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    def search(self, query: str, max_results: int = 20) -> list[AcademicCandidate]:
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"{_S2_BASE}/paper/search"
            f"?query={encoded}"
            f"&fields={_S2_FIELDS}"
            f"&limit={min(max_results, 100)}"
        )
        try:
            raw = self._http_fn(url, self._timeout, self._headers())
        except HarvestError as exc:
            _logger.warning("SemanticScholarHarvester: search failed: %s", exc)
            return []

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("SemanticScholarHarvester: JSON parse error: %s", exc)
            return []

        papers = data.get("data", [])
        if not isinstance(papers, list):
            _logger.warning("SemanticScholarHarvester: unexpected response shape")
            return []

        candidates: list[AcademicCandidate] = []
        for paper in papers:
            title = paper.get("title") or ""
            abstract = paper.get("abstract") or ""
            s2_id = paper.get("paperId") or ""

            authors_raw = paper.get("authors") or []
            authors = [a.get("name", "") for a in authors_raw if a.get("name")]

            pub_date = paper.get("publicationDate") or ""
            if not pub_date and paper.get("year"):
                pub_date = str(paper["year"])

            external_ids = paper.get("externalIds") or {}
            arxiv_id = external_ids.get("ArXiv") or external_ids.get("arxiv")
            doi = external_ids.get("DOI") or external_ids.get("doi")

            canonical_ids: dict = {}
            if s2_id:
                canonical_ids["s2_paper_id"] = s2_id
            if arxiv_id:
                canonical_ids["arxiv_id"] = arxiv_id
            if doi:
                canonical_ids["doi"] = doi

            # Prefer arXiv canonical URL; fall back to S2 paper URL
            if arxiv_id:
                source_url = f"https://arxiv.org/abs/{arxiv_id}"
            elif doi:
                source_url = f"https://doi.org/{doi}"
            elif s2_id:
                source_url = f"https://www.semanticscholar.org/paper/{s2_id}"
            else:
                continue  # Skip papers with no usable URL

            # Capture open-access PDF URL when available
            oa_pdf = paper.get("openAccessPdf")
            if isinstance(oa_pdf, dict) and oa_pdf.get("url"):
                canonical_ids["s2_pdf_url"] = oa_pdf["url"]

            fos_raw = paper.get("fieldsOfStudy") or []
            fields_of_study = [f for f in fos_raw if isinstance(f, str)]

            candidates.append(AcademicCandidate(
                source_url=source_url,
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=pub_date[:10] if pub_date and len(pub_date) >= 10 else pub_date or None,
                source_name="semantic_scholar",
                canonical_ids=canonical_ids,
                fields_of_study=fields_of_study,
            ))

        return candidates


# ---------------------------------------------------------------------------
# Crossref harvester
# ---------------------------------------------------------------------------

_CROSSREF_BASE = "https://api.crossref.org/works"
_CROSSREF_SELECT = "DOI,title,abstract,author,published-print,published-online,URL,subject"


def _crossref_date(item: dict) -> Optional[str]:
    """Extract the best available publication date from a Crossref item."""
    for field in ("published-print", "published-online", "created", "deposited"):
        dp = item.get(field, {}).get("date-parts")
        if dp and isinstance(dp, list) and dp[0]:
            parts = dp[0]
            try:
                year = parts[0]
                month = parts[1] if len(parts) > 1 else 1
                day = parts[2] if len(parts) > 2 else 1
                return f"{year:04d}-{month:02d}-{day:02d}"
            except (TypeError, ValueError, IndexError):
                continue
    return None


class CrossrefHarvester(AcademicHarvesterBase):
    """Metadata harvester using the Crossref REST API.

    Completely public; no authentication required.
    Best used for DOI-based enrichment and broad journal/conference coverage.
    Note: abstract is not always present in Crossref responses.

    Capability: backfill (query by keyword + date range). Monitoring via search_since().
    """

    def search(self, query: str, max_results: int = 20) -> list[AcademicCandidate]:
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"{_CROSSREF_BASE}"
            f"?query={encoded}"
            f"&rows={min(max_results, 100)}"
            f"&select={urllib.parse.quote(_CROSSREF_SELECT)}"
        )
        headers = {
            "User-Agent": "PolyTool-RIS/1.0 (mailto:ris@polytool.local)",
        }
        try:
            raw = self._http_fn(url, self._timeout, headers)
        except HarvestError as exc:
            _logger.warning("CrossrefHarvester: search failed: %s", exc)
            return []

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("CrossrefHarvester: JSON parse error: %s", exc)
            return []

        items = data.get("message", {}).get("items", [])
        if not isinstance(items, list):
            _logger.warning("CrossrefHarvester: unexpected response shape")
            return []

        candidates: list[AcademicCandidate] = []
        for item in items:
            doi = item.get("DOI") or ""
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            abstract = item.get("abstract") or ""
            # Crossref abstracts may contain JATS XML tags — strip them
            if abstract:
                abstract = re.sub(r"<[^>]+>", " ", abstract).strip()
                abstract = re.sub(r"\s+", " ", abstract)

            authors_raw = item.get("author") or []
            authors = []
            for a in authors_raw:
                given = a.get("given", "")
                family = a.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)

            published_date = _crossref_date(item)

            canonical_ids: dict = {}
            if doi:
                canonical_ids["doi"] = doi

            # source_url: prefer doi.org canonical
            crossref_url = item.get("URL") or ""
            if doi:
                source_url = f"https://doi.org/{doi}"
            elif crossref_url:
                source_url = crossref_url
            else:
                continue

            subject_raw = item.get("subject") or []
            fields_of_study = [s for s in subject_raw if isinstance(s, str)]

            candidates.append(AcademicCandidate(
                source_url=source_url,
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=published_date,
                source_name="crossref",
                canonical_ids=canonical_ids,
                fields_of_study=fields_of_study,
            ))

        return candidates

    def search_since(self, query: str, since_date: str,
                     max_results: int = 20) -> list[AcademicCandidate]:
        """Use Crossref native date-range filter (from-pub-date)."""
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"{_CROSSREF_BASE}"
            f"?query={encoded}"
            f"&rows={min(max_results, 100)}"
            f"&select={urllib.parse.quote(_CROSSREF_SELECT)}"
            f"&filter=from-pub-date:{since_date}"
        )
        headers = {"User-Agent": "PolyTool-RIS/1.0 (mailto:ris@polytool.local)"}
        try:
            raw = self._http_fn(url, self._timeout, headers)
        except HarvestError as exc:
            _logger.warning("CrossrefHarvester: search_since failed: %s", exc)
            return []

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("CrossrefHarvester: JSON parse error: %s", exc)
            return []

        items = data.get("message", {}).get("items", [])
        if not isinstance(items, list):
            return []

        # Reuse the same item parsing as search()
        candidates: list[AcademicCandidate] = []
        for item in items:
            doi = item.get("DOI") or ""
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            abstract = item.get("abstract") or ""
            if abstract:
                abstract = re.sub(r"<[^>]+>", " ", abstract).strip()
                abstract = re.sub(r"\s+", " ", abstract)
            authors_raw = item.get("author") or []
            authors = []
            for a in authors_raw:
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)
            published_date = _crossref_date(item)
            canonical_ids: dict = {}
            if doi:
                canonical_ids["doi"] = doi
            crossref_url = item.get("URL") or ""
            if doi:
                source_url = f"https://doi.org/{doi}"
            elif crossref_url:
                source_url = crossref_url
            else:
                continue
            subject_raw = item.get("subject") or []
            fields_of_study = [s for s in subject_raw if isinstance(s, str)]
            candidates.append(AcademicCandidate(
                source_url=source_url,
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=published_date,
                source_name="crossref",
                canonical_ids=canonical_ids,
                fields_of_study=fields_of_study,
            ))
        return candidates


# ---------------------------------------------------------------------------
# OpenReview harvester
# ---------------------------------------------------------------------------

_OPENREVIEW_BASE = "https://api2.openreview.net"


class OpenReviewHarvester(AcademicHarvesterBase):
    """Metadata harvester using the OpenReview API v2.

    Covers ML/CS conference papers (NeurIPS, ICLR, ICML, etc.).
    Completely public; no authentication required.

    Backfill mode is most valuable here (papers from past conferences).
    The OpenReview API v2 uses a different content schema from v1:
    content fields are wrapped as {"value": ...}.
    """

    def search(self, query: str, max_results: int = 20) -> list[AcademicCandidate]:
        encoded = urllib.parse.quote_plus(query)
        url = (
            f"{_OPENREVIEW_BASE}/notes/search"
            f"?term={encoded}"
            f"&limit={min(max_results, 100)}"
            f"&source=forum"
        )
        headers = {"User-Agent": "PolyTool-RIS/1.0"}
        try:
            raw = self._http_fn(url, self._timeout, headers)
        except HarvestError as exc:
            _logger.warning("OpenReviewHarvester: search failed: %s", exc)
            return []

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            _logger.warning("OpenReviewHarvester: JSON parse error: %s", exc)
            return []

        notes = data.get("notes", [])
        if not isinstance(notes, list):
            _logger.warning("OpenReviewHarvester: unexpected response shape")
            return []

        candidates: list[AcademicCandidate] = []
        for note in notes:
            note_id = note.get("id") or ""
            content = note.get("content") or {}

            # API v2: fields are {"value": ...}; API v1: fields are plain values
            def _val(f: str) -> str:
                v = content.get(f)
                if isinstance(v, dict):
                    return v.get("value") or ""
                return v or ""

            title = _val("title")
            abstract = _val("abstract")

            authors_raw = content.get("authors")
            authors: list[str] = []
            if isinstance(authors_raw, dict):
                authors_raw = authors_raw.get("value", [])
            if isinstance(authors_raw, list):
                authors = [str(a) for a in authors_raw if a]

            keywords_raw = content.get("keywords")
            if isinstance(keywords_raw, dict):
                keywords_raw = keywords_raw.get("value", [])
            fields_of_study = [str(k) for k in (keywords_raw or []) if k]

            # cdate is milliseconds since epoch
            cdate = note.get("cdate")
            published_date = None
            if cdate:
                try:
                    import datetime as _dt
                    published_date = _dt.datetime.fromtimestamp(
                        cdate / 1000, tz=_dt.timezone.utc
                    ).strftime("%Y-%m-%d")
                except (TypeError, ValueError, OSError):
                    pass

            if not note_id or not title:
                continue

            source_url = f"https://openreview.net/forum?id={note_id}"
            canonical_ids: dict = {"openreview_id": note_id}

            candidates.append(AcademicCandidate(
                source_url=source_url,
                title=title,
                abstract=abstract,
                authors=authors,
                published_date=published_date,
                source_name="openreview",
                canonical_ids=canonical_ids,
                fields_of_study=fields_of_study,
            ))

        return candidates


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

HARVESTER_REGISTRY: dict[str, type[AcademicHarvesterBase]] = {
    "arxiv": ArxivHarvester,
    "semantic_scholar": SemanticScholarHarvester,
    "crossref": CrossrefHarvester,
    "openreview": OpenReviewHarvester,
}

#: Capability matrix for documentation and operator output.
#: Keys match HARVESTER_REGISTRY. Each value is a dict with capability flags.
SOURCE_CAPABILITY_MATRIX: dict[str, dict] = {
    "arxiv": {
        "description": "arXiv Atom API — preprints across CS/math/physics/quantitative finance",
        "metadata_only": True,
        "pdf_url_capable": True,
        "backfill_mode": True,
        "monitoring_mode": True,
        "auth_required": False,
        "rate_limit_note": "~3 req/s; add delay for bulk queries",
        "notes": "Primary source for recent preprints; existing L0/L1 path fetches PDFs via Marker",
    },
    "semantic_scholar": {
        "description": "S2 Graph API v1 — cross-publisher aggregator with structured metadata",
        "metadata_only": True,
        "pdf_url_capable": True,
        "backfill_mode": True,
        "monitoring_mode": True,
        "auth_required": False,
        "rate_limit_note": "100 req/5 min unauthenticated; set S2_API_KEY for 1 req/s",
        "notes": "Best aggregator; returns externalIds including arXiv IDs and DOIs",
    },
    "crossref": {
        "description": "Crossref REST API — DOI resolution, journal/conference coverage",
        "metadata_only": True,
        "pdf_url_capable": False,
        "backfill_mode": True,
        "monitoring_mode": True,
        "auth_required": False,
        "rate_limit_note": "Generous public limits; add Mailto header for higher tier",
        "notes": "Abstract not always present; best used for DOI enrichment",
    },
    "openreview": {
        "description": "OpenReview API v2 — NeurIPS/ICLR/ICML and ML conference papers",
        "metadata_only": True,
        "pdf_url_capable": False,
        "backfill_mode": True,
        "monitoring_mode": False,
        "auth_required": False,
        "rate_limit_note": "Public read access; no documented rate limit",
        "notes": "Best for ML conference papers; backfill is most useful (past conferences)",
    },
    "ssrn": {
        "description": "SSRN — finance/economics working papers [DEFERRED]",
        "metadata_only": None,
        "pdf_url_capable": None,
        "backfill_mode": None,
        "monitoring_mode": None,
        "auth_required": True,
        "rate_limit_note": "Session/cookie/redirect handling required",
        "notes": (
            "DEFERRED: session/cookie handling is brittle (flagged in RAG pipeline survey). "
            "Community scrapers (talsan/ssrn, karthiktadepalli1/ssrn-scraper) exist but have "
            "maintenance risk. Requires Director approval before implementation."
        ),
        "status": "deferred",
    },
    "nber": {
        "description": "NBER — macro/finance working papers [DEFERRED]",
        "metadata_only": None,
        "pdf_url_capable": None,
        "backfill_mode": None,
        "monitoring_mode": None,
        "auth_required": False,
        "rate_limit_note": "HTML scraping required",
        "notes": (
            "DEFERRED: ledwindra/nber scraper last updated 2021-2022; may need modernization. "
            "No clean public API. Requires Director approval before implementation."
        ),
        "status": "deferred",
    },
}


def get_harvester(
    name: str,
    timeout: int = _DEFAULT_TIMEOUT,
    _http_fn: Optional[Callable] = None,
    **kwargs,
) -> AcademicHarvesterBase:
    """Return a fresh harvester instance for *name*.

    Parameters
    ----------
    name:
        Source name key from HARVESTER_REGISTRY.
    timeout:
        HTTP request timeout in seconds.
    _http_fn:
        Injectable HTTP function for offline testing.
    **kwargs:
        Additional constructor arguments passed to the harvester.

    Returns
    -------
    AcademicHarvesterBase

    Raises
    ------
    KeyError
        If *name* is not in HARVESTER_REGISTRY.
    """
    cls = HARVESTER_REGISTRY[name]
    return cls(timeout=timeout, _http_fn=_http_fn, **kwargs)
