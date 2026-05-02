"""Tests for the Scientific RAG Evaluation Benchmark v0 infrastructure.

All tests are offline and deterministic. No network calls, no external DBs.
Uses tmp_path for file I/O and in-memory SQLite for KnowledgeStore tests.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _make_corpus_json(
    *,
    version: str = "v0",
    review_status: str = "draft",
    seed_keywords: Optional[List[str]] = None,
    entries: Optional[List[dict]] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Build a minimal corpus manifest dict."""
    d: dict = {
        "version": version,
        "review_status": review_status,
        "seed_topic_keywords": seed_keywords or ["prediction market"],
        "entries": entries if entries is not None else [],
    }
    if extra:
        d.update(extra)
    return d


def _make_qa_json(
    *,
    version: str = "v0",
    review_status: str = "reviewed",
    pairs: Optional[List[dict]] = None,
) -> dict:
    """Build a minimal golden QA dict."""
    return {
        "version": version,
        "review_status": review_status,
        "pairs": pairs if pairs is not None else [],
    }


def _write_json(path: Path, data: dict) -> Path:
    """Write dict to JSON file and return path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_qa_pair(
    *,
    id: str = "qa_001",
    question: str = "What is gamma?",
    expected_paper_id: str = "doc_abc",
    expected_answer_substring: str = "gamma",
    category: str = "concept_definition",
    difficulty: str = "easy",
    expected_section_or_page: Optional[str] = None,
) -> dict:
    pair: dict = {
        "id": id,
        "question": question,
        "expected_paper_id": expected_paper_id,
        "expected_answer_substring": expected_answer_substring,
        "category": category,
        "difficulty": difficulty,
    }
    if expected_section_or_page is not None:
        pair["expected_section_or_page"] = expected_section_or_page
    return pair


def _create_knowledge_db(db_path: Path, rows: List[Dict[str, Any]]) -> None:
    """Create an in-file KnowledgeStore DB with seed rows for testing."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            source_url TEXT,
            source_family TEXT,
            content_hash TEXT,
            chunk_count INTEGER,
            published_at TEXT,
            ingested_at TEXT,
            confidence_tier TEXT,
            metadata_json TEXT
        )
    """)
    conn.executemany(
        """INSERT OR REPLACE INTO source_documents
           (id, title, source_url, source_family, content_hash,
            chunk_count, published_at, ingested_at, confidence_tier, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r["id"],
                r.get("title", ""),
                r.get("source_url", ""),
                r.get("source_family", "academic"),
                r.get("content_hash", "abc123"),
                r.get("chunk_count", 10),
                r.get("published_at", None),
                r.get("ingested_at", "2026-01-01T00:00:00+00:00"),
                r.get("confidence_tier", "medium"),
                json.dumps(r.get("_meta", {})),
            )
            for r in rows
        ],
    )
    conn.commit()
    conn.close()


def _make_all_metrics_result(
    *,
    off_topic_rate_pct: float = 10.0,
    fallback_rate_pct: float = 10.0,
    p_at_5: Optional[float] = 0.8,
    median_chunks: float = 15.0,
    eq_heavy_not_parseable_pct: float = 0.0,
    corpus_size: int = 10,
    golden_qa_review_status: str = "reviewed",
):
    """Build a minimal AllMetricsResult with controllable key metric values."""
    from packages.research.eval_benchmark.metrics import (
        AllMetricsResult, MetricResult,
    )

    def _ok(name: str, value: dict, detail=None) -> MetricResult:
        return MetricResult(name=name, status="ok", value=value, detail=detail or [])

    def _na(name: str, notes: str = "") -> MetricResult:
        return MetricResult(name=name, status="not_available", value={}, notes=notes)

    m6 = (
        _ok("retrieval_answer_quality", {"p_at_5": p_at_5, "answer_correctness_rate": 0.8, "evaluated_count": 5})
        if p_at_5 is not None
        else _na("retrieval_answer_quality", "empty QA set")
    )

    # Build eq_heavy detail for metric 9
    eq_detail = []
    if eq_heavy_not_parseable_pct > 0:
        eq_detail = [
            {
                "source_id": f"doc_{i}",
                "title": f"Paper {i}",
                "category": "equation_heavy",
                "body_source": "pdf",
                "quality_flags": {"equation_parseable": False, "table_detectable": False, "section_headers_detectable": False, "has_page_count": True},
            }
            for i in range(4)  # 4 not parseable
        ] + [
            {
                "source_id": "doc_pass",
                "title": "Paper pass",
                "category": "equation_heavy",
                "body_source": "pdf",
                "quality_flags": {"equation_parseable": True, "table_detectable": True, "section_headers_detectable": True, "has_page_count": True},
            }
        ]
    else:
        eq_detail = [
            {
                "source_id": "doc_0",
                "title": "Good paper",
                "category": "equation_heavy",
                "body_source": "pdf",
                "quality_flags": {"equation_parseable": True, "table_detectable": True, "section_headers_detectable": True, "has_page_count": True},
            }
        ]

    import datetime
    return AllMetricsResult(
        off_topic_rate=_ok("off_topic_rate", {"off_topic_count": int(off_topic_rate_pct), "total": 100, "off_topic_rate_pct": off_topic_rate_pct}),
        body_source_distribution=_ok("body_source_distribution", {"counts": {"pdf": 8, "abstract_fallback": 2}, "percentages": {"pdf": 80.0, "abstract_fallback": 20.0}}),
        fallback_rate=_ok("fallback_rate", {"fallback_count": int(fallback_rate_pct), "total": 100, "fallback_rate_pct": fallback_rate_pct, "by_reason": {}}),
        chunk_count_distribution=_ok("chunk_count_distribution", {"mean": median_chunks, "median": median_chunks, "p5": 2.0, "p95": 50.0, "histogram": []}),
        low_chunk_suspicious_records=_ok("low_chunk_suspicious_records", {"suspicious_count": 0, "total": corpus_size}),
        retrieval_answer_quality=m6,
        citation_traceability=_ok("citation_traceability", {"traceable_count": 4, "evaluated_count": 5, "traceability_rate_pct": 80.0}),
        duplicate_dedup_behavior=_ok("duplicate_dedup_behavior", {"exact_hash_dupes": 0, "title_dupes": 0, "total_docs": corpus_size}),
        parser_quality_notes=_ok("parser_quality_notes", {"sampled_count": len(eq_detail), "equation_heavy_count": len(eq_detail), "table_heavy_count": 0}, detail=eq_detail),
        corpus_size=corpus_size,
        run_ts=datetime.datetime(2026, 4, 30, 12, 0, 0).isoformat(),
        corpus_version="v0",
        golden_qa_review_status=golden_qa_review_status,
    )


# ===========================================================================
# corpus.py tests
# ===========================================================================

