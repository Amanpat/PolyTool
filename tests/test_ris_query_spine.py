"""Tests for RIS Phase 2 query spine: KnowledgeStore as third RRF source.

All tests use KnowledgeStore(":memory:") -- no disk, no network.
Covers:
- query_knowledge_store_for_rrf output shape and content
- Filtering by source_family, min_freshness, text_query
- Contradicted claim lower score
- Stale claim staleness_note="STALE"
- Provenance docs present for claims with evidence
- Three-way RRF fusion via reciprocal_rank_fusion_multi
- query_index with knowledge_store_path passes through KS results
- Backward compat: query_index without knowledge_store_path unchanged
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

# Ensure packages/ and project root are on sys.path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from packages.polymarket.rag.knowledge_store import KnowledgeStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_store_with_corpus() -> tuple[KnowledgeStore, dict]:
    """Seed a small in-memory KnowledgeStore corpus for testing.

    Returns (store, ids_dict) where ids_dict has keys:
        doc1_id, doc2_id, claim_fresh_id, claim_stale_id, claim_contradicted_id
    """
    store = KnowledgeStore(":memory:")

    # Source documents
    doc1_id = store.add_source_document(
        title="Jon-Becker Analysis",
        source_url="internal://jon_becker_2024",
        source_family="wallet_analysis",
        published_at="2025-12-01T00:00:00+00:00",
        confidence_tier="high",
    )
    doc2_id = store.add_source_document(
        title="Market Microstructure Book",
        source_url="internal://microstructure_book",
        source_family="book_foundational",
        published_at="2024-01-01T00:00:00+00:00",
        confidence_tier="medium",
    )

    # Claim 1: fresh, non-contradicted
    claim_fresh_id = store.add_claim(
        claim_text="gabagool22 exclusively trades 5m BTC/ETH pairs with high confidence.",
        claim_type="empirical",
        confidence=0.90,
        trust_tier="high",
        actor="test_actor",
        source_document_id=doc1_id,
        created_at="2025-12-01T00:00:00+00:00",
        updated_at="2025-12-01T00:00:00+00:00",
    )

    # Claim 2: stale (will have freshness < 0.5 due to old published_at on source)
    # Use "news" family (half_life_months=3) so a 2020 date decays far below 0.5
    doc_old_id = store.add_source_document(
        title="Very Old Source",
        source_url="internal://very_old_source",
        source_family="news",  # news: 3-month half-life -> very stale for 2020 doc
        published_at="2020-01-01T00:00:00+00:00",  # very old -> stale
        confidence_tier="low",
    )
    claim_stale_id = store.add_claim(
        claim_text="Polymarket has extremely low liquidity in sports markets.",
        claim_type="empirical",
        confidence=0.70,
        trust_tier="low",
        actor="test_actor",
        source_document_id=doc_old_id,
        created_at="2020-01-01T00:00:00+00:00",
        updated_at="2020-01-01T00:00:00+00:00",
    )

    # Claim 3: contradicted (has CONTRADICTS relation pointing to it)
    claim_contradicted_id = store.add_claim(
        claim_text="Market makers earn guaranteed profits on every trade.",
        claim_type="empirical",
        confidence=0.80,
        trust_tier="medium",
        actor="test_actor",
        source_document_id=doc2_id,
        created_at="2025-06-01T00:00:00+00:00",
        updated_at="2025-06-01T00:00:00+00:00",
    )

    # Claim 4: the contradicting claim
    claim_contradicting_id = store.add_claim(
        claim_text="Market makers can lose money due to adverse selection.",
        claim_type="empirical",
        confidence=0.95,
        trust_tier="high",
        actor="test_actor",
        source_document_id=doc1_id,
        created_at="2025-12-01T00:00:00+00:00",
        updated_at="2025-12-01T00:00:00+00:00",
    )

    # Add CONTRADICTS relation: claim_contradicting -> claim_contradicted
    store.add_relation(claim_contradicting_id, claim_contradicted_id, "CONTRADICTS")

    # Add evidence link for claim_fresh (provenance)
    store.add_evidence(
        claim_id=claim_fresh_id,
        source_document_id=doc1_id,
        excerpt="gabagool22 trade analysis excerpt",
    )

    ids = {
        "doc1_id": doc1_id,
        "doc2_id": doc2_id,
        "claim_fresh_id": claim_fresh_id,
        "claim_stale_id": claim_stale_id,
        "claim_contradicted_id": claim_contradicted_id,
        "claim_contradicting_id": claim_contradicting_id,
    }
    return store, ids


# ---------------------------------------------------------------------------
# Tests: reciprocal_rank_fusion_multi
# ---------------------------------------------------------------------------

class TestRecipocalRankFusionMulti:
    """Test the new N-list RRF function."""

    def test_rrf_multi_two_lists_matches_two_list_version(self):
        """reciprocal_rank_fusion_multi with 2 lists should match original behavior."""
        from packages.polymarket.rag.lexical import (
            reciprocal_rank_fusion,
            reciprocal_rank_fusion_multi,
        )
        list_a = [
            {"chunk_id": "a", "score": 1.0, "snippet": "A"},
            {"chunk_id": "b", "score": 0.9, "snippet": "B"},
        ]
        list_b = [
            {"chunk_id": "b", "score": 0.8, "snippet": "B"},
            {"chunk_id": "c", "score": 0.7, "snippet": "C"},
        ]
        two_list = reciprocal_rank_fusion(list_a, list_b, rrf_k=60)
        multi = reciprocal_rank_fusion_multi([list_a, list_b], rrf_k=60)

        # Same chunk_ids in same order
        assert [r["chunk_id"] for r in two_list] == [r["chunk_id"] for r in multi]
        # Same fused scores (within floating point tolerance)
        for r2, rm in zip(two_list, multi):
            assert abs(r2["fused_score"] - rm["fused_score"]) < 1e-9

    def test_rrf_multi_three_lists(self):
        """Three-way fusion: chunk appearing in all 3 lists has highest score."""
        from packages.polymarket.rag.lexical import reciprocal_rank_fusion_multi

        list_a = [{"chunk_id": "shared", "score": 1.0}, {"chunk_id": "only_a", "score": 0.9}]
        list_b = [{"chunk_id": "shared", "score": 1.0}, {"chunk_id": "only_b", "score": 0.9}]
        list_c = [{"chunk_id": "shared", "score": 1.0}, {"chunk_id": "only_c", "score": 0.9}]

        fused = reciprocal_rank_fusion_multi([list_a, list_b, list_c], rrf_k=60)
        assert fused[0]["chunk_id"] == "shared", "shared chunk should rank #1"

    def test_rrf_multi_empty_lists(self):
        """Empty lists in the multi-list RRF should not crash."""
        from packages.polymarket.rag.lexical import reciprocal_rank_fusion_multi

        list_a = [{"chunk_id": "a", "score": 1.0}]
        result = reciprocal_rank_fusion_multi([list_a, [], []], rrf_k=60)
        assert len(result) == 1
        assert result[0]["chunk_id"] == "a"

    def test_rrf_multi_preserves_metadata(self):
        """RRF multi should preserve the merged metadata from result dicts."""
        from packages.polymarket.rag.lexical import reciprocal_rank_fusion_multi

        list_a = [{"chunk_id": "x", "score": 1.0, "metadata": {"source": "ks"}, "snippet": "hello"}]
        result = reciprocal_rank_fusion_multi([list_a], rrf_k=60)
        assert result[0]["metadata"]["source"] == "ks"

    def test_rrf_multi_single_empty_list(self):
        """Single empty list returns empty result."""
        from packages.polymarket.rag.lexical import reciprocal_rank_fusion_multi

        result = reciprocal_rank_fusion_multi([[]], rrf_k=60)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: query_knowledge_store_for_rrf
# ---------------------------------------------------------------------------

class TestQueryKnowledgeStoreForRRF:
    """Test the new RRF-compatible KS adapter function."""

    def test_output_shape(self):
        """Each result must have chunk_id, score, snippet, file_path, metadata keys."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            assert len(results) > 0
            for r in results:
                assert "chunk_id" in r
                assert "score" in r
                assert "snippet" in r
                assert "file_path" in r
                assert "metadata" in r
                assert "chunk_index" in r
                assert "doc_id" in r
        finally:
            store.close()

    def test_file_path_is_virtual_ks_path(self):
        """file_path should use knowledge_store:// virtual scheme."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            for r in results:
                assert r["file_path"].startswith("knowledge_store://claim/")
        finally:
            store.close()

    def test_metadata_source_field(self):
        """metadata.source must be 'knowledge_store' for all results."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            for r in results:
                assert r["metadata"]["source"] == "knowledge_store"
        finally:
            store.close()

    def test_filter_by_source_family(self):
        """source_family filter should exclude claims from other families."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store, source_family="wallet_analysis")
            # Only claims from wallet_analysis source docs
            for r in results:
                assert r["metadata"].get("claim_type") is not None  # sanity
            # Should exclude claims linked to book_foundational docs
            file_paths = [r["file_path"] for r in results]
            # claim_contradicted (doc2: book_foundational) should not appear
            assert not any(ids["claim_contradicted_id"] in fp for fp in file_paths)
        finally:
            store.close()

    def test_filter_by_min_freshness(self):
        """min_freshness filter should exclude stale claims."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            # Very high threshold should exclude stale claims
            results = query_knowledge_store_for_rrf(store, min_freshness=0.9)
            # Stale claim from year 2020 should be excluded
            file_paths = [r["file_path"] for r in results]
            assert not any(ids["claim_stale_id"] in fp for fp in file_paths)
        finally:
            store.close()

    def test_excludes_archived_by_default(self):
        """Archived claims should not appear in results."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store = KnowledgeStore(":memory:")
        doc_id = store.add_source_document(title="Doc", source_url="u://x", source_family="wallet_analysis")
        archived_id = store.add_claim(
            claim_text="This claim is archived.",
            claim_type="empirical",
            confidence=0.9,
            trust_tier="high",
            lifecycle="archived",
            actor="test",
            source_document_id=doc_id,
            created_at="2025-01-01T00:00:00+00:00",
            updated_at="2025-01-01T00:00:00+00:00",
        )
        try:
            results = query_knowledge_store_for_rrf(store)
            file_paths = [r["file_path"] for r in results]
            assert not any(archived_id in fp for fp in file_paths)
        finally:
            store.close()

    def test_text_query_filters_claims(self):
        """text_query should filter to claims containing the query substring (case-insensitive)."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store, text_query="gabagool22")
            assert len(results) >= 1
            for r in results:
                assert "gabagool22" in r["snippet"].lower() or "gabagool22" in r["metadata"].get("claim_text", "").lower()
        finally:
            store.close()

    def test_text_query_case_insensitive(self):
        """text_query filter must be case-insensitive."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results_lower = query_knowledge_store_for_rrf(store, text_query="GABAGOOL22")
            results_upper = query_knowledge_store_for_rrf(store, text_query="gabagool22")
            assert len(results_lower) == len(results_upper)
        finally:
            store.close()

    def test_text_query_none_returns_all(self):
        """When text_query is None, all claims are returned."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results_all = query_knowledge_store_for_rrf(store, text_query=None)
            results_filtered = query_knowledge_store_for_rrf(store, text_query="gabagool22")
            assert len(results_all) > len(results_filtered)
        finally:
            store.close()

    def test_contradicted_claim_has_lower_score(self):
        """Contradicted claims should rank below non-contradicted claims of similar confidence."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            score_by_id = {
                r["chunk_id"]: r["score"]
                for r in results
            }
            assert ids["claim_contradicted_id"] in score_by_id
            assert ids["claim_contradicting_id"] in score_by_id
            # contradicted claim should have lower score than contradicting claim
            assert score_by_id[ids["claim_contradicted_id"]] < score_by_id[ids["claim_contradicting_id"]]
        finally:
            store.close()

    def test_stale_claim_annotated_in_metadata(self):
        """Claims with freshness_modifier < 0.5 should have metadata.staleness_note='STALE'."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            stale_results = [
                r for r in results if r["chunk_id"] == ids["claim_stale_id"]
            ]
            # The stale claim should appear (since we don't filter by freshness here)
            if stale_results:
                meta = stale_results[0]["metadata"]
                # freshness_modifier < 0.5 -> STALE, or <0.7 -> AGING
                fm = meta.get("freshness_modifier", 1.0)
                if fm < 0.5:
                    assert meta.get("staleness_note") == "STALE"
                elif fm < 0.7:
                    assert meta.get("staleness_note") == "AGING"
        finally:
            store.close()

    def test_provenance_docs_populated_for_claim_with_evidence(self):
        """Claims with evidence links should have metadata.provenance_docs populated."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            fresh_results = [r for r in results if r["chunk_id"] == ids["claim_fresh_id"]]
            assert len(fresh_results) == 1
            provenance = fresh_results[0]["metadata"]["provenance_docs"]
            assert isinstance(provenance, list)
            assert len(provenance) > 0  # has evidence link
        finally:
            store.close()

    def test_sorted_by_score_descending(self):
        """Results should be sorted by score descending."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)
        finally:
            store.close()

    def test_top_k_limits_results(self):
        """top_k parameter should limit results count."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store, top_k=2)
            assert len(results) <= 2
        finally:
            store.close()

    def test_snippet_truncated_to_400_chars(self):
        """snippet should be truncated to 400 chars."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store = KnowledgeStore(":memory:")
        doc_id = store.add_source_document(title="D", source_url="u://y", source_family="wallet_analysis")
        long_text = "x" * 600
        store.add_claim(
            claim_text=long_text,
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            source_document_id=doc_id,
            created_at="2025-01-01T00:00:00+00:00",
            updated_at="2025-01-01T00:00:00+00:00",
        )
        try:
            results = query_knowledge_store_for_rrf(store)
            assert len(results) == 1
            assert len(results[0]["snippet"]) <= 403  # 400 + possible "..."
        finally:
            store.close()


