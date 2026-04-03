"""Tests for RIS Phase 5 live fetchers — all offline via injectable _http_fn."""

from __future__ import annotations

import base64
import json
import textwrap
from typing import Callable

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_arxiv_xml(
    arxiv_id: str = "2301.12345",
    title: str = "Test Paper Title",
    abstract: str = "This is the abstract.",
    authors: list[str] | None = None,
    published: str = "2023-01-30T00:00:00Z",
) -> bytes:
    """Build a minimal arXiv Atom API XML response."""
    if authors is None:
        authors = ["Alice Smith", "Bob Jones"]
    author_xml = "\n".join(
        f"    <author><name>{a}</name></author>" for a in authors
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>{title}</title>
    <summary>{abstract}</summary>
{author_xml}
    <published>{published}</published>
  </entry>
</feed>"""
    return xml.encode("utf-8")


def _make_github_repo_json(
    description: str = "A great repo",
    stars: int = 42,
    forks: int = 7,
    license_spdx: str | None = "MIT",
    pushed_at: str = "2024-03-15T12:00:00Z",
) -> bytes:
    data = {
        "description": description,
        "stargazers_count": stars,
        "forks_count": forks,
        "pushed_at": pushed_at,
    }
    if license_spdx is not None:
        data["license"] = {"spdx_id": license_spdx, "name": "MIT License"}
    return json.dumps(data).encode("utf-8")


def _make_github_readme_json(readme_text: str = "# My Readme\n\nHello world") -> bytes:
    content = base64.b64encode(readme_text.encode("utf-8")).decode("ascii")
    return json.dumps({"content": content, "encoding": "base64"}).encode("utf-8")


def _make_blog_html(
    title: str = "Test Blog Post",
    body: str = "<p>This is the body of the article.</p>",
    author: str | None = "Jane Doe",
    published: str | None = "2024-01-15T10:00:00Z",
    publisher: str | None = "Test Blog",
) -> bytes:
    meta_tags = ""
    if author:
        meta_tags += f'<meta name="author" content="{author}">\n'
    if published:
        meta_tags += f'<meta property="article:published_time" content="{published}">\n'
    if publisher:
        meta_tags += f'<meta property="og:site_name" content="{publisher}">\n'
    html = f"""<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
{meta_tags}
</head>
<body>
{body}
</body>
</html>"""
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# LiveAcademicFetcher tests
# ---------------------------------------------------------------------------


class TestLiveAcademicFetcher:
    def _make_fetcher(self, responses: dict) -> "LiveAcademicFetcher":
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        def http_fn(url: str, timeout: int, headers: dict) -> bytes:
            for key, val in responses.items():
                if key in url:
                    if isinstance(val, Exception):
                        raise val
                    return val
            raise AssertionError(f"Unexpected URL in test: {url}")

        return LiveAcademicFetcher(_http_fn=http_fn)

    def test_fetch_abs_url_returns_correct_dict(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        xml_bytes = _make_arxiv_xml(
            arxiv_id="2301.12345",
            title="My Paper",
            abstract="Great abstract",
            authors=["Alice", "Bob"],
            published="2023-01-30T00:00:00Z",
        )
        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, timeout, headers: xml_bytes
        )
        result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
        assert result["url"] == "https://arxiv.org/abs/2301.12345"
        assert result["title"] == "My Paper"
        assert result["abstract"] == "Great abstract"
        assert result["authors"] == ["Alice", "Bob"]
        assert result["published_date"] == "2023-01-30"

    def test_fetch_pdf_url_normalizes_to_abs(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        xml_bytes = _make_arxiv_xml(arxiv_id="2301.12345")
        captured_urls = []

        def http_fn(url, timeout, headers):
            captured_urls.append(url)
            return xml_bytes

        fetcher = LiveAcademicFetcher(_http_fn=http_fn)
        result = fetcher.fetch("https://arxiv.org/pdf/2301.12345")
        # The result URL should be the abs form
        assert result["url"] == "https://arxiv.org/abs/2301.12345"
        # The API call should use /abs/ form
        assert any("abs" in u or "export.arxiv.org" in u for u in captured_urls)

    def test_fetch_raises_error_on_http_error(self):
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher
        import urllib.error

        def http_fn(url, timeout, headers):
            raise FetchError("HTTP 503: Service Unavailable")

        fetcher = LiveAcademicFetcher(_http_fn=http_fn)
        with pytest.raises(FetchError):
            fetcher.fetch("https://arxiv.org/abs/2301.12345")

    def test_fetch_raises_error_on_no_entry(self):
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher
        empty_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, timeout, headers: empty_xml)
        with pytest.raises(FetchError, match="no results"):
            fetcher.fetch("https://arxiv.org/abs/9999.99999")

    def test_fetch_strips_whitespace_from_title_and_abstract(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        xml_bytes = _make_arxiv_xml(
            title="  Whitespace Paper  ",
            abstract="\n  Multiline abstract\n  continues here\n  ",
        )
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, timeout, headers: xml_bytes)
        result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
        assert result["title"] == "Whitespace Paper"
        assert result["abstract"] == "Multiline abstract\n  continues here"

    def test_fetch_multiple_authors(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        xml_bytes = _make_arxiv_xml(authors=["Author One", "Author Two", "Author Three"])
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, timeout, headers: xml_bytes)
        result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
        assert result["authors"] == ["Author One", "Author Two", "Author Three"]

    def test_output_passes_into_academic_adapter(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        from packages.research.ingestion.adapters import AcademicAdapter
        xml_bytes = _make_arxiv_xml()
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, timeout, headers: xml_bytes)
        result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
        adapter = AcademicAdapter()
        doc = adapter.adapt(result)
        assert doc.title
        assert doc.source_family == "academic"


# ---------------------------------------------------------------------------
# LiveGitHubFetcher tests
# ---------------------------------------------------------------------------


class TestLiveGitHubFetcher:
    def _make_fetcher(self, repo_bytes: bytes, readme_bytes: bytes | None = None, token: str | None = None):
        from packages.research.ingestion.fetchers import FetchError, LiveGitHubFetcher

        call_count = {"repo": 0, "readme": 0}

        def http_fn(url, timeout, headers):
            if "readme" in url.lower():
                call_count["readme"] += 1
                if readme_bytes is None:
                    from urllib.error import HTTPError
                    raise FetchError("404 Not Found")
                return readme_bytes
            else:
                call_count["repo"] += 1
                return repo_bytes

        fetcher = LiveGitHubFetcher(token=token, _http_fn=http_fn)
        fetcher._call_count = call_count
        return fetcher

    def test_fetch_returns_correct_dict(self):
        repo = _make_github_repo_json(description="Test repo", stars=100, forks=10, license_spdx="MIT")
        readme = _make_github_readme_json("# Test Readme")
        fetcher = self._make_fetcher(repo, readme)
        result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
        assert result["repo_url"] == "https://github.com/polymarket/py-clob-client"
        assert result["description"] == "Test repo"
        assert result["stars"] == 100
        assert result["forks"] == 10
        assert result["license"] == "MIT"
        assert result["last_commit_date"] == "2024-03-15"
        assert "# Test Readme" in result["readme_text"]

    def test_token_is_propagated_in_headers(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher
        captured_headers = []

        def http_fn(url, timeout, headers):
            captured_headers.append(dict(headers))
            if "readme" in url.lower():
                return _make_github_readme_json()
            return _make_github_repo_json()

        fetcher = LiveGitHubFetcher(token="mytoken123", _http_fn=http_fn)
        fetcher.fetch("https://github.com/polymarket/py-clob-client")
        # At least one call should have the Authorization header
        assert any("Authorization" in h and "mytoken123" in h["Authorization"] for h in captured_headers)

    def test_no_token_omits_auth_header(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher
        captured_headers = []

        def http_fn(url, timeout, headers):
            captured_headers.append(dict(headers))
            if "readme" in url.lower():
                return _make_github_readme_json()
            return _make_github_repo_json()

        fetcher = LiveGitHubFetcher(token=None, _http_fn=http_fn)
        # Temporarily clear env var
        import os
        old = os.environ.pop("GITHUB_TOKEN", None)
        try:
            fetcher2 = LiveGitHubFetcher(token=None, _http_fn=http_fn)
            fetcher2.fetch("https://github.com/polymarket/py-clob-client")
        finally:
            if old is not None:
                os.environ["GITHUB_TOKEN"] = old
        # Authorization header should not be present
        assert not any("Authorization" in h for h in captured_headers)

    def test_readme_404_falls_back_to_empty(self):
        from packages.research.ingestion.fetchers import FetchError, LiveGitHubFetcher

        def http_fn(url, timeout, headers):
            if "readme" in url.lower():
                raise FetchError("404 Not Found")
            return _make_github_repo_json()

        fetcher = LiveGitHubFetcher(_http_fn=http_fn)
        result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
        assert result["readme_text"] == ""

    def test_invalid_url_raises_fetch_error(self):
        from packages.research.ingestion.fetchers import FetchError, LiveGitHubFetcher
        fetcher = LiveGitHubFetcher(_http_fn=lambda url, timeout, headers: b"{}")
        with pytest.raises(FetchError):
            fetcher.fetch("https://not-github.com/some/repo")

    def test_no_license_field(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher
        repo = _make_github_repo_json(license_spdx=None)
        readme = _make_github_readme_json()
        fetcher = self._make_fetcher(repo, readme)
        result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
        assert result["license"] is None

    def test_output_passes_into_github_adapter(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher
        from packages.research.ingestion.adapters import GithubAdapter
        repo = _make_github_repo_json()
        readme = _make_github_readme_json()
        fetcher = self._make_fetcher(repo, readme)
        result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
        adapter = GithubAdapter()
        doc = adapter.adapt(result)
        assert doc.source_family == "github"
        assert doc.title


# ---------------------------------------------------------------------------
# LiveBlogFetcher tests
# ---------------------------------------------------------------------------


class TestLiveBlogFetcher:
    def _make_fetcher(self, html_bytes: bytes):
        from packages.research.ingestion.fetchers import LiveBlogFetcher
        return LiveBlogFetcher(_http_fn=lambda url, timeout, headers: html_bytes)

    def test_fetch_returns_correct_dict_keys(self):
        html = _make_blog_html(title="My Article", author="Jane Doe")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/my-article")
        assert result["url"] == "https://blog.example.com/my-article"
        assert "title" in result
        assert "body_text" in result
        assert "author" in result
        assert "published_date" in result
        assert "publisher" in result

    def test_fetch_extracts_title(self):
        html = _make_blog_html(title="My Blog Article")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["title"] == "My Blog Article"

    def test_fetch_strips_html_tags_from_body(self):
        html = _make_blog_html(body="<p>Hello <b>world</b>!</p><div>More text</div>")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert "<p>" not in result["body_text"]
        assert "<b>" not in result["body_text"]
        assert "Hello" in result["body_text"]
        assert "world" in result["body_text"]

    def test_fetch_extracts_author_from_name_meta(self):
        html = _make_blog_html(author="Jane Doe")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["author"] == "Jane Doe"

    def test_fetch_extracts_author_from_og_property(self):
        html = b"""<html><head>
<title>Test</title>
<meta property="og:article:author" content="OG Author">
</head><body>content</body></html>"""
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["author"] == "OG Author"

    def test_fetch_extracts_published_date(self):
        html = _make_blog_html(published="2024-01-15T10:00:00Z")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["published_date"] == "2024-01-15"

    def test_fetch_extracts_publisher(self):
        html = _make_blog_html(publisher="Test Publisher")
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["publisher"] == "Test Publisher"

    def test_fetch_returns_none_for_missing_meta(self):
        html = b"""<html><head><title>Just a title</title></head>
<body><p>Body text</p></body></html>"""
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert result["author"] is None
        assert result["published_date"] is None
        assert result["publisher"] is None

    def test_body_truncated_at_50000_chars(self):
        big_body = "<p>" + "x" * 100000 + "</p>"
        html = _make_blog_html(body=big_body)
        fetcher = self._make_fetcher(html)
        result = fetcher.fetch("https://blog.example.com/article")
        assert len(result["body_text"]) <= 50000

    def test_fetch_raises_on_http_error(self):
        from packages.research.ingestion.fetchers import FetchError, LiveBlogFetcher

        def http_fn(url, timeout, headers):
            raise FetchError("Connection refused")

        fetcher = LiveBlogFetcher(_http_fn=http_fn)
        with pytest.raises(FetchError):
            fetcher.fetch("https://blog.example.com/article")

    def test_output_passes_into_blognews_adapter(self):
        from packages.research.ingestion.fetchers import LiveBlogFetcher
        from packages.research.ingestion.adapters import BlogNewsAdapter
        html = _make_blog_html(title="Test Article", author="Writer", body="<p>Content</p>")
        fetcher = LiveBlogFetcher(_http_fn=lambda url, timeout, headers: html)
        result = fetcher.fetch("https://blog.example.com/article")
        adapter = BlogNewsAdapter()
        doc = adapter.adapt(result)
        assert doc.title == "Test Article"
        assert doc.source_family in ("blog", "news")


# ---------------------------------------------------------------------------
# FETCHER_REGISTRY and get_fetcher tests
# ---------------------------------------------------------------------------


class TestFetcherRegistry:
    def test_get_fetcher_academic(self):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher, get_fetcher
        fetcher = get_fetcher("academic")
        assert isinstance(fetcher, LiveAcademicFetcher)

    def test_get_fetcher_github(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher, get_fetcher
        fetcher = get_fetcher("github")
        assert isinstance(fetcher, LiveGitHubFetcher)

    def test_get_fetcher_blog(self):
        from packages.research.ingestion.fetchers import LiveBlogFetcher, get_fetcher
        fetcher = get_fetcher("blog")
        assert isinstance(fetcher, LiveBlogFetcher)

    def test_get_fetcher_news_returns_blog_fetcher(self):
        from packages.research.ingestion.fetchers import LiveBlogFetcher, get_fetcher
        fetcher = get_fetcher("news")
        assert isinstance(fetcher, LiveBlogFetcher)

    def test_get_fetcher_unknown_raises(self):
        from packages.research.ingestion.fetchers import get_fetcher
        with pytest.raises(KeyError):
            get_fetcher("unknown_family")

    def test_get_fetcher_passes_kwargs(self):
        from packages.research.ingestion.fetchers import LiveGitHubFetcher, get_fetcher
        fetcher = get_fetcher("github", token="tok123")
        assert isinstance(fetcher, LiveGitHubFetcher)
        assert fetcher._token == "tok123"


# ---------------------------------------------------------------------------
# _default_urlopen tests
# ---------------------------------------------------------------------------


class TestDefaultUrlopen:
    def test_raises_fetch_error_on_url_error(self):
        """_default_urlopen wraps URLError in FetchError."""
        from packages.research.ingestion.fetchers import FetchError, _default_urlopen
        import urllib.error

        # Patch urllib.request.urlopen to raise URLError
        import unittest.mock as mock
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(FetchError):
                _default_urlopen("http://localhost:1/nope", timeout=1, headers={})

    def test_raises_fetch_error_on_timeout(self):
        from packages.research.ingestion.fetchers import FetchError, _default_urlopen
        import socket
        import unittest.mock as mock
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            with pytest.raises(FetchError):
                _default_urlopen("http://localhost:1/nope", timeout=1, headers={})


# ---------------------------------------------------------------------------
# @pytest.mark.live smoke tests (skipped in offline runs)
# ---------------------------------------------------------------------------


@pytest.mark.live
class TestLiveSmoke:
    def test_arxiv_live(self):
        """Smoke: fetch a known arXiv paper."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        fetcher = LiveAcademicFetcher(timeout=15)
        result = fetcher.fetch("https://arxiv.org/abs/2301.12345")
        assert "title" in result
        assert "abstract" in result
        assert isinstance(result["authors"], list)

    def test_github_live(self):
        """Smoke: fetch a known public GitHub repo."""
        from packages.research.ingestion.fetchers import LiveGitHubFetcher
        fetcher = LiveGitHubFetcher(timeout=15)
        result = fetcher.fetch("https://github.com/polymarket/py-clob-client")
        assert "repo_url" in result
        assert "readme_text" in result
        assert result["stars"] >= 0

    def test_blog_live(self):
        """Smoke: fetch a known blog page."""
        from packages.research.ingestion.fetchers import LiveBlogFetcher
        fetcher = LiveBlogFetcher(timeout=15)
        result = fetcher.fetch("https://blog.polymarket.com")
        assert "title" in result
        assert "body_text" in result