class TestCorpusLoad:
    def test_corpus_load_valid(self, tmp_path):
        """Load valid manifest JSON with one entry."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest, CorpusManifest

        data = _make_corpus_json(
            entries=[{"source_id": "abc123", "title": "A Paper", "category": "equation_heavy", "tags": ["math"]}]
        )
        p = _write_json(tmp_path / "corpus.json", data)
        manifest = load_corpus_manifest(p)

        assert isinstance(manifest, CorpusManifest)
        assert manifest.version == "v0"
        assert manifest.review_status == "draft"
        assert len(manifest.entries) == 1
        assert manifest.entries[0].source_id == "abc123"
        assert manifest.entries[0].category == "equation_heavy"
        assert manifest.entries[0].tags == ["math"]

    def test_corpus_missing_required_field(self, tmp_path):
        """Raises CorpusValidationError for missing version field."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest, CorpusValidationError

        data = {
            "review_status": "draft",
            "seed_topic_keywords": ["prediction market"],
            "entries": [],
        }
        p = _write_json(tmp_path / "corpus.json", data)
        with pytest.raises(CorpusValidationError, match="version"):
            load_corpus_manifest(p)

    def test_corpus_invalid_category(self, tmp_path):
        """Raises CorpusValidationError for an unrecognized category value."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest, CorpusValidationError

        data = _make_corpus_json(
            entries=[{"source_id": "abc", "category": "not_a_valid_category"}]
        )
        p = _write_json(tmp_path / "corpus.json", data)
        with pytest.raises(CorpusValidationError, match="invalid category"):
            load_corpus_manifest(p)

    def test_corpus_empty_entries(self, tmp_path):
        """Allows empty entries list."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest

        data = _make_corpus_json(entries=[])
        p = _write_json(tmp_path / "corpus.json", data)
        manifest = load_corpus_manifest(p)
        assert manifest.entries == []

    def test_corpus_missing_source_id(self, tmp_path):
        """Raises CorpusValidationError when an entry is missing source_id."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest, CorpusValidationError

        data = _make_corpus_json(entries=[{"title": "No ID paper"}])
        p = _write_json(tmp_path / "corpus.json", data)
        with pytest.raises(CorpusValidationError, match="source_id"):
            load_corpus_manifest(p)

    def test_corpus_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for non-existent file."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest

        with pytest.raises(FileNotFoundError):
            load_corpus_manifest(tmp_path / "nonexistent.json")

    def test_corpus_none_category_allowed(self, tmp_path):
        """None category (omitted) is valid."""
        from packages.research.eval_benchmark.corpus import load_corpus_manifest

        data = _make_corpus_json(entries=[{"source_id": "abc"}])
        p = _write_json(tmp_path / "corpus.json", data)
        manifest = load_corpus_manifest(p)
        assert manifest.entries[0].category is None


# ===========================================================================
# golden_qa.py tests
# ===========================================================================

class TestGoldenQALoad:
    def test_golden_qa_load_valid(self, tmp_path):
        """Load valid QA with one pair."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, GoldenQASet

        data = _make_qa_json(pairs=[_make_qa_pair()])
        p = _write_json(tmp_path / "qa.json", data)
        qa = load_golden_qa(p)

        assert isinstance(qa, GoldenQASet)
        assert qa.version == "v0"
        assert qa.review_status == "reviewed"
        assert len(qa.pairs) == 1
        assert qa.pairs[0].id == "qa_001"
        assert qa.pairs[0].category == "concept_definition"
        assert qa.pairs[0].difficulty == "easy"

    def test_golden_qa_missing_required_field(self, tmp_path):
        """Raises GoldenQAValidationError when a required field is missing."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, GoldenQAValidationError

        # Missing 'question' in pair
        data = _make_qa_json(pairs=[{
            "id": "qa_001",
            # no 'question'
            "expected_paper_id": "doc",
            "expected_answer_substring": "foo",
            "category": "concept_definition",
            "difficulty": "easy",
        }])
        p = _write_json(tmp_path / "qa.json", data)
        with pytest.raises(GoldenQAValidationError, match="question"):
            load_golden_qa(p)

    def test_golden_qa_invalid_category(self, tmp_path):
        """Raises GoldenQAValidationError for an unrecognized QA category."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, GoldenQAValidationError

        data = _make_qa_json(pairs=[_make_qa_pair(category="not_real_category")])
        p = _write_json(tmp_path / "qa.json", data)
        with pytest.raises(GoldenQAValidationError, match="invalid category"):
            load_golden_qa(p)

    def test_golden_qa_invalid_difficulty(self, tmp_path):
        """Raises GoldenQAValidationError for an unrecognized difficulty value."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, GoldenQAValidationError

        data = _make_qa_json(pairs=[_make_qa_pair(difficulty="impossible")])
        p = _write_json(tmp_path / "qa.json", data)
        with pytest.raises(GoldenQAValidationError, match="invalid difficulty"):
            load_golden_qa(p)

    def test_golden_qa_is_reviewed(self, tmp_path):
        """is_reviewed returns True for 'reviewed', False for other statuses."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, is_reviewed

        reviewed_data = _make_qa_json(review_status="reviewed")
        draft_data = _make_qa_json(review_status="operator_review_required")

        p_rev = _write_json(tmp_path / "rev.json", reviewed_data)
        p_dra = _write_json(tmp_path / "dra.json", draft_data)

        assert is_reviewed(load_golden_qa(p_rev)) is True
        assert is_reviewed(load_golden_qa(p_dra)) is False

    def test_golden_qa_missing_top_level_field(self, tmp_path):
        """Raises GoldenQAValidationError when 'version' is missing."""
        from packages.research.eval_benchmark.golden_qa import load_golden_qa, GoldenQAValidationError

        data = {"review_status": "draft", "pairs": []}
        p = _write_json(tmp_path / "qa.json", data)
        with pytest.raises(GoldenQAValidationError, match="version"):
            load_golden_qa(p)


# ===========================================================================
# metrics.py tests
# ===========================================================================

class TestMetric1OffTopicRate:
    def test_metric1_off_topic_rate(self):
        """1/3 docs are off-topic with mock docs and seed keywords."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [
            {"id": "1", "title": "Prediction market efficiency"},
            {"id": "2", "title": "Avellaneda-Stoikov model calibration"},
            {"id": "3", "title": "Completely unrelated quantum chemistry paper"},
        ]
        keywords = ["prediction market", "avellaneda-stoikov", "kelly criterion"]
        result = compute_metric_1_off_topic_rate(docs, keywords)

        assert result.status == "ok"
        assert result.value["total"] == 3
        assert result.value["off_topic_count"] == 1
        assert result.value["off_topic_rate_pct"] == pytest.approx(33.33, abs=0.1)
        assert len(result.detail) == 1
        assert result.detail[0]["source_id"] == "3"

    def test_metric1_all_on_topic(self):
        """Zero off-topic when all titles match."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [{"id": "1", "title": "market microstructure analysis"}]
        result = compute_metric_1_off_topic_rate(docs, ["market microstructure"])
        assert result.value["off_topic_rate_pct"] == 0.0

    def test_metric1_empty_docs(self):
        """Empty docs list returns zero counts."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        result = compute_metric_1_off_topic_rate([], ["keyword"])
        assert result.value["total"] == 0
        assert result.value["off_topic_count"] == 0


class TestMetric2BodySourceDistribution:
    def test_metric2_body_source_distribution(self):
        """Correct counts for pdf/abstract_fallback mix."""
        from packages.research.eval_benchmark.metrics import compute_metric_2_body_source_distribution

        docs = [
            {"id": "1", "_meta": {"body_source": "pdf"}},
            {"id": "2", "_meta": {"body_source": "pdf"}},
            {"id": "3", "_meta": {"body_source": "abstract_fallback"}},
            {"id": "4", "_meta": {"body_source": "marker"}},
        ]
        result = compute_metric_2_body_source_distribution(docs)

        assert result.status == "ok"
        counts = result.value["counts"]
        assert counts["pdf"] == 2
        assert counts["abstract_fallback"] == 1
        assert counts["marker"] == 1
        pcts = result.value["percentages"]
        assert pcts["pdf"] == pytest.approx(50.0)
        assert pcts["abstract_fallback"] == pytest.approx(25.0)


class TestMetric3FallbackRate:
    def test_metric3_fallback_rate(self):
        """Correct rate with fallback_reason breakdown."""
        from packages.research.eval_benchmark.metrics import compute_metric_3_fallback_rate

        docs = [
            {"id": "1", "_meta": {"body_source": "pdf"}},
            {"id": "2", "_meta": {"body_source": "abstract_fallback", "fallback_reason": "pdf_parse_failed"}},
            {"id": "3", "_meta": {"body_source": "abstract_fallback", "fallback_reason": "no_pdf_url"}},
        ]
        result = compute_metric_3_fallback_rate(docs)

        assert result.status == "ok"
        assert result.value["fallback_count"] == 2
        assert result.value["total"] == 3
        assert result.value["fallback_rate_pct"] == pytest.approx(66.67, abs=0.1)
        by_reason = result.value["by_reason"]
        assert by_reason.get("pdf_parse_failed") == 1
        assert by_reason.get("no_pdf_url") == 1


class TestMetric4ChunkCountDistribution:
    def test_metric4_chunk_count_distribution(self):
        """mean/median/histogram computed correctly."""
        from packages.research.eval_benchmark.metrics import compute_metric_4_chunk_count_distribution

        docs = [{"id": str(i), "chunk_count": cc} for i, cc in enumerate([1, 5, 10, 20, 100])]
        result = compute_metric_4_chunk_count_distribution(docs)

        assert result.status == "ok"
        assert result.value["mean"] == pytest.approx(27.2, abs=0.1)
        assert result.value["median"] == pytest.approx(10.0, abs=0.1)
        histogram = {h["bucket"]: h["count"] for h in result.value["histogram"]}
        assert histogram["0-2"] == 1    # chunk_count=1
        assert histogram["3-9"] == 1    # chunk_count=5
        assert histogram["10-19"] == 1  # chunk_count=10
        assert histogram["20-49"] == 1  # chunk_count=20
        assert histogram["100-199"] == 1  # chunk_count=100

    def test_metric4_empty_docs(self):
        """Empty docs returns zero values."""
        from packages.research.eval_benchmark.metrics import compute_metric_4_chunk_count_distribution

        result = compute_metric_4_chunk_count_distribution([])
        assert result.value["mean"] == 0.0
        assert result.value["median"] == 0.0


class TestMetric5LowChunkRecords:
    def test_metric5_low_chunk_records(self):
        """Finds docs with chunk_count < 3."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [
            {"id": "1", "title": "Good paper", "chunk_count": 15, "_meta": {"body_source": "pdf"}},
            {"id": "2", "title": "Stub paper", "chunk_count": 1, "_meta": {"body_source": "abstract_fallback", "body_length": 250}},
            {"id": "3", "title": "Zero chunks", "chunk_count": 0, "_meta": {"body_source": "unknown"}},
        ]
        result = compute_metric_5_low_chunk_suspicious_records(docs)

        assert result.status == "ok"
        assert result.value["suspicious_count"] == 2
        assert result.value["total"] == 3
        suspicious_ids = {d["source_id"] for d in result.detail}
        assert "2" in suspicious_ids
        assert "3" in suspicious_ids
        assert "1" not in suspicious_ids


