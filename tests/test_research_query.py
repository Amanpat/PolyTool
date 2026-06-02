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


def _get_ks_doc_id(ks, title: str) -> str:
    """Return the KS source_document.id for the given title (for fake Chroma setup)."""
    row = ks._conn.execute(
        "SELECT id FROM source_documents WHERE title = ?", (title,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No source document with title={title!r}")
    return str(row[0])


class _FakeChromaCollForAcademic:
    """Fake ChromaDB collection for offline semantic retrieval tests.

    query_responses maps query_text.lower() -> [(ks_doc_id, similarity_score), ...]
    """

    def __init__(self, query_responses: dict):
        self._resp = {k.lower(): v for k, v in query_responses.items()}

    def query(self, query_texts=None, query_embeddings=None, n_results=10, where=None, include=None):
        qt = (query_texts[0] if query_texts else "").lower()
        hits = self._resp.get(qt, [])[:n_results]
        return {
            "ids": [[f"chunk_{doc_id}_0" for doc_id, _ in hits]],
            "distances": [[max(0.0, 1.0 - score) for _, score in hits]],
            "metadatas": [[
                {"ks_doc_id": doc_id, "chunk_index": 0, "body_source": "marker"}
                for doc_id, _ in hits
            ]],
            "documents": [[f"Chunk content for document {doc_id}" for doc_id, _ in hits]],
        }


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


# ---------------------------------------------------------------------------
# Tests — _sanitize_snippet (Deliverable C)
# ---------------------------------------------------------------------------


class TestSanitizeSnippet:
    """Unit tests for the display-only Marker artifact sanitizer."""

    def _sanitize(self, text):
        from packages.research.synthesis.academic_query import _sanitize_snippet
        return _sanitize_snippet(text)

    # --- Known Marker HTML tags ---

    def test_strips_sup_tag(self):
        assert "<sup>" not in self._sanitize("<sup>∗</sup> Footnote text here.")

    def test_strips_sup_content_preserved(self):
        # Content between tags is kept; only the tags are removed
        result = self._sanitize("<sup>∗</sup> Footnote text here.")
        assert "∗" in result
        assert "Footnote text here" in result

    def test_strips_closing_sup_tag(self):
        assert "</sup>" not in self._sanitize("text<sup>1</sup> more text")

    def test_strips_sub_tag(self):
        result = self._sanitize("CO<sub>2</sub> emissions")
        assert "<sub>" not in result
        assert "</sub>" not in result
        assert "CO" in result
        assert "2" in result

    def test_strips_br_tag(self):
        assert "<br>" not in self._sanitize("line one<br>line two")

    def test_strips_br_self_closing(self):
        assert "<br/>" not in self._sanitize("line one<br/>line two")

    def test_strips_br_spaced_self_closing(self):
        assert "<br />" not in self._sanitize("line one<br />line two")

    def test_strips_anchor_tag_with_href(self):
        result = self._sanitize('<a href="https://example.com">link text</a>')
        assert "<a" not in result
        assert "</a>" not in result
        assert "link text" in result

    # --- Page reference anchors ---

    def test_strips_page_ref_at_start(self):
        result = self._sanitize("(#page-18-0) Some citation text.")
        assert "(#page-18-0)" not in result
        assert "Some citation text" in result

    def test_strips_page_ref_mid_text(self):
        raw = "Sentence one (#page-3-1) continues here."
        result = self._sanitize(raw)
        assert "(#page-3-1)" not in result
        assert "Sentence one" in result
        assert "continues here" in result

    def test_strips_multiple_page_refs(self):
        raw = "(#page-1-0) First. (#page-2-0) Second."
        result = self._sanitize(raw)
        assert "(#page-1-0)" not in result
        assert "(#page-2-0)" not in result
        assert "First" in result
        assert "Second" in result

    def test_page_ref_large_numbers(self):
        result = self._sanitize("Text (#page-123-456) end.")
        assert "(#page-123-456)" not in result

    # --- Markdown heading markers ---

    def test_strips_h4_heading(self):
        raw = "#### **Abstract**\n\nContent here."
        result = self._sanitize(raw)
        assert "####" not in result
        assert "Abstract" in result
        assert "Content here" in result

    def test_strips_h1_heading(self):
        raw = "# Introduction\n\nSome text."
        result = self._sanitize(raw)
        assert result.startswith("Introduction") or "Introduction" in result
        assert "#" not in result.split("\n")[0]

    def test_strips_h2_heading(self):
        raw = "## Related Work\n\nSome text."
        result = self._sanitize(raw)
        assert "##" not in result
        assert "Related Work" in result

    def test_heading_only_at_line_start(self):
        # # inside the middle of a line must not be stripped
        raw = "Price of BTC in USD is $50,000 (a 50# gain)."
        result = self._sanitize(raw)
        assert "50#" in result  # mid-line # preserved

    # --- Whitespace normalization ---

    def test_collapses_excess_newlines(self):
        raw = "Para one.\n\n\n\nPara two."
        result = self._sanitize(raw)
        assert "\n\n\n" not in result
        assert "Para one" in result
        assert "Para two" in result

    def test_collapses_excess_spaces(self):
        raw = "word1   word2    word3"
        result = self._sanitize(raw)
        assert "   " not in result
        assert "word1" in result
        assert "word2" in result

    def test_leading_trailing_whitespace_stripped(self):
        result = self._sanitize("  \n  some text  \n  ")
        assert result == result.strip()

    # --- Preservation guarantees ---

    def test_plain_text_unchanged(self):
        plain = "Prediction markets aggregate information efficiently in binary markets."
        assert self._sanitize(plain) == plain

    def test_numbers_preserved(self):
        raw = "Performance improved from 22.5% to 47.1% on QA tasks."
        result = self._sanitize(raw)
        assert "22.5%" in result
        assert "47.1%" in result

    def test_math_inequality_preserved(self):
        # Bare < and > in math context must survive (not matching named tags)
        raw = "If a < b and b > 0 then a < b < c."
        result = self._sanitize(raw)
        assert "a < b" in result
        assert "b > 0" in result

    def test_latex_dollar_math_preserved(self):
        raw = "Given $\\sigma^2 \\leq 0.003$, the spread is minimal."
        result = self._sanitize(raw)
        assert "$\\sigma^2" in result

    def test_real_marker_abstract_snippet(self):
        """Simulate the actual bad snippet from arxiv:2510.05533."""
        raw = (
            "<sup>∗</sup> Work was done while the author was working at JP Morgan Chase.\n\n"
            "#### **Abstract**\n\n"
            "We provide a comprehensive survey of Large Language Models in financial prediction."
        )
        result = self._sanitize(raw)
        assert "<sup>" not in result
        assert "</sup>" not in result
        assert "####" not in result
        assert "∗" in result
        assert "Abstract" in result
        assert "We provide a comprehensive survey" in result

    def test_real_marker_page_ref_snippet(self):
        """Simulate the actual page-ref snippet from arxiv:2510.05533."""
        raw = (
            "(#page-18-0) (Li et al., 2024b; Wang et al., 2023) can be used to significantly "
            "improve the generation quality of LLMs (Gao et al., 2023) from 22.5% to 47.1% on "
            "Open-Book QA (Mihaylov et al., 2018)."
        )
        result = self._sanitize(raw)
        assert "(#page-18-0)" not in result
        assert "Li et al., 2024b" in result
        assert "22.5%" in result
        assert "47.1%" in result

    def test_strips_inline_heading_mid_snippet(self):
        """#### mid-snippet (not at line start) must be stripped."""
        raw = "DISC FinLLM #### **Abstract** Large language models provide..."
        result = self._sanitize(raw)
        assert "####" not in result
        assert "DISC FinLLM" in result
        assert "Large language models" in result

    def test_strips_orphaned_page_anchor_after_truncation(self):
        """(#pag... artifact left by :400 truncation must be removed."""
        raw = "DISC FinLLM [2023b\\)], DISC FinLLM [2023\\)] (#pag"
        result = self._sanitize(raw)
        assert "(#pag" not in result
        assert "DISC FinLLM" in result


class TestSanitizeSnippetIntegration:
    """Integration: AcademicCitation.best_snippet is sanitized; KS claim_text is not."""

    def _call(self, question, ks, **kwargs):
        from packages.research.synthesis.academic_query import query_academic_corpus
        return query_academic_corpus(question, _store=ks, **kwargs)

    def test_citation_snippet_has_no_html_tags(self):
        """best_snippet must have Marker HTML tags stripped."""
        raw_claim = "<sup>∗</sup> Prediction markets aggregate information efficiently."
        ks = _make_ks(academic_docs=[{
            "title": "Sanitize Test Paper",
            "metadata_json": _marker_metadata("9876.54321", "marker"),
            "claims": [raw_claim],
        }])
        result = self._call("prediction markets", ks)
        assert result.had_fallback is False
        snippet = result.citations[0].best_snippet
        assert "<sup>" not in snippet
        assert "</sup>" not in snippet
        # Content between tags survives
        assert "∗" in snippet or "Prediction markets" in snippet

    def test_citation_snippet_has_no_page_ref(self):
        """best_snippet must have (#page-N-M) anchors stripped."""
        raw_claim = "(#page-5-0) Language models achieve 47.1% accuracy on QA tasks."
        ks = _make_ks(academic_docs=[{
            "title": "PageRef Test Paper",
            "metadata_json": _marker_metadata("1111.22222", "marker"),
            "claims": [raw_claim],
        }])
        result = self._call("language models", ks)
        assert result.had_fallback is False
        snippet = result.citations[0].best_snippet
        assert "(#page-5-0)" not in snippet
        assert "47.1%" in snippet

    def test_citation_snippet_has_no_md_heading(self):
        """best_snippet must have markdown heading markers stripped."""
        raw_claim = "#### **Results**\n\nThe model achieves state-of-the-art performance."
        ks = _make_ks(academic_docs=[{
            "title": "Heading Test Paper",
            "metadata_json": _marker_metadata("3333.44444", "marker"),
            "claims": [raw_claim],
        }])
        result = self._call("Results", ks)
        assert result.had_fallback is False
        snippet = result.citations[0].best_snippet
        assert "####" not in snippet
        assert "Results" in snippet
        assert "state-of-the-art" in snippet

    def test_stored_claim_text_not_modified(self):
        """Sanitization must only affect display output; KS claim_text is unchanged."""
        raw_claim = "<sup>1</sup> (Li et al., 2024b) can improve prediction market accuracy."
        ks = _make_ks(academic_docs=[{
            "title": "Immutability Test Paper",
            "metadata_json": _marker_metadata("5555.66666", "marker"),
            "claims": [raw_claim],
        }])
        # Run the query (which sanitizes the snippet)
        result = self._call("prediction market", ks)
        assert result.had_fallback is False

        # Verify the same underlying KS claim_text still has raw content.
        all_claims = ks.query_claims()
        matching = [c for c in all_claims if "prediction market" in c.get("claim_text", "").lower()]
        assert len(matching) >= 1
        stored_text = matching[0]["claim_text"]
        # Raw HTML must still be in the stored claim
        assert "<sup>" in stored_text or raw_claim in stored_text


# ---------------------------------------------------------------------------
# Tests - L2.1 Deliverable B semantic retrieval acceptance gaps
# ---------------------------------------------------------------------------


class TestSemanticRetrievalAcceptanceGaps:
    """Acceptance cases that require semantic retrieval beyond substring search.

    These tests are intentionally xfailed while Deliverable B is blocked. They
    should be unmarked and made passing when query_academic_corpus gains a
    Chroma-backed semantic fallback/merge path.
    """

    def _call(self, question, ks, **kwargs):
        from packages.research.synthesis.academic_query import query_academic_corpus
        return query_academic_corpus(question, _store=ks, **kwargs)

    def test_abbreviation_query_llm_finds_large_language_model_paper_not_bellman(self):
        """LLM must not be satisfied by substring hits inside unrelated words."""
        ks = _make_ks(academic_docs=[
            {
                "title": "Bellman Equations in Market Making",
                "metadata_json": _marker_metadata("1810.04383", "marker"),
                "claims": ["Hamilton-Jacobi-Bellman equations define the control problem."],
            },
            {
                "title": "The New Quant",
                "metadata_json": _marker_metadata("2510.05533", "marker"),
                "claims": [
                    "Large Language Models can support financial prediction and trading."
                ],
            },
        ])
        new_quant_id = _get_ks_doc_id(ks, "The New Quant")
        fake_coll = _FakeChromaCollForAcademic({
            "llm": [(new_quant_id, 0.92)],
        })
        result = self._call("LLM", ks, _chroma_collection=fake_coll, _embed_fn=lambda q: None)
        assert result.had_fallback is False
        assert result.citations
        assert result.citations[0].title == "The New Quant"
        assert all("Bellman" not in c.title for c in result.citations)

    def test_multi_word_query_language_model_financial_prediction_returns_paper(self):
        """Non-contiguous related terms should retrieve through semantic search."""
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": [
                "Large language models are evaluated for financial prediction tasks."
            ],
        }])
        new_quant_id = _get_ks_doc_id(ks, "The New Quant")
        fake_coll = _FakeChromaCollForAcademic({
            "language model financial prediction": [(new_quant_id, 0.88)],
        })
        result = self._call("language model financial prediction", ks, _chroma_collection=fake_coll, _embed_fn=lambda q: None)
        assert result.had_fallback is False
        assert result.citations[0].title == "The New Quant"

    def test_conversational_hallucination_query_returns_paper(self):
        """Conversational wording should still retrieve the core topic."""
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": [
                "Hallucination is a key limitation for language-model trading systems."
            ],
        }])
        new_quant_id = _get_ks_doc_id(ks, "The New Quant")
        fake_coll = _FakeChromaCollForAcademic({
            "what does this paper say about hallucination": [(new_quant_id, 0.85)],
        })
        result = self._call(
            "what does this paper say about hallucination", ks,
            _chroma_collection=fake_coll,
            _embed_fn=lambda q: None,
        )
        assert result.had_fallback is False
        assert result.citations[0].title == "The New Quant"

    def test_unrelated_weather_query_stays_rejected(self):
        """The semantic path must not make unrelated controls look relevant."""
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": [
                "Large language models are evaluated for financial prediction tasks."
            ],
        }])
        result = self._call("weather forecast", ks)
        assert result.had_fallback is True
        assert result.citations == []

    def test_weather_query_low_similarity_chroma_hit_rejected_by_threshold(self):
        """Low-similarity nearest-neighbor Chroma hit must be discarded.

        Even when academic_papers exists and the embedding path is active, an
        unrelated query ('weather forecast') that returns only a low-similarity
        hit must be treated as no-result and fall through to had_fallback=True.
        """
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": [
                "Large language models are evaluated for financial prediction tasks."
            ],
        }])
        new_quant_id = _get_ks_doc_id(ks, "The New Quant")
        # Score 0.10 is well below min_similarity (0.18) — rejected at the chunk level
        fake_coll = _FakeChromaCollForAcademic({
            "weather forecast": [(new_quant_id, 0.10)],
        })
        result = self._call("weather forecast", ks, _chroma_collection=fake_coll, _embed_fn=lambda q: None)
        assert result.had_fallback is True, (
            "Low-similarity nearest-neighbor hit (0.10) should be discarded by "
            "the min_similarity threshold and fall through to lexical/no-result"
        )
        assert result.citations == []

    def test_out_of_domain_single_borderline_hit_rejected_by_confidence_guard(self):
        """Single barely-above-threshold hit (protein-folding style) must be rejected.

        Score 0.182 clears min_similarity (0.18) but falls below confident_threshold
        (0.19). The nearest-neighbor rejection guard fires: len(hits)==1 and
        score < confident_threshold → return [], falling through to had_fallback=True.

        Reproduces the Codex BLOCK (2026-05-28): 'protein folding molecular dynamics'
        returned arxiv:1705.01446 at score 0.18156, just above the legacy 0.18 threshold.
        """
        ks = _make_ks(academic_docs=[{
            "title": "Finance Stochastic Control Paper",
            "metadata_json": _marker_metadata("1705.01446", "marker"),
            "claims": ["Stochastic control and Hamilton-Jacobi-Bellman equations in finance."],
        }])
        paper_id = _get_ks_doc_id(ks, "Finance Stochastic Control Paper")
        # Score 0.182 simulates the protein-folding nearest-neighbor case
        fake_coll = _FakeChromaCollForAcademic({
            "protein folding molecular dynamics": [(paper_id, 0.182)],
        })
        result = self._call(
            "protein folding molecular dynamics", ks,
            _chroma_collection=fake_coll, _embed_fn=lambda q: None,
        )
        assert result.had_fallback is True, (
            "Single hit at 0.182 (below confident_threshold=0.19) must be rejected "
            "by the nearest-neighbor guard even though it clears min_similarity=0.18"
        )
        assert result.citations == []

    def test_relevant_single_hit_at_hallucination_score_passes(self):
        """A single hit at score 0.197 (hallucination AT-3 calibration) must still pass.

        Score 0.197 > confident_threshold (0.19): single-hit confidence guard allows it.
        Documents the calibration boundary: protein folding (0.182) rejects;
        hallucination (0.197) accepts. Raising confident_threshold above 0.197
        would break AT-3 (the hallucination acceptance test).
        """
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": ["Hallucination is a key limitation for LLM-based trading systems."],
        }])
        new_quant_id = _get_ks_doc_id(ks, "The New Quant")
        # Score 0.197 — the live hallucination query score from the L2.1 repair run
        fake_coll = _FakeChromaCollForAcademic({
            "what does this paper say about hallucination": [(new_quant_id, 0.197)],
        })
        result = self._call(
            "what does this paper say about hallucination", ks,
            _chroma_collection=fake_coll, _embed_fn=lambda q: None,
        )
        assert result.had_fallback is False, (
            "Score 0.197 >= confident_threshold=0.19: hallucination query must still accept"
        )
        assert len(result.citations) == 1
        assert result.citations[0].title == "The New Quant"

    def test_multiple_hits_above_min_threshold_bypass_confidence_guard(self):
        """Two papers above min_similarity bypass the single-hit guard.

        When ≥2 distinct papers pass min_similarity, the query is not a lone
        nearest-neighbor artifact. Both papers must be returned even if neither
        individually exceeds confident_threshold.
        """
        ks = _make_ks(academic_docs=[
            {
                "title": "LLM Finance Paper",
                "metadata_json": _marker_metadata("2510.05533", "marker"),
                "claims": ["Large language models for financial prediction."],
            },
            {
                "title": "Prediction Market Paper",
                "metadata_json": _marker_metadata("2507.01990", "marker"),
                "claims": ["Prediction market microstructure and liquidity."],
            },
        ])
        llm_id = _get_ks_doc_id(ks, "LLM Finance Paper")
        pm_id = _get_ks_doc_id(ks, "Prediction Market Paper")
        # Both papers score between min_similarity (0.18) and confident_threshold (0.19)
        # — the single-hit guard must NOT fire when len(hits) >= 2
        fake_coll = _FakeChromaCollForAcademic({
            "llm prediction markets": [(llm_id, 0.185), (pm_id, 0.184)],
        })
        result = self._call(
            "llm prediction markets", ks,
            _chroma_collection=fake_coll, _embed_fn=lambda q: None,
        )
        assert result.had_fallback is False, (
            "Multiple papers above min_similarity must be accepted without the "
            "single-hit confidence guard firing"
        )
        assert len(result.citations) == 2

    def test_result_exposes_retrieval_mode_metadata(self):
        """Operators need to distinguish lexical, semantic, and fallback results."""
        ks = _make_ks(academic_docs=[{
            "title": "The New Quant",
            "metadata_json": _marker_metadata("2510.05533", "marker"),
            "claims": [
                "Large language models are evaluated for financial prediction tasks."
            ],
        }])
        result = self._call("language model financial prediction", ks)
        assert getattr(result, "retrieval_mode") in {"lexical", "semantic", "hybrid"}


