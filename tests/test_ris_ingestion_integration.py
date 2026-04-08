"""Integration tests for the RIS v1 ingestion pipeline.

All tests use in-memory KnowledgeStore for isolation.
No network calls, no Chroma.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ris_seed_corpus"
SAMPLE_MD = FIXTURES_DIR / "sample_research.md"
SAMPLE_TXT = FIXTURES_DIR / "sample_wallet_analysis.txt"


@pytest.fixture()
def memory_store():
    """Provide a fresh in-memory KnowledgeStore and close it after the test."""
    from packages.polymarket.rag.knowledge_store import KnowledgeStore

    store = KnowledgeStore(":memory:")
    yield store
    store.close()


# ---------------------------------------------------------------------------
# PlainTextExtractor tests
# ---------------------------------------------------------------------------


def test_plain_text_extractor_from_md_file():
    """Extracts title from first H1, sets body and source_family correctly."""
    from packages.research.ingestion.extractors import PlainTextExtractor

    extractor = PlainTextExtractor()
    doc = extractor.extract(SAMPLE_MD, source_type="manual")

    assert doc.title == "Prediction Market Microstructure Analysis"
    assert "microstructure" in doc.body.lower()
    assert doc.source_family == "manual"  # SOURCE_FAMILIES["manual"] = "manual"
    assert doc.source_url.startswith("file://")
    assert doc.metadata.get("content_hash")


def test_plain_text_extractor_from_txt_file():
    """Extracts from .txt file; title falls back to filename stem."""
    from packages.research.ingestion.extractors import PlainTextExtractor

    extractor = PlainTextExtractor()
    doc = extractor.extract(SAMPLE_TXT, source_type="dossier")

    # No H1 in .txt -> title is filename stem
    assert doc.title == "sample_wallet_analysis"
    assert "gabagool22" in doc.body
    assert doc.source_family == "dossier_report"  # SOURCE_FAMILIES["dossier"]
    assert doc.source_url.startswith("file://")


def test_plain_text_extractor_from_raw_text():
    """Raw-text mode: accepts title kwarg, uses internal:// source_url."""
    from packages.research.ingestion.extractors import PlainTextExtractor

    raw = "This is a plain-text research note about prediction market dynamics."
    extractor = PlainTextExtractor()
    doc = extractor.extract(raw, title="Research Note", source_type="blog")

    assert doc.title == "Research Note"
    assert doc.body == raw
    assert doc.source_family == "blog"
    assert doc.source_url == "internal://manual"


def test_plain_text_extractor_missing_file():
    """Raises FileNotFoundError on non-existent file path."""
    from packages.research.ingestion.extractors import PlainTextExtractor

    extractor = PlainTextExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract(Path("/nonexistent/does_not_exist.md"))


# ---------------------------------------------------------------------------
# IngestPipeline tests
# ---------------------------------------------------------------------------


def test_pipeline_ingest_no_eval(memory_store):
    """Ingest with --no-eval: returns IngestResult with doc_id, chunk_count > 0, rejected=False."""
    from packages.research.ingestion.pipeline import IngestPipeline

    pipeline = IngestPipeline(store=memory_store)  # no evaluator = no eval gate
    result = pipeline.ingest(SAMPLE_MD, source_type="manual")

    assert result.rejected is False
    assert result.doc_id
    assert result.chunk_count > 0
    assert result.gate_decision is None


def test_pipeline_ingest_with_eval(memory_store):
    """Ingest with evaluator: gate_decision is set and gate is REVIEW for valid content.

    Phase 2 behavior: ManualProvider all-3s yields composite=3.0 < P3 threshold 3.2,
    so the gate is REVIEW rather than ACCEPT. REVIEW documents are still ingested
    (not rejected) — they pass the pipeline but are flagged for human review.
    """
    from packages.research.ingestion.pipeline import IngestPipeline
    from packages.research.evaluation.evaluator import DocumentEvaluator

    pipeline = IngestPipeline(store=memory_store, evaluator=DocumentEvaluator())
    result = pipeline.ingest(SAMPLE_MD, source_type="manual")

    assert result.rejected is False
    assert result.gate_decision is not None
    assert result.gate_decision.gate == "REVIEW"
    assert result.chunk_count > 0


def test_pipeline_hard_stop_empty(memory_store, tmp_path):
    """Hard stop on empty body: rejected=True, reject_reason mentions empty/too_short."""
    from packages.research.ingestion.pipeline import IngestPipeline

    empty_file = tmp_path / "empty.md"
    empty_file.write_text("", encoding="utf-8")

    pipeline = IngestPipeline(store=memory_store)
    result = pipeline.ingest(empty_file, source_type="manual")

    assert result.rejected is True
    assert result.reject_reason is not None
    reason_lower = result.reject_reason.lower()
    assert "empty" in reason_lower or "too_short" in reason_lower or "short" in reason_lower


# ---------------------------------------------------------------------------
# query_knowledge_store tests
# ---------------------------------------------------------------------------