class TestMetric6RetrievalAnswerQuality:
    def test_metric6_not_available_when_no_lexical_db(self, tmp_path):
        """Returns not_available status when lexical DB does not exist."""
        from packages.research.eval_benchmark.metrics import compute_metric_6_retrieval_answer_quality
        from packages.research.eval_benchmark.golden_qa import GoldenQASet, QAPair

        qa = GoldenQASet(
            version="v0",
            review_status="reviewed",
            pairs=[
                QAPair(
                    id="qa_001",
                    question="What is gamma?",
                    expected_paper_id="doc_123",
                    expected_answer_substring="gamma",
                    category="concept_definition",
                    difficulty="easy",
                )
            ],
        )
        fake_db = tmp_path / "nonexistent" / "lexical.sqlite3"
        result = compute_metric_6_retrieval_answer_quality(qa, fake_db)

        assert result.status == "not_available"
        assert "lexical" in result.notes.lower()

    def test_metric6_not_available_empty_qa(self, tmp_path):
        """Returns not_available when QA set is empty."""
        from packages.research.eval_benchmark.metrics import compute_metric_6_retrieval_answer_quality
        from packages.research.eval_benchmark.golden_qa import GoldenQASet

        qa = GoldenQASet(version="v0", review_status="reviewed", pairs=[])
        result = compute_metric_6_retrieval_answer_quality(qa, tmp_path / "lexical.sqlite3")

        assert result.status == "not_available"
        assert "empty" in result.notes.lower()


class TestMetric7CitationTraceability:
    def test_metric7_not_available_when_no_lexical_db(self, tmp_path):
        """Returns not_available when lexical DB does not exist."""
        from packages.research.eval_benchmark.metrics import compute_metric_7_citation_traceability
        from packages.research.eval_benchmark.golden_qa import GoldenQASet, QAPair

        qa = GoldenQASet(
            version="v0",
            review_status="reviewed",
            pairs=[QAPair(
                id="qa_001",
                question="test?",
                expected_paper_id="doc_abc",
                expected_answer_substring="test",
                category="concept_definition",
                difficulty="easy",
            )],
        )
        docs = [{"id": "doc_abc", "source_url": "http://example.com/paper"}]
        fake_db = tmp_path / "no_db" / "lexical.sqlite3"
        result = compute_metric_7_citation_traceability(qa, docs, fake_db)

        assert result.status == "not_available"


