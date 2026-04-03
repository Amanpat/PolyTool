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
import os
import re
import xml.etree.ElementTree as ET
from typing import Callable, Optional
import urllib.error
import urllib.request


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

    def __init__(self, timeout: int = 15, _http_fn: Optional[Callable] = None) -> None:
        self._timeout = timeout
        self._http_fn = _http_fn if _http_fn is not None else _default_urlopen

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

        return {
            "url": canonical_url,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published_date": published_date,
        }


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
# Registry and factory
# ---------------------------------------------------------------------------

FETCHER_REGISTRY: dict[str, type] = {
    "academic": LiveAcademicFetcher,
    "github": LiveGitHubFetcher,
    "blog": LiveBlogFetcher,
    "news": LiveBlogFetcher,
}


def get_fetcher(family: str, **kwargs) -> "LiveAcademicFetcher | LiveGitHubFetcher | LiveBlogFetcher":
    """Return a fresh fetcher instance for *family*.

    Parameters
    ----------
    family:
        Source-family key ("academic", "github", "blog", "news").
    **kwargs:
        Passed to the fetcher constructor.

    Returns
    -------
    LiveAcademicFetcher | LiveGitHubFetcher | LiveBlogFetcher

    Raises
    ------
    KeyError
        If *family* is not in FETCHER_REGISTRY.
    """
    cls = FETCHER_REGISTRY[family]
    return cls(**kwargs)