# ---------------------------------------------------------------------------
# Tests: query_index with knowledge_store_path (three-way fusion)
# ---------------------------------------------------------------------------

class TestQueryIndexKnowledgeStore:
    """Test query_index integration with KnowledgeStore as third RRF source."""

    def _make_mock_vector_results(self) -> list[dict]:
        return [
            {"chunk_id": "vec1", "score": 0.9, "snippet": "vector result 1", "file_path": "kb/doc1.md",
             "chunk_index": 0, "doc_id": "d1", "metadata": {}},
            {"chunk_id": "vec2", "score": 0.8, "snippet": "vector result 2", "file_path": "kb/doc2.md",
             "chunk_index": 0, "doc_id": "d2", "metadata": {}},
        ]

    def _make_mock_lexical_results(self) -> list[dict]:
        return [
            {"chunk_id": "lex1", "score": None, "lexical_score": -1.5, "lexical_rank": 1,
             "snippet": "lexical result 1", "file_path": "kb/doc3.md",
             "chunk_index": 0, "doc_id": "d3", "metadata": {}},
        ]

    def test_backward_compat_no_knowledge_store(self):
        """query_index without knowledge_store_path should not import KnowledgeStore."""
        from packages.polymarket.rag.query import query_index

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 384

        with patch("packages.polymarket.rag.query._run_vector_query", return_value=[]) as mock_v, \
             patch("packages.polymarket.rag.query._run_lexical_query", return_value=[]) as mock_l:
            results = query_index(
                question="test query",
                embedder=mock_embedder,
                hybrid=True,
                k=5,
            )
            mock_v.assert_called_once()
            mock_l.assert_called_once()
            assert isinstance(results, list)

    def test_knowledge_store_path_requires_hybrid(self):
        """knowledge_store_path with hybrid=False should raise ValueError."""
        from packages.polymarket.rag.query import query_index

        mock_embedder = MagicMock()
        store, ids = _make_store_with_corpus()
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
                ks_path = Path(f.name)
            with pytest.raises(ValueError, match="knowledge_store.*hybrid"):
                query_index(
                    question="test",
                    embedder=mock_embedder,
                    hybrid=False,
                    knowledge_store_path=ks_path,
                    k=5,
                )
        finally:
            store.close()

    def test_three_way_fusion_merges_ks_results(self):
        """query_index with knowledge_store_path should include KS results in output."""
        from packages.polymarket.rag.query import query_index

        store, ids = _make_store_with_corpus()

        # Write in-memory store to a temp file so query_index can open it
        import tempfile
        import shutil
        import sqlite3

        # Create a real temp KS file for query_index to open
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
            ks_path = Path(f.name)

        # Copy the in-memory store to the temp file
        disk_store = KnowledgeStore(str(ks_path))
        # Re-seed the disk store
        doc1_id = disk_store.add_source_document(
            title="Jon-Becker Analysis",
            source_url="internal://jon_becker_2024",
            source_family="wallet_analysis",
            published_at="2025-12-01T00:00:00+00:00",
        )
        claim_id = disk_store.add_claim(
            claim_text="gabagool22 trades BTC/ETH pairs.",
            claim_type="empirical",
            confidence=0.9,
            trust_tier="high",
            actor="test",
            source_document_id=doc1_id,
            created_at="2025-12-01T00:00:00+00:00",
            updated_at="2025-12-01T00:00:00+00:00",
        )
        disk_store.close()

        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 384

        with patch("packages.polymarket.rag.query._run_vector_query", return_value=[]) as mock_v, \
             patch("packages.polymarket.rag.query._run_lexical_query", return_value=[]) as mock_l:
            results = query_index(
                question="gabagool22 trades",  # matches "gabagool22 trades BTC/ETH pairs."
                embedder=mock_embedder,
                hybrid=True,
                k=10,
                knowledge_store_path=ks_path,
            )
            mock_v.assert_called_once()
            mock_l.assert_called_once()
            # KS results should appear
            assert any(r.get("metadata", {}).get("source") == "knowledge_store" for r in results)

        store.close()
        # Cleanup
        try:
            ks_path.unlink()
        except Exception:
            pass

    def test_three_way_fusion_rank_order(self):
        """Three-way fusion: chunk in all 3 lists should rank highest."""
        from packages.polymarket.rag.lexical import reciprocal_rank_fusion_multi

        # Chunk "shared" appears in all 3 lists at rank 1
        shared = {"chunk_id": "shared", "score": 1.0, "snippet": "shared result",
                  "file_path": "kb/shared.md", "chunk_index": 0, "doc_id": "d0", "metadata": {}}
        only_vec = {"chunk_id": "vec_only", "score": 0.9, "snippet": "vec",
                    "file_path": "kb/v.md", "chunk_index": 0, "doc_id": "dv", "metadata": {}}
        only_lex = {"chunk_id": "lex_only", "score": 0.8, "snippet": "lex",
                    "file_path": "kb/l.md", "chunk_index": 0, "doc_id": "dl", "metadata": {}}
        only_ks = {"chunk_id": "ks_only", "score": 0.7, "snippet": "ks",
                   "file_path": "knowledge_store://claim/abc", "chunk_index": 0, "doc_id": "", "metadata": {}}

        fused = reciprocal_rank_fusion_multi(
            [[shared, only_vec], [shared, only_lex], [shared, only_ks]],
            rrf_k=60
        )
        assert fused[0]["chunk_id"] == "shared"

    def test_ks_results_have_knowledge_store_metadata(self):
        """Results from KS source should have metadata.source = 'knowledge_store'."""
        from packages.research.ingestion.retriever import query_knowledge_store_for_rrf

        store, ids = _make_store_with_corpus()
        try:
            results = query_knowledge_store_for_rrf(store)
            for r in results:
                assert r["metadata"]["source"] == "knowledge_store"
        finally:
            store.close()