class TestMetric8DuplicateDedup:
    def test_metric8_duplicate_detection(self):
        """Finds identical content_hash duplicates."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "Paper A", "content_hash": "hash_same"},
            {"id": "2", "title": "Paper B", "content_hash": "hash_same"},
            {"id": "3", "title": "Paper C", "content_hash": "hash_unique"},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)

        assert result.status == "ok"
        assert result.value["exact_hash_dupes"] == 1
        assert result.value["total_docs"] == 3
        assert len(result.detail) == 1
        assert set(result.detail[0]["source_ids"]) == {"1", "2"}

    def test_metric8_title_duplicates(self):
        """Finds case-insensitive title duplicates."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "Market Microstructure Analysis", "content_hash": "hash1"},
            {"id": "2", "title": "market microstructure analysis", "content_hash": "hash2"},
            {"id": "3", "title": "Other Paper", "content_hash": "hash3"},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)

        assert result.value["title_dupes"] == 1
        assert result.value["exact_hash_dupes"] == 0

    def test_metric8_no_duplicates(self):
        """No duplicates returns zero counts."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "Paper One", "content_hash": "h1"},
            {"id": "2", "title": "Paper Two", "content_hash": "h2"},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)
        assert result.value["exact_hash_dupes"] == 0
        assert result.value["title_dupes"] == 0


class TestMetric9ParserQuality:
    def test_metric9_parser_quality(self):
        """Qualitative flags computed for equation_heavy docs."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        body_with_equations = "The formula x = y + z is central. Section 3 elaborates."
        docs = [
            {
                "id": "doc1",
                "title": "Math Paper",
                "_meta": {
                    "body_source": "pdf",
                    "page_count": 12,
                    "category": "equation_heavy",
                    "body": body_with_equations,
                },
            },
        ]
        result = compute_metric_9_parser_quality_notes(docs)

        assert result.status == "ok"
        assert result.value["sampled_count"] == 1
        assert len(result.detail) == 1
        flags = result.detail[0]["quality_flags"]
        assert flags["equation_parseable"] is True
        assert flags["has_page_count"] is True

    def test_metric9_skips_abstract_fallback(self):
        """Abstract fallback docs are excluded from parser quality assessment."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        docs = [
            {
                "id": "doc1",
                "title": "Abstract Only Paper",
                "_meta": {
                    "body_source": "abstract_fallback",
                    "category": "equation_heavy",
                },
            },
        ]
        result = compute_metric_9_parser_quality_notes(docs)

        assert result.value["sampled_count"] == 0
        assert result.detail == []


# ===========================================================================
# report.py tests
# ===========================================================================

class TestReportGeneration:
    def test_generate_markdown_contains_sections(self):
        """All 9 metric sections are present in the Markdown output."""
        from packages.research.eval_benchmark.report import generate_markdown_report

        metrics = _make_all_metrics_result()
        md = generate_markdown_report(metrics, "NONE", "System healthy.")

        expected_section_names = [
            "Off Topic Rate",
            "Body Source Distribution",
            "Fallback Rate",
            "Chunk Count Distribution",
            "Low Chunk Suspicious Records",
            "Retrieval Answer Quality",
            "Citation Traceability",
            "Duplicate Dedup Behavior",
            "Parser Quality Notes",
        ]
        for section in expected_section_names:
            assert section in md, f"Expected section '{section}' not found in Markdown"

    def test_generate_markdown_shows_draft_warning(self):
        """Markdown report includes DRAFT warning when QA is unreviewed."""
        from packages.research.eval_benchmark.report import generate_markdown_report

        metrics = _make_all_metrics_result(golden_qa_review_status="operator_review_required")
        md = generate_markdown_report(metrics, "NONE", "System healthy.")

        assert "DRAFT" in md or "WARNING" in md

    def test_generate_json_structure(self):
        """JSON report has all required top-level keys."""
        from packages.research.eval_benchmark.report import generate_json_report

        metrics = _make_all_metrics_result()
        report = generate_json_report(metrics, "A", "High off-topic rate.")

        assert "run_ts" in report
        assert "corpus_version" in report
        assert "corpus_size" in report
        assert "golden_qa_review_status" in report
        assert "recommendation" in report
        assert "metrics" in report
        assert report["recommendation"]["label"] == "A"
        assert report["recommendation"]["justification"] == "High off-topic rate."

        # All 9 metrics present
        for metric_name in [
            "off_topic_rate", "body_source_distribution", "fallback_rate",
            "chunk_count_distribution", "low_chunk_suspicious_records",
            "retrieval_answer_quality", "citation_traceability",
            "duplicate_dedup_behavior", "parser_quality_notes",
        ]:
            assert metric_name in report["metrics"], f"Missing metric: {metric_name}"

    def test_write_reports_creates_files(self, tmp_path):
        """write_reports creates both .md and .json files."""
        from packages.research.eval_benchmark.report import write_reports

        metrics = _make_all_metrics_result()
        md_path, json_path = write_reports(tmp_path, metrics, "NONE", "Healthy.")

        assert md_path.exists()
        assert json_path.exists()
        assert md_path.suffix == ".md"
        assert json_path.suffix == ".json"

        # Files are non-empty
        assert md_path.stat().st_size > 0
        assert json_path.stat().st_size > 0

        # JSON is valid
        with json_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        assert "metrics" in data


# ===========================================================================
# recommender.py tests
# ===========================================================================

class TestRecommender:
    def test_recommend_A_high_off_topic(self):
        """Recommendation A triggered when off_topic_rate > 30%."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(off_topic_rate_pct=35.0)
        rec = recommend(metrics)

        assert rec.label == "A"
        assert "A" in rec.title or "Pre-fetch" in rec.title
        assert any("Rule A" in r for r in rec.triggered_rules)

    def test_recommend_B_high_fallback(self):
        """Recommendation B triggered when fallback_rate > 40%."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(off_topic_rate_pct=5.0, fallback_rate_pct=45.0)
        rec = recommend(metrics)

        assert rec.label == "B"
        assert any("Rule B" in r for r in rec.triggered_rules)

    def test_recommend_C_low_p_at_5(self):
        """Recommendation C triggered when P@5 < 0.5."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(
            off_topic_rate_pct=5.0,
            fallback_rate_pct=5.0,
            p_at_5=0.3,
        )
        rec = recommend(metrics)

        assert rec.label == "C"
        assert any("Rule C" in r for r in rec.triggered_rules)

    def test_recommend_E_low_chunks(self):
        """Recommendation E triggered when median_chunks < 3."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(
            off_topic_rate_pct=5.0,
            fallback_rate_pct=5.0,
            p_at_5=0.8,
            median_chunks=2.0,
        )
        rec = recommend(metrics)

        assert rec.label == "E"
        assert any("Rule E" in r for r in rec.triggered_rules)

    def test_recommend_none_healthy(self):
        """NONE returned when all metrics are within healthy thresholds."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(
            off_topic_rate_pct=5.0,
            fallback_rate_pct=10.0,
            p_at_5=0.8,
            median_chunks=15.0,
        )
        rec = recommend(metrics)

        assert rec.label == "NONE"
        assert "healthy" in rec.justification.lower()
        assert rec.triggered_rules == []

    def test_recommend_priority_A_over_B(self):
        """A takes priority over B when both rules trigger."""
        from packages.research.eval_benchmark.recommender import recommend

        metrics = _make_all_metrics_result(
            off_topic_rate_pct=40.0,  # triggers A
            fallback_rate_pct=50.0,  # would trigger B
        )
        rec = recommend(metrics)

        # A must win over B
        assert rec.label == "A"
        # But B rule should also appear in triggered_rules
        rule_labels = [r[:6] for r in rec.triggered_rules]
        assert any("Rule A" in r for r in rec.triggered_rules)
        assert any("Rule B" in r for r in rec.triggered_rules)


# ===========================================================================
# CLI / policy tests
# ===========================================================================

class TestCLI:
    def test_cli_dry_run_exits_0(self, tmp_path):
        """dry-run with valid fixture files exits 0."""
        from tools.cli.research_eval_benchmark import main

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[{"source_id": "abc"}]),
        )
        qa_path = _write_json(
            tmp_path / "qa.json",
            _make_qa_json(pairs=[_make_qa_pair()]),
        )

        result = main([
            "--corpus", str(corpus_path),
            "--golden-set", str(qa_path),
            "--dry-run",
        ])
        assert result == 0

    def test_cli_requires_corpus_arg(self, tmp_path, capsys):
        """Exits non-zero without --corpus arg."""
        from tools.cli.research_eval_benchmark import main

        # argparse will raise SystemExit on missing required arg
        with pytest.raises(SystemExit) as exc_info:
            main([])
        # argparse exits with code 2 for missing required args
        assert exc_info.value.code != 0

    def test_cli_strict_mode_blocks_unreviewed_baseline(self, tmp_path, capsys):
        """--save-baseline with unreviewed QA exits 1 when --strict."""
        from tools.cli.research_eval_benchmark import main

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[{"source_id": "abc"}]),
        )
        qa_path = _write_json(
            tmp_path / "qa.json",
            _make_qa_json(review_status="operator_review_required", pairs=[_make_qa_pair()]),
        )

        result = main([
            "--corpus", str(corpus_path),
            "--golden-set", str(qa_path),
            "--strict",
            "--dry-run",  # dry-run so we don't need DB
        ])
        assert result == 1

    def test_cli_strict_mode_blocks_save_baseline_unreviewed(self, tmp_path, capsys):
        """--save-baseline requires reviewed QA; unreviewed exits 1."""
        from tools.cli.research_eval_benchmark import main

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[{"source_id": "abc"}]),
        )
        qa_path = _write_json(
            tmp_path / "qa.json",
            _make_qa_json(review_status="draft", pairs=[_make_qa_pair()]),
        )

        result = main([
            "--corpus", str(corpus_path),
            "--golden-set", str(qa_path),
            "--save-baseline",
            "--dry-run",
        ])
        # --save-baseline with draft QA should fail
        assert result == 1

    def test_cli_draft_mode_proceeds_with_warning(self, tmp_path, capsys):
        """Draft QA runs without --strict in dry-run mode, exits 0 with warning."""
        from tools.cli.research_eval_benchmark import main

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[{"source_id": "abc"}]),
        )
        qa_path = _write_json(
            tmp_path / "qa.json",
            _make_qa_json(review_status="operator_review_required", pairs=[_make_qa_pair()]),
        )

        result = main([
            "--corpus", str(corpus_path),
            "--golden-set", str(qa_path),
            "--dry-run",
            # no --strict
        ])
        assert result == 0

        # Warning should have been printed to stderr
        captured = capsys.readouterr()
        assert "WARNING" in captured.err or "not operator-reviewed" in captured.err.lower() or "NOT operator-reviewed" in captured.err

    def test_cli_corpus_not_found_exits_1(self, tmp_path, capsys):
        """Missing corpus file exits 1."""
        from tools.cli.research_eval_benchmark import main

        result = main([
            "--corpus", str(tmp_path / "nonexistent.json"),
        ])
        assert result == 1


