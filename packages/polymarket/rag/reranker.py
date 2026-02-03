"""Reranking interfaces and CrossEncoder implementation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class BaseReranker:
    """Simple reranker interface for scoring query-document pairs."""

    model_name: str

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        raise NotImplementedError


class CrossEncoderReranker(BaseReranker):
    """Cross-encoder reranker for local RAG reranking."""

    def __init__(
        self,
        model_name: str = DEFAULT_RERANK_MODEL,
        device: str = "auto",
        cache_folder: str = "kb/rag/models",
    ) -> None:
        try:
            import torch
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers (and torch) are required. Install requirements-rag.txt."
            ) from exc

        self.model_name = model_name
        resolved_device = device
        if device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = resolved_device

        # Resolve cache folder to absolute path
        cache_path = Path(cache_folder)
        if not cache_path.is_absolute():
            cache_path = (Path.cwd() / cache_path).resolve()

        # CrossEncoder doesn't accept cache_folder parameter directly.
        # Instead, set the SENTENCE_TRANSFORMERS_HOME environment variable.
        old_cache_home = os.environ.get("SENTENCE_TRANSFORMERS_HOME")
        try:
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(cache_path)
            self.model = CrossEncoder(model_name, device=resolved_device)
        finally:
            # Restore the original environment variable
            if old_cache_home is not None:
                os.environ["SENTENCE_TRANSFORMERS_HOME"] = old_cache_home
            else:
                os.environ.pop("SENTENCE_TRANSFORMERS_HOME", None)

    def score_pairs(self, query: str, documents: list[str]) -> list[float]:
        """Score query-document pairs using the cross-encoder model.

        Args:
            query: The query string
            documents: List of document strings to score against the query

        Returns:
            List of float scores, one per document
        """
        if not documents:
            return []

        # Build query-document pairs
        pairs = [(query, doc) for doc in documents]

        # Get predictions from the model
        scores = self.model.predict(pairs)

        # Convert to list of floats
        return [float(score) for score in scores]


def rerank_results(
    results: list[dict],
    query: str,
    reranker: BaseReranker,
    top_n: int = 50,
) -> list[dict]:
    """Rerank search results using a cross-encoder model.

    Args:
        results: List of search result dicts (from query_index)
        query: The original query string
        reranker: The reranker instance to use
        top_n: Number of top results to rerank (default 50)

    Returns:
        Reranked list of results with rerank_score added and final_rank updated
    """
    if not results:
        return []

    # Determine how many results to rerank
    num_to_rerank = min(len(results), top_n)
    candidates = results[:num_to_rerank]
    remaining = results[num_to_rerank:]

    # Extract snippets for reranking
    documents = [r["snippet"] for r in candidates]

    # Get rerank scores
    scores = reranker.score_pairs(query, documents)

    # Add rerank_score to each candidate
    for i, candidate in enumerate(candidates):
        candidate["rerank_score"] = scores[i]

    # Sort by rerank_score descending
    candidates.sort(key=lambda r: r["rerank_score"], reverse=True)

    # Re-assign final_rank (1-based sequential)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["final_rank"] = rank

    # Add remaining results with rerank_score=None
    for i, result in enumerate(remaining, start=len(candidates) + 1):
        result["rerank_score"] = None
        result["final_rank"] = i

    return candidates + remaining
