"""Deterministic offline tests for RIS Phase 2 extractor stubs and benchmark harness.

All tests use tmp_path for fixtures and output dirs. No network calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ris_seed_corpus"


# ---------------------------------------------------------------------------
# MarkdownExtractor tests
# ---------------------------------------------------------------------------


class TestMarkdownExtractor:
    def test_markdown_extractor_is_subclass_of_extractor(self):
        """MarkdownExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import MarkdownExtractor, Extractor
        assert issubclass(MarkdownExtractor, Extractor)

    def test_markdown_extractor_extracts_from_file(self, tmp_path):
        """MarkdownExtractor.extract() returns ExtractedDocument from a .md file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Title\n\nBody text here.\n", encoding="utf-8")

        from packages.research.ingestion.extractors import MarkdownExtractor
        extractor = MarkdownExtractor()
        doc = extractor.extract(md_file, source_type="manual")

        from packages.research.ingestion.extractors import ExtractedDocument
        assert isinstance(doc, ExtractedDocument)
        assert doc.title == "Test Title"
        assert "Body text here" in doc.body

    def test_markdown_extractor_title_from_h1(self, tmp_path):
        """MarkdownExtractor uses H1 heading as title."""
        md_file = tmp_path / "h1test.md"
        md_file.write_text("# My Research Paper\n\nSome content.\n", encoding="utf-8")

        from packages.research.ingestion.extractors import MarkdownExtractor
        extractor = MarkdownExtractor()
        doc = extractor.extract(md_file, source_type="manual")
        assert doc.title == "My Research Paper"

    def test_markdown_extractor_fallback_title(self, tmp_path):
        """MarkdownExtractor uses filename stem when no H1 present."""
        md_file = tmp_path / "noh1.md"
        md_file.write_text("Just a paragraph.\n", encoding="utf-8")

        from packages.research.ingestion.extractors import MarkdownExtractor
        extractor = MarkdownExtractor()
        doc = extractor.extract(md_file, source_type="manual")
        assert doc.title == "noh1"

    def test_markdown_extractor_source_url_is_file_uri(self, tmp_path):
        """MarkdownExtractor sets source_url as file:// URI."""
        md_file = tmp_path / "uri_test.md"
        md_file.write_text("# URI\n\nTest.\n", encoding="utf-8")

        from packages.research.ingestion.extractors import MarkdownExtractor
        extractor = MarkdownExtractor()
        doc = extractor.extract(md_file, source_type="manual")
        assert doc.source_url.startswith("file://")


# ---------------------------------------------------------------------------
# StubPDFExtractor tests
# ---------------------------------------------------------------------------


class TestStubPDFExtractor:
    def test_stub_pdf_extractor_is_subclass_of_extractor(self):
        """StubPDFExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import StubPDFExtractor, Extractor
        assert issubclass(StubPDFExtractor, Extractor)

    def test_stub_pdf_extractor_raises_not_implemented(self, tmp_path):
        """StubPDFExtractor.extract() raises NotImplementedError."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        from packages.research.ingestion.extractors import StubPDFExtractor
        extractor = StubPDFExtractor()
        with pytest.raises(NotImplementedError):
            extractor.extract(pdf_file, source_type="manual")

    def test_stub_pdf_extractor_error_message(self, tmp_path):
        """StubPDFExtractor error message mentions library options."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        from packages.research.ingestion.extractors import StubPDFExtractor
        extractor = StubPDFExtractor()
        with pytest.raises(NotImplementedError, match="docling|marker|pymupdf"):
            extractor.extract(pdf_file, source_type="manual")


# ---------------------------------------------------------------------------
# StubDocxExtractor tests
# ---------------------------------------------------------------------------


class TestStubDocxExtractor:
    def test_stub_docx_extractor_is_subclass_of_extractor(self):
        """StubDocxExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import StubDocxExtractor, Extractor
        assert issubclass(StubDocxExtractor, Extractor)

    def test_stub_docx_extractor_raises_not_implemented(self, tmp_path):
        """StubDocxExtractor.extract() raises NotImplementedError."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"fake docx content")

        from packages.research.ingestion.extractors import StubDocxExtractor
        extractor = StubDocxExtractor()
        with pytest.raises(NotImplementedError):
            extractor.extract(docx_file, source_type="manual")

    def test_stub_docx_extractor_error_message(self, tmp_path):
        """StubDocxExtractor error message mentions python-docx."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"fake docx")

        from packages.research.ingestion.extractors import StubDocxExtractor
        extractor = StubDocxExtractor()
        with pytest.raises(NotImplementedError, match="python-docx"):
            extractor.extract(docx_file, source_type="manual")