# ===========================================================================
# New tests: Codex blocking/major fixes
# ===========================================================================

class TestMetric6AnswerOnlyInExpectedPaper:
    def test_answer_not_credited_from_wrong_paper(self):
        """answer_found must be False when the answer substring is in a non-expected chunk."""
        from packages.research.eval_benchmark.metrics import _evaluate_retrieval_pair

        # The answer substring 'gamma' appears in a wrong-paper chunk only
        results = [
            {
                "file_path": "wrong_paper.pdf",
                "doc_id": "wrong_doc",
                "snippet": "gamma is a risk-aversion parameter in portfolio theory",
            }
        ]
        ev = _evaluate_retrieval_pair(results, "expected_doc", "gamma")
        assert ev["paper_found"] is False
        assert ev["answer_found"] is False

    def test_answer_credited_only_in_expected_paper_chunk(self):
        """answer_found is True only when expected paper's chunk contains the answer."""
        from packages.research.eval_benchmark.metrics import _evaluate_retrieval_pair

        results = [
            {
                "file_path": "expected_doc/paper.pdf",
                "doc_id": "expected_doc",
                "snippet": "the gamma parameter controls inventory aversion",
            }
        ]
        ev = _evaluate_retrieval_pair(results, "expected_doc", "gamma")
        assert ev["paper_found"] is True
        assert ev["answer_found"] is True
        assert ev["matched_rank"] == 1

    def test_answer_not_credited_when_expected_paper_chunk_lacks_substring(self):
        """answer_found is False when expected paper found but chunk lacks answer substring."""
        from packages.research.eval_benchmark.metrics import _evaluate_retrieval_pair

        results = [
            {
                "file_path": "expected_doc/paper.pdf",
                "doc_id": "expected_doc",
                "snippet": "this chunk discusses inventory management without mentioning the parameter",
            }
        ]
        ev = _evaluate_retrieval_pair(results, "expected_doc", "gamma")
        assert ev["paper_found"] is True
        assert ev["answer_found"] is False  # Paper found, but answer not in chunk

    def test_top_5_doc_ids_populated(self):
        """top_5_doc_ids lists doc ids from all returned results."""
        from packages.research.eval_benchmark.metrics import _evaluate_retrieval_pair

        results = [
            {"file_path": "", "doc_id": "doc_a", "snippet": ""},
            {"file_path": "", "doc_id": "doc_b", "snippet": "answer text"},
        ]
        ev = _evaluate_retrieval_pair(results, "doc_b", "answer text")
        assert "doc_a" in ev["top_5_doc_ids"]
        assert "doc_b" in ev["top_5_doc_ids"]


class TestMetric5ReviewPriority:
    def test_priority_high_zero_chunks(self):
        """Zero chunks → review_priority=high."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [{"id": "1", "title": "No chunks", "chunk_count": 0, "_meta": {"body_source": "unknown"}}]
        result = compute_metric_5_low_chunk_suspicious_records(docs)
        assert result.detail[0]["review_priority"] == "high"

    def test_priority_high_abstract_fallback(self):
        """abstract_fallback body → review_priority=high even with chunk_count=2."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [{"id": "1", "title": "Abstract only", "chunk_count": 2,
                 "_meta": {"body_source": "abstract_fallback", "body_length": 5000}}]
        result = compute_metric_5_low_chunk_suspicious_records(docs)
        assert result.detail[0]["review_priority"] == "high"

    def test_priority_high_very_short_body(self):
        """body_length < 100 → review_priority=high."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [{"id": "1", "title": "Tiny body", "chunk_count": 1,
                 "_meta": {"body_source": "pdf", "body_length": 50}}]
        result = compute_metric_5_low_chunk_suspicious_records(docs)
        assert result.detail[0]["review_priority"] == "high"

    def test_priority_medium_pdf_one_chunk(self):
        """PDF body with 1 chunk and decent body length → review_priority=medium."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [{"id": "1", "title": "Thin pdf", "chunk_count": 1,
                 "_meta": {"body_source": "pdf", "body_length": 5000}}]
        result = compute_metric_5_low_chunk_suspicious_records(docs)
        assert result.detail[0]["review_priority"] == "medium"

    def test_priority_field_present_in_all_suspicious(self):
        """review_priority field is present in every suspicious record."""
        from packages.research.eval_benchmark.metrics import compute_metric_5_low_chunk_suspicious_records

        docs = [
            {"id": "1", "title": "A", "chunk_count": 0, "_meta": {}},
            {"id": "2", "title": "B", "chunk_count": 2, "_meta": {"body_source": "pdf", "body_length": 3000}},
        ]
        result = compute_metric_5_low_chunk_suspicious_records(docs)
        for row in result.detail:
            assert "review_priority" in row


class TestMetric8ExtendedDuplicates:
    def test_canonical_id_duplicates(self):
        """DOI-based canonical id duplicates are detected."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "Paper A", "content_hash": "h1", "_meta": {"doi": "10.1234/xyz"}},
            {"id": "2", "title": "Paper A v2", "content_hash": "h2", "_meta": {"doi": "10.1234/xyz"}},
            {"id": "3", "title": "Other Paper", "content_hash": "h3", "_meta": {}},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)
        assert result.value["canonical_id_dupes"] == 1

    def test_no_canonical_id_dupes_when_distinct(self):
        """Distinct DOIs produce no canonical_id_dupes."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "Paper A", "content_hash": "h1", "_meta": {"doi": "10.1/a"}},
            {"id": "2", "title": "Paper B", "content_hash": "h2", "_meta": {"doi": "10.1/b"}},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)
        assert result.value["canonical_id_dupes"] == 0

    def test_similar_title_body_same_body_is_title_dupe(self):
        """Same title AND same body prefix maps to title_dupes not similar_title_body_dupes."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        shared_body = "Introduction to market microstructure concepts and models"
        docs = [
            {"id": "1", "title": "Market Analysis", "content_hash": "h1", "_meta": {"body": shared_body}},
            {"id": "2", "title": "Market Analysis", "content_hash": "h2", "_meta": {"body": shared_body}},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)
        assert result.value["title_dupes"] == 1

    def test_canonical_id_dupes_in_detail(self):
        """Canonical id dupe detail includes canonical_id and source_ids."""
        from packages.research.eval_benchmark.metrics import compute_metric_8_duplicate_dedup_behavior

        docs = [
            {"id": "1", "title": "X", "content_hash": "h1", "_meta": {"arxiv_id": "2301.00001"}},
            {"id": "2", "title": "Y", "content_hash": "h2", "_meta": {"arxiv_id": "2301.00001"}},
        ]
        result = compute_metric_8_duplicate_dedup_behavior(docs)
        assert result.value["canonical_id_dupes"] == 1
        assert any("2301.00001" in d.get("canonical_id", "") for d in result.detail)


class TestMetric9CategoryFiltering:
    def test_excludes_docs_not_in_sampled_categories(self):
        """Docs whose category is not in sampled_categories are excluded from assessment."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        docs = [
            {"id": "1", "title": "Prose paper", "_meta": {
                "body_source": "pdf", "category": "prose_heavy", "body": "some text here"}},
            {"id": "2", "title": "Equation paper", "_meta": {
                "body_source": "pdf", "category": "equation_heavy", "body": "x = y + z here"}},
        ]
        result = compute_metric_9_parser_quality_notes(docs, ["equation_heavy"])
        assert result.value["sampled_count"] == 1
        assert len(result.detail) == 1
        assert result.detail[0]["source_id"] == "2"

    def test_issue_counts_increment(self):
        """equation_not_parseable_count increments for docs lacking equation markers."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        docs = [
            {"id": "1", "title": "Math Paper", "_meta": {
                "body_source": "pdf", "category": "equation_heavy",
                "body": "plain prose with no math markers at all"}},
        ]
        result = compute_metric_9_parser_quality_notes(docs, ["equation_heavy"])
        assert result.value["sampled_count"] == 1
        assert result.value["equation_not_parseable_count"] == 1

    def test_skipped_abstract_fallback_count_in_scope(self):
        """abstract_fallback docs in sampled_categories increment skipped counter."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        docs = [
            {"id": "1", "title": "Abstract only", "_meta": {
                "body_source": "abstract_fallback", "category": "equation_heavy"}},
        ]
        result = compute_metric_9_parser_quality_notes(docs, ["equation_heavy"])
        assert result.value["sampled_count"] == 0
        assert result.value["skipped_abstract_fallback_count"] == 1

    def test_null_category_excluded(self):
        """Docs with category=None are excluded from sampled-category assessment."""
        from packages.research.eval_benchmark.metrics import compute_metric_9_parser_quality_notes

        docs = [
            {"id": "1", "title": "Uncategorised", "_meta": {
                "body_source": "pdf", "category": None, "body": "x = y"}},
        ]
        result = compute_metric_9_parser_quality_notes(docs, ["equation_heavy", "table_heavy"])
        assert result.value["sampled_count"] == 0


