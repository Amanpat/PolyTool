"""Offline tests for arXiv PDF download in LiveAcademicFetcher.

Covers:
- PDF success path: body_text = extracted PDF text, not abstract
- PDF HTTP failure: falls back to abstract with metadata
- Short extracted body: falls back to abstract with metadata
- search_by_topic: each result goes through same PDF path
- AcademicAdapter: body_source/body_length/page_count/fallback_reason in metadata
"""

from __future__ import annotations

from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Shared helper: build canned arXiv Atom XML
# ---------------------------------------------------------------------------

def _arxiv_atom(
    arxiv_id: str,
    title: str = "Test Paper",
    abstract: str = "Short abstract text.",
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>{title}</title>
    <summary>{abstract}</summary>
    <author><name>Test Author</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>""".encode("utf-8")


def _build_search_feed(*arxiv_ids: str) -> bytes:
    entries = ""
    for arxiv_id in arxiv_ids:
        entries += f"""<entry>
  <id>http://arxiv.org/abs/{arxiv_id}v1</id>
  <title>Paper {arxiv_id}</title>
  <summary>Abstract for {arxiv_id}.</summary>
  <author><name>Author</name></author>
  <published>2024-01-01T00:00:00Z</published>
</entry>"""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f"{entries}"
        "</feed>"
    ).encode("utf-8")


def _make_pdf_extractor_mock(body: str, page_count: int = 5):
    """Return a mock extractor class whose .extract() returns an ExtractedDocument."""
    from packages.research.ingestion.extractors import ExtractedDocument

    doc = ExtractedDocument(
        title="Test Paper",
        body=body,
        source_url="file:///tmp/test.pdf",
        source_family="manual",
        metadata={"page_count": page_count, "content_hash": "abc123"},
    )
    mock_cls = MagicMock()
    mock_cls.return_value.extract.return_value = doc
    return mock_cls


# ---------------------------------------------------------------------------
# PDF success path
# ---------------------------------------------------------------------------


class TestAcademicFetchPDFSuccess:
    def test_body_text_is_pdf_not_abstract(self):
        """On PDF success, body_text is the extracted PDF text, not the abstract."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        pdf_body = "Full paper content. " * 400  # >> 2000 chars
        mock_cls = _make_pdf_extractor_mock(pdf_body, page_count=8)

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00001"),
            _pdf_http_fn=lambda url, t, h: b"fake-pdf-bytes",
            _pdf_extractor_cls=mock_cls,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00001")

        assert result["body_source"] == "pdf"
        assert result["body_text"] == pdf_body
        assert result["body_length"] == len(pdf_body)
        assert result["page_count"] == 8

    def test_pdf_url_format(self):
        """PDF is downloaded from https://arxiv.org/pdf/{id}.pdf."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        pdf_urls: list[str] = []
        pdf_body = "A" * 6000

        def pdf_http_fn(url, t, h):
            pdf_urls.append(url)
            return b"fake-pdf-bytes"

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.99999"),
            _pdf_http_fn=pdf_http_fn,
            _pdf_extractor_cls=_make_pdf_extractor_mock(pdf_body),
        )
        fetcher.fetch("https://arxiv.org/abs/2501.99999")

        assert len(pdf_urls) == 1
        assert "arxiv.org/pdf/2501.99999" in pdf_urls[0]

    def test_abstract_still_present_in_result(self):
        """Abstract key is preserved alongside full body_text."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        abstract = "Short abstract text."
        pdf_body = "B" * 6000

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00007", abstract=abstract),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_extractor_cls=_make_pdf_extractor_mock(pdf_body),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00007")

        assert result["abstract"] == abstract
        assert result["body_text"] == pdf_body


# ---------------------------------------------------------------------------
# Fallback: HTTP failure
# ---------------------------------------------------------------------------


class TestAcademicFetchPDFHttpFailure:
    def test_http_failure_falls_back_to_abstract(self):
        """If PDF download fails, body_text = abstract, body_source = abstract_fallback."""
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher

        abstract = "The abstract text."

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00002", abstract=abstract),
            _pdf_http_fn=lambda url, t, h: (_ for _ in ()).throw(
                FetchError("HTTP 403 Forbidden")
            ),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00002")

        assert result["body_source"] == "abstract_fallback"
        assert result["body_text"] == abstract
        assert "fallback_reason" in result

    def test_http_failure_does_not_raise(self):
        """PDF download failure must not propagate — fetch() returns successfully."""
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher

        def exploding_pdf(url, t, h):
            raise FetchError("Connection refused")

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00005"),
            _pdf_http_fn=exploding_pdf,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00005")
        assert "url" in result and "title" in result  # successful return


# ---------------------------------------------------------------------------
# Fallback: short extracted text
# ---------------------------------------------------------------------------


class TestAcademicFetchPDFShortText:
    def test_short_body_falls_back_to_abstract(self):
        """Extracted text < 2000 chars triggers fallback to abstract."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        abstract = "The abstract."
        short_body = "X" * 500  # < 2000

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00003", abstract=abstract),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_extractor_cls=_make_pdf_extractor_mock(short_body),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00003")

        assert result["body_source"] == "abstract_fallback"
        assert result["body_text"] == abstract
        assert "too short" in result.get("fallback_reason", "")

    def test_extraction_exception_falls_back(self):
        """If PDFExtractor.extract() raises, fallback to abstract without crashing."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        abstract = "The abstract."
        mock_cls = MagicMock()
        mock_cls.return_value.extract.side_effect = RuntimeError("PDF corrupted")

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2501.00004", abstract=abstract),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_extractor_cls=mock_cls,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2501.00004")

        assert result["body_source"] == "abstract_fallback"
        assert result["body_text"] == abstract
        assert "fallback_reason" in result


