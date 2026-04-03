"""Tests for RIS_01 practical v1 scope:
- LiveAcademicFetcher.search_by_topic()
- BookAdapter
- IngestPipeline.ingest_external() with post_ingest_extract kwarg

All tests are offline / deterministic (no network calls).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: minimal Atom XML fixtures
# ---------------------------------------------------------------------------

_ATOM_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
)
_ATOM_FOOTER = "</feed>"


def _atom_entry(
    arxiv_id: str,
    title: str,
    abstract: str,
    authors: list[str],
    published: str = "2023-01-15T00:00:00Z",
) -> str:
    author_xml = "".join(
        f"<author><name>{a}</name></author>" for a in authors
    )
    return (
        f"<entry>"
        f"<id>http://arxiv.org/abs/{arxiv_id}v1</id>"
        f"<title>{title}</title>"
        f"<summary>{abstract}</summary>"
        f"{author_xml}"
        f"<published>{published}</published>"
        f"</entry>"
    )


def _build_atom_feed(*entries: str) -> bytes:
    body = _ATOM_HEADER + "".join(entries) + _ATOM_FOOTER
    return body.encode("utf-8")


def _empty_atom_feed() -> bytes:
    return (_ATOM_HEADER + _ATOM_FOOTER).encode("utf-8")


# ---------------------------------------------------------------------------
# Tests: LiveAcademicFetcher.search_by_topic()
# ---------------------------------------------------------------------------


class TestSearchByTopic:
    """search_by_topic() returns list[dict]; injectable _http_fn for offline tests."""

    def test_two_entries_returns_two_dicts(self) -> None:
        """Returns a list of two dicts when API returns two entries."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        entry1 = _atom_entry(
            "2301.00001",
            "Paper One",
            "Abstract one.",
            ["Alice Smith"],
            "2023-01-10T00:00:00Z",
        )
        entry2 = _atom_entry(
            "2301.00002",
            "Paper Two",
            "Abstract two.",
            ["Bob Jones", "Carol White"],
            "2023-02-20T00:00:00Z",
        )
        feed_bytes = _build_atom_feed(entry1, entry2)

        calls: list = []

        def mock_http(url: str, timeout: int, headers: dict) -> bytes:
            calls.append(url)
            return feed_bytes

        fetcher = LiveAcademicFetcher(_http_fn=mock_http)
        results = fetcher.search_by_topic("prediction markets", max_results=5)

        assert len(results) == 2
        assert len(calls) == 1
        # Verify URL contains the encoded query
        assert "search_query" in calls[0]
        assert "max_results=5" in calls[0]

    def test_result_dict_keys(self) -> None:
        """Each result dict has url, title, abstract, authors, published_date keys."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        entry = _atom_entry(
            "2312.99999",
            "Test Title",
            "Test Abstract",
            ["Author A"],
            "2023-12-01T00:00:00Z",
        )
        feed_bytes = _build_atom_feed(entry)

        fetcher = LiveAcademicFetcher(_http_fn=lambda url, t, h: feed_bytes)
        results = fetcher.search_by_topic("test query")

        assert len(results) == 1
        result = results[0]
        assert set(result.keys()) == {"url", "title", "abstract", "authors", "published_date"}
        assert result["title"] == "Test Title"
        assert result["abstract"] == "Test Abstract"
        assert result["authors"] == ["Author A"]
        assert result["published_date"] == "2023-12-01"
        assert "arxiv.org/abs/2312.99999" in result["url"]

    def test_empty_feed_returns_empty_list(self) -> None:
        """Returns [] when API returns zero entries (no FetchError)."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        empty_feed = _empty_atom_feed()
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, t, h: empty_feed)
        results = fetcher.search_by_topic("obscure topic with no results")
        assert results == []

    def test_network_error_raises_fetch_error(self) -> None:
        """FetchError propagates on network failure (consistent with fetch())."""
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher

        def failing_http(url: str, timeout: int, headers: dict) -> bytes:
            raise FetchError("Network failure")

        fetcher = LiveAcademicFetcher(_http_fn=failing_http)
        with pytest.raises(FetchError):
            fetcher.search_by_topic("some topic")

    def test_query_is_url_encoded(self) -> None:
        """The search query is URL-encoded in the API URL."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        captured_urls: list[str] = []

        def mock_http(url: str, timeout: int, headers: dict) -> bytes:
            captured_urls.append(url)
            return _empty_atom_feed()

        fetcher = LiveAcademicFetcher(_http_fn=mock_http)
        fetcher.search_by_topic("market microstructure theory")

        assert len(captured_urls) == 1
        url = captured_urls[0]
        # Spaces should be encoded
        assert " " not in url
        assert "export.arxiv.org" in url

    def test_max_results_reflected_in_url(self) -> None:
        """max_results parameter is included in the API URL."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        captured_urls: list[str] = []

        def mock_http(url: str, timeout: int, headers: dict) -> bytes:
            captured_urls.append(url)
            return _empty_atom_feed()

        fetcher = LiveAcademicFetcher(_http_fn=mock_http)
        fetcher.search_by_topic("test", max_results=10)

        assert "max_results=10" in captured_urls[0]

    def test_multiple_authors_parsed(self) -> None:
        """Multiple authors are returned as list[str]."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        entry = _atom_entry(
            "2301.00003",
            "Multi-Author Paper",
            "Abstract.",
            ["Author One", "Author Two", "Author Three"],
        )
        feed_bytes = _build_atom_feed(entry)
        fetcher = LiveAcademicFetcher(_http_fn=lambda url, t, h: feed_bytes)
        results = fetcher.search_by_topic("test")
        assert results[0]["authors"] == ["Author One", "Author Two", "Author Three"]


# ---------------------------------------------------------------------------
# Tests: BookAdapter
# ---------------------------------------------------------------------------


class TestBookAdapter:
    """BookAdapter converts structured book metadata to ExtractedDocument."""

    def _full_raw_source(self) -> dict:
        return {
            "title": "Market Microstructure Theory",
            "authors": ["Maureen O'Hara"],
            "book_id": "market_microstructure_theory",
            "chapter": "Chapter 3: The Inventory Model",
            "body_text": "The inventory model is central to understanding market maker behavior.",
            "published_date": "1995-01-01",
        }

    def test_adapt_returns_extracted_document(self) -> None:
        """adapt() returns ExtractedDocument with source_family='book'."""
        from packages.research.ingestion.adapters import BookAdapter
        from packages.research.ingestion.extractors import ExtractedDocument

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())

        assert isinstance(doc, ExtractedDocument)
        assert doc.source_family == "book"

    def test_source_type_is_book(self) -> None:
        """metadata['source_type'] is 'book'."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())
        assert doc.metadata.get("source_type") == "book"

    def test_canonical_url_uses_book_id_and_chapter_slug(self) -> None:
        """canonical_url = internal://book/{book_id}/{slugified_chapter}."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())

        # Chapter: "Chapter 3: The Inventory Model" -> slugified
        assert doc.source_url.startswith("internal://book/market_microstructure_theory/")
        # Slug should be lowercase, spaces->underscore, special chars stripped
        slug = doc.source_url.split("/")[-1]
        assert slug == slug.lower()
        assert " " not in slug

    def test_missing_chapter_falls_back_to_root(self) -> None:
        """When chapter and section are missing, slug is 'root'."""
        from packages.research.ingestion.adapters import BookAdapter

        raw = dict(self._full_raw_source())
        del raw["chapter"]
        adapter = BookAdapter()
        doc = adapter.adapt(raw)
        assert doc.source_url.endswith("/root")

    def test_section_used_when_chapter_absent(self) -> None:
        """When chapter is absent but section is present, section slug is used."""
        from packages.research.ingestion.adapters import BookAdapter

        raw = dict(self._full_raw_source())
        del raw["chapter"]
        raw["section"] = "Section 2.1 Basics"
        adapter = BookAdapter()
        doc = adapter.adapt(raw)
        assert "section" in doc.source_url.lower() or "2" in doc.source_url

    def test_authors_list_joined(self) -> None:
        """authors as list -> comma-joined author string."""
        from packages.research.ingestion.adapters import BookAdapter

        raw = dict(self._full_raw_source())
        raw["authors"] = ["Author A", "Author B"]
        adapter = BookAdapter()
        doc = adapter.adapt(raw)
        assert "Author A" in doc.author
        assert "Author B" in doc.author

    def test_authors_string_passthrough(self) -> None:
        """authors as str -> used directly."""
        from packages.research.ingestion.adapters import BookAdapter

        raw = dict(self._full_raw_source())
        raw["authors"] = "Maureen O'Hara"
        adapter = BookAdapter()
        doc = adapter.adapt(raw)
        assert "Maureen" in doc.author

    def test_book_id_in_canonical_ids(self) -> None:
        """canonical_ids contains {'book_id': book_id}."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())
        canonical_ids = doc.metadata.get("canonical_ids", {})
        assert canonical_ids.get("book_id") == "market_microstructure_theory"

    def test_body_text_used_as_body(self) -> None:
        """body_text is used as the document body."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())
        assert "inventory model" in doc.body

    def test_publish_date_propagated(self) -> None:
        """published_date is propagated to publish_date."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())
        assert doc.publish_date == "1995-01-01"

    def test_registered_in_adapter_registry(self) -> None:
        """BookAdapter is registered in ADAPTER_REGISTRY under 'book' key."""
        from packages.research.ingestion.adapters import ADAPTER_REGISTRY, BookAdapter

        assert "book" in ADAPTER_REGISTRY
        assert ADAPTER_REGISTRY["book"] is BookAdapter

    def test_canonical_url_format_full(self) -> None:
        """canonical_url has format internal://book/{book_id}/{chapter_slug}."""
        from packages.research.ingestion.adapters import BookAdapter

        adapter = BookAdapter()
        doc = adapter.adapt(self._full_raw_source())

        # "Chapter 3: The Inventory Model" slugified -> "chapter_3__the_inventory_model" or similar
        # The key invariant: starts with correct prefix
        expected_prefix = "internal://book/market_microstructure_theory/"
        assert doc.source_url.startswith(expected_prefix)
        slug_part = doc.source_url[len(expected_prefix):]
        # Slug should be non-empty, lowercase, no spaces
        assert len(slug_part) > 0
        assert " " not in slug_part