class TestReportTriggeredRules:
    def test_json_report_includes_triggered_rules(self):
        """triggered_rules are stored in recommendation section of JSON."""
        from packages.research.eval_benchmark.report import generate_json_report

        metrics = _make_all_metrics_result()
        rules = ["Rule A: off_topic_rate=40% > 30%", "Rule B: fallback_rate=50% > 40%"]
        report = generate_json_report(metrics, "A", "High off-topic rate.", rules)

        assert "triggered_rules" in report["recommendation"]
        assert len(report["recommendation"]["triggered_rules"]) == 2
        assert any("Rule A" in r for r in report["recommendation"]["triggered_rules"])

    def test_json_report_empty_triggered_rules(self):
        """Empty triggered_rules list is preserved (not omitted)."""
        from packages.research.eval_benchmark.report import generate_json_report

        metrics = _make_all_metrics_result()
        report = generate_json_report(metrics, "NONE", "Healthy.", [])
        assert report["recommendation"]["triggered_rules"] == []

    def test_json_report_none_triggered_rules_becomes_empty_list(self):
        """None triggered_rules defaults to empty list in JSON output."""
        from packages.research.eval_benchmark.report import generate_json_report

        metrics = _make_all_metrics_result()
        report = generate_json_report(metrics, "NONE", "Healthy.", None)
        assert report["recommendation"]["triggered_rules"] == []

    def test_markdown_report_includes_triggered_rules(self):
        """Triggered rules appear verbatim in Markdown report."""
        from packages.research.eval_benchmark.report import generate_markdown_report

        metrics = _make_all_metrics_result()
        rules = ["Rule A: off_topic_rate=40% > 30%"]
        md = generate_markdown_report(metrics, "A", "High off-topic rate.", rules)

        assert "Triggered rules" in md
        assert "Rule A" in md

    def test_markdown_report_no_rules_fired_message(self):
        """Markdown shows 'No threshold rules fired' when triggered_rules is empty."""
        from packages.research.eval_benchmark.report import generate_markdown_report

        metrics = _make_all_metrics_result()
        md = generate_markdown_report(metrics, "NONE", "Healthy.", [])
        assert "No threshold rules fired" in md

    def test_write_reports_passes_triggered_rules(self, tmp_path):
        """write_reports with triggered_rules writes them to both files."""
        from packages.research.eval_benchmark.report import write_reports
        import json as _json

        metrics = _make_all_metrics_result()
        rules = ["Rule C: p_at_5=0.3 < 0.5"]
        md_path, json_path = write_reports(tmp_path, metrics, "C", "Low retrieval.", rules)

        with json_path.open(encoding="utf-8") as fh:
            data = _json.load(fh)
        assert data["recommendation"]["triggered_rules"] == rules

        md_content = md_path.read_text(encoding="utf-8")
        assert "Rule C" in md_content


class TestMissingSourceIds:
    def test_compute_all_metrics_detects_missing_ids(self, tmp_path):
        """AllMetricsResult.missing_source_ids lists manifest IDs absent from DB."""
        from packages.research.eval_benchmark.metrics import compute_all_metrics
        from packages.research.eval_benchmark.corpus import load_corpus_manifest
        from packages.research.eval_benchmark.golden_qa import load_golden_qa

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[
                {"source_id": "exists_doc"},
                {"source_id": "missing_doc"},
            ]),
        )
        qa_path = _write_json(tmp_path / "qa.json", _make_qa_json())
        kb_path = tmp_path / "kb.sqlite3"
        _create_knowledge_db(kb_path, [{"id": "exists_doc", "title": "Real Paper"}])

        corpus = load_corpus_manifest(corpus_path)
        qa = load_golden_qa(qa_path)
        result = compute_all_metrics(corpus, qa, kb_path, tmp_path / "nolex.sqlite3")

        assert result.manifest_entries == 2
        assert result.corpus_size == 1
        assert "missing_doc" in result.missing_source_ids

    def test_compute_all_metrics_no_missing_when_all_present(self, tmp_path):
        """missing_source_ids is empty when all manifest IDs are in DB."""
        from packages.research.eval_benchmark.metrics import compute_all_metrics
        from packages.research.eval_benchmark.corpus import load_corpus_manifest
        from packages.research.eval_benchmark.golden_qa import load_golden_qa

        corpus_path = _write_json(
            tmp_path / "corpus.json",
            _make_corpus_json(entries=[{"source_id": "doc_a"}]),
        )
        qa_path = _write_json(tmp_path / "qa.json", _make_qa_json())
        kb_path = tmp_path / "kb.sqlite3"
        _create_knowledge_db(kb_path, [{"id": "doc_a", "title": "Paper A"}])

        corpus = load_corpus_manifest(corpus_path)
        qa = load_golden_qa(qa_path)
        result = compute_all_metrics(corpus, qa, kb_path, tmp_path / "nolex.sqlite3")

        assert result.missing_source_ids == []
        assert result.corpus_size == 1


