"""Offline tests for arXiv PDF download in LiveAcademicFetcher.

Covers:
- PDF success path: body_text = extracted PDF text, not abstract
- PDF HTTP failure: falls back to abstract with metadata
- Short extracted body: falls back to abstract with metadata
- search_by_topic: each result goes through same PDF path
- AcademicAdapter: body_source/body_length/page_count/fallback_reason in metadata
- MarkerPDFExtractor: unit tests with injected modules
- LiveAcademicFetcher: Marker integration (success, fallback, auto mode, explicit modes)
- AcademicAdapter: Marker metadata propagation
"""

from __future__ import annotations

import pytest
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


# ---------------------------------------------------------------------------
# Helpers for Marker-specific tests
# ---------------------------------------------------------------------------


def _make_marker_extractor_cls(
    body: str,
    page_count: int = 5,
    marker_version: str = "1.2.0",
    structured_metadata: "dict | None" = None,
    structured_metadata_truncated: bool = False,
    raise_exc: "Exception | None" = None,
):
    """Return a fake class usable as _marker_extractor_cls in LiveAcademicFetcher."""
    from packages.research.ingestion.extractors import ExtractedDocument

    if structured_metadata is None:
        structured_metadata = {"page_1": {"blocks": 10}}

    class _FakeMarker:
        def extract(self, path, **kwargs):
            if raise_exc is not None:
                raise raise_exc
            return ExtractedDocument(
                title="Marker Paper",
                body=body,
                source_url=f"file://{path}",
                source_family="manual",
                metadata={
                    "page_count": page_count,
                    "body_source": "marker",
                    "has_structured_metadata": True,
                    "structured_metadata": structured_metadata,
                    "structured_metadata_truncated": structured_metadata_truncated,
                    "marker_version": marker_version,
                    "content_hash": "abc123",
                },
            )

    return _FakeMarker


def _make_marker_modules_fake(
    body: str,
    page_count: int = 5,
    out_meta: "dict | None" = None,
):
    """Return injectable marker modules dict for MarkerPDFExtractor unit tests."""
    if out_meta is None:
        out_meta = {"page_count": page_count, "languages": ["en"]}

    class _FakeRendered:
        class _Meta:
            pass
        metadata = _Meta()

    def _fake_create_model_dict():
        return {}

    def _fake_text_from_rendered(rendered):
        return (body, out_meta, {})

    class _FakePdfConverter:
        def __init__(self, artifact_dict=None):
            pass
        def __call__(self, path):
            return _FakeRendered()

    return {
        "PdfConverter": _FakePdfConverter,
        "create_model_dict": _fake_create_model_dict,
        "text_from_rendered": _fake_text_from_rendered,
    }


# ---------------------------------------------------------------------------
# MarkerPDFExtractor unit tests
# ---------------------------------------------------------------------------


