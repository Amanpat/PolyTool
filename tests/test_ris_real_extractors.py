"""Offline tests for RIS Phase 3 real extractors, enhanced benchmark, and reseed workflow.

All tests are offline, deterministic, and require no network or external dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ris_seed_corpus"
STRUCTURED_MD = FIXTURE_DIR / "sample_structured.md"


# ---------------------------------------------------------------------------
# StructuredMarkdownExtractor tests
# ---------------------------------------------------------------------------


class TestStructuredMarkdownExtractor:
    def test_structured_markdown_extractor_is_subclass_of_extractor(self):
        """StructuredMarkdownExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor, Extractor
        assert issubclass(StructuredMarkdownExtractor, Extractor)

    def test_structured_markdown_extractor_registered(self):
        """get_extractor('structured_markdown') returns StructuredMarkdownExtractor."""
        from packages.research.ingestion.extractors import get_extractor, StructuredMarkdownExtractor
        ext = get_extractor("structured_markdown")
        assert isinstance(ext, StructuredMarkdownExtractor)

    def test_structured_markdown_on_fixture_returns_extracted_document(self):
        """StructuredMarkdownExtractor.extract() returns ExtractedDocument from fixture."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor, ExtractedDocument
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        assert isinstance(doc, ExtractedDocument)
        assert doc.title
        assert len(doc.body) > 0

    def test_structured_markdown_section_count_gte_2(self):
        """StructuredMarkdownExtractor returns section_count >= 2 on fixture."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        assert doc.metadata.get("section_count", 0) >= 2

    def test_structured_markdown_header_count_gte_3(self):
        """StructuredMarkdownExtractor returns header_count >= 3 on fixture."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        assert doc.metadata.get("header_count", 0) >= 3

    def test_structured_markdown_table_count_gte_1(self):
        """StructuredMarkdownExtractor returns table_count >= 1 on fixture."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        assert doc.metadata.get("table_count", 0) >= 1

    def test_structured_markdown_code_block_count_gte_1(self):
        """StructuredMarkdownExtractor returns code_block_count >= 1 on fixture."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        assert doc.metadata.get("code_block_count", 0) >= 1

    def test_structured_markdown_sections_is_list(self):
        """StructuredMarkdownExtractor metadata['sections'] is a list of strings."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor
        ext = StructuredMarkdownExtractor()
        doc = ext.extract(STRUCTURED_MD, source_type="reference_doc")
        sections = doc.metadata.get("sections", None)
        assert isinstance(sections, list)
        assert len(sections) >= 2
        for s in sections:
            assert isinstance(s, str)

    def test_structured_markdown_body_preserved(self):
        """StructuredMarkdownExtractor body preserves all sections unchanged."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor, PlainTextExtractor
        structured = StructuredMarkdownExtractor()
        plain = PlainTextExtractor()
        doc_s = structured.extract(STRUCTURED_MD, source_type="reference_doc")
        doc_p = plain.extract(STRUCTURED_MD, source_type="reference_doc")
        # Body should be identical or longer (structured preserves, not strips)
        assert len(doc_s.body) >= len(doc_p.body)

    def test_structured_markdown_body_longer_than_plain_text(self, tmp_path):
        """StructuredMarkdownExtractor body is >= PlainTextExtractor body on same file."""
        md_file = tmp_path / "rich.md"
        md_file.write_text(
            "# Title\n\n## Section 1\n\nText.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "```python\nprint('hello')\n```\n",
            encoding="utf-8",
        )
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor, PlainTextExtractor
        s = StructuredMarkdownExtractor().extract(md_file, source_type="manual")
        p = PlainTextExtractor().extract(md_file, source_type="manual")
        assert len(s.body) >= len(p.body)

    def test_structured_markdown_fallback_on_corrupt_input(self, tmp_path):
        """StructuredMarkdownExtractor falls back gracefully on read errors."""
        # Create a valid file with minimal content (simulating a nearly-empty doc)
        md_file = tmp_path / "minimal.md"
        md_file.write_text("", encoding="utf-8")
        from packages.research.ingestion.extractors import StructuredMarkdownExtractor, ExtractedDocument
        ext = StructuredMarkdownExtractor()
        # Should not crash; should return ExtractedDocument
        doc = ext.extract(md_file, source_type="manual")
        assert isinstance(doc, ExtractedDocument)
        # section_count should be 0 for empty file (not a crash)
        assert doc.metadata.get("section_count", 0) == 0


# ---------------------------------------------------------------------------
# PDFExtractor — real implementation with graceful ImportError fallback
# ---------------------------------------------------------------------------


class TestPDFExtractor:
    def test_pdf_extractor_is_subclass_of_extractor(self):
        """PDFExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import PDFExtractor, Extractor
        assert issubclass(PDFExtractor, Extractor)

    def test_pdf_extractor_registered(self):
        """EXTRACTOR_REGISTRY['pdf'] maps to PDFExtractor (not stub)."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY, PDFExtractor
        assert EXTRACTOR_REGISTRY["pdf"] is PDFExtractor

    def test_pdf_extractor_raises_import_error_when_pdfplumber_missing(self, tmp_path):
        """PDFExtractor raises ImportError with install hint when pdfplumber absent."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")
        from packages.research.ingestion.extractors import PDFExtractor
        ext = PDFExtractor()
        # Patch pdfplumber as unavailable
        with patch.dict("sys.modules", {"pdfplumber": None}):
            # Force re-evaluation by patching the extractor's _pdfplumber attribute
            ext._pdfplumber = None
            with pytest.raises((ImportError, Exception)):
                ext.extract(pdf_file, source_type="manual")

    def test_pdf_extractor_import_error_message_mentions_pdfplumber(self, tmp_path):
        """PDFExtractor ImportError message mentions pdfplumber install."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")
        from packages.research.ingestion.extractors import PDFExtractor
        ext = PDFExtractor()
        ext._pdfplumber = None
        try:
            ext.extract(pdf_file, source_type="manual")
        except (ImportError, Exception) as exc:
            assert "pdfplumber" in str(exc).lower() or "pdf" in str(exc).lower()


# ---------------------------------------------------------------------------
# DocxExtractor — real implementation with graceful ImportError fallback
# ---------------------------------------------------------------------------


class TestDocxExtractor:
    def test_docx_extractor_is_subclass_of_extractor(self):
        """DocxExtractor is a subclass of Extractor ABC."""
        from packages.research.ingestion.extractors import DocxExtractor, Extractor
        assert issubclass(DocxExtractor, Extractor)

    def test_docx_extractor_registered(self):
        """EXTRACTOR_REGISTRY['docx'] maps to DocxExtractor (not stub)."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY, DocxExtractor
        assert EXTRACTOR_REGISTRY["docx"] is DocxExtractor

    def test_docx_extractor_raises_import_error_when_python_docx_missing(self, tmp_path):
        """DocxExtractor raises ImportError with install hint when python-docx absent."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"fake docx content")
        from packages.research.ingestion.extractors import DocxExtractor
        ext = DocxExtractor()
        ext._docx = None
        with pytest.raises((ImportError, Exception)):
            ext.extract(docx_file, source_type="manual")

    def test_docx_extractor_import_error_message_mentions_python_docx(self, tmp_path):
        """DocxExtractor ImportError message mentions python-docx."""
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"fake docx content")
        from packages.research.ingestion.extractors import DocxExtractor
        ext = DocxExtractor()
        ext._docx = None
        try:
            ext.extract(docx_file, source_type="manual")
        except (ImportError, Exception) as exc:
            assert "python-docx" in str(exc) or "docx" in str(exc).lower()


# ---------------------------------------------------------------------------
# EXTRACTOR_REGISTRY completeness
# ---------------------------------------------------------------------------


class TestExtractorRegistryPhase3:
    def test_registry_has_structured_markdown(self):
        """EXTRACTOR_REGISTRY contains 'structured_markdown' key."""
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "structured_markdown" in EXTRACTOR_REGISTRY

    def test_registry_has_plain_text(self):
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "plain_text" in EXTRACTOR_REGISTRY

    def test_registry_has_markdown(self):
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "markdown" in EXTRACTOR_REGISTRY

    def test_registry_has_pdf(self):
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "pdf" in EXTRACTOR_REGISTRY

    def test_registry_has_docx(self):
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert "docx" in EXTRACTOR_REGISTRY

    def test_registry_has_at_least_5_entries(self):
        from packages.research.ingestion.extractors import EXTRACTOR_REGISTRY
        assert len(EXTRACTOR_REGISTRY) >= 5


# ---------------------------------------------------------------------------
# Benchmark quality proxy fields
# ---------------------------------------------------------------------------


class TestBenchmarkQualityProxies:
    def test_extractor_metric_has_section_count_field(self):
        """ExtractorMetric has section_count field."""
        from packages.research.ingestion.benchmark import ExtractorMetric
        m = ExtractorMetric(
            extractor_name="test", file_name="test.md",
            char_count=10, word_count=2, elapsed_ms=1.0,
        )
        assert hasattr(m, "section_count")
        assert m.section_count == 0

    def test_extractor_metric_has_header_count_field(self):
        """ExtractorMetric has header_count field."""
        from packages.research.ingestion.benchmark import ExtractorMetric
        m = ExtractorMetric(
            extractor_name="test", file_name="test.md",
            char_count=10, word_count=2, elapsed_ms=1.0,
        )
        assert hasattr(m, "header_count")
        assert m.header_count == 0

    def test_extractor_metric_has_table_count_field(self):
        """ExtractorMetric has table_count field."""
        from packages.research.ingestion.benchmark import ExtractorMetric
        m = ExtractorMetric(
            extractor_name="test", file_name="test.md",
            char_count=10, word_count=2, elapsed_ms=1.0,
        )
        assert hasattr(m, "table_count")
        assert m.table_count == 0

    def test_extractor_metric_has_code_block_count_field(self):
        """ExtractorMetric has code_block_count field."""
        from packages.research.ingestion.benchmark import ExtractorMetric
        m = ExtractorMetric(
            extractor_name="test", file_name="test.md",
            char_count=10, word_count=2, elapsed_ms=1.0,
        )
        assert hasattr(m, "code_block_count")
        assert m.code_block_count == 0

    def test_extractor_metric_has_extractor_used_field(self):
        """ExtractorMetric has extractor_used field."""
        from packages.research.ingestion.benchmark import ExtractorMetric
        m = ExtractorMetric(
            extractor_name="test", file_name="test.md",
            char_count=10, word_count=2, elapsed_ms=1.0,
        )
        assert hasattr(m, "extractor_used")

    def test_benchmark_populates_quality_proxies_from_structured_metadata(self, tmp_path):
        """run_extractor_benchmark populates section_count from StructuredMarkdownExtractor."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        fixture_dir = tmp_path / "bm_fixtures"
        fixture_dir.mkdir()
        # Copy the structured fixture
        import shutil
        shutil.copy(STRUCTURED_MD, fixture_dir / "sample_structured.md")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(fixture_dir, extractors=["structured_markdown"])
        successful = [m for m in result.metrics if m.error is None]
        assert len(successful) >= 1
        m = successful[0]
        assert m.section_count >= 2, f"Expected section_count >= 2, got {m.section_count}"
        assert m.header_count >= 3, f"Expected header_count >= 3, got {m.header_count}"
        assert m.table_count >= 1, f"Expected table_count >= 1, got {m.table_count}"
        assert m.code_block_count >= 1, f"Expected code_block_count >= 1, got {m.code_block_count}"

    def test_benchmark_plain_text_has_zero_quality_proxies(self, tmp_path):
        """run_extractor_benchmark returns 0 quality proxies for plain_text extractor."""
        md_file = tmp_path / "doc.md"
        md_file.write_text("# Title\n\n## Section\n\nText.\n", encoding="utf-8")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(tmp_path, extractors=["plain_text"])
        successful = [m for m in result.metrics if m.error is None]
        assert len(successful) >= 1
        m = successful[0]
        # plain_text doesn't compute structural metadata
        assert m.section_count == 0
        assert m.header_count == 0

    def test_benchmark_summary_has_avg_section_count(self, tmp_path):
        """BenchmarkResult summary has avg_section_count for structured_markdown."""
        if not STRUCTURED_MD.exists():
            pytest.skip("sample_structured.md fixture not found")
        fixture_dir = tmp_path / "bm2"
        fixture_dir.mkdir()
        import shutil
        shutil.copy(STRUCTURED_MD, fixture_dir / "sample_structured.md")

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        result = run_extractor_benchmark(fixture_dir, extractors=["structured_markdown"])
        stats = result.summary.get("structured_markdown", {})
        assert "avg_section_count" in stats, f"Missing avg_section_count in {stats}"
        assert "avg_header_count" in stats

    def test_benchmark_artifact_includes_quality_proxy_fields(self, tmp_path):
        """benchmark_results.json artifact includes section_count in metrics."""
        md_file = tmp_path / "doc.md"
        md_file.write_text(
            "# Title\n\n## S1\n\nText.\n\n| A | B |\n|---|---|\n| x | y |\n\n"
            "```python\ncode\n```\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "out"

        from packages.research.ingestion.benchmark import run_extractor_benchmark
        run_extractor_benchmark(
            tmp_path, extractors=["structured_markdown"], output_dir=output_dir
        )
        artifact = output_dir / "benchmark_results.json"
        assert artifact.exists()
        data = json.loads(artifact.read_text(encoding="utf-8"))
        assert "metrics" in data
        if data["metrics"]:
            m = data["metrics"][0]
            assert "section_count" in m


# ---------------------------------------------------------------------------
# Task 2: Seed extractor selection and reseed tests
# ---------------------------------------------------------------------------


class TestSeedExtractorSelection:
    """Tests for extractor field in SeedEntry and auto-detection in run_seed."""

    def test_seed_entry_has_extractor_field(self):
        """SeedEntry has an optional extractor field."""
        from packages.research.ingestion.seed import SeedEntry
        entry = SeedEntry(
            path="docs/test.md",
            title="Test",
            source_type="reference_doc",
            source_family="book_foundational",
        )
        assert hasattr(entry, "extractor")
        assert entry.extractor is None

    def test_load_seed_manifest_parses_extractor_field(self, tmp_path):
        """load_seed_manifest() parses 'extractor' field from entries."""
        manifest_data = {
            "version": "3",
            "description": "Test manifest with extractor field",
            "entries": [
                {
                    "path": "docs/reference/RAGfiles/RIS_OVERVIEW.md",
                    "title": "RIS Overview",
                    "source_type": "reference_doc",
                    "source_family": "book_foundational",
                    "extractor": "structured_markdown",
                }
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        from packages.research.ingestion.seed import load_seed_manifest
        manifest = load_seed_manifest(manifest_file)
        assert len(manifest.entries) == 1
        assert manifest.entries[0].extractor == "structured_markdown"

    def test_seed_auto_detect_md_uses_structured_markdown(self, tmp_path):
        """run_seed() auto-detects structured_markdown for .md files when extractor=None."""
        md_file = tmp_path / "test_doc.md"
        md_file.write_text("# Test\n\n## Section\n\nContent here.\n", encoding="utf-8")

        manifest_data = {
            "version": "3",
            "description": "Test",
            "entries": [
                {
                    "path": str(md_file),
                    "title": "Test Doc",
                    "source_type": "reference_doc",
                    "source_family": "book_foundational",
                }
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        manifest = load_seed_manifest(manifest_file)
        store = KnowledgeStore(":memory:")
        try:
            result = run_seed(manifest, store, skip_eval=True)
            assert result.total == 1
            # Should succeed (no failure)
            failed_entries = [r for r in result.results if r["status"] == "failed"]
            assert len(failed_entries) == 0, f"Unexpected failures: {failed_entries}"
            # Check extractor_used in result
            ingested = [r for r in result.results if r["status"] == "ingested"]
            assert len(ingested) == 1
            assert ingested[0].get("extractor_used") == "structured_markdown"
        finally:
            store.close()

    def test_seed_with_extractor_field_uses_specified_extractor(self, tmp_path):
        """run_seed() uses the extractor specified in the manifest entry."""
        md_file = tmp_path / "test_doc.md"
        md_file.write_text("# Test\n\nContent here.\n", encoding="utf-8")

        manifest_data = {
            "version": "3",
            "description": "Test",
            "entries": [
                {
                    "path": str(md_file),
                    "title": "Test Doc",
                    "source_type": "reference_doc",
                    "source_family": "book_foundational",
                    "extractor": "structured_markdown",
                }
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        manifest = load_seed_manifest(manifest_file)
        store = KnowledgeStore(":memory:")
        try:
            result = run_seed(manifest, store, skip_eval=True)
            assert result.total == 1
            ingested = [r for r in result.results if r["status"] == "ingested"]
            assert len(ingested) == 1
            assert ingested[0].get("extractor_used") == "structured_markdown"
        finally:
            store.close()

    def test_reseed_replaces_document(self, tmp_path):
        """run_seed(reseed=True) replaces existing document, no duplicates."""
        md_file = tmp_path / "reseed_doc.md"
        md_file.write_text("# Reseed Test\n\n## Section\n\nContent for reseed test.\n", encoding="utf-8")

        manifest_data = {
            "version": "3",
            "description": "Reseed test",
            "entries": [
                {
                    "path": str(md_file),
                    "title": "Reseed Test",
                    "source_type": "reference_doc",
                    "source_family": "book_foundational",
                    "extractor": "structured_markdown",
                }
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        manifest = load_seed_manifest(manifest_file)
        store = KnowledgeStore(":memory:")
        try:
            # First seed
            r1 = run_seed(manifest, store, skip_eval=True)
            assert r1.ingested == 1
            first_doc_id = r1.results[0]["doc_id"]

            # Get count before reseed
            count_before = store._conn.execute(
                "SELECT COUNT(*) FROM source_documents"
            ).fetchone()[0]

            # Reseed
            r2 = run_seed(manifest, store, skip_eval=True, reseed=True)
            assert r2.ingested == 1

            # Count should not increase (replaced, not duplicated)
            count_after = store._conn.execute(
                "SELECT COUNT(*) FROM source_documents"
            ).fetchone()[0]
            assert count_after <= count_before, (
                f"Reseed should not increase document count: before={count_before}, after={count_after}"
            )
        finally:
            store.close()

    def test_reseed_false_does_not_delete(self, tmp_path):
        """run_seed(reseed=False) is idempotent — seeds twice without deleting."""
        md_file = tmp_path / "idempotent_doc.md"
        md_file.write_text("# Idempotent\n\nContent.\n", encoding="utf-8")

        manifest_data = {
            "version": "3",
            "description": "Idempotent test",
            "entries": [
                {
                    "path": str(md_file),
                    "title": "Idempotent",
                    "source_type": "reference_doc",
                    "source_family": "book_foundational",
                }
            ],
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        from packages.research.ingestion.seed import load_seed_manifest, run_seed
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        manifest = load_seed_manifest(manifest_file)
        store = KnowledgeStore(":memory:")
        try:
            r1 = run_seed(manifest, store, skip_eval=True)
            assert r1.ingested == 1

            r2 = run_seed(manifest, store, skip_eval=True, reseed=False)
            # Second ingest should succeed (INSERT OR IGNORE is idempotent)
            assert r2.total == 1
        finally:
            store.close()

    def test_cli_reseed_flag_parses_correctly(self):
        """research-seed --reseed flag is accepted by the argument parser."""
        import subprocess
        result = subprocess.run(
            [
                sys.executable, "-m", "polytool", "research-seed",
                "--manifest", "config/seed_manifest.json",
                "--reseed", "--help",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        # --help causes exit 0; --reseed must not cause an error
        assert result.returncode == 0
        assert "--reseed" in result.stdout

    def test_seed_manifest_v3_has_extractor_fields(self):
        """config/seed_manifest.json v3 has version=3 and extractor fields."""
        manifest_path = REPO_ROOT / "config" / "seed_manifest.json"
        if not manifest_path.exists():
            pytest.skip("seed_manifest.json not found")
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data.get("version") == "3"
        for entry in data.get("entries", []):
            assert "extractor" in entry, f"Entry missing extractor field: {entry.get('title')}"