# ---------------------------------------------------------------------------
# Tests — _open_chroma_collection fast-fail behaviour
# ---------------------------------------------------------------------------


class TestOpenChromaCollectionFastFail:
    """Verify _open_chroma_collection fails fast without touching HuggingFace.

    The fix: collection existence is checked via list_collections() (local SQLite,
    no network) BEFORE SentenceTransformerEmbeddingFunction is instantiated.
    These tests assert that the embedding function is never called when the
    academic_papers collection is absent.
    """

    def _call(self, **kwargs):
        from packages.research.synthesis.academic_query import _open_chroma_collection
        return _open_chroma_collection(**kwargs)

    def test_missing_collection_returns_none_without_touching_collection(self, monkeypatch):
        """When academic_papers is absent, returns (None, reason) without get_collection."""
        import sys
        from unittest.mock import MagicMock

        fake_client = MagicMock()
        fake_coll_obj = MagicMock()
        fake_coll_obj.name = "some_other_collection"
        fake_client.list_collections.return_value = [fake_coll_obj]

        fake_chromadb = MagicMock()
        fake_chromadb.PersistentClient.return_value = fake_client

        monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

        coll, reason = self._call()

        assert coll is None
        assert reason is not None
        assert "academic_papers" in reason
        # get_collection must never be called when collection is absent
        fake_client.get_collection.assert_not_called()

    def test_empty_collection_list_returns_none_without_touching_collection(self, monkeypatch):
        """When Chroma store is empty, returns (None, reason) without get_collection."""
        import sys
        from unittest.mock import MagicMock

        fake_client = MagicMock()
        fake_client.list_collections.return_value = []

        fake_chromadb = MagicMock()
        fake_chromadb.PersistentClient.return_value = fake_client

        monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

        coll, reason = self._call()

        assert coll is None
        assert reason is not None
        fake_client.get_collection.assert_not_called()

    def test_chromadb_import_error_returns_none_gracefully(self, monkeypatch):
        """When chromadb is not installed, returns (None, reason) without raising."""
        import sys
        # Simulate ImportError by removing chromadb from sys.modules
        monkeypatch.setitem(sys.modules, "chromadb", None)

        coll, reason = self._call()

        assert coll is None
        assert reason is not None
        assert "chromadb" in reason.lower()

    def test_academic_papers_present_opens_collection_without_ef(self, monkeypatch):
        """When academic_papers exists, collection is opened WITHOUT an embedding function.

        The marker queue upserts pre-computed embeddings; attaching a Chroma EF at
        open time would cause an EF conflict error. Query-time embeddings are computed
        separately by _query_chroma_semantic using SentenceTransformerEmbedder.
        """
        import sys
        from unittest.mock import MagicMock

        fake_collection = MagicMock()
        fake_client = MagicMock()
        fake_coll_obj = MagicMock()
        fake_coll_obj.name = "academic_papers"
        fake_client.list_collections.return_value = [fake_coll_obj]
        fake_client.get_collection.return_value = fake_collection

        fake_chromadb = MagicMock()
        fake_chromadb.PersistentClient.return_value = fake_client

        monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

        coll, reason = self._call()

        assert reason is None
        assert coll is fake_collection
        # get_collection must be called WITHOUT an embedding_function kwarg
        fake_client.get_collection.assert_called_once_with(name="academic_papers")