class TestMarkerPDFExtractorUnit:
    def test_missing_raises_import_error(self):
        """When marker-pdf is not installed and no modules injected, ImportError is raised."""
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        extractor = MarkerPDFExtractor()  # no modules injected, real marker absent
        with pytest.raises(ImportError, match="marker-pdf"):
            extractor.extract("/nonexistent/path.pdf")

    def test_injection_success_body_source_marker(self, tmp_path):
        """Injected modules produce body_source='marker' and correct Markdown body."""
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 minimal")
        md_body = "# Section One\n\nContent here. " * 20

        modules = _make_marker_modules_fake(md_body)
        doc = MarkerPDFExtractor(_marker_modules=modules).extract(str(fake_pdf))

        assert doc.metadata["body_source"] == "marker"
        assert doc.body == md_body
        assert doc.metadata["has_structured_metadata"] is True
        assert "structured_metadata" in doc.metadata

    def test_injection_page_count_in_metadata(self, tmp_path):
        """page_count is extracted from injected out_meta."""
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")
        modules = _make_marker_modules_fake("# Title\n\nBody. " * 30, page_count=7)
        doc = MarkerPDFExtractor(_marker_modules=modules).extract(str(fake_pdf))

        assert doc.metadata["page_count"] == 7

    def test_json_size_cap_truncates(self, tmp_path):
        """Structured metadata exceeding 20 MB is truncated and flagged."""
        from packages.research.ingestion.extractors import (
            MarkerPDFExtractor,
            _MARKER_METADATA_SIZE_LIMIT,
        )

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")
        # Build out_meta that serialises to > 20 MB
        huge_meta = {
            "page_count": 3,
            "data": "x" * (_MARKER_METADATA_SIZE_LIMIT + 1024),
        }
        modules = _make_marker_modules_fake("# Title\n\nBody. " * 30, out_meta=huge_meta)
        doc = MarkerPDFExtractor(_marker_modules=modules).extract(str(fake_pdf))

        assert doc.metadata["structured_metadata_truncated"] is True
        assert doc.metadata["structured_metadata"].get("truncated") is True

    def test_llm_flag_sets_marker_llm_boost(self, tmp_path):
        """_enable_llm=True sets body_source='marker_llm_boost'."""
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake")
        modules = _make_marker_modules_fake("# Title\n\nBody. " * 30)
        doc = MarkerPDFExtractor(_marker_modules=modules, _enable_llm=True).extract(
            str(fake_pdf)
        )

        assert doc.metadata["body_source"] == "marker_llm_boost"

    def test_nonexistent_file_raises_file_not_found(self, tmp_path):
        """FileNotFoundError when source path does not exist (modules injected)."""
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        modules = _make_marker_modules_fake("body")
        extractor = MarkerPDFExtractor(_marker_modules=modules)
        with pytest.raises(FileNotFoundError):
            extractor.extract(str(tmp_path / "missing.pdf"))


# ---------------------------------------------------------------------------
# Marker integration via LiveAcademicFetcher
# ---------------------------------------------------------------------------


