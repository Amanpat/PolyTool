"""Tests for the reranking module (packages/polymarket/rag/reranker.py)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.reranker import BaseReranker, rerank_results


class _FakeReranker(BaseReranker):
    """Deterministic reranker that scores by snippet length."""

    def __init__(self) -> None:
        self.model_name = "fake-reranker"

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        """Score documents by their length (longer = higher score)."""
        return [float(len(doc)) for doc in documents]


def _make_result(snippet: str, file_path: str = "test.txt", chunk_id: str = "abc123") -> dict:
    """Helper to create a result dict for testing."""
    return {
        "file_path": file_path,
        "chunk_id": chunk_id,
        "chunk_index": 0,
        "doc_id": "doc_abc",
        "score": 0.9,
        "snippet": snippet,
        "metadata": {"doc_type": "test"},
    }


class RerankerUnitTests(unittest.TestCase):
    """Unit tests for rerank_results function."""

    def test_rerank_reorders_by_score(self) -> None:
        """Test that reranking reorders results by rerank_score."""
        reranker = _FakeReranker()

        # Create results with different snippet lengths: short, long, medium
        results = [
            _make_result("short", file_path="a.txt", chunk_id="id1"),
            _make_result("this is a much longer snippet for testing", file_path="b.txt", chunk_id="id2"),
            _make_result("medium length", file_path="c.txt", chunk_id="id3"),
        ]

        reranked = rerank_results(results, query="test", reranker=reranker, top_n=10)

        # Should be ordered: longest, medium, shortest
        self.assertEqual(reranked[0]["chunk_id"], "id2")
        self.assertEqual(reranked[1]["chunk_id"], "id3")
        self.assertEqual(reranked[2]["chunk_id"], "id1")

        # Check that rerank_score is present
        self.assertIn("rerank_score", reranked[0])
        self.assertGreater(reranked[0]["rerank_score"], reranked[1]["rerank_score"])
        self.assertGreater(reranked[1]["rerank_score"], reranked[2]["rerank_score"])

    def test_rerank_final_rank_reassigned(self) -> None:
        """Test that final_rank is reassigned after reranking."""
        reranker = _FakeReranker()

        results = [
            _make_result("short", chunk_id="id1"),
            _make_result("this is a much longer snippet", chunk_id="id2"),
            _make_result("medium", chunk_id="id3"),
        ]

        reranked = rerank_results(results, query="test", reranker=reranker, top_n=10)

        # final_rank should be 1, 2, 3 after reordering
        self.assertEqual(reranked[0]["final_rank"], 1)
        self.assertEqual(reranked[1]["final_rank"], 2)
        self.assertEqual(reranked[2]["final_rank"], 3)

    def test_rerank_empty_results(self) -> None:
        """Test that reranking empty list returns empty list."""
        reranker = _FakeReranker()
        reranked = rerank_results([], query="test", reranker=reranker, top_n=10)
        self.assertEqual(reranked, [])

    def test_rerank_top_n_limits_reranking(self) -> None:
        """Test that only top_n results are reranked."""
        reranker = _FakeReranker()

        # Create 5 results with varying lengths
        results = [
            _make_result("a", chunk_id="id1"),
            _make_result("bb", chunk_id="id2"),
            _make_result("ccc", chunk_id="id3"),
            _make_result("dddd", chunk_id="id4"),
            _make_result("eeeee", chunk_id="id5"),
        ]

        # Only rerank top 3
        reranked = rerank_results(results, query="test", reranker=reranker, top_n=3)

        # First 3 should have rerank_score
        self.assertIsNotNone(reranked[0]["rerank_score"])
        self.assertIsNotNone(reranked[1]["rerank_score"])
        self.assertIsNotNone(reranked[2]["rerank_score"])

        # Last 2 should have rerank_score=None
        self.assertIsNone(reranked[3]["rerank_score"])
        self.assertIsNone(reranked[4]["rerank_score"])

        # First 3 should be reordered by length (longest first among top 3)
        # Top 3 were: "a" (1), "bb" (2), "ccc" (3)
        # Reordered: "ccc" (3), "bb" (2), "a" (1)
        self.assertEqual(reranked[0]["chunk_id"], "id3")
        self.assertEqual(reranked[1]["chunk_id"], "id2")
        self.assertEqual(reranked[2]["chunk_id"], "id1")

        # Last 2 remain in original order
        self.assertEqual(reranked[3]["chunk_id"], "id4")
        self.assertEqual(reranked[4]["chunk_id"], "id5")

    def test_rerank_preserves_metadata(self) -> None:
        """Test that all original fields are preserved after reranking."""
        reranker = _FakeReranker()

        results = [
            _make_result("short text", file_path="test1.txt", chunk_id="id1"),
        ]

        reranked = rerank_results(results, query="test", reranker=reranker, top_n=10)

        # Check all original fields are preserved
        self.assertEqual(reranked[0]["file_path"], "test1.txt")
        self.assertEqual(reranked[0]["chunk_id"], "id1")
        self.assertEqual(reranked[0]["chunk_index"], 0)
        self.assertEqual(reranked[0]["doc_id"], "doc_abc")
        self.assertEqual(reranked[0]["score"], 0.9)
        self.assertEqual(reranked[0]["snippet"], "short text")
        self.assertIn("metadata", reranked[0])


class RerankerIntegrationWithQueryTests(unittest.TestCase):
    """Integration tests for reranker with query_index."""

    def test_query_index_with_reranker(self) -> None:
        """Test that query_index applies reranking when reranker is provided."""
        from polymarket.rag.query import query_index

        # Mock _run_vector_query to return stubbed results
        stub_results = [
            _make_result("short", chunk_id="id1"),
            _make_result("this is a much longer snippet", chunk_id="id2"),
            _make_result("medium", chunk_id="id3"),
        ]

        with patch("polymarket.rag.query._run_vector_query", return_value=stub_results):
            from polymarket.rag.embedder import BaseEmbedder
            import numpy as np

            class _FakeEmbedder(BaseEmbedder):
                model_name = "fake"
                dimension = 4

                def embed_texts(self, texts):
                    return np.array([[1, 2, 3, 4]] * len(list(texts)), dtype="float32")

            results = query_index(
                question="test",
                embedder=_FakeEmbedder(),
                k=3,
                reranker=_FakeReranker(),
                private_only=False,
            )

            # Results should be reordered by length (longest first)
            self.assertEqual(len(results), 3)
            self.assertIn("rerank_score", results[0])
            self.assertEqual(results[0]["chunk_id"], "id2")  # longest
            self.assertEqual(results[1]["chunk_id"], "id3")  # medium
            self.assertEqual(results[2]["chunk_id"], "id1")  # shortest

    def test_query_index_without_reranker_unchanged(self) -> None:
        """Test that query_index without reranker does not add rerank_score."""
        from polymarket.rag.query import query_index

        stub_results = [
            _make_result("short", chunk_id="id1"),
            _make_result("long snippet", chunk_id="id2"),
        ]

        with patch("polymarket.rag.query._run_vector_query", return_value=stub_results):
            from polymarket.rag.embedder import BaseEmbedder
            import numpy as np

            class _FakeEmbedder(BaseEmbedder):
                model_name = "fake"
                dimension = 4

                def embed_texts(self, texts):
                    return np.array([[1, 2, 3, 4]] * len(list(texts)), dtype="float32")

            results = query_index(
                question="test",
                embedder=_FakeEmbedder(),
                k=2,
                reranker=None,  # No reranker
                private_only=False,
            )

            # Results should NOT have rerank_score
            self.assertNotIn("rerank_score", results[0])
            self.assertNotIn("rerank_score", results[1])

            # Order should be unchanged (as returned by stub)
            self.assertEqual(results[0]["chunk_id"], "id1")
            self.assertEqual(results[1]["chunk_id"], "id2")


if __name__ == "__main__":
    unittest.main()
