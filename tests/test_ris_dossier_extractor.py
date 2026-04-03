"""Offline deterministic tests for RIS dossier extraction pipeline.

Tests cover:
- parse_dossier_json: header, detectors, pnl_summary extraction
- parse_memo: TODO filtering, usable body text
- parse_hypothesis_candidates: top candidates with key metrics
- extract_dossier_findings: structured finding dicts from a dossier dir
- batch_extract_dossiers: walks tree, yields per-run results
- DossierAdapter.adapt: returns ExtractedDocument with source_family="dossier_report"
- IngestPipeline round-trip: source_family="dossier_report" in KnowledgeStore
- Idempotency: double-extraction does not duplicate source_documents
- Graceful handling of missing/partial files
- Provenance metadata preservation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures — minimal dossier files
# ---------------------------------------------------------------------------

MINIMAL_DOSSIER_JSON = {
    "schema_version": 1,
    "header": {
        "export_id": "test-export-123",
        "generated_at": "2026-04-01T10:00:00Z",
        "max_trades": 100,
        "proxy_wallet": "0xABCDEF1234567890",
        "user_input": "@testuser",
        "window_days": 30,
        "window_end": "2026-04-01T00:00:00Z",
        "window_start": "2026-03-02T00:00:00Z",
    },
    "detectors": {
        "bucket_type": "weekly",
        "latest": [
            {"bucket_start": "2026-03-28T00:00:00Z", "detector": "COMPLETE_SET_ARBISH", "label": "ARB_LIKELY", "score": 1.0},
            {"bucket_start": "2026-03-28T00:00:00Z", "detector": "DCA_LADDERING", "label": "DCA_LIKELY", "score": 0.8},
            {"bucket_start": "2026-03-28T00:00:00Z", "detector": "MARKET_SELECTION_BIAS", "label": "NO_BIAS", "score": 0.2},
            {"bucket_start": "2026-03-28T00:00:00Z", "detector": "HOLDING_STYLE", "label": "SHORT_TERM", "score": 0.9},
        ],
        "trend": [],
    },
    "pnl_summary": {
        "latest_bucket": "2026-03-29T00:00:00Z",
        "pricing_confidence": "high",
        "pricing_snapshot_ratio": 0.92,
        "trend_30d": "upward",
    },
    "anchors": [],
    "coverage": {},
    "distributions": {},
    "liquidity_summary": {},
    "positions": [],
}

MINIMAL_MEMO_WITH_CONTENT = """# LLM Research Packet v1

User input: @testuser
Proxy wallet: 0xABCDEF1234567890

## Executive Summary
This wallet exhibits strong arb-likely behavior with DCA laddering.

## Key Observations
- Wallet trades high-frequency arb patterns.
- Position sizes are relatively uniform.

## Hypotheses
| claim | evidence |
|-------|----------|
| Arb focus | score=1.0 |
"""

MINIMAL_MEMO_ALL_TODOS = """# LLM Research Packet v1

User input: @testuser

## Executive Summary
- TODO: Summarize the strategy in 2-3 sentences.

## Key Observations
- TODO: Bullet observations backed by metrics/trade_uids.

