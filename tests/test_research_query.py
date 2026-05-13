"""Tests for L2 academic corpus query (research-query / academic_query.py).

Tests cover:
- Marker-only gate: academic source_family filter applied correctly
- Bad-document rejection: non-academic docs not returned
- Empty corpus graceful fallback
- Multi-angle query merging (deduplication by claim_id)
- Citation metadata extraction (arxiv_id, body_source from metadata_json)
- Paper-level grouping and ranking
- CLI smoke test (--help, missing KS)

Note on KS substring matching: query_knowledge_store_for_rrf uses verbatim
case-insensitive substring matching on claim_text. All test queries are chosen
to be exact substrings of the corresponding claim texts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers — build in-memory KS with test data
# ---------------------------------------------------------------------------

def _make_ks(academic_docs=(), non_academic_docs=()):
    """Return an in-memory KnowledgeStore populated with test documents."""
    from packages.polymarket.rag.knowledge_store import KnowledgeStore

    ks = KnowledgeStore(":memory:")

    for doc in academic_docs:
        doc_id = ks.add_source_document(
            title=doc.get("title", "Test Paper"),
            source_url=doc.get("source_url", "https://arxiv.org/abs/0000.00000"),
            source_family="academic",
            content_hash="abc" + doc.get("title", "x")[:8],
            chunk_count=1,
            published_at="2026-01-01",
            ingested_at="2026-05-09T00:00:00Z",
            confidence_tier=None,
            metadata_json=doc.get("metadata_json"),
        )
        for claim_text in doc.get("claims", []):
            ks.add_claim(
                claim_text=claim_text,
                claim_type="finding",
                confidence=0.8,
                trust_tier="T2",
                actor="test",
                source_document_id=doc_id,
            )

    for doc in non_academic_docs:
        doc_id = ks.add_source_document(
            title=doc.get("title", "Non-Academic Doc"),
            source_url=doc.get("source_url", "https://example.com/blog"),
            source_family=doc.get("source_family", "blog"),
            content_hash="zz" + doc.get("title", "x")[:8],
            chunk_count=1,
            published_at="2026-01-01",
            ingested_at="2026-05-09T00:00:00Z",
            confidence_tier=None,
            metadata_json=doc.get("metadata_json"),
        )
        for claim_text in doc.get("claims", []):
            ks.add_claim(
                claim_text=claim_text,
                claim_type="finding",
                confidence=0.8,
                trust_tier="T2",
                actor="test",
                source_document_id=doc_id,
            )

    return ks


def _marker_metadata(arxiv_id="2604.24366", body_source="marker", body_length=56923) -> str:
    """Build a metadata_json string with canonical_ids and body_source."""
    return json.dumps({
        "canonical_ids": {"arxiv_id": arxiv_id},
        "body_source": body_source,
        "body_length": body_length,
        "source_type": "arxiv",
    })


# ---------------------------------------------------------------------------
# Tests — academic_query.query_academic_corpus()
# ---------------------------------------------------------------------------


class TestQueryAcademicCorpus:
    """Unit tests for query_academic_corpus using injected in-memory KS."""

    def _call(self, question, ks, **kwargs):
        from packages.research.synthesis.academic_query import query_academic_corpus
        return query_academic_corpus(question, _store=ks, **kwargs)

    def test_empty_ks_returns_fallback(self):
        ks = _make_ks()
        result = self._call("market microstructure", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.marker_only_count == 0
        assert result.warning is not None
        assert "research-marker-queue" in result.warning

    def test_academic_doc_returned(self):
        # Claim contains the query "bid-ask" as a verbatim substring
        ks = _make_ks(academic_docs=[{
            "title": "Polymarket microstructure",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "metadata_json": _marker_metadata("2604.24366", "marker"),
            "claims": ["Polymarket has efficient bid-ask spreads for binary markets."],
        }])
        result = self._call("bid-ask", ks)
        assert result.had_fallback is False
        assert len(result.citations) == 1
        assert result.citations[0].title == "Polymarket microstructure"
        assert result.citations[0].arxiv_id == "2604.24366"
        assert result.citations[0].body_source == "marker"
        assert result.marker_only_count == 1

    def test_non_academic_docs_not_returned(self):
        """Non-academic source_family docs must not appear in citations."""
        # Both docs contain "prediction" — KS filter must exclude the blog doc
        ks = _make_ks(
            academic_docs=[{
                "title": "Academic Paper",
                "metadata_json": _marker_metadata("1234.56789", "marker"),
                "claims": ["Academic finding about prediction markets."],
            }],
            non_academic_docs=[{
                "title": "Blog Post",
                "source_family": "blog",
                "metadata_json": json.dumps({"body_source": "html"}),
                "claims": ["Blog post about prediction markets and strategies."],
            }],
        )
        result = self._call("prediction", ks)
        assert result.had_fallback is False
        titles = [c.title for c in result.citations]
        assert "Academic Paper" in titles
        assert "Blog Post" not in titles

    def test_bad_body_source_not_returned(self):
        """Legacy academic docs with non-marker body_source are filtered out."""
        ks = _make_ks(academic_docs=[{
            "title": "Pdfplumber Paper",
            "metadata_json": json.dumps({
                "canonical_ids": {"arxiv_id": "9999.99999"},
                "body_source": "pdfplumber",
                "body_length": 50000,
            }),
            "claims": ["Some pdfplumber-parsed finding from a paper."],
        }])
        # "pdfplumber-parsed" is a verbatim substring of the claim
        result = self._call("pdfplumber-parsed", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.marker_only_count == 0
        assert result.total_claims_found == 1
        assert result.warning is not None
        assert "Marker-ready" in result.warning

    def test_short_marker_body_not_returned(self):
        """Marker metadata must also satisfy the RAG-ready body-length floor."""
        ks = _make_ks(academic_docs=[{
            "title": "Short Marker Paper",
            "metadata_json": _marker_metadata("1111.00001", "marker", body_length=4999),
            "claims": ["short marker body about microstructure"],
        }])
        result = self._call("microstructure", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.marker_only_count == 0

    def test_bad_top_result_does_not_hide_marker_ready_paper(self):
        """Filtering happens before the final k cap is applied."""
        ks = _make_ks(academic_docs=[
            {
                "title": "Legacy Pdfplumber Paper",
                "metadata_json": json.dumps({
                    "canonical_ids": {"arxiv_id": "9999.99999"},
                    "body_source": "pdfplumber",
                    "body_length": 50000,
                }),
                "claims": ["microstructure finding from a legacy row"],
            },
            {
                "title": "Marker Paper",
                "metadata_json": _marker_metadata("2604.24366", "marker"),
                "claims": ["microstructure finding from a Marker-ready row"],
            },
        ])
        result = self._call("microstructure", ks, k=1)
        assert result.had_fallback is False
        assert len(result.citations) == 1
        assert result.citations[0].title == "Marker Paper"
        assert result.marker_only_count == 1

    def test_multiple_papers_returned(self):
        """Multiple papers matching the query should all be returned."""
        ks = _make_ks(academic_docs=[
            {
                "title": "Paper A",
                "metadata_json": _marker_metadata("1111.11111", "marker"),
                "claims": ["microstructure efficiency in prediction markets"],
            },
            {
                "title": "Paper B",
                "metadata_json": _marker_metadata("2222.22222", "marker"),
                "claims": ["microstructure bid-ask spread analysis"],
            },
        ])
        # "microstructure" appears in both claims
        result = self._call("microstructure", ks, k=5)
        assert len(result.citations) >= 1
        assert result.marker_only_count >= 1

    def test_deduplication_by_claim_id(self):
        """Same claim matched by multiple query angles should appear once."""
        ks = _make_ks(academic_docs=[{
            "title": "Deduplicated Paper",
            "metadata_json": _marker_metadata("3333.33333", "marker"),
            "claims": ["prediction market microstructure efficiency study"],
        }])
        # "prediction" matches both primary and angle queries
        result = self._call("prediction", ks, max_query_angles=3, k=10)
        assert result.had_fallback is False
        titles = [c.title for c in result.citations]
        assert titles.count("Deduplicated Paper") == 1

    def test_k_limits_citations(self):
        """k parameter must cap the number of returned paper citations."""
        ks = _make_ks(academic_docs=[
            {
                "title": f"Paper {i}",
                "metadata_json": _marker_metadata(f"{i:04d}.{i:05d}", "marker"),
                "claims": [f"finding number {i} about market behavior"],
            }
            for i in range(5)
        ])
        # "finding" appears in all 5 claims
        result = self._call("finding", ks, k=2)
        assert len(result.citations) <= 2

    def test_query_angles_populated(self):
        """query_angles should always contain the primary question."""
        ks = _make_ks(academic_docs=[{
            "title": "Test",
            "metadata_json": _marker_metadata(),
            "claims": ["test claim about prediction markets"],
        }])
        result = self._call("prediction", ks, max_query_angles=2)
        assert "prediction" in result.query_angles

    def test_arxiv_id_extraction(self):
        """arxiv_id from canonical_ids must be extracted and set on citation."""
        ks = _make_ks(academic_docs=[{
            "title": "arXiv Paper",
            "metadata_json": json.dumps({
                "canonical_ids": {"arxiv_id": "2109.07581"},
                "body_source": "marker",
                "body_length": 56923,
            }),
            "claims": ["COVID-19 disrupted sports betting markets significantly."],
        }])
        result = self._call("COVID-19", ks)
        assert len(result.citations) == 1
        assert result.citations[0].arxiv_id == "2109.07581"

    def test_missing_metadata_json_does_not_crash(self):
        """Papers without metadata_json should not crash or become queryable."""
        ks = _make_ks(academic_docs=[{
            "title": "No Metadata Paper",
            "metadata_json": None,
            "claims": ["sports betting market inefficiency result"],
        }])
        result = self._call("inefficiency", ks)
        assert result.had_fallback is True
        assert result.citations == []

    def test_claim_count_per_paper(self):
        """claim_count on each citation should reflect number of matched claims."""
        ks = _make_ks(academic_docs=[{
            "title": "Multi-claim Paper",
            "metadata_json": _marker_metadata("4444.44444", "marker"),
            "claims": [
                "market maker profitability in binary prediction markets",
                "avellaneda stoikov model performance study",
                "inventory control strategies for market makers",
            ],
        }])
        # "maker" appears in 2 of the 3 claims
        result = self._call("maker", ks, k=5)
        assert len(result.citations) == 1
        assert result.citations[0].claim_count >= 1

    def test_total_claims_found_non_negative(self):
        """total_claims_found must always be non-negative."""
        ks = _make_ks()
        result = self._call("anything", ks)
        assert result.total_claims_found >= 0

    def test_case_a_empty_ks_returns_no_docs_warning(self):
        """Empty KS (Case A) → warning says no academic documents found."""
        ks = _make_ks()
        result = self._call("quantum field theory", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.warning is not None
        assert "No academic documents found" in result.warning
        assert "research-marker-queue" in result.warning

    def test_case_b_populated_ks_unrelated_query_returns_no_relevant_warning(self):
        """KS has Marker-ready academic docs but query matches nothing (Case B).

        Warning must indicate documents exist but none matched — not the
        misleading 'no academic documents found' message from Case A.
        """
        ks = _make_ks(academic_docs=[{
            "title": "Prediction Market Microstructure",
            "metadata_json": _marker_metadata("2604.24366", "marker"),
            "claims": ["Polymarket bid-ask spread efficiency in binary markets."],
        }])
        # Query text does not appear in any claim as a substring
        result = self._call("quantum field theory irrelevant xyz", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.warning is not None
        assert "Academic documents exist" in result.warning
        assert "no relevant" in result.warning.lower()
        # Must NOT claim the corpus is empty
        assert "No academic documents found" not in result.warning

    def test_max_angles_one_runs_primary_only(self):
        """max_query_angles=1 should only run the primary query."""
        ks = _make_ks(academic_docs=[{
            "title": "Test Paper",
            "metadata_json": _marker_metadata(),
            "claims": ["Polymarket microstructure data analysis"],
        }])
        result = self._call("microstructure", ks, max_query_angles=1)
        # Should return primary only
        assert result.query_angles == ["microstructure"]

    def test_source_url_on_citation(self):
        """source_url should be populated from the source document."""
        ks = _make_ks(academic_docs=[{
            "title": "URL Test Paper",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "metadata_json": _marker_metadata("2604.24366", "marker"),
            "claims": ["Polymarket bid-ask spread analysis"],
        }])
        result = self._call("bid-ask", ks)
        assert result.citations[0].source_url == "https://arxiv.org/abs/2604.24366"


# ---------------------------------------------------------------------------
# Tests — CLI (research_query.main)
# ---------------------------------------------------------------------------


class TestResearchQueryCLI:
    """Smoke tests for the research-query CLI."""

    def test_help_exits_zero(self):
        from tools.cli.research_query import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_missing_question_exits_nonzero(self):
        from tools.cli.research_query import main
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_nonexistent_ks_returns_fallback_json(self, capsys, tmp_path):
        """When KS doesn't exist, CLI returns fallback JSON with had_fallback=True."""
        from tools.cli.research_query import main
        missing = str(tmp_path / "nonexistent.sqlite3")
        rc = main(["--question", "market microstructure", "--knowledge-store", missing])
        assert rc == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["had_fallback"] is True
        assert payload["citations"] == []
        assert payload["warning"] is not None

    def test_k_validation(self, tmp_path):
        """--k <= 0 must return error exit code."""
        from tools.cli.research_query import main
        rc = main(["--question", "test", "--k", "0",
                   "--knowledge-store", str(tmp_path / "x.db")])
        assert rc == 1

    def test_max_angles_validation(self, tmp_path):
        """--max-angles < 1 must return error exit code."""
        from tools.cli.research_query import main
        rc = main(["--question", "test", "--max-angles", "0",
                   "--knowledge-store", str(tmp_path / "x.db")])
        assert rc == 1

    def test_output_is_valid_json(self, capsys, tmp_path):
        """CLI output for missing KS must be parseable JSON with required keys."""
        from tools.cli.research_query import main
        missing = str(tmp_path / "missing.sqlite3")
        main(["--question", "sports betting", "--knowledge-store", missing])
        captured = capsys.readouterr()
        payload = json.loads(captured.out)  # must not raise
        assert "question" in payload
        assert "citations" in payload
        assert "had_fallback" in payload
        assert "query_angles" in payload
        assert "marker_only_count" in payload
        assert "total_claims_found" in payload