class TestMetric1AbstractKeyword:
    def test_abstract_keyword_not_in_title_not_off_topic(self):
        """Title is generic but abstract contains seed keyword; doc must NOT be off-topic."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [
            {"id": "1", "title": "A Technical Study",
             "_meta": {"abstract": "this paper analyzes prediction market efficiency"}}
        ]
        result = compute_metric_1_off_topic_rate(docs, ["prediction market"])
        assert result.value["off_topic_count"] == 0

    def test_body_keyword_not_in_title_not_off_topic(self):
        """Seed keyword only in body excerpt; doc must NOT be off-topic."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [
            {"id": "1", "title": "General Analysis",
             "_meta": {"body": "We study limit order book dynamics and market microstructure."}}
        ]
        result = compute_metric_1_off_topic_rate(docs, ["limit order book"])
        assert result.value["off_topic_count"] == 0

    def test_empty_seed_keywords_returns_error(self):
        """Empty seed keywords list returns error status."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [{"id": "1", "title": "Some Paper", "_meta": {}}]
        result = compute_metric_1_off_topic_rate(docs, [])
        assert result.status == "error"

    def test_blank_only_keywords_returns_error(self):
        """List of blank strings is treated as empty."""
        from packages.research.eval_benchmark.metrics import compute_metric_1_off_topic_rate

        docs = [{"id": "1", "title": "Some Paper", "_meta": {}}]
        result = compute_metric_1_off_topic_rate(docs, ["  ", ""])
        assert result.status == "error"


# ===========================================================================
# lexical_refresh.py tests
# ===========================================================================

def _make_cache_file(cache_dir, url: str, body_text: str):
    """Write a fake raw_source_cache academic JSON file."""
    import hashlib, json
    fname = hashlib.sha256(url.encode()).hexdigest()[:16] + ".json"
    data = {
        "source_id": fname.replace(".json", ""),
        "source_family": "academic",
        "cached_at": "2026-01-01T00:00:00Z",
        "payload": {
            "url": url,
            "title": "Test Paper",
            "abstract": "Test abstract.",
            "body_text": body_text,
            "body_source": "pdf",
            "body_length": len(body_text),
        },
    }
    fpath = cache_dir / fname
    fpath.write_text(json.dumps(data), encoding="utf-8")
    return fpath


def _make_knowledge_db(db_path, entries: list) -> None:
    """Write a minimal KnowledgeStore SQLite DB with source_documents rows."""
    import sqlite3
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS source_documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            source_url TEXT,
            source_family TEXT,
            content_hash TEXT,
            chunk_count INTEGER,
            published_at TEXT,
            ingested_at TEXT,
            confidence_tier TEXT,
            metadata_json TEXT
        )
    """)
    for entry in entries:
        conn.execute(
            "INSERT OR REPLACE INTO source_documents "
            "(id, title, source_url, source_family) VALUES (?, ?, ?, ?)",
            (entry["id"], entry.get("title", ""), entry.get("source_url", ""), "academic"),
        )
    conn.commit()
    conn.close()