class TestMarkerFetcherIntegration:
    def test_marker_success_body_source(self):
        """_pdf_parser='marker' with success → body_source='marker'."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        md_body = "# Paper Title\n\nSection content. " * 30
        marker_cls = _make_marker_extractor_cls(md_body, page_count=8, marker_version="1.3.0")

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10001"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="marker",
            _marker_extractor_cls=marker_cls,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10001")

        assert result["body_source"] == "marker"
        assert result["body_text"] == md_body
        assert result["body_length"] == len(md_body)
        assert result["has_structured_metadata"] is True

    def test_marker_metadata_propagated(self):
        """marker_version and structured_metadata are present in fetch result."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        md_body = "# Paper\n\nText. " * 30
        smd = {"page_1": {"block_count": 5}}
        marker_cls = _make_marker_extractor_cls(
            md_body, marker_version="1.3.0", structured_metadata=smd
        )

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10002"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="marker",
            _marker_extractor_cls=marker_cls,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10002")

        assert result.get("marker_version") == "1.3.0"
        assert result.get("structured_metadata") == smd

    def test_marker_short_output_falls_back(self):
        """Marker returns <200 chars → triggers pdfplumber fallback."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        short_body = "X" * 50
        marker_cls = _make_marker_extractor_cls(short_body)
        long_pdf = "pdfplumber body text. " * 200

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10003"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="marker",
            _marker_extractor_cls=marker_cls,
            _pdfplumber_extractor_cls=_make_pdf_extractor_mock(long_pdf, page_count=3),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10003")

        assert result["body_source"] != "marker"
        assert "marker output too short" in result.get("fallback_reason", "")

    def test_marker_import_error_explicit_mode(self):
        """_pdf_parser='marker' + ImportError → body_source='pdfplumber_fallback'."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        class _MarkerNotAvailable:
            def extract(self, *a, **kw):
                raise ImportError("marker-pdf not installed")

        long_pdf = "pdfplumber body text. " * 200

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10004"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="marker",
            _marker_extractor_cls=_MarkerNotAvailable,
            _pdfplumber_extractor_cls=_make_pdf_extractor_mock(long_pdf),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10004")

        assert result["body_source"] == "pdfplumber_fallback"
        assert "fallback_reason" in result

    def test_auto_mode_marker_not_installed_stays_pdf(self):
        """auto mode + Marker ImportError → body_source='pdf' (silent fallback)."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        class _MarkerNotAvailable:
            def extract(self, *a, **kw):
                raise ImportError("marker-pdf not installed")

        long_pdf = "pdfplumber body text. " * 200

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10005"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="auto",
            _marker_extractor_cls=_MarkerNotAvailable,
            _pdfplumber_extractor_cls=_make_pdf_extractor_mock(long_pdf),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10005")

        assert result["body_source"] == "pdf"

    def test_auto_mode_marker_runtime_error_is_pdfplumber_fallback(self):
        """auto mode + Marker RuntimeError → body_source='pdfplumber_fallback'."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        marker_cls = _make_marker_extractor_cls("", raise_exc=RuntimeError("OOM"))
        long_pdf = "pdfplumber body text. " * 200

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10006"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="auto",
            _marker_extractor_cls=marker_cls,
            _pdfplumber_extractor_cls=_make_pdf_extractor_mock(long_pdf),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10006")

        assert result["body_source"] == "pdfplumber_fallback"
        assert "fallback_reason" in result

    def test_pdfplumber_explicit_mode(self):
        """_pdf_parser='pdfplumber' → body_source='pdf', skips Marker entirely."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        long_pdf = "pdfplumber body text. " * 200

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10007"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="pdfplumber",
            _pdfplumber_extractor_cls=_make_pdf_extractor_mock(long_pdf, page_count=4),
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10007")

        assert result["body_source"] == "pdf"
        assert result["body_text"] == long_pdf

    def test_marker_json_size_cap_flagged_in_result(self):
        """structured_metadata_truncated=True propagates into fetch result."""
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        md_body = "# Title\n\nContent. " * 30
        marker_cls = _make_marker_extractor_cls(
            md_body, structured_metadata_truncated=True
        )

        fetcher = LiveAcademicFetcher(
            _http_fn=lambda url, t, h: _arxiv_atom("2510.10008"),
            _pdf_http_fn=lambda url, t, h: b"fake",
            _pdf_parser="marker",
            _marker_extractor_cls=marker_cls,
        )
        result = fetcher.fetch("https://arxiv.org/abs/2510.10008")

        assert result.get("structured_metadata_truncated") is True


# ---------------------------------------------------------------------------
# AcademicAdapter: Marker metadata propagation
# ---------------------------------------------------------------------------


class TestAcademicAdapterMarkerMetadata:
    def test_marker_fields_in_doc_metadata(self):
        """AcademicAdapter propagates has_structured_metadata and marker_version."""
        from packages.research.ingestion.adapters import AcademicAdapter

        raw = {
            "url": "https://arxiv.org/abs/2510.00001",
            "title": "Marker Paper",
            "abstract": "Short abstract.",
            "authors": ["Author A"],
            "published_date": "2024-01-01",
            "body_text": "# Section\n\nMarkdown body. " * 50,
            "body_source": "marker",
            "body_length": 1200,
            "page_count": 6,
            "has_structured_metadata": True,
            "marker_version": "1.3.0",
            "structured_metadata": {"page_1": {"blocks": 4}},
            "structured_metadata_truncated": False,
        }
        doc = AcademicAdapter().adapt(raw)

        assert doc.metadata["body_source"] == "marker"
        assert doc.metadata["has_structured_metadata"] is True
        assert doc.metadata["marker_version"] == "1.3.0"
        # structured_metadata is a cache-only field; not propagated to doc.metadata
        assert "structured_metadata" not in doc.metadata

    def test_marker_truncated_flag_propagated(self):
        """structured_metadata_truncated=True is surfaced in doc.metadata."""
        from packages.research.ingestion.adapters import AcademicAdapter

        raw = {
            "url": "https://arxiv.org/abs/2510.00002",
            "title": "Truncated Meta Paper",
            "abstract": "Abstract.",
            "authors": [],
            "published_date": "2024-01-01",
            "body_text": "# Title\n\nBody. " * 50,
            "body_source": "marker",
            "has_structured_metadata": True,
            "marker_version": "1.3.0",
            "structured_metadata_truncated": True,
        }
        doc = AcademicAdapter().adapt(raw)

        assert doc.metadata["structured_metadata_truncated"] is True