# ---------------------------------------------------------------------------
# Tests: IngestPipeline.ingest_external() with post_ingest_extract
# ---------------------------------------------------------------------------


class TestIngestExternalWithExtractClaims:
    """ingest_external() accepts post_ingest_extract kwarg and calls extract_and_link."""

    def _make_pipeline(self, mock_extract_and_link=None):
        """Create a minimal IngestPipeline with an in-memory KnowledgeStore."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.pipeline import IngestPipeline

        store = KnowledgeStore(":memory:")
        pipeline = IngestPipeline(store=store, evaluator=None)
        return pipeline, store

    def _book_raw_source(self) -> dict:
        return {
            "title": "Test Book",
            "authors": ["Test Author"],
            "book_id": "test_book",
            "chapter": "Chapter 1",
            "body_text": "This is a test chapter with enough content to pass hard stops. " * 5,
            "published_date": "2020-01-01",
        }

    def test_post_ingest_extract_false_does_not_call_extract(self) -> None:
        """When post_ingest_extract=False, extract_and_link is NOT called."""
        pipeline, store = self._make_pipeline()

        with patch(
            "packages.research.ingestion.claim_extractor.extract_and_link"
        ) as mock_fn:
            result = pipeline.ingest_external(
                self._book_raw_source(),
                "book",
                post_ingest_extract=False,
            )
        mock_fn.assert_not_called()
        assert not result.rejected

    def test_post_ingest_extract_true_calls_extract(self) -> None:
        """When post_ingest_extract=True, extract_and_link is called with (store, doc_id)."""
        pipeline, store = self._make_pipeline()

        call_log: list = []

        def fake_extract_and_link(s, doc_id):
            call_log.append(doc_id)

        import packages.research.ingestion.claim_extractor as ce_mod
        original = getattr(ce_mod, "extract_and_link", None)
        ce_mod.extract_and_link = fake_extract_and_link
        try:
            result = pipeline.ingest_external(
                self._book_raw_source(),
                "book",
                post_ingest_extract=True,
            )
        finally:
            if original is not None:
                ce_mod.extract_and_link = original
            else:
                # Restore to original state if it didn't exist
                pass

        # doc_id should be non-empty (document was accepted)
        assert not result.rejected
        assert result.doc_id
        # extract_and_link was called once with the doc_id
        assert len(call_log) == 1
        assert call_log[0] == result.doc_id

    def test_post_ingest_extract_exception_is_non_fatal(self) -> None:
        """If extract_and_link raises, ingest result is still accepted (non-fatal)."""
        from packages.research.ingestion.pipeline import IngestPipeline
        from packages.polymarket.rag.knowledge_store import KnowledgeStore

        store = KnowledgeStore(":memory:")
        pipeline = IngestPipeline(store=store, evaluator=None)

        # Patch claim_extractor module to raise on import/call
        import packages.research.ingestion.claim_extractor as ce_mod

        original_fn = getattr(ce_mod, "extract_and_link", None)

        def raising_fn(store, doc_id):
            raise RuntimeError("Extraction failed!")

        ce_mod.extract_and_link = raising_fn
        try:
            result = pipeline.ingest_external(
                self._book_raw_source(),
                "book",
                post_ingest_extract=True,
            )
        finally:
            if original_fn is not None:
                ce_mod.extract_and_link = original_fn
            else:
                del ce_mod.extract_and_link

        # Rejection must be False — extraction failure is non-fatal
        assert not result.rejected
        assert result.doc_id

    def test_ingest_external_signature_accepts_post_ingest_extract(self) -> None:
        """ingest_external() method signature accepts post_ingest_extract kwarg without error."""
        import inspect
        from packages.research.ingestion.pipeline import IngestPipeline

        sig = inspect.signature(IngestPipeline.ingest_external)
        params = sig.parameters
        assert "post_ingest_extract" in params, (
            "ingest_external() must accept post_ingest_extract kwarg"
        )


# ---------------------------------------------------------------------------
# Tests: book_sample.json fixture
# ---------------------------------------------------------------------------


class TestBookSampleFixture:
    """The book_sample.json fixture exists and has the required keys."""

    def test_fixture_exists(self) -> None:
        """tests/fixtures/ris_external_sources/book_sample.json exists."""
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "ris_external_sources"
            / "book_sample.json"
        )
        assert fixture_path.exists(), f"Missing fixture: {fixture_path}"

    def test_fixture_has_required_keys(self) -> None:
        """book_sample.json has title, authors, book_id, chapter, body_text, published_date."""
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "ris_external_sources"
            / "book_sample.json"
        )
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        required_keys = {"title", "authors", "book_id", "chapter", "body_text", "published_date"}
        missing = required_keys - set(data.keys())
        assert not missing, f"Fixture missing keys: {missing}"

    def test_fixture_is_ingestible(self) -> None:
        """book_sample.json can be ingested through BookAdapter without error."""
        import json as _json
        from pathlib import Path as _Path
        from packages.research.ingestion.adapters import BookAdapter
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.pipeline import IngestPipeline

        fixture_path = (
            _Path(__file__).parent
            / "fixtures"
            / "ris_external_sources"
            / "book_sample.json"
        )
        raw = _json.loads(fixture_path.read_text(encoding="utf-8"))

        store = KnowledgeStore(":memory:")
        pipeline = IngestPipeline(store=store, evaluator=None)
        result = pipeline.ingest_external(raw, "book")
        store.close()

        assert not result.rejected, f"Fixture was rejected: {result.reject_reason}"
        assert result.doc_id