# ---------------------------------------------------------------------------
# search_by_topic: each result goes through PDF path
# ---------------------------------------------------------------------------


class TestAcademicSearchPDF:
    def test_search_results_include_body_source(self):
        """Each search_by_topic result has body_source and body_text."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        pdf_body = "C" * 6000
        mock_cls = _make_pdf_extractor_mock(pdf_body, page_count=3)

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _build_search_feed("2501.00010", "2501.00011"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_extractor_cls=mock_cls,
        )
        results = fetcher.search_by_topic("test topic", max_results=2)

        assert len(results) == 2
        for r in results:
            assert "body_source" in r
            assert "body_text" in r

    def test_search_pdf_success_path(self):
        """search_by_topic: PDF success sets body_source=pdf on each result."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        pdf_body = "D" * 6000
        mock_cls = _make_pdf_extractor_mock(pdf_body)

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _build_search_feed("2501.00020"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_extractor_cls=mock_cls,
        )
        results = fetcher.search_by_topic("prediction markets")

        assert results[0]["body_source"] == "pdf"
        assert results[0]["body_text"] == pdf_body

    def test_search_pdf_failure_falls_back(self):
        """search_by_topic: PDF failure falls back to abstract for that result."""
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher

        abstract = "Abstract for 2501.00030."

        feed = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry>'
            '<id>http://arxiv.org/abs/2501.00030v1</id>'
            '<title>Fail Paper</title>'
            f'<summary>{abstract}</summary>'
            '<author><name>Auth</name></author>'
            '<published>2024-01-01T00:00:00Z</published>'
            '</entry>'
            "</feed>"
        ).encode("utf-8")

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: feed,
            _pdf_http_fn=lambda url, t, h: (_ for _ in ()).throw(FetchError("403")),
        )
        results = fetcher.search_by_topic("fail topic")

        assert results[0]["body_source"] == "abstract_fallback"
        assert results[0]["body_text"] == abstract


# ---------------------------------------------------------------------------
# AcademicAdapter: metadata propagation
# ---------------------------------------------------------------------------


class TestAcademicAdapterBodySourceMetadata:
    def test_body_source_pdf_in_metadata(self):
        """AcademicAdapter propagates body_source=pdf into doc.metadata."""
        from packages.research.ingestion.adapters import AcademicAdapter

        raw = {
            "url": "https://arxiv.org/abs/2501.00001",
            "title": "Test Paper",
            "abstract": "Short abstract.",
            "authors": ["Author A"],
            "published_date": "2024-01-01",
            "body_text": "Full PDF body. " * 400,
            "body_source": "pdf",
            "body_length": 6000,
            "page_count": 8,
        }
        doc = AcademicAdapter().adapt(raw)

        assert doc.metadata["body_source"] == "pdf"
        assert doc.metadata["body_length"] == 6000
        assert doc.metadata["page_count"] == 8

    def test_body_source_fallback_in_metadata(self):
        """AcademicAdapter propagates body_source=abstract_fallback and fallback_reason."""
        from packages.research.ingestion.adapters import AcademicAdapter

        raw = {
            "url": "https://arxiv.org/abs/2501.00002",
            "title": "Test Paper",
            "abstract": "The abstract text.",
            "authors": [],
            "published_date": "2024-01-01",
            "body_text": "The abstract text.",
            "body_source": "abstract_fallback",
            "fallback_reason": "HTTP 403 Forbidden",
        }
        doc = AcademicAdapter().adapt(raw)

        assert doc.metadata["body_source"] == "abstract_fallback"
        assert doc.metadata["fallback_reason"] == "HTTP 403 Forbidden"
        assert "body_length" not in doc.metadata

    def test_default_body_source_is_abstract(self):
        """When body_source absent in raw_source, metadata defaults to 'abstract'."""
        from packages.research.ingestion.adapters import AcademicAdapter

        raw = {
            "url": "https://arxiv.org/abs/2501.00003",
            "title": "Old-style Paper",
            "abstract": "Abstract text.",
            "authors": ["A"],
            "published_date": "2024-01-01",
        }
        doc = AcademicAdapter().adapt(raw)
        assert doc.metadata["body_source"] == "abstract"

    def test_pdf_body_text_used_as_doc_body(self):
        """When body_source=pdf, doc.body is the full PDF text, not abstract."""
        from packages.research.ingestion.adapters import AcademicAdapter

        long_pdf_text = "PDF content line. " * 400
        raw = {
            "url": "https://arxiv.org/abs/2501.00004",
            "title": "Full Paper",
            "abstract": "Short abstract.",
            "authors": ["A"],
            "published_date": "2024-01-01",
            "body_text": long_pdf_text,
            "body_source": "pdf",
            "body_length": len(long_pdf_text),
            "page_count": 10,
        }
        doc = AcademicAdapter().adapt(raw)
        assert doc.body == long_pdf_text