class TestScopedLexicalRefresh:
    """Tests for packages/research/eval_benchmark/lexical_refresh.py."""

    def test_refresh_indexes_corpus_papers(self, tmp_path):
        """Scoped refresh inserts chunks for each indexed paper into the lexical DB."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus
        from packages.polymarket.rag.lexical import open_lexical_db

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid_a = "a" * 64
        sid_b = "b" * 64
        url_a = "https://arxiv.org/abs/0000.0001"
        url_b = "https://arxiv.org/abs/0000.0002"
        _make_cache_file(cache_dir, url_a, "prediction market limit order book spread")
        _make_cache_file(cache_dir, url_b, "avellaneda stoikov inventory risk model")
        _make_knowledge_db(kb_db, [
            {"id": sid_a, "source_url": url_a},
            {"id": sid_b, "source_url": url_b},
        ])

        result = refresh_lexical_for_corpus(
            [sid_a, sid_b],
            lexical_db_path=lex_db,
            knowledge_db_path=kb_db,
            cache_dir=cache_dir,
            verbose=False,
        )

        assert result.indexed == 2
        assert result.skipped_no_body == 0
        assert result.skipped_no_url == 0
        assert result.total_chunks >= 2

        conn = open_lexical_db(lex_db)
        rows = conn.execute(
            "SELECT DISTINCT doc_id FROM chunks WHERE doc_type='academic'"
        ).fetchall()
        conn.close()
        indexed_ids = {r[0] for r in rows}
        assert sid_a in indexed_ids
        assert sid_b in indexed_ids

    def test_refresh_skips_missing_cache(self, tmp_path):
        """Papers with no cache file body are counted as skipped."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid_present = "c" * 64
        sid_missing = "d" * 64
        url_present = "https://arxiv.org/abs/0000.0003"
        url_missing = "https://arxiv.org/abs/0000.0004"
        _make_cache_file(cache_dir, url_present, "market microstructure bid ask spread")
        _make_knowledge_db(kb_db, [
            {"id": sid_present, "source_url": url_present},
            {"id": sid_missing, "source_url": url_missing},
        ])

        result = refresh_lexical_for_corpus(
            [sid_present, sid_missing],
            lexical_db_path=lex_db,
            knowledge_db_path=kb_db,
            cache_dir=cache_dir,
            verbose=False,
        )

        assert result.indexed == 1
        assert result.skipped_no_body == 1
        assert sid_present in result.indexed_ids
        assert sid_missing in result.skipped_ids

    def test_refresh_skips_no_url_in_kb(self, tmp_path):
        """Papers not found in KnowledgeStore are counted as skipped."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"
        _make_knowledge_db(kb_db, [])

        sid_orphan = "e" * 64
        result = refresh_lexical_for_corpus(
            [sid_orphan],
            lexical_db_path=lex_db,
            knowledge_db_path=kb_db,
            cache_dir=cache_dir,
            verbose=False,
        )

        assert result.indexed == 0
        assert result.skipped_no_url == 1

    def test_refresh_idempotent(self, tmp_path):
        """Re-running refresh replaces chunks without duplicating them."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus
        from packages.polymarket.rag.lexical import open_lexical_db

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid = "f" * 64
        url = "https://arxiv.org/abs/0000.0005"
        _make_cache_file(cache_dir, url, "optimal execution limit order book adverse selection")
        _make_knowledge_db(kb_db, [{"id": sid, "source_url": url}])

        for _ in range(2):
            refresh_lexical_for_corpus(
                [sid], lexical_db_path=lex_db, knowledge_db_path=kb_db,
                cache_dir=cache_dir, verbose=False,
            )

        conn = open_lexical_db(lex_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id=?", (sid,)
        ).fetchone()[0]
        conn.close()
        assert count > 0

        # Run once more, count must be identical
        refresh_lexical_for_corpus(
            [sid], lexical_db_path=lex_db, knowledge_db_path=kb_db,
            cache_dir=cache_dir, verbose=False,
        )
        conn = open_lexical_db(lex_db)
        count2 = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id=?", (sid,)
        ).fetchone()[0]
        conn.close()
        assert count2 == count

    def test_refresh_only_indexes_requested_ids(self, tmp_path):
        """Non-corpus papers in the cache directory are NOT indexed."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus
        from packages.polymarket.rag.lexical import open_lexical_db

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid_in = "1" * 64
        sid_out = "2" * 64
        url_in = "https://arxiv.org/abs/0000.0006"
        url_out = "https://arxiv.org/abs/0000.0007"
        _make_cache_file(cache_dir, url_in, "prediction market polymarket")
        _make_cache_file(cache_dir, url_out, "unrelated biology paper text")
        _make_knowledge_db(kb_db, [
            {"id": sid_in, "source_url": url_in},
            {"id": sid_out, "source_url": url_out},
        ])

        refresh_lexical_for_corpus(
            [sid_in],
            lexical_db_path=lex_db,
            knowledge_db_path=kb_db,
            cache_dir=cache_dir,
            verbose=False,
        )

        conn = open_lexical_db(lex_db)
        all_doc_ids = {r[0] for r in conn.execute("SELECT DISTINCT doc_id FROM chunks").fetchall()}
        conn.close()
        assert sid_in in all_doc_ids
        assert sid_out not in all_doc_ids

    def test_refresh_chunks_retrievable_by_fts(self, tmp_path):
        """After refresh, FTS5 search for a unique body term returns the correct doc_id."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus
        from packages.polymarket.rag.lexical import open_lexical_db, lexical_search

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid = "9" * 64
        url = "https://arxiv.org/abs/0000.0008"
        unique_phrase = "xylophonic martingale boundary condition"
        _make_cache_file(
            cache_dir, url,
            f"Some background text. {unique_phrase}. More text follows here."
        )
        _make_knowledge_db(kb_db, [{"id": sid, "source_url": url}])

        refresh_lexical_for_corpus(
            [sid], lexical_db_path=lex_db, knowledge_db_path=kb_db,
            cache_dir=cache_dir, verbose=False,
        )

        conn = open_lexical_db(lex_db)
        results = lexical_search(
            conn, "xylophonic martingale", k=5, private_only=False, public_only=False
        )
        conn.close()

        assert len(results) >= 1
        assert any(r["doc_id"] == sid for r in results)

    def test_refresh_doc_id_matches_source_id(self, tmp_path):
        """doc_id and file_path in lexical chunks equal the corpus source_id."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus
        from packages.polymarket.rag.lexical import open_lexical_db

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid = "abcdef1234abcdef" * 4  # 64-char id
        url = "https://arxiv.org/abs/1234.5678"
        _make_cache_file(cache_dir, url, "market microstructure spread inventory risk")
        _make_knowledge_db(kb_db, [{"id": sid, "source_url": url}])

        refresh_lexical_for_corpus(
            [sid], lexical_db_path=lex_db, knowledge_db_path=kb_db,
            cache_dir=cache_dir, verbose=False,
        )

        conn = open_lexical_db(lex_db)
        rows = conn.execute(
            "SELECT DISTINCT doc_id, file_path FROM chunks WHERE doc_id=?", (sid,)
        ).fetchall()
        conn.close()

        assert len(rows) >= 1
        assert rows[0][0] == sid
        assert rows[0][1] == sid

    def test_refresh_result_fields(self, tmp_path):
        """RefreshResult dataclass has correct field values after a run."""
        from packages.research.eval_benchmark.lexical_refresh import refresh_lexical_for_corpus

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        kb_db = tmp_path / "knowledge.sqlite3"
        lex_db = tmp_path / "lexical.sqlite3"

        sid_a = "aa" * 32
        sid_b = "bb" * 32
        url_a = "https://arxiv.org/abs/5555.0001"
        _make_cache_file(cache_dir, url_a, "prediction market informed trading spread")
        _make_knowledge_db(kb_db, [
            {"id": sid_a, "source_url": url_a},
            {"id": sid_b, "source_url": ""},  # no URL -> skipped as no_url
        ])

        result = refresh_lexical_for_corpus(
            [sid_a, sid_b],
            lexical_db_path=lex_db,
            knowledge_db_path=kb_db,
            cache_dir=cache_dir,
            verbose=False,
        )

        assert result.corpus_entries == 2
        assert result.indexed == 1
        assert result.skipped_no_url == 1
        assert result.total_chunks >= 1
        assert result.elapsed_seconds >= 0.0
        assert sid_a in result.indexed_ids
        assert sid_b in result.skipped_ids


# ===========================================================================
# TestSimulatePrefetchFilterCLI
# ===========================================================================

class TestSimulatePrefetchFilterCLI:
    """Tests for --simulate-prefetch-filter CLI path."""

    def _make_minimal_db(self, tmp_path, docs):
        """Create a minimal SQLite KnowledgeStore DB with the given docs.

        docs is a list of dicts with keys: id, title, metadata_json (optional).
        """
        db_path = tmp_path / "knowledge.sqlite3"
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE source_documents (
                id TEXT PRIMARY KEY,
                title TEXT,
                source_url TEXT,
                source_family TEXT,
                content_hash TEXT,
                chunk_count INTEGER DEFAULT 5,
                published_at TEXT,
                ingested_at TEXT,
                confidence_tier TEXT,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        for doc in docs:
            conn.execute(
                "INSERT INTO source_documents (id, title, source_url, source_family, content_hash, "
                "chunk_count, published_at, ingested_at, confidence_tier, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc["id"],
                    doc.get("title", ""),
                    doc.get("source_url", ""),
                    doc.get("source_family", "academic"),
                    doc.get("content_hash", ""),
                    doc.get("chunk_count", 5),
                    None, None, None,
                    doc.get("metadata_json", "{}"),
                ),
            )
        conn.commit()
        conn.close()
        return db_path

    def test_simulate_exits_0_with_minimal_corpus(self, tmp_path):
        """--simulate-prefetch-filter exits 0 with a valid corpus and DB."""
        corpus_data = _make_corpus_json(
            version="v0",
            seed_keywords=["prediction market"],
            entries=[{"source_id": "doc_abc", "title": "Prediction Market Microstructure"}],
        )
        corpus_path = _write_json(tmp_path / "corpus.json", corpus_data)
        db_path = self._make_minimal_db(tmp_path, [
            {"id": "doc_abc", "title": "Prediction Market Microstructure",
             "metadata_json": json.dumps({"abstract": "prediction market limit order book"})}
        ])
        from tools.cli.research_eval_benchmark import main
        rc = main([
            "--corpus", str(corpus_path),
            "--db", str(db_path),
            "--simulate-prefetch-filter",
        ])
        assert rc == 0

    def test_simulate_bad_filter_config_exits_1(self, tmp_path):
        """--simulate-prefetch-filter with nonexistent --filter-config exits 1."""
        corpus_data = _make_corpus_json(entries=[])
        corpus_path = _write_json(tmp_path / "corpus.json", corpus_data)
        db_path = self._make_minimal_db(tmp_path, [])
        from tools.cli.research_eval_benchmark import main
        rc = main([
            "--corpus", str(corpus_path),
            "--db", str(db_path),
            "--simulate-prefetch-filter",
            "--filter-config", str(tmp_path / "nonexistent.json"),
        ])
        assert rc == 1

    def test_simulate_reject_counted_correctly(self, tmp_path):
        """Clearly off-topic paper (hastelloy) appears in REJECT count."""
        corpus_data = _make_corpus_json(
            seed_keywords=["prediction market"],
            entries=[
                {"source_id": "doc_on_topic", "title": "Prediction Market Microstructure"},
                {"source_id": "doc_off_topic", "title": "Hastelloy-X SLM Fabricated Fatigue Life"},
            ],
        )
        corpus_path = _write_json(tmp_path / "corpus.json", corpus_data)
        db_path = self._make_minimal_db(tmp_path, [
            {"id": "doc_on_topic", "title": "Prediction Market Microstructure",
             "metadata_json": json.dumps({"abstract": "prediction market analysis"})},
            {"id": "doc_off_topic", "title": "Hastelloy-X SLM Fabricated Fatigue Life",
             "metadata_json": json.dumps({"abstract": "hastelloy microstructure fatigue"})},
        ])
        from tools.cli.research_eval_benchmark import main
        rc = main([
            "--corpus", str(corpus_path),
            "--db", str(db_path),
            "--simulate-prefetch-filter",
        ])
        assert rc == 0  # simulation always exits 0

    def test_simulate_with_calibrated_fixture_hits_target(self, tmp_path):
        """A corpus where only clearly on-topic papers remain after filtering hits <10% target."""
        corpus_data = _make_corpus_json(
            seed_keywords=["prediction market", "market microstructure"],
            entries=[
                {"source_id": "doc_pm", "title": "Prediction Market Limit Order Book Dynamics"},
                {"source_id": "doc_mm", "title": "Market Microstructure and Market Making"},
                {"source_id": "doc_off", "title": "Hastelloy-X SLM Fabricated Fatigue Life"},
            ],
        )
        corpus_path = _write_json(tmp_path / "corpus.json", corpus_data)
        db_path = self._make_minimal_db(tmp_path, [
            {"id": "doc_pm", "title": "Prediction Market Limit Order Book Dynamics",
             "metadata_json": json.dumps({"abstract": "prediction market informed trading"})},
            {"id": "doc_mm", "title": "Market Microstructure and Market Making",
             "metadata_json": json.dumps({"abstract": "market microstructure bid-ask spread"})},
            {"id": "doc_off", "title": "Hastelloy-X SLM Fabricated Fatigue Life",
             "metadata_json": json.dumps({"abstract": "hastelloy fatigue slm fabricated"})},
        ])
        from tools.cli.research_eval_benchmark import main
        rc = main([
            "--corpus", str(corpus_path),
            "--db", str(db_path),
            "--simulate-prefetch-filter",
        ])
        assert rc == 0
