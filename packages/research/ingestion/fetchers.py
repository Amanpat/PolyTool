"""RIS Phase 5 -- live HTTP fetchers for external sources.

Provides three fetcher classes that produce raw_source dicts compatible with
the Phase 4 adapter contracts (AcademicAdapter, GithubAdapter, BlogNewsAdapter).

All fetchers accept an injectable _http_fn for offline testing. In production
they use _default_urlopen which wraps stdlib urllib.request (no extra deps).

FETCHER_REGISTRY and get_fetcher() mirror the adapter registry pattern.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Callable, Optional
import urllib.error
import urllib.request

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FetchError
# ---------------------------------------------------------------------------


class FetchError(Exception):
    """Raised when a fetcher fails to retrieve or parse a source."""


# ---------------------------------------------------------------------------
# Default HTTP helper (stdlib only, no requests/httpx)
# ---------------------------------------------------------------------------


def _default_urlopen(url: str, timeout: int, headers: dict) -> bytes:
    """Fetch *url* and return the response body as bytes.

    Parameters
    ----------
    url:
        Target URL.
    timeout:
        Request timeout in seconds.
    headers:
        HTTP headers dict (e.g. Authorization, Accept).

    Returns
    -------
    bytes
        Response body.

    Raises
    ------
    FetchError
        On HTTPError, URLError, TimeoutError, or other network failure.
    """
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} {exc.reason} for {url}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"URL error for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FetchError(f"Timeout fetching {url}") from exc
    except Exception as exc:
        raise FetchError(f"Error fetching {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# Regex patterns (local copies — do not import from normalize.py to avoid
# potential circular imports; these match normalize._ARXIV_URL_ID_RE and
# normalize._GITHUB_REPO_RE exactly)
# ---------------------------------------------------------------------------

_ARXIV_URL_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
_GITHUB_REPO_RE = re.compile(r"https?://github\.com/([^/\s]+/[^/\s#?]+)")

# Atom namespace for arXiv API responses
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


# ---------------------------------------------------------------------------
# LiveAcademicFetcher
# ---------------------------------------------------------------------------


class LiveAcademicFetcher:
    """Fetch an arXiv paper via the arXiv Atom API.

    Returns a raw_source dict with keys:
        url, title, abstract, authors (list[str]), published_date (YYYY-MM-DD)

    Compatible with AcademicAdapter.adapt().
    """

    def __init__(
        self,
        timeout: int = 15,
        _http_fn: Optional[Callable] = None,
        _pdf_http_fn: Optional[Callable] = None,
        _pdf_extractor_cls=None,
        _pdf_parser: str = "auto",
        _marker_extractor_cls=None,
        _pdfplumber_extractor_cls=None,
    ) -> None:
        self._timeout = timeout
        self._http_fn = _http_fn if _http_fn is not None else _default_urlopen
        self._pdf_http_fn = _pdf_http_fn if _pdf_http_fn is not None else self._http_fn
        self._pdf_extractor_cls = _pdf_extractor_cls  # backward compat only
        self._marker_extractor_cls = _marker_extractor_cls
        self._pdfplumber_extractor_cls = _pdfplumber_extractor_cls

        # parser: env var overrides constructor default
        import os as _os
        _env = _os.environ.get("RIS_PDF_PARSER", "").lower()
        self._pdf_parser = _env if _env in ("auto", "pdfplumber", "marker") else _pdf_parser

    # ------------------------------------------------------------------
    # PDF body extraction helpers
    # ------------------------------------------------------------------

    def _fetch_pdf_body(self, arxiv_id: str) -> "tuple[str, dict]":
        """Download arXiv PDF and extract body text.

        Returns (body_text, meta_dict).
        body_source values:
          "pdf"                — pdfplumber success (default or auto without marker)
          "marker"             — Marker success
          "marker_llm_boost"   — Marker with LLM flag enabled
          "pdfplumber_fallback"— Marker failed, pdfplumber succeeded
          "abstract_fallback"  — all extraction failed; caller uses abstract
        """
        import os as _os
        import tempfile

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        tmp_path = None
        try:
            pdf_bytes = self._pdf_http_fn(pdf_url, self._timeout, {})

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(pdf_bytes)
                tmp_path = f.name

            return self._parse_pdf(tmp_path)

        except Exception as exc:
            return ("", {"body_source": "abstract_fallback", "fallback_reason": str(exc)[:200]})

        finally:
            if tmp_path is not None:
                try:
                    _os.unlink(tmp_path)
                except OSError:
                    pass

    def _parse_pdf(self, tmp_path: str) -> "tuple[str, dict]":
        """Dispatch to the right parser. Returns (body_text, meta_dict)."""
        # Backward compat: _pdf_extractor_cls set → behave exactly like Layer 0
        if self._pdf_extractor_cls is not None:
            return self._compat_extract(tmp_path)

        if self._pdf_parser == "pdfplumber":
            return self._pdfplumber_extract(tmp_path, fallback_reason=None)

        # "auto" or "marker": try Marker first, fall back to pdfplumber
        return self._try_marker_or_fallback(tmp_path)

    def _compat_extract(self, tmp_path: str) -> "tuple[str, dict]":
        """Layer-0 backward-compat path using injected _pdf_extractor_cls."""
        try:
            extractor = self._pdf_extractor_cls()
            doc = extractor.extract(tmp_path)
            body_text = doc.body
            page_count = doc.metadata.get("page_count", 0)
            if len(body_text) < 2000:
                return ("", {
                    "body_source": "abstract_fallback",
                    "fallback_reason": f"extracted text too short ({len(body_text)} chars)",
                })
            return (body_text, {
                "body_source": "pdf",
                "body_length": len(body_text),
                "page_count": page_count,
            })
        except Exception as exc:
            return ("", {"body_source": "abstract_fallback", "fallback_reason": str(exc)[:200]})

    def _try_marker_or_fallback(self, tmp_path: str) -> "tuple[str, dict]":
        """Attempt Marker extraction; fall back to pdfplumber on any failure."""
        marker_fail_reason: "Optional[str]" = None

        try:
            from packages.research.ingestion.extractors import MarkerPDFExtractor
            marker_cls = self._marker_extractor_cls or MarkerPDFExtractor
            extractor = marker_cls()
            doc = extractor.extract(tmp_path)
            body_text = doc.body or ""

            if len(body_text) < 200:
                marker_fail_reason = f"marker output too short ({len(body_text)} chars)"
            else:
                return self._build_marker_result(body_text, doc.metadata)

        except ImportError:
            if self._pdf_parser == "auto":
                marker_fail_reason = None  # silent: marker not installed in auto mode
            else:
                marker_fail_reason = "marker-pdf not installed"
        except Exception as exc:
            marker_fail_reason = str(exc)[:200]

        return self._pdfplumber_extract(tmp_path, fallback_reason=marker_fail_reason)

    def _pdfplumber_extract(
        self, tmp_path: str, fallback_reason: "Optional[str]"
    ) -> "tuple[str, dict]":
        """Run pdfplumber extraction. Sets body_source based on fallback_reason."""
        try:
            from packages.research.ingestion.extractors import PDFExtractor
            extractor_cls = self._pdfplumber_extractor_cls or PDFExtractor
            extractor = extractor_cls()
            doc = extractor.extract(tmp_path)
            body_text = doc.body
            page_count = doc.metadata.get("page_count", 0)

            if len(body_text) < 2000:
                return ("", {
                    "body_source": "abstract_fallback",
                    "fallback_reason": f"extracted text too short ({len(body_text)} chars)",
                })

            if fallback_reason is not None:
                return (body_text, {
                    "body_source": "pdfplumber_fallback",
                    "fallback_reason": fallback_reason,
                    "body_length": len(body_text),
                    "page_count": page_count,
                })
            return (body_text, {
                "body_source": "pdf",
                "body_length": len(body_text),
                "page_count": page_count,
            })
        except Exception as exc:
            return ("", {"body_source": "abstract_fallback", "fallback_reason": str(exc)[:200]})

    def _build_marker_result(
        self, body_text: str, doc_meta: dict
    ) -> "tuple[str, dict]":
        """Assemble meta_dict for a successful Marker extraction."""
        meta: dict = {
            "body_source": doc_meta.get("body_source", "marker"),
            "body_length": len(body_text),
            "has_structured_metadata": True,
        }
        if doc_meta.get("page_count"):
            meta["page_count"] = doc_meta["page_count"]
        if doc_meta.get("marker_version"):
            meta["marker_version"] = doc_meta["marker_version"]
        if doc_meta.get("structured_metadata") is not None:
            meta["structured_metadata"] = doc_meta["structured_metadata"]
        if doc_meta.get("structured_metadata_truncated"):
            meta["structured_metadata_truncated"] = True
        return (body_text, meta)

    def fetch(self, url: str) -> dict:
        """Fetch arXiv paper metadata from *url*.

        Handles both /abs/ and /pdf/ URL forms. Normalizes to /abs/ before
        calling the arXiv API.

        Returns
        -------
        dict
            Keys: url, title, abstract, authors, published_date.

        Raises
        ------
        FetchError
            If the URL is not an arXiv URL, or if the API returns no results,
            or on any network/HTTP error.
        """
        # Extract arXiv ID from URL
        match = _ARXIV_URL_ID_RE.search(url)
        if not match:
            raise FetchError(f"Cannot extract arXiv ID from URL: {url!r}")
        arxiv_id = match.group(1)

        # Canonical abs URL
        canonical_url = f"https://arxiv.org/abs/{arxiv_id}"

        # Call arXiv Atom API
        api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1"
        xml_bytes = self._http_fn(api_url, self._timeout, {})

        # Parse Atom XML
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise FetchError(f"Failed to parse arXiv API response: {exc}") from exc

        entry = root.find("atom:entry", _ATOM_NS)
        if entry is None:
            raise FetchError(f"arXiv returned no results for {arxiv_id}")

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
            published_date = published_el.text[:10]  # YYYY-MM-DD

        body_text, body_meta = self._fetch_pdf_body(arxiv_id)

        result = {
            "url": canonical_url,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published_date": published_date,
            "body_text": body_text if body_text else abstract,
        }
        result.update(body_meta)

        if body_meta.get("body_source") == "pdf":
            _logger.info(
                "academic fetch: arxiv:%s body_source=pdf body_length=%d page_count=%s",
                arxiv_id,
                body_meta.get("body_length", 0),
                body_meta.get("page_count", "?"),
            )
        else:
            _logger.info(
                "academic fetch: arxiv:%s body_source=abstract_fallback reason=%s",
                arxiv_id,
                body_meta.get("fallback_reason", "unknown"),
            )

        return result

    def search_by_topic(self, query: str, max_results: int = 5) -> list[dict]:
        """Search arXiv for papers matching *query*.

        Uses the arXiv Atom API search endpoint.

        Parameters
        ----------
        query:
            Topic/keyword search string (e.g. "prediction markets microstructure").
        max_results:
            Maximum number of results to return (default 5).

        Returns
        -------
        list[dict]
            Each dict has the same keys as fetch():
            url, title, abstract, authors (list[str]), published_date.
            Returns [] when the API returns zero entries (no FetchError).

        Raises
        ------
        FetchError
            On network failure or XML parse error.
        """
        encoded = urllib.parse.quote_plus(query)
        api_url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query=all:{encoded}&max_results={max_results}"
        )

        xml_bytes = self._http_fn(api_url, self._timeout, {})

        # Parse Atom XML
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise FetchError(f"Failed to parse arXiv search API response: {exc}") from exc

        results = []
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
                published_date = published_el.text[:10]  # YYYY-MM-DD

            # Build canonical URL from entry id element
            id_el = entry.find("atom:id", _ATOM_NS)
            canonical_url = ""
            arxiv_id = None
            if id_el is not None and id_el.text:
                raw_id = id_el.text.strip()
                # arXiv IDs in feed: http://arxiv.org/abs/YYMM.NNNNNvN
                id_match = _ARXIV_URL_ID_RE.search(raw_id)
                if id_match:
                    arxiv_id = id_match.group(1)
                    canonical_url = f"https://arxiv.org/abs/{arxiv_id}"
                else:
                    canonical_url = raw_id

            entry_dict: dict = {
                "url": canonical_url,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published_date": published_date,
            }

            if arxiv_id:
                body_text, body_meta = self._fetch_pdf_body(arxiv_id)
                entry_dict["body_text"] = body_text if body_text else abstract
                entry_dict.update(body_meta)
                if body_meta.get("body_source") == "pdf":
                    _logger.info(
                        "academic fetch: arxiv:%s body_source=pdf body_length=%d page_count=%s",
                        arxiv_id,
                        body_meta.get("body_length", 0),
                        body_meta.get("page_count", "?"),
                    )
                else:
                    _logger.info(
                        "academic fetch: arxiv:%s body_source=abstract_fallback reason=%s",
                        arxiv_id,
                        body_meta.get("fallback_reason", "unknown"),
                    )

            results.append(entry_dict)

        return results


# ---------------------------------------------------------------------------
# LiveGitHubFetcher
# ---------------------------------------------------------------------------


class LiveGitHubFetcher:
    """Fetch GitHub repository metadata via the GitHub REST API.

    Returns a raw_source dict with keys:
        repo_url, readme_text, description, stars, forks, license, last_commit_date

    Compatible with GithubAdapter.adapt().

    If GITHUB_TOKEN env var is set (or token passed to __init__), it is used
    for Authorization: token ... header, raising the rate limit from 60/hr to
    5000/hr.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: int = 15,
        _http_fn: Optional[Callable] = None,
    ) -> None:
        if token is None:
            token = os.environ.get("GITHUB_TOKEN")
        self._token = token
        self._timeout = timeout
        self._http_fn = _http_fn if _http_fn is not None else _default_urlopen

    def _build_headers(self) -> dict:
        headers: dict = {"Accept": "application/vnd.github.v3+json"}
        if self._token:
            headers["Authorization"] = f"token {self._token}"
        return headers

    def fetch(self, url: str) -> dict:
        """Fetch repository metadata from *url*.

        Returns
        -------
        dict
            Keys: repo_url, readme_text, description, stars, forks,
                  license, last_commit_date.

        Raises
        ------
        FetchError
            If *url* is not a valid GitHub repo URL, or on network error.
        """
        match = _GITHUB_REPO_RE.match(url)
        if not match:
            raise FetchError(f"Cannot parse GitHub owner/repo from URL: {url!r}")
        owner_repo = match.group(1)
        # Strip trailing .git if present
        owner_repo = owner_repo.rstrip("/")
        if owner_repo.endswith(".git"):
            owner_repo = owner_repo[:-4]

        canonical_url = f"https://github.com/{owner_repo}"
        headers = self._build_headers()

        # Fetch repo metadata
        api_url = f"https://api.github.com/repos/{owner_repo}"
        repo_bytes = self._http_fn(api_url, self._timeout, headers)
        try:
            repo_data = json.loads(repo_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FetchError(f"Invalid JSON from GitHub API: {exc}") from exc

        description = repo_data.get("description") or ""
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        pushed_at = repo_data.get("pushed_at", "")
        last_commit_date = pushed_at[:10] if pushed_at else None

        # Parse license
        license_info = repo_data.get("license")
        license_name: Optional[str] = None
        if license_info:
            license_name = (
                license_info.get("spdx_id")
                or license_info.get("name")
                or None
            )

        # Fetch README (may 404 for repos without one)
        readme_url = f"https://api.github.com/repos/{owner_repo}/readme"
        readme_text = ""
        try:
            readme_bytes = self._http_fn(readme_url, self._timeout, headers)
            readme_data = json.loads(readme_bytes)
            encoded_content = readme_data.get("content", "")
            # GitHub API wraps content in base64 with newlines
            if readme_data.get("encoding") == "base64":
                readme_text = base64.b64decode(
                    encoded_content.replace("\n", "")
                ).decode("utf-8", errors="replace")
            else:
                readme_text = encoded_content
        except FetchError:
            # 404 or other error fetching README — acceptable, use empty string
            readme_text = ""
        except (json.JSONDecodeError, UnicodeDecodeError, Exception):
            readme_text = ""

        return {
            "repo_url": canonical_url,
            "readme_text": readme_text,
            "description": description,
            "stars": stars,
            "forks": forks,
            "license": license_name,
            "last_commit_date": last_commit_date,
        }


# ---------------------------------------------------------------------------
# LiveBlogFetcher
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
_META_NAME_RE = re.compile(
    r'<meta\s[^>]*name=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_PROP_RE = re.compile(
    r'<meta\s[^>]*property=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class LiveBlogFetcher:
    """Fetch a blog post or news article via plain HTTP GET.

    Uses regex-based HTML extraction (no BeautifulSoup dependency).

    Returns a raw_source dict with keys:
        url, title, body_text, author, published_date, publisher

    Compatible with BlogNewsAdapter.adapt().
    """

    def __init__(self, timeout: int = 15, _http_fn: Optional[Callable] = None) -> None:
        self._timeout = timeout
        self._http_fn = _http_fn if _http_fn is not None else _default_urlopen

    def fetch(self, url: str) -> dict:
        """Fetch and parse the HTML at *url*.

        Returns
        -------
        dict
            Keys: url, title, body_text, author, published_date, publisher.
            Missing optional fields are returned as None.

        Raises
        ------
        FetchError
            On network or HTTP errors.
        """
        html_bytes = self._http_fn(url, self._timeout, {})
        # Decode with UTF-8 fallback to latin-1
        try:
            html = html_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html = html_bytes.decode("latin-1")

        # --- Title ---
        title_match = _TITLE_RE.search(html)
        title = title_match.group(1).strip() if title_match else None

        # --- Collect meta name attributes ---
        meta_name: dict[str, str] = {}
        for m in _META_NAME_RE.finditer(html):
            meta_name[m.group(1).lower()] = m.group(2)

        # --- Collect meta property attributes ---
        meta_prop: dict[str, str] = {}
        for m in _META_PROP_RE.finditer(html):
            meta_prop[m.group(1).lower()] = m.group(2)

        # --- Author ---
        author: Optional[str] = (
            meta_name.get("author")
            or meta_prop.get("og:article:author")
            or meta_prop.get("article:author")
            or None
        )

        # --- Published date ---
        raw_date: Optional[str] = (
            meta_prop.get("article:published_time")
            or meta_prop.get("og:article:published_time")
            or None
        )
        published_date: Optional[str] = raw_date[:10] if raw_date else None

        # --- Publisher ---
        publisher: Optional[str] = meta_prop.get("og:site_name") or None

        # --- Body text: strip all HTML tags, collapse whitespace ---
        body_text = _HTML_TAG_RE.sub(" ", html)
        body_text = _WHITESPACE_RE.sub(" ", body_text).strip()
        body_text = body_text[:50000]

        return {
            "url": url,
            "title": title,
            "body_text": body_text,
            "author": author,
            "published_date": published_date,
            "publisher": publisher,
        }


# ---------------------------------------------------------------------------
# clean_transcript — pure function for VTT/YouTube transcript cleaning
# ---------------------------------------------------------------------------

# VTT timestamp line: "00:00:01.000 --> 00:00:03.000" (with optional position/align)
_VTT_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}.*$", re.MULTILINE)
# Inline timestamps: "<00:00:05.000>"
_INLINE_TIMESTAMP_RE = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
# Sponsor / boilerplate patterns (case-insensitive line-level matching)
_SPONSOR_PATTERNS = [
    re.compile(r".*\bsponsored by\b.*", re.IGNORECASE),
    re.compile(r".*\blike and subscribe\b.*", re.IGNORECASE),
    re.compile(r".*\bsmash the like button\b.*", re.IGNORECASE),
    re.compile(r".*\bsubscribe to the channel\b.*", re.IGNORECASE),
    re.compile(r".*\blink in (?:the )?description\b.*", re.IGNORECASE),
    re.compile(r".*\buse code\b.*\bfor.*\b(?:off|discount)\b.*", re.IGNORECASE),
]
# Collapse whitespace
_MULTI_SPACE_RE = re.compile(r"  +")


def clean_transcript(text: str) -> str:
    """Strip VTT noise and boilerplate from a YouTube transcript string.

    Steps applied in order:
    1. Remove the WEBVTT header line.
    2. Remove VTT timestamp range lines (``HH:MM:SS.mmm --> HH:MM:SS.mmm``).
    3. Remove inline timestamps (``<HH:MM:SS.mmm>``).
    4. Remove align/position directive lines (``align:start position:0%`` etc.).
    5. Remove sponsor boilerplate lines (see ``_SPONSOR_PATTERNS``).
    6. Deduplicate consecutive identical lines.
    7. Collapse multiple spaces.
    8. Strip leading/trailing whitespace.

    Parameters
    ----------
    text:
        Raw VTT or transcript string.

    Returns
    -------
    str
        Cleaned transcript.  Empty string if *text* is empty or whitespace-only.
    """
    if not text or not text.strip():
        return ""

    # 1. Remove WEBVTT header
    lines = text.replace("\r\n", "\n").split("\n")

    cleaned_lines = []
    prev_line = None
    for line in lines:
        # Remove WEBVTT header
        if line.strip() == "WEBVTT":
            continue

        # Remove VTT timestamp range lines
        if _VTT_TIMESTAMP_RE.match(line.strip()):
            continue

        # Remove align/position directive lines
        if re.match(r"^\s*(?:align|position|line|size):", line, re.IGNORECASE):
            continue

        # Remove inline timestamps from the line
        line = _INLINE_TIMESTAMP_RE.sub("", line)

        # Remove sponsor/boilerplate lines
        skip = False
        for pattern in _SPONSOR_PATTERNS:
            if pattern.match(line.strip()):
                skip = True
                break
        if skip:
            continue

        # Deduplicate consecutive identical lines
        stripped = line.strip()
        if stripped == prev_line:
            continue
        prev_line = stripped

        if stripped:
            cleaned_lines.append(stripped)

    result = " ".join(cleaned_lines)
    # Collapse multiple spaces
    result = _MULTI_SPACE_RE.sub(" ", result).strip()
    return result


# ---------------------------------------------------------------------------
# LiveRedditFetcher
# ---------------------------------------------------------------------------


class LiveRedditFetcher:
    """Fetch a Reddit post and its top comments.

    Offline mode: Use ``fetch_raw(raw_post_dict)`` to bypass network entirely.
    Live mode: Requires ``praw_instance`` — install praw and create a Reddit
    script app at reddit.com/prefs/apps, then pass a ``praw.Reddit`` instance.

    PRAW is NEVER imported at module level.  Missing praw raises ``FetchError``
    inside ``fetch()``, not at import time.

    Returns a raw_source dict compatible with ``RedditAdapter.adapt()``.
    """

    def __init__(
        self,
        praw_instance=None,
        _fetch_fn=None,
    ) -> None:
        self._praw = praw_instance
        self._fetch_fn = _fetch_fn  # reserved for future injectable use

    def fetch_raw(self, raw_post_dict: dict) -> dict:
        """Return *raw_post_dict* immediately (offline/fixture mode).

        Parameters
        ----------
        raw_post_dict:
            Pre-built dict matching the RedditAdapter contract.

        Returns
        -------
        dict
            The same dict, unchanged.
        """
        return raw_post_dict

    def fetch(self, url: str) -> dict:
        """Fetch a Reddit post from *url* using PRAW.

        Requires ``praw_instance`` to be set.  Without it, raises
        ``FetchError`` with instructions to use ``fetch_raw()`` instead.

        Parameters
        ----------
        url:
            Full Reddit post URL.

        Returns
        -------
        dict
            Keys: url, title, body_text, author, published_date,
                  subreddit, score, num_comments, top_comments (list[str]).

        Raises
        ------
        FetchError
            If praw is not installed or praw_instance is not set.
        """
        if self._praw is None:
            # Attempt to import praw to check availability
            try:
                import praw as _praw_mod  # noqa: F401
            except ImportError:
                raise FetchError(
                    "praw is required for live Reddit fetching -- "
                    "install praw or use fetch_raw() with a fixture dict."
                )
            raise FetchError(
                "PRAW not available -- pass raw fixture dict via fetch_raw() "
                "or provide a praw_instance to LiveRedditFetcher()."
            )

        # Live PRAW path
        try:
            submission = self._praw.submission(url=url)
            submission.comments.replace_more(limit=0)
            top_comments = [
                comment.body
                for comment in submission.comments.list()[:5]
            ]
            import datetime as _dt
            published_date = (
                _dt.datetime.utcfromtimestamp(submission.created_utc).strftime("%Y-%m-%d")
                if hasattr(submission, "created_utc")
                else None
            )
            return {
                "url": url,
                "title": submission.title,
                "body_text": submission.selftext or "",
                "author": str(submission.author) if submission.author else "unknown",
                "published_date": published_date,
                "subreddit": str(submission.subreddit),
                "score": submission.score,
                "num_comments": submission.num_comments,
                "top_comments": top_comments,
            }
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(f"PRAW fetch failed for {url}: {exc}") from exc


# ---------------------------------------------------------------------------
# LiveYouTubeFetcher
# ---------------------------------------------------------------------------


class LiveYouTubeFetcher:
    """Fetch YouTube video metadata and transcript via yt-dlp.

    Offline mode: Use ``fetch_raw(raw_dict)`` to bypass subprocess entirely.
    Live mode: Requires yt-dlp installed.  No API key needed.

    yt-dlp is NEVER imported at module level.  Missing yt-dlp raises
    ``FetchError`` inside ``fetch()``.

    Duration filter: raises ``FetchError`` if duration < 180s or > 3600s.

    Returns a raw_source dict compatible with ``YouTubeAdapter.adapt()``.
    """

    def __init__(self, _subprocess_fn=None) -> None:
        self._subprocess_fn = _subprocess_fn

    def fetch_raw(self, raw_dict: dict) -> dict:
        """Return *raw_dict* immediately (offline/fixture mode).

        Parameters
        ----------
        raw_dict:
            Pre-built dict matching the YouTubeAdapter contract.

        Returns
        -------
        dict
            The same dict, unchanged.
        """
        return raw_dict

    def fetch(self, url: str) -> dict:
        """Fetch YouTube video metadata and transcript from *url*.

        Uses yt-dlp subprocess calls.

        Parameters
        ----------
        url:
            YouTube video URL.

        Returns
        -------
        dict
            Keys: url, title, transcript_text, channel, published_date,
                  duration_seconds, view_count.

        Raises
        ------
        FetchError
            If yt-dlp is not found, if duration is out of range, or on
            any subprocess/IO failure.
        """
        import subprocess
        import tempfile
        import os as _os

        _run = self._subprocess_fn

        def _run_ytdlp(*args, **kwargs):
            if _run is not None:
                return _run(*args, **kwargs)
            return subprocess.run(*args, **kwargs)

        # Fetch metadata via yt-dlp --dump-json
        try:
            meta_result = _run_ytdlp(
                ["yt-dlp", "--dump-json", "--no-playlist", url],
                capture_output=True,
                text=True,
            )
            if meta_result.returncode != 0:
                raise FetchError(
                    f"yt-dlp metadata fetch failed (exit {meta_result.returncode}): "
                    f"{meta_result.stderr.strip()}"
                )
            meta = json.loads(meta_result.stdout)
        except FetchError:
            raise
        except OSError as exc:
            raise FetchError(f"yt-dlp not found: {exc}") from exc
        except Exception as exc:
            raise FetchError(f"yt-dlp metadata error for {url}: {exc}") from exc

        duration = meta.get("duration", 0) or 0
        if duration < 180:
            raise FetchError(
                f"Video too short ({duration}s < 180s), skipping: {url}"
            )
        if duration > 3600:
            raise FetchError(
                f"Video too long ({duration}s > 3600s), skipping: {url}"
            )

        title = meta.get("title", "")
        channel = meta.get("uploader") or meta.get("channel") or ""
        upload_date = meta.get("upload_date", "")
        published_date = (
            f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
            if upload_date and len(upload_date) == 8
            else None
        )
        view_count = meta.get("view_count", 0) or 0

        # Fetch transcript via yt-dlp --write-auto-sub
        transcript_text = ""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                sub_result = _run_ytdlp(
                    [
                        "yt-dlp",
                        "--write-auto-sub",
                        "--skip-download",
                        "--sub-langs", "en",
                        "--sub-format", "vtt",
                        "-o", _os.path.join(tmpdir, "%(id)s.%(ext)s"),
                        url,
                    ],
                    capture_output=True,
                    text=True,
                )
                # Find the VTT file
                vtt_files = [
                    f for f in _os.listdir(tmpdir)
                    if f.endswith(".vtt")
                ]
                if vtt_files:
                    vtt_path = _os.path.join(tmpdir, vtt_files[0])
                    raw_vtt = open(vtt_path, encoding="utf-8").read()
                    transcript_text = clean_transcript(raw_vtt)
        except FetchError:
            raise
        except Exception:
            transcript_text = ""

        return {
            "url": url,
            "title": title,
            "transcript_text": transcript_text,
            "channel": channel,
            "published_date": published_date,
            "duration_seconds": duration,
            "view_count": view_count,
        }


# ---------------------------------------------------------------------------
# Registry and factory
# ---------------------------------------------------------------------------

FETCHER_REGISTRY: dict[str, type] = {
    "academic": LiveAcademicFetcher,
    "github": LiveGitHubFetcher,
    "blog": LiveBlogFetcher,
    "news": LiveBlogFetcher,
    "reddit": LiveRedditFetcher,
    "youtube": LiveYouTubeFetcher,
}


def get_fetcher(family: str, **kwargs) -> "LiveAcademicFetcher | LiveGitHubFetcher | LiveBlogFetcher | LiveRedditFetcher | LiveYouTubeFetcher":
    """Return a fresh fetcher instance for *family*.

    Parameters
    ----------
    family:
        Source-family key ("academic", "github", "blog", "news", "reddit", "youtube").
    **kwargs:
        Passed to the fetcher constructor.

    Returns
    -------
    fetcher instance

    Raises
    ------
    KeyError
        If *family* is not in FETCHER_REGISTRY.
    """
    cls = FETCHER_REGISTRY[family]
    return cls(**kwargs)