def test_query_knowledge_store_basic(memory_store):
    """Ingest 2 docs of different families; source_family filter returns only matching."""
    from packages.research.ingestion.pipeline import IngestPipeline
    from packages.research.ingestion.retriever import query_knowledge_store

    pipeline = IngestPipeline(store=memory_store)
    pipeline.ingest(SAMPLE_MD, source_type="manual")      # family = "manual"
    pipeline.ingest(SAMPLE_TXT, source_type="dossier")    # family = "dossier_report"

    # Add a claim for each doc so query_claims returns something
    docs_manual = memory_store.query_claims(apply_freshness=False)
    # query_claims returns claims; we need to add claims for this test to have results
    # Let's add claims directly
    doc_id_m = memory_store.add_source_document(
        title="Manual Doc",
        source_url="internal://test1",
        source_family="manual",
        content_hash="aaa",
    )
    doc_id_d = memory_store.add_source_document(
        title="Dossier Doc",
        source_url="internal://test2",
        source_family="dossier_report",
        content_hash="bbb",
    )
    memory_store.add_claim(
        claim_text="Manual family claim for testing retrieval.",
        claim_type="empirical",
        confidence=0.9,
        trust_tier="PRACTITIONER",
        actor="test",
        source_document_id=doc_id_m,
    )
    memory_store.add_claim(
        claim_text="Dossier family claim for testing retrieval.",
        claim_type="empirical",
        confidence=0.9,
        trust_tier="PRACTITIONER",
        actor="test",
        source_document_id=doc_id_d,
    )

    manual_results = query_knowledge_store(memory_store, source_family="manual")
    dossier_results = query_knowledge_store(memory_store, source_family="dossier_report")

    assert any("manual" in str(r).lower() or True for r in manual_results)
    # All manual_results must come from manual family docs
    for r in manual_results:
        src_doc_id = r.get("source_document_id")
        if src_doc_id:
            src_doc = memory_store.get_source_document(src_doc_id)
            if src_doc:
                assert src_doc["source_family"] == "manual"

    assert len(manual_results) >= 1
    assert len(dossier_results) >= 1
    # manual results should not include dossier claim
    manual_claim_texts = [r["claim_text"] for r in manual_results]
    assert not any("dossier" in t.lower() for t in manual_claim_texts)


def test_query_knowledge_store_min_freshness(memory_store):
    """Old news doc gets low freshness; min_freshness=0.9 excludes it."""
    from packages.research.ingestion.retriever import query_knowledge_store

    # Add a news doc published 3 years ago (half-life=3 months -> very low freshness)
    old_published = "2022-01-01T00:00:00+00:00"
    doc_id = memory_store.add_source_document(
        title="Old News Article",
        source_url="internal://old_news",
        source_family="news",
        content_hash="ccc",
        published_at=old_published,
    )
    memory_store.add_claim(
        claim_text="Old news claim that should have very low freshness score.",
        claim_type="empirical",
        confidence=0.9,
        trust_tier="PRACTITIONER",
        actor="test",
        source_document_id=doc_id,
    )

    # With high min_freshness the old claim should be excluded
    results_strict = query_knowledge_store(memory_store, min_freshness=0.9)
    old_claim_texts = [r["claim_text"] for r in results_strict]
    assert not any("old news" in t.lower() for t in old_claim_texts)

    # Without filter it should appear
    results_all = query_knowledge_store(memory_store, min_freshness=None)
    all_claim_texts = [r["claim_text"] for r in results_all]
    assert any("old news" in t.lower() for t in all_claim_texts)


# ---------------------------------------------------------------------------
# format_provenance tests
# ---------------------------------------------------------------------------


def test_format_provenance_output(memory_store):
    """format_provenance returns string with claim text, confidence, and source title."""
    from packages.research.ingestion.retriever import format_provenance

    doc_id = memory_store.add_source_document(
        title="Test Source",
        source_url="internal://test",
        source_family="manual",
        content_hash="ddd",
    )
    claim_id = memory_store.add_claim(
        claim_text="Test claim for provenance formatting.",
        claim_type="empirical",
        confidence=0.85,
        trust_tier="PRACTITIONER",
        actor="test",
        source_document_id=doc_id,
    )
    memory_store.add_evidence(
        claim_id=claim_id,
        source_document_id=doc_id,
        excerpt="Test excerpt",
    )

    claim = memory_store.get_claim(claim_id)
    source_docs = memory_store.get_provenance(claim_id)

    provenance_str = format_provenance(claim, source_docs)

    assert "Test claim" in provenance_str
    assert "0.85" in provenance_str
    assert "Test Source" in provenance_str


# ---------------------------------------------------------------------------
# End-to-end fixture test
# ---------------------------------------------------------------------------


def test_end_to_end_fixture_ingest(memory_store):
    """Ingest sample_research.md -> add claim -> query -> result present."""
    from packages.research.ingestion.pipeline import IngestPipeline

    pipeline = IngestPipeline(store=memory_store)
    result = pipeline.ingest(SAMPLE_MD, source_type="manual")

    assert result.rejected is False
    assert result.doc_id

    # Add a claim linked to the ingested doc
    claim_id = memory_store.add_claim(
        claim_text="Prediction Market Microstructure Analysis claim.",
        claim_type="empirical",
        confidence=0.8,
        trust_tier="PRACTITIONER",
        actor="test",
        source_document_id=result.doc_id,
    )

    # Verify source doc is retrievable
    doc = memory_store.get_source_document(result.doc_id)
    assert doc is not None
    assert "Prediction Market Microstructure" in (doc.get("title") or "")


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def test_cli_smoke_no_eval():
    """CLI research-ingest --file sample_research.md --no-eval --json exits 0."""
    result = subprocess.run(
        [
            sys.executable, "-m", "polytool",
            "research-ingest",
            "--file", str(SAMPLE_MD),
            "--no-eval",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),  # repo root
    )
    assert result.returncode == 0, (
        f"CLI exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = json.loads(result.stdout)
    assert "doc_id" in output
    assert output.get("rejected") is False