# ---------------------------------------------------------------------------
# Tests — private helpers
# ---------------------------------------------------------------------------


class TestAcademicQueryHelpers:
    """Unit tests for private helper functions."""

    def test_extract_arxiv_id_valid(self):
        from packages.research.synthesis.academic_query import _extract_arxiv_id
        meta = json.dumps({"canonical_ids": {"arxiv_id": "2604.24366"}})
        assert _extract_arxiv_id(meta) == "2604.24366"

    def test_extract_arxiv_id_missing(self):
        from packages.research.synthesis.academic_query import _extract_arxiv_id
        meta = json.dumps({"canonical_ids": {}})
        assert _extract_arxiv_id(meta) is None

    def test_extract_arxiv_id_none_input(self):
        from packages.research.synthesis.academic_query import _extract_arxiv_id
        assert _extract_arxiv_id(None) is None

    def test_extract_arxiv_id_bad_json(self):
        from packages.research.synthesis.academic_query import _extract_arxiv_id
        assert _extract_arxiv_id("not-json") is None

    def test_extract_body_source_marker(self):
        from packages.research.synthesis.academic_query import _extract_body_source
        meta = json.dumps({"body_source": "marker"})
        assert _extract_body_source(meta) == "marker"

    def test_extract_body_source_missing(self):
        from packages.research.synthesis.academic_query import _extract_body_source
        assert _extract_body_source(None) == "unknown"
        assert _extract_body_source(json.dumps({})) == "unknown"

    def test_merge_claims_keeps_best_score(self):
        from packages.research.synthesis.academic_query import _merge_claims
        items = [
            {"chunk_id": "c1", "score": 0.5, "doc_id": "d1"},
            {"chunk_id": "c1", "score": 0.9, "doc_id": "d1"},
            {"chunk_id": "c2", "score": 0.3, "doc_id": "d2"},
        ]
        merged = _merge_claims(items)
        assert len(merged) == 2
        assert merged["c1"]["score"] == 0.9

    def test_merge_claims_empty(self):
        from packages.research.synthesis.academic_query import _merge_claims
        assert _merge_claims([]) == {}

    def test_merge_claims_skips_missing_chunk_id(self):
        from packages.research.synthesis.academic_query import _merge_claims
        items = [{"score": 0.5, "doc_id": "d1"}, {"chunk_id": "", "score": 0.3}]
        merged = _merge_claims(items)
        assert merged == {}

    def test_group_by_paper(self):
        from packages.research.synthesis.academic_query import _group_by_paper
        merged = {
            "c1": {"chunk_id": "c1", "score": 0.8, "doc_id": "doc_a"},
            "c2": {"chunk_id": "c2", "score": 0.6, "doc_id": "doc_a"},
            "c3": {"chunk_id": "c3", "score": 0.4, "doc_id": "doc_b"},
        }
        by_paper = _group_by_paper(merged)
        assert len(by_paper["doc_a"]) == 2
        assert len(by_paper["doc_b"]) == 1

    def test_build_sub_queries_includes_primary(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("market microstructure", max_angles=3, include_step_back=False)
        labels = [label for _, label in queries]
        assert "primary" in labels
        assert queries[0][0] == "market microstructure"

    def test_build_sub_queries_deduplicates(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("x", max_angles=3, include_step_back=False)
        texts = [q for q, _ in queries]
        assert len(texts) == len(set(texts))

    def test_build_sub_queries_max_angles_one(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("market", max_angles=1, include_step_back=False)
        assert len(queries) == 1
        assert queries[0][1] == "primary"

    def test_build_sub_queries_step_back_included(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("market making", max_angles=2, include_step_back=True)
        labels = [label for _, label in queries]
        assert "step_back" in labels

    # ------------------------------------------------------------------
    # Tests — _normalize_question
    # ------------------------------------------------------------------

    def test_normalize_question_what_are(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("what are prediction markets") == "prediction markets"

    def test_normalize_question_what_is(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("what is market microstructure") == "market microstructure"

    def test_normalize_question_explain(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("explain sports betting markets") == "sports betting markets"

    def test_normalize_question_how_does(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("how does avellaneda stoikov work") == "avellaneda stoikov work"

    def test_normalize_question_no_preamble_unchanged(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("prediction markets") == "prediction markets"

    def test_normalize_question_trailing_punctuation_stripped(self):
        from packages.research.synthesis.academic_query import _normalize_question
        assert _normalize_question("what are prediction markets?") == "prediction markets"

    def test_normalize_question_empty_after_strip_returns_original(self):
        from packages.research.synthesis.academic_query import _normalize_question
        # Edge case: "what is" alone — no core content
        assert _normalize_question("what is") == "what is"

    def test_build_sub_queries_includes_normalized_angle(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("what are prediction markets", max_angles=3, include_step_back=False)
        texts = [q for q, _ in queries]
        assert "what are prediction markets" in texts  # primary preserved
        assert "prediction markets" in texts            # normalized angle added

    def test_build_sub_queries_no_duplicate_when_no_preamble(self):
        from packages.research.synthesis.academic_query import _build_sub_queries
        queries = _build_sub_queries("prediction markets", max_angles=3, include_step_back=False)
        texts = [q for q, _ in queries]
        assert texts.count("prediction markets") == 1  # not duplicated


# ---------------------------------------------------------------------------
# Tests — natural-language question retrieval robustness
# ---------------------------------------------------------------------------


class TestNaturalLanguageRetrieval:
    """Verify that question-phrased queries retrieve the same papers as
    keyword queries when the corpus contains matching claims.
    """

    def _call(self, question, ks, **kwargs):
        from packages.research.synthesis.academic_query import query_academic_corpus
        return query_academic_corpus(question, _store=ks, **kwargs)

    def _pm_ks(self):
        """KS with a single Marker-ready prediction-markets paper."""
        return _make_ks(academic_docs=[{
            "title": "Prediction Market Microstructure",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "metadata_json": _marker_metadata("2604.24366", "marker"),
            "claims": [
                "Prediction markets aggregate information efficiently.",
                "Polymarket prediction markets show low bid-ask spreads.",
            ],
        }])

    def test_keyword_query_returns_citation(self):
        """Baseline: bare keyword query returns Marker citation."""
        ks = self._pm_ks()
        result = self._call("prediction markets", ks)
        assert result.had_fallback is False
        assert len(result.citations) == 1
        assert result.citations[0].body_source == "marker"

    def test_what_are_question_returns_same_citation(self):
        """'what are prediction markets' should return the same citation."""
        ks = self._pm_ks()
        result = self._call("what are prediction markets", ks)
        assert result.had_fallback is False
        assert len(result.citations) == 1
        assert result.citations[0].title == "Prediction Market Microstructure"
        assert result.citations[0].body_source == "marker"

    def test_explain_question_returns_citation(self):
        """'explain prediction markets' should retrieve the paper."""
        ks = self._pm_ks()
        result = self._call("explain prediction markets", ks)
        assert result.had_fallback is False
        assert len(result.citations) >= 1

    def test_unrelated_question_returns_no_match_warning(self):
        """Unrelated query against populated corpus returns Case B warning."""
        ks = self._pm_ks()
        result = self._call("quantum chromodynamics lattice gauge theory", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.warning is not None
        assert "Academic documents exist" in result.warning
        assert "No academic documents found" not in result.warning

    def test_empty_ks_returns_empty_corpus_warning(self):
        """Empty KS always returns Case A warning regardless of question phrasing."""
        ks = _make_ks()
        result = self._call("what are prediction markets", ks)
        assert result.had_fallback is True
        assert result.citations == []
        assert result.warning is not None
        assert "No academic documents found" in result.warning

    def test_original_question_preserved_in_result(self):
        """Output question field must always be the original, not the normalized form."""
        ks = self._pm_ks()
        result = self._call("what are prediction markets", ks)
        assert result.question == "what are prediction markets"

    def test_normalized_angle_in_query_angles(self):
        """query_angles should include the normalized core phrase."""
        ks = self._pm_ks()
        result = self._call("what are prediction markets", ks, max_query_angles=3)
        assert "prediction markets" in result.query_angles