# ---------------------------------------------------------------------------
# EXTRACTOR_REGISTRY and get_extractor tests
# ---------------------------------------------------------------------------


class TestExtractorRegistry:
    def test_extractor_registry_exists(self):
        """EXTRACTOR_REGISTRY is a dict mapping name -> extractor class."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert isinstance(EXTRACTOR_REGISTRY, dict)
        assert len(EXTRACTOR_REGISTRY) >= 4

    def test_extractor_registry_contains_expected_keys(self):
        """EXTRACTOR_REGISTRY has plain_text, markdown, pdf, docx keys."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "plain_text" in EXTRACTOR_REGISTRY
        assert "markdown" in EXTRACTOR_REGISTRY
        assert "pdf" in EXTRACTOR_REGISTRY
        assert "docx" in EXTRACTOR_REGISTRY

    def test_get_extractor_plain_text(self):
        """get_extractor('plain_text') returns a PlainTextExtractor instance."""
        from packages.research.ingestion.extractors import get_extractor, PlainTextExtractor
        extractor = get_extractor("plain_text")
        assert isinstance(extractor, PlainTextExtractor)

    def test_get_extractor_markdown(self):
        """get_extractor('markdown') returns a MarkdownExtractor instance."""
        from packages.research.ingestion.extractors import get_extractor, MarkdownExtractor
        extractor = get_extractor("markdown")
        assert isinstance(extractor, MarkdownExtractor)

    def test_get_extractor_pdf(self):
        """get_extractor('pdf') returns a PDFExtractor instance (real, not stub)."""
        from packages.research.ingestion.extractors import get_extractor, PDFExtractor
        extractor = get_extractor("pdf")
        assert isinstance(extractor, PDFExtractor)

    def test_get_extractor_docx(self):
        """get_extractor('docx') returns a DocxExtractor instance (real, not stub)."""
        from packages.research.ingestion.extractors import get_extractor, DocxExtractor
        extractor = get_extractor("docx")
        assert isinstance(extractor, DocxExtractor)

    def test_get_extractor_unknown_raises(self):
        """get_extractor('unknown_format') raises KeyError."""
        from packages.research.ingestion.extractors import get_extractor
        with pytest.raises(KeyError):
            get_extractor("unknown_format")

    def test_extractor_registry_values_are_extractor_classes(self):
        """All EXTRACTOR_REGISTRY values are subclasses of Extractor ABC."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY, Extractor
        for name, cls in EXTRACTOR_REGISTRY.items():
            assert issubclass(cls, Extractor), f"{name} must be subclass of Extractor"


# ---------------------------------------------------------------------------
# BenchmarkResult and run_extractor_benchmark tests
# ---------------------------------------------------------------------------


class TestRunExtractorBenchmark:
    def test_benchmark_imports_cleanly(self):
        """BenchmarkResult and run_extractor_benchmark are importable."""
        from packages.research.ingestion.benchmark import BenchmarkResult, run_extractor_benchmark
        assert BenchmarkResult is not None
        assert callable(run_extractor_benchmark)

    def test_benchmark_returns_benchmark_result(self, tmp_path):
        """run_extractor_benchmark() returns a BenchmarkResult."""
        md_file = tmp_path / "sample.md"
        md_file.write_text("# Sample\n\nContent for benchmark.\n", encoding="utf-8")

        from packages.research.ingestion.benchmark import BenchmarkResult, run_extractor_benchmark
        result = run_extractor_benchmark(tmp_path, extractors=["plain_text", "markdown"])
        assert isinstance(result, BenchmarkResult)

    def test_benchmark_metrics_per_extractor_per_file(self, tmp_path):
        """run_extractor_benchmark() returns metrics for each extractor-file pair."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Title\n\nSome content here.\n", encoding="utf-8")

        from packages.research.ingestion.benchmark import run_extractor_benchmark, ExtractorMetric
        result = run_extractor_benchmark(tmp_path, extractors=["plain_text"])

        assert len(result.metrics) >= 1
        metric = result.metrics[0]
        assert isinstance(metric, ExtractorMetric)
        assert metric.extractor_name == "plain_text"
        assert metric.file_name == "doc.md"
        assert metric.char_count > 0
        assert metric.word_count > 0
        assert metric.elapsed_ms >= 0

    def test_benchmark_records_stub_errors(self, tmp_path):
        """run_extractor_benchmark() records NotImplementedError for stub extractors."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Title\n\nContent.\n", encoding="utf-8")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(tmp_path, extractors=["pdf"])

        # pdf is a stub -- should record an error, not crash
        assert len(result.metrics) >= 1
        metric = result.metrics[0]
        assert metric.error is not None
        assert metric.char_count == 0
        assert metric.word_count == 0

    def test_benchmark_writes_artifacts(self, tmp_path):
        """run_extractor_benchmark() writes benchmark_results.json to output_dir."""
        md_file = tmp_path / "input.md"
        md_file.write_text("# Input\n\nTest content.\n", encoding="utf-8")
        output_dir = tmp_path / "benchmark_out"

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        run_extractor_benchmark(tmp_path, extractors=["plain_text"], output_dir=output_dir)

        artifact = output_dir / "benchmark_results.json"
        assert artifact.exists(), "benchmark_results.json must be written to output_dir"
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert "metrics" in data
        assert "summary" in data

    def test_benchmark_summary_contains_extractor_stats(self, tmp_path):
        """run_extractor_benchmark() summary has per-extractor success/fail counts."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent.\n", encoding="utf-8")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(tmp_path, extractors=["plain_text", "markdown"])

        assert "plain_text" in result.summary
        assert "markdown" in result.summary
        for name in ["plain_text", "markdown"]:
            stats = result.summary[name]
            assert "success_count" in stats
            assert "fail_count" in stats

    def test_benchmark_fixture_file_exercises_plain_text(self):
        """run_extractor_benchmark() on the real fixture dir succeeds for plain_text."""
        from packages.research.ingestion.benchmark import run_extractor_benchmark
        if not FIXTURE_DIR.exists():
            pytest.skip("Fixture dir not found")

        result = run_extractor_benchmark(FIXTURE_DIR, extractors=["plain_text"])
        successful = [m for m in result.metrics if m.error is None]
        assert len(successful) >= 1

    def test_benchmark_pdf_txt_fixture_plain_text(self):
        """benchmark on the sample_structured.pdf.txt fixture succeeds for plain_text."""
        pdf_txt = FIXTURE_DIR / "sample_structured.pdf.txt"
        if not pdf_txt.exists():
            pytest.skip("sample_structured.pdf.txt fixture not found")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(FIXTURE_DIR, extractors=["plain_text"])
        file_names = [m.file_name for m in result.metrics]
        assert "sample_structured.pdf.txt" in file_names


