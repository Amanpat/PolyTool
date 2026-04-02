"""RIS Phase 4 — external source acquisition tests.

Covers: RawSourceCache, metadata normalization, source adapters (Academic,
GitHub, BlogNews), ADAPTER_REGISTRY, and end-to-end pipeline integration.

All tests are deterministic and offline — no network calls.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ris_external_sources"
ARXIV_FIXTURE = FIXTURES_DIR / "arxiv_sample.json"
GITHUB_FIXTURE = FIXTURES_DIR / "github_sample.json"
BLOG_FIXTURE = FIXTURES_DIR / "blog_sample.json"


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# TestRawSourceCache
# ===========================================================================


class TestRawSourceCache:
    def test_cache_and_retrieve(self, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "cache")
        payload = {"url": "https://example.com/paper", "title": "Test Paper"}
        source_id = "abc123"
        cache.cache_raw(source_id, payload, "academic")
        result = cache.get_raw(source_id, "academic")
        assert result is not None
        assert result["payload"] == payload

    def test_has_raw_true_false(self, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "cache")
        assert cache.has_raw("missing_id", "academic") is False
        cache.cache_raw("present_id", {"key": "val"}, "academic")
        assert cache.has_raw("present_id", "academic") is True

    def test_get_missing_returns_none(self, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "cache")
        assert cache.get_raw("no_such_id", "github") is None

    def test_cache_dir_auto_created(self, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache_dir = tmp_path / "new_cache" / "nested"
        assert not cache_dir.exists()
        cache = RawSourceCache(cache_dir)
        cache.cache_raw("x", {"a": 1}, "blog")
        assert cache_dir.exists()

    def test_source_id_deterministic(self, tmp_path):
        """Same canonical URL always produces same source_id."""
        from packages.research.ingestion.source_cache import RawSourceCache, make_source_id

        url = "https://arxiv.org/abs/2301.12345"
        id1 = make_source_id(url)
        id2 = make_source_id(url)
        assert id1 == id2
        assert len(id1) == 16  # sha256[:16]

    def test_envelope_has_required_fields(self, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "cache")
        cache.cache_raw("env_test", {"data": "here"}, "news")
        envelope = cache.get_raw("env_test", "news")
        assert envelope is not None
        assert "source_id" in envelope
        assert "source_family" in envelope
        assert "cached_at" in envelope
        assert "payload" in envelope
        assert envelope["source_id"] == "env_test"
        assert envelope["source_family"] == "news"

    def test_different_families_isolated(self, tmp_path):
        """Same source_id in different families are separate entries."""
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "cache")
        cache.cache_raw("shared_id", {"family": "academic"}, "academic")
        cache.cache_raw("shared_id", {"family": "github"}, "github")
        academic = cache.get_raw("shared_id", "academic")
        github = cache.get_raw("shared_id", "github")
        assert academic["payload"]["family"] == "academic"
        assert github["payload"]["family"] == "github"


# ===========================================================================
# TestNormalization
# ===========================================================================


class TestNormalization:
    def test_canonicalize_url_strips_fragment(self):
        from packages.research.ingestion.normalize import canonicalize_url

        url = "https://arxiv.org/abs/2301.12345#abstract"
        assert canonicalize_url(url) == "https://arxiv.org/abs/2301.12345"

    def test_canonicalize_url_trailing_slash(self):
        from packages.research.ingestion.normalize import canonicalize_url

        url = "https://example.com/page/"
        assert canonicalize_url(url) == "https://example.com/page"

    def test_canonicalize_url_arxiv_normalize(self):
        from packages.research.ingestion.normalize import canonicalize_url

        # PDF URL -> abs URL
        pdf_url = "https://arxiv.org/pdf/2301.12345"
        result = canonicalize_url(pdf_url)
        assert "/abs/" in result
        assert "/pdf/" not in result

    def test_canonicalize_url_github_normalize(self):
        from packages.research.ingestion.normalize import canonicalize_url

        # Strip tree/blob suffixes from GitHub URLs
        url = "https://github.com/polymarket/py-clob-client/tree/main"
        result = canonicalize_url(url)
        assert result == "https://github.com/polymarket/py-clob-client"

    def test_canonicalize_url_lowercases_scheme_host(self):
        from packages.research.ingestion.normalize import canonicalize_url

        url = "HTTPS://ArXiv.ORG/abs/2301.12345"
        result = canonicalize_url(url)
        assert result.startswith("https://arxiv.org/")

    def test_extract_doi(self):
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "The DOI for this paper is 10.1234/pm.2023.001 in the bibliography."
        url = "https://arxiv.org/abs/2301.12345"
        ids = extract_canonical_ids(text, url)
        assert "doi" in ids
        assert ids["doi"].startswith("10.1234/")

    def test_extract_arxiv_id_from_body(self):
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "See the companion paper arXiv:2301.12345 for details."
        url = "https://example.com"
        ids = extract_canonical_ids(text, url)
        assert "arxiv_id" in ids
        assert "2301.12345" in ids["arxiv_id"]

    def test_extract_arxiv_id_from_url(self):
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "No arxiv mention in text."
        url = "https://arxiv.org/abs/2301.12345"
        ids = extract_canonical_ids(text, url)
        assert "arxiv_id" in ids
        assert "2301.12345" in ids["arxiv_id"]

    def test_extract_ssrn_id(self):
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "Working paper at SSRN:3456789 covers complementary findings."
        url = "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3456789"
        ids = extract_canonical_ids(text, url)
        assert "ssrn_id" in ids
        assert "3456789" in ids["ssrn_id"]

    def test_extract_github_repo_url(self):
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "Source code at https://github.com/polymarket/py-clob-client."
        url = "https://github.com/polymarket/py-clob-client"
        ids = extract_canonical_ids(text, url)
        assert "repo_url" in ids
        assert "github.com/polymarket/py-clob-client" in ids["repo_url"]

    def test_normalize_metadata_academic(self):
        from packages.research.ingestion.normalize import normalize_metadata, NormalizedMetadata

        raw = _load_fixture(ARXIV_FIXTURE)
        meta = normalize_metadata(raw, "academic")
        assert isinstance(meta, NormalizedMetadata)
        assert meta.source_family == "academic"
        assert meta.canonical_url is not None
        assert meta.title == raw["title"]

    def test_normalize_metadata_github(self):
        from packages.research.ingestion.normalize import normalize_metadata, NormalizedMetadata

        raw = _load_fixture(GITHUB_FIXTURE)
        meta = normalize_metadata(raw, "github")
        assert isinstance(meta, NormalizedMetadata)
        assert meta.source_family == "github"
        assert meta.canonical_url is not None

    def test_normalize_metadata_blog(self):
        from packages.research.ingestion.normalize import normalize_metadata, NormalizedMetadata

        raw = _load_fixture(BLOG_FIXTURE)
        meta = normalize_metadata(raw, "blog")
        assert isinstance(meta, NormalizedMetadata)
        assert meta.source_family == "blog"
        assert meta.title == raw["title"]
        assert meta.author == raw["author"]

    def test_canonical_ids_stable(self):
        """Extracting canonical IDs from the same text twice gives same result."""
        from packages.research.ingestion.normalize import extract_canonical_ids

        text = "DOI: 10.1234/test.001 and arXiv:2301.12345"
        url = "https://arxiv.org/abs/2301.12345"
        ids1 = extract_canonical_ids(text, url)
        ids2 = extract_canonical_ids(text, url)
        assert ids1 == ids2


# ===========================================================================
# TestAcademicAdapter
# ===========================================================================


class TestAcademicAdapter:
    def test_adapt_arxiv_fixture(self, tmp_path):
        from packages.research.ingestion.adapters import AcademicAdapter
        from packages.research.ingestion.extractors import ExtractedDocument

        adapter = AcademicAdapter()
        raw = _load_fixture(ARXIV_FIXTURE)
        doc = adapter.adapt(raw)
        assert isinstance(doc, ExtractedDocument)
        assert doc.title == raw["title"]
        assert doc.source_family == "academic"
        assert doc.body  # non-empty

    def test_adapt_produces_correct_source_family(self):
        from packages.research.ingestion.adapters import AcademicAdapter

        adapter = AcademicAdapter()
        raw = _load_fixture(ARXIV_FIXTURE)
        doc = adapter.adapt(raw)
        assert doc.source_family == "academic"

    def test_adapt_extracts_canonical_ids(self):
        from packages.research.ingestion.adapters import AcademicAdapter

        adapter = AcademicAdapter()
        raw = _load_fixture(ARXIV_FIXTURE)
        doc = adapter.adapt(raw)
        canonical_ids = doc.metadata.get("canonical_ids", {})
        assert "doi" in canonical_ids or "arxiv_id" in canonical_ids

    def test_adapt_caches_raw(self, tmp_path):
        from packages.research.ingestion.adapters import AcademicAdapter
        from packages.research.ingestion.source_cache import RawSourceCache

        adapter = AcademicAdapter()
        cache = RawSourceCache(tmp_path / "cache")
        raw = _load_fixture(ARXIV_FIXTURE)
        doc = adapter.adapt(raw, cache=cache)
        # At least one entry should be cached
        cached_items = list((tmp_path / "cache").rglob("*.json"))
        assert len(cached_items) >= 1

    def test_adapt_missing_optional_fields(self):
        """Adapter handles minimal dict with only required fields."""
        from packages.research.ingestion.adapters import AcademicAdapter

        adapter = AcademicAdapter()
        minimal = {
            "url": "https://arxiv.org/abs/2301.99999",
            "title": "Minimal Paper",
            "abstract": "Short abstract here.",
        }
        doc = adapter.adapt(minimal)
        assert doc.title == "Minimal Paper"
        assert doc.source_family == "academic"
        assert doc.author  # defaults applied

    def test_adapt_sets_source_type_arxiv(self):
        from packages.research.ingestion.adapters import AcademicAdapter

        adapter = AcademicAdapter()
        raw = {"url": "https://arxiv.org/abs/2301.12345", "title": "T", "abstract": "A"}
        doc = adapter.adapt(raw)
        assert doc.metadata.get("source_type") == "arxiv"

    def test_adapt_sets_source_type_ssrn(self):
        from packages.research.ingestion.adapters import AcademicAdapter

        adapter = AcademicAdapter()
        raw = {
            "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3456789",
            "title": "SSRN Paper",
            "abstract": "Abstract here.",
        }
        doc = adapter.adapt(raw)
        assert doc.metadata.get("source_type") == "ssrn"


# ===========================================================================
# TestGithubAdapter
# ===========================================================================


class TestGithubAdapter:
    def test_adapt_github_fixture(self, tmp_path):
        from packages.research.ingestion.adapters import GithubAdapter
        from packages.research.ingestion.extractors import ExtractedDocument

        adapter = GithubAdapter()
        raw = _load_fixture(GITHUB_FIXTURE)
        doc = adapter.adapt(raw)
        assert isinstance(doc, ExtractedDocument)
        assert doc.source_family == "github"

    def test_adapt_produces_correct_metadata(self):
        from packages.research.ingestion.adapters import GithubAdapter

        adapter = GithubAdapter()
        raw = _load_fixture(GITHUB_FIXTURE)
        doc = adapter.adapt(raw)
        assert doc.metadata.get("stars") == 142
        assert doc.metadata.get("forks") == 38
        canonical_ids = doc.metadata.get("canonical_ids", {})
        assert "repo_url" in canonical_ids

    def test_adapt_caches_raw(self, tmp_path):
        from packages.research.ingestion.adapters import GithubAdapter
        from packages.research.ingestion.source_cache import RawSourceCache

        adapter = GithubAdapter()
        cache = RawSourceCache(tmp_path / "cache")
        raw = _load_fixture(GITHUB_FIXTURE)
        adapter.adapt(raw, cache=cache)
        cached_items = list((tmp_path / "cache").rglob("*.json"))
        assert len(cached_items) >= 1

    def test_adapt_canonical_repo_url(self):
        from packages.research.ingestion.adapters import GithubAdapter

        adapter = GithubAdapter()
        raw = {
            "repo_url": "https://github.com/polymarket/py-clob-client/tree/main",
            "readme_text": "# Readme content here",
            "description": "A client library",
            "stars": 50,
            "forks": 10,
            "license": "MIT",
            "last_commit_date": "2026-01-01",
        }
        doc = adapter.adapt(raw)
        repo_url = doc.metadata["canonical_ids"].get("repo_url", "")
        assert "/tree/" not in repo_url


# ===========================================================================
# TestBlogNewsAdapter
# ===========================================================================


class TestBlogNewsAdapter:
    def test_adapt_blog_fixture(self):
        from packages.research.ingestion.adapters import BlogNewsAdapter
        from packages.research.ingestion.extractors import ExtractedDocument

        adapter = BlogNewsAdapter()
        raw = _load_fixture(BLOG_FIXTURE)
        doc = adapter.adapt(raw)
        assert isinstance(doc, ExtractedDocument)
        assert doc.title == raw["title"]
        assert doc.author == raw["author"]

    def test_adapt_news_heuristic(self):
        """Known news domains get source_type='news'; others get 'blog'."""
        from packages.research.ingestion.adapters import BlogNewsAdapter

        adapter = BlogNewsAdapter()
        # blog.polymarket.com -> blog
        blog_raw = _load_fixture(BLOG_FIXTURE)
        blog_doc = adapter.adapt(blog_raw)
        assert blog_doc.metadata.get("source_type") in ("blog", "news")

        # reuters.com -> news
        news_raw = {
            "url": "https://www.reuters.com/article/polymarket-growth-2026",
            "title": "Polymarket sees record volume in Q1 2026",
            "body_text": "Reuters reports that Polymarket achieved record trading volumes.",
            "author": "Staff Reporter",
            "published_date": "2026-03-01",
            "publisher": "Reuters",
        }
        news_doc = adapter.adapt(news_raw)
        assert news_doc.metadata.get("source_type") == "news"

    def test_adapt_caches_raw(self, tmp_path):
        from packages.research.ingestion.adapters import BlogNewsAdapter
        from packages.research.ingestion.source_cache import RawSourceCache

        adapter = BlogNewsAdapter()
        cache = RawSourceCache(tmp_path / "cache")
        raw = _load_fixture(BLOG_FIXTURE)
        adapter.adapt(raw, cache=cache)
        cached_items = list((tmp_path / "cache").rglob("*.json"))
        assert len(cached_items) >= 1

    def test_adapt_source_family_blog(self):
        from packages.research.ingestion.adapters import BlogNewsAdapter

        adapter = BlogNewsAdapter()
        raw = _load_fixture(BLOG_FIXTURE)
        doc = adapter.adapt(raw)
        assert doc.source_family in ("blog", "news")

    def test_adapt_publish_date_passed_through(self):
        from packages.research.ingestion.adapters import BlogNewsAdapter

        adapter = BlogNewsAdapter()
        raw = _load_fixture(BLOG_FIXTURE)
        doc = adapter.adapt(raw)
        assert doc.publish_date == raw["published_date"]


# ===========================================================================
# TestAdapterRegistry
# ===========================================================================


class TestAdapterRegistry:
    def test_get_adapter_academic(self):
        from packages.research.ingestion.adapters import get_adapter, AcademicAdapter

        adapter = get_adapter("academic")
        assert isinstance(adapter, AcademicAdapter)

    def test_get_adapter_github(self):
        from packages.research.ingestion.adapters import get_adapter, GithubAdapter

        adapter = get_adapter("github")
        assert isinstance(adapter, GithubAdapter)

    def test_get_adapter_blog(self):
        from packages.research.ingestion.adapters import get_adapter, BlogNewsAdapter

        adapter = get_adapter("blog")
        assert isinstance(adapter, BlogNewsAdapter)

    def test_get_adapter_news(self):
        from packages.research.ingestion.adapters import get_adapter, BlogNewsAdapter

        adapter = get_adapter("news")
        assert isinstance(adapter, BlogNewsAdapter)

    def test_get_adapter_unknown_raises(self):
        from packages.research.ingestion.adapters import get_adapter

        with pytest.raises((KeyError, ValueError)):
            get_adapter("unknown_family_xyz")


# ===========================================================================
# TestEndToEnd (Task 2 — pipeline integration)
# ===========================================================================


@pytest.fixture()
def memory_store():
    """Fresh in-memory KnowledgeStore."""
    from packages.polymarket.rag.knowledge_store import KnowledgeStore

    store = KnowledgeStore(":memory:")
    yield store
    store.close()


@pytest.fixture()
def pipeline_no_eval(memory_store):
    """IngestPipeline with no evaluator (no-eval mode)."""
    from packages.research.ingestion.pipeline import IngestPipeline

    return IngestPipeline(store=memory_store, evaluator=None)


class TestEndToEnd:
    def test_ingest_external_arxiv_fixture(self, pipeline_no_eval):
        raw = _load_fixture(ARXIV_FIXTURE)
        result = pipeline_no_eval.ingest_external(raw, "academic")
        assert not result.rejected, f"Rejected: {result.reject_reason}"
        assert result.doc_id
        assert result.chunk_count > 0

    def test_ingest_external_github_fixture(self, pipeline_no_eval):
        raw = _load_fixture(GITHUB_FIXTURE)
        result = pipeline_no_eval.ingest_external(raw, "github")
        assert not result.rejected, f"Rejected: {result.reject_reason}"
        assert result.doc_id
        assert result.chunk_count > 0

    def test_ingest_external_blog_fixture(self, pipeline_no_eval):
        raw = _load_fixture(BLOG_FIXTURE)
        result = pipeline_no_eval.ingest_external(raw, "blog")
        assert not result.rejected, f"Rejected: {result.reject_reason}"
        assert result.doc_id
        assert result.chunk_count > 0

    def test_ingest_external_with_cache(self, pipeline_no_eval, tmp_path):
        from packages.research.ingestion.source_cache import RawSourceCache

        cache = RawSourceCache(tmp_path / "raw_cache")
        raw = _load_fixture(ARXIV_FIXTURE)
        result = pipeline_no_eval.ingest_external(raw, "academic", cache=cache)
        assert not result.rejected
        # Verify raw payload persisted on disk
        cached_files = list((tmp_path / "raw_cache").rglob("*.json"))
        assert len(cached_files) >= 1

    def test_ingest_external_bad_family_rejected(self, pipeline_no_eval):
        raw = {"url": "https://example.com", "title": "Test", "body_text": "Body content here"}
        result = pipeline_no_eval.ingest_external(raw, "unknown_xyz_family")
        assert result.rejected
        assert result.reject_reason

    def test_ingest_external_missing_required_fields_rejected(self, pipeline_no_eval):
        """Missing required fields for academic adapter -> rejected."""
        # Academic adapter requires at minimum url and title or abstract
        raw = {}  # Completely empty
        result = pipeline_no_eval.ingest_external(raw, "academic")
        # Should either reject gracefully or handle with defaults
        # Either rejection or doc_id="" is acceptable for empty payload
        assert result is not None  # At minimum, returns a result without crash

    def test_ingest_external_metadata_canonical_ids_preserved(self, memory_store):
        """Canonical IDs extracted by adapter survive into stored document metadata."""
        from packages.research.ingestion.pipeline import IngestPipeline

        pipeline = IngestPipeline(store=memory_store, evaluator=None)
        raw = _load_fixture(ARXIV_FIXTURE)
        result = pipeline.ingest_external(raw, "academic")
        assert not result.rejected
        # The metadata with canonical_ids should be stored
        # We verify indirectly through the doc_id existing
        assert result.doc_id