## Hypotheses
| claim | evidence |
|-------|----------|
| TODO  | TODO     |
"""

MINIMAL_HYPOTHESIS_CANDIDATES = {
    "candidates": [
        {
            "rank": 1,
            "segment_key": "category:politics",
            "clv_variant_used": "settlement",
            "denominators": {},
            "falsification_plan": "Test on different category",
            "metrics": {
                "avg_clv_pct": 3.5,
                "beat_close_rate": 0.65,
                "count": 42,
                "win_rate": 0.58,
                "median_clv_pct": 2.8,
                "notional_weighted_avg_clv_pct": 3.1,
                "notional_weighted_beat_close_rate": 0.62,
            },
        },
        {
            "rank": 2,
            "segment_key": "category:sports",
            "clv_variant_used": "pre_event",
            "denominators": {},
            "falsification_plan": "Test on different category",
            "metrics": {
                "avg_clv_pct": 1.2,
                "beat_close_rate": 0.51,
                "count": 18,
                "win_rate": 0.50,
                "median_clv_pct": 1.0,
                "notional_weighted_avg_clv_pct": 1.1,
                "notional_weighted_beat_close_rate": 0.50,
            },
        },
    ],
    "generated_at": "2026-04-01T10:00:00Z",
    "run_id": "test-run-id-abc",
    "user_slug": "testuser",
    "wallet": "0xABCDEF1234567890",
}


@pytest.fixture
def dossier_dir(tmp_path):
    """Create a minimal dossier run directory with all four files."""
    run_dir = tmp_path / "users" / "testuser" / "0xABCDEF1234567890" / "2026-04-01" / "test-run-id-abc"
    run_dir.mkdir(parents=True)

    (run_dir / "dossier.json").write_text(json.dumps(MINIMAL_DOSSIER_JSON))
    (run_dir / "memo.md").write_text(MINIMAL_MEMO_WITH_CONTENT)
    (run_dir / "hypothesis_candidates.json").write_text(json.dumps(MINIMAL_HYPOTHESIS_CANDIDATES))

    return run_dir


@pytest.fixture
def dossier_dir_todos_memo(tmp_path):
    """Dossier dir where memo.md is all TODOs."""
    run_dir = tmp_path / "users" / "testuser" / "0xABCDEF" / "2026-04-01" / "run-todos"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.json").write_text(json.dumps(MINIMAL_DOSSIER_JSON))
    (run_dir / "memo.md").write_text(MINIMAL_MEMO_ALL_TODOS)
    (run_dir / "hypothesis_candidates.json").write_text(json.dumps(MINIMAL_HYPOTHESIS_CANDIDATES))
    return run_dir


@pytest.fixture
def dossier_dir_missing_files(tmp_path):
    """Dossier dir with only dossier.json (memo and candidates missing)."""
    run_dir = tmp_path / "users" / "testuser" / "0xABCDEF" / "2026-04-01" / "run-missing"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.json").write_text(json.dumps(MINIMAL_DOSSIER_JSON))
    return run_dir


@pytest.fixture
def batch_dossiers_base(tmp_path):
    """Multiple dossier run dirs under a single base."""
    base = tmp_path / "batch_base"
    for i, run_id in enumerate(["run-aaa", "run-bbb", "run-ccc"]):
        user = f"user{i}"
        wallet = f"0xWALLET{i}"
        run_dir = base / "users" / user / wallet / "2026-04-01" / run_id
        run_dir.mkdir(parents=True)
        dossier = dict(MINIMAL_DOSSIER_JSON)
        dossier = json.loads(json.dumps(MINIMAL_DOSSIER_JSON))
        dossier["header"]["user_input"] = f"@{user}"
        dossier["header"]["proxy_wallet"] = wallet
        (run_dir / "dossier.json").write_text(json.dumps(dossier))
        (run_dir / "memo.md").write_text(MINIMAL_MEMO_WITH_CONTENT)
        (run_dir / "hypothesis_candidates.json").write_text(json.dumps(MINIMAL_HYPOTHESIS_CANDIDATES))
    return base


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _import_extractor():
    from packages.research.integration.dossier_extractor import (
        _parse_dossier_json,
        _parse_memo,
        _parse_hypothesis_candidates,
        extract_dossier_findings,
        batch_extract_dossiers,
        ingest_dossier_findings,
    )
    return _parse_dossier_json, _parse_memo, _parse_hypothesis_candidates, extract_dossier_findings, batch_extract_dossiers, ingest_dossier_findings


def _import_adapter():
    from packages.research.integration.dossier_extractor import DossierAdapter
    return DossierAdapter


# ---------------------------------------------------------------------------
# Tests: _parse_dossier_json
# ---------------------------------------------------------------------------

class TestParseDossierJson:
    def test_parses_header_fields(self, tmp_path):
        p = tmp_path / "dossier.json"
        p.write_text(json.dumps(MINIMAL_DOSSIER_JSON))
        fn = _import_extractor()[0]
        result = fn(p)
        assert result["export_id"] == "test-export-123"
        assert result["proxy_wallet"] == "0xABCDEF1234567890"
        assert result["user_input"] == "@testuser"
        assert result["generated_at"] == "2026-04-01T10:00:00Z"
        assert result["window_days"] == 30

    def test_parses_detector_labels(self, tmp_path):
        p = tmp_path / "dossier.json"
        p.write_text(json.dumps(MINIMAL_DOSSIER_JSON))
        fn = _import_extractor()[0]
        result = fn(p)
        labels = result["detector_labels"]
        assert "COMPLETE_SET_ARBISH" in labels
        assert labels["COMPLETE_SET_ARBISH"] == "ARB_LIKELY"
        assert "DCA_LADDERING" in labels
        assert labels["DCA_LADDERING"] == "DCA_LIKELY"

    def test_parses_pnl_summary(self, tmp_path):
        p = tmp_path / "dossier.json"
        p.write_text(json.dumps(MINIMAL_DOSSIER_JSON))
        fn = _import_extractor()[0]
        result = fn(p)
        assert result["pricing_confidence"] == "high"
        assert result["pnl_trend_30d"] == "upward"

    def test_missing_file_raises(self, tmp_path):
        fn = _import_extractor()[0]
        with pytest.raises(FileNotFoundError):
            fn(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# Tests: _parse_memo
# ---------------------------------------------------------------------------

class TestParseMemo:
    def test_returns_usable_content(self, tmp_path):
        p = tmp_path / "memo.md"
        p.write_text(MINIMAL_MEMO_WITH_CONTENT)
        fn = _import_extractor()[1]
        result = fn(p)
        assert len(result) > 0
        assert "arb-likely" in result.lower() or "arb" in result.lower()

    def test_all_todos_returns_empty_or_minimal(self, tmp_path):
        p = tmp_path / "memo.md"
        p.write_text(MINIMAL_MEMO_ALL_TODOS)
        fn = _import_extractor()[1]
        result = fn(p)
        # Should strip TODO content or return empty string
        assert "TODO" not in result

    def test_missing_file_returns_empty_string(self, tmp_path):
        fn = _import_extractor()[1]
        result = fn(tmp_path / "nonexistent.md")
        assert result == ""


# ---------------------------------------------------------------------------
# Tests: _parse_hypothesis_candidates
# ---------------------------------------------------------------------------

class TestParseHypothesisCandidates:
    def test_returns_list_of_dicts(self, tmp_path):
        p = tmp_path / "hypothesis_candidates.json"
        p.write_text(json.dumps(MINIMAL_HYPOTHESIS_CANDIDATES))
        fn = _import_extractor()[2]
        result = fn(p)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_extracts_key_metrics(self, tmp_path):
        p = tmp_path / "hypothesis_candidates.json"
        p.write_text(json.dumps(MINIMAL_HYPOTHESIS_CANDIDATES))
        fn = _import_extractor()[2]
        result = fn(p)
        top = result[0]
        assert "segment_key" in top
        assert "avg_clv_pct" in top
        assert "beat_close_rate" in top
        assert "count" in top
        assert top["segment_key"] == "category:politics"
        assert top["avg_clv_pct"] == 3.5

    def test_missing_file_returns_empty_list(self, tmp_path):
        fn = _import_extractor()[2]
        result = fn(tmp_path / "nonexistent.json")
        assert result == []


# ---------------------------------------------------------------------------
# Tests: extract_dossier_findings
# ---------------------------------------------------------------------------

class TestExtractDossierFindings:
    def test_returns_list_of_dicts(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        assert isinstance(findings, list)
        assert len(findings) >= 1

    def test_each_finding_has_required_keys(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        for f in findings:
            assert "title" in f, f"Missing 'title' in {f.keys()}"
            assert "body" in f, f"Missing 'body' in {f.keys()}"
            assert "source_url" in f, f"Missing 'source_url' in {f.keys()}"
            assert "source_family" in f, f"Missing 'source_family' in {f.keys()}"
            assert "author" in f, f"Missing 'author' in {f.keys()}"
            assert "metadata" in f, f"Missing 'metadata' in {f.keys()}"

    def test_source_family_is_dossier_report(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        for f in findings:
            assert f["source_family"] == "dossier_report"

    def test_source_url_is_file_uri(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        for f in findings:
            assert f["source_url"].startswith("file://"), f"source_url should be file:// URI, got {f['source_url']}"

    def test_metadata_has_provenance(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        for f in findings:
            meta = f["metadata"]
            assert "wallet" in meta
            assert "run_id" in meta
            assert "dossier_path" in meta

    def test_author_is_user_slug(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        # Author should be derived from user_input or dossier dir
        for f in findings:
            assert f["author"] != ""
            assert f["author"] is not None

    def test_detector_document_produced(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        titles = [f["title"] for f in findings]
        detector_docs = [t for t in titles if "Detector" in t or "detector" in t.lower()]
        assert len(detector_docs) >= 1, f"Expected a detector document, got titles: {titles}"

    def test_missing_memo_handled_gracefully(self, dossier_dir_missing_files):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir_missing_files)
        # Should still return at least the detector document
        assert isinstance(findings, list)
        assert len(findings) >= 1

    def test_todos_memo_no_memo_document(self, dossier_dir_todos_memo):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir_todos_memo)
        memo_docs = [f for f in findings if "Memo" in f["title"]]
        # Either no memo doc, or memo doc body has no TODO content
        for doc in memo_docs:
            assert "TODO" not in doc["body"]

    def test_hypothesis_document_produced_when_candidates_exist(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        titles = [f["title"] for f in findings]
        hyp_docs = [t for t in titles if "Hypothesis" in t or "hypothesis" in t.lower() or "Candidate" in t]
        assert len(hyp_docs) >= 1, f"Expected hypothesis document, got: {titles}"


# ---------------------------------------------------------------------------
# Tests: batch_extract_dossiers
# ---------------------------------------------------------------------------

class TestBatchExtractDossiers:
    def test_returns_all_findings_from_all_runs(self, batch_dossiers_base):
        _, _, _, _, batch_extract, _ = _import_extractor()
        all_findings = batch_extract(batch_dossiers_base)
        # Should have findings from all 3 runs (1+ per run)
        assert len(all_findings) >= 3

    def test_all_findings_have_dossier_report_family(self, batch_dossiers_base):
        _, _, _, _, batch_extract, _ = _import_extractor()
        findings = batch_extract(batch_dossiers_base)
        for f in findings:
            assert f["source_family"] == "dossier_report"

    def test_empty_base_dir_returns_empty_list(self, tmp_path):
        empty_base = tmp_path / "empty"
        empty_base.mkdir()
        _, _, _, _, batch_extract, _ = _import_extractor()
        result = batch_extract(empty_base)
        assert result == []

    def test_dir_without_dossier_json_is_skipped(self, tmp_path):
        """A run dir without dossier.json should be skipped silently."""
        base = tmp_path / "base"
        run_dir = base / "users" / "testuser" / "0xWALLET" / "2026-04-01" / "run-no-dossier"
        run_dir.mkdir(parents=True)
        (run_dir / "memo.md").write_text("some content")
        _, _, _, _, batch_extract, _ = _import_extractor()
        result = batch_extract(base)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: DossierAdapter
# ---------------------------------------------------------------------------

class TestDossierAdapter:
    def test_adapt_returns_extracted_document(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        DossierAdapter = _import_adapter()
        adapter = DossierAdapter()
        raw = findings[0]
        doc = adapter.adapt(raw)
        from packages.research.ingestion.extractors import ExtractedDocument
        assert isinstance(doc, ExtractedDocument)

    def test_adapt_source_family_is_dossier_report(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        DossierAdapter = _import_adapter()
        adapter = DossierAdapter()
        doc = adapter.adapt(findings[0])
        assert doc.source_family == "dossier_report"

    def test_adapt_preserves_title(self, dossier_dir):
        _, _, _, extract, _, _ = _import_extractor()
        findings = extract(dossier_dir)
        DossierAdapter = _import_adapter()
        adapter = DossierAdapter()
        doc = adapter.adapt(findings[0])
        assert doc.title == findings[0]["title"]

    def test_dossier_in_adapter_registry(self):
        from packages.research.ingestion.adapters import ADAPTER_REGISTRY
        assert "dossier" in ADAPTER_REGISTRY


# ---------------------------------------------------------------------------
# Tests: IngestPipeline round-trip
# ---------------------------------------------------------------------------

class TestIngestPipelineRoundTrip:
    def test_ingest_stores_source_document(self, dossier_dir):
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        _, _, _, extract, _, ingest = _import_extractor()
        findings = extract(dossier_dir)
        store = KnowledgeStore(db_path=":memory:")
        results = ingest(findings, store)
        assert len(results) >= 1
        # At least one should be accepted (not rejected)
        accepted = [r for r in results if not r.rejected]
        assert len(accepted) >= 1

    def test_ingested_has_dossier_report_family(self, dossier_dir):
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        _, _, _, extract, _, ingest = _import_extractor()
        findings = extract(dossier_dir)
        store = KnowledgeStore(db_path=":memory:")
        results = ingest(findings, store)
        accepted = [r for r in results if not r.rejected]
        assert len(accepted) >= 1
        # Verify the stored documents have the correct source_family
        rows = store._conn.execute(
            "SELECT source_family FROM source_documents WHERE source_family='dossier_report'"
        ).fetchall()
        assert len(rows) >= 1

    def test_idempotency_no_duplicate_docs(self, dossier_dir):
        """Running extraction twice on same dossier does not create duplicate source_documents."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        _, _, _, extract, _, ingest = _import_extractor()
        findings = extract(dossier_dir)
        store = KnowledgeStore(db_path=":memory:")
        # First ingest
        ingest(findings, store)
        count_1 = store._conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        # Second ingest (same findings)
        ingest(findings, store)
        count_2 = store._conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        assert count_1 == count_2, f"Duplicate docs created: {count_1} -> {count_2}"