# ---------------------------------------------------------------------------
# __init__.py exports for new extractor types and benchmark
# ---------------------------------------------------------------------------


class TestIngestionPackageExports:
    def test_markdown_extractor_exported(self):
        """MarkdownExtractor is importable from packages.research.ingestion."""
        from packages.research.ingestion import MarkdownExtractor
        assert MarkdownExtractor is not None

    def test_stub_pdf_extractor_exported(self):
        """StubPDFExtractor is importable from packages.research.ingestion."""
        from packages.research.ingestion import StubPDFExtractor
        assert StubPDFExtractor is not None

    def test_stub_docx_extractor_exported(self):
        """StubDocxExtractor is importable from packages.research.ingestion."""
        from packages.research.ingestion import StubDocxExtractor
        assert StubDocxExtractor is not None

    def test_benchmark_result_exported(self):
        """BenchmarkResult is importable from packages.research.ingestion."""
        from packages.research.ingestion import BenchmarkResult
        assert BenchmarkResult is not None

    def test_run_extractor_benchmark_exported(self):
        """run_extractor_benchmark is importable from packages.research.ingestion."""
        from packages.research.ingestion import run_extractor_benchmark
        assert callable(run_extractor_benchmark)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


class TestResearchBenchmarkCLI:
    def test_cli_help_exits_0(self):
        """research-benchmark --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "polytool", "research-benchmark", "--help"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0

    def test_cli_json_output_on_fixtures(self):
        """research-benchmark --fixtures-dir <dir> --json exits 0 and prints valid JSON."""
        if not FIXTURE_DIR.exists():
            pytest.skip("Fixture dir not found")

        result = subprocess.run(
            [
                sys.executable, "-m", "polytool", "research-benchmark",
                "--fixtures-dir", str(FIXTURE_DIR),
                "--extractors", "plain_text,markdown",
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "metrics" in data
        assert "summary" in data
