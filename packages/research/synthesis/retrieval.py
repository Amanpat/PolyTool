"""RIS v1 synthesis — combined retrieval helper.

Merges results from multiple planned queries (direct, HyDE-expanded, step-back)
through the existing query_index() RRF spine in packages/polymarket/rag/query.py.

Usage:
    from packages.research.synthesis.retrieval import retrieve_for_research, RetrievalPlan

    # Deterministic multi-angle retrieval (no LLM, no Chroma required for structure)
    plan = retrieve_for_research("crypto pair bot profitability")

    # With HyDE expansion for better recall
    plan = retrieve_for_research("market making spreads", use_hyde=True)

    # With custom query_index parameters (pass-through)
    plan = retrieve_for_research(
        "prediction market strategies",
        query_index_kwargs={"hybrid": True, "k": 12},
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from packages.research.synthesis.query_planner import QueryPlan, plan_queries
from packages.research.synthesis.hyde import HydeResult, expand_hyde


# ---------------------------------------------------------------------------
# Deferred import for query_index to avoid import-time Chroma dependency
# ---------------------------------------------------------------------------


def query_index(**kwargs):
    """Thin wrapper around the real query_index that allows monkeypatching in tests."""
    from packages.polymarket.rag.query import query_index as _qi
    return _qi(**kwargs)


# ---------------------------------------------------------------------------
# RetrievalPlan dataclass
# ---------------------------------------------------------------------------


@dataclass
class RetrievalPlan:
    """Result of combined multi-angle retrieval for a research topic.

    Fields:
        topic: The original research topic.
        query_plan: The QueryPlan produced by the query planner.
        hyde_result: Optional HyDE expansion result (None if use_hyde=False).
        results: Deduplicated, score-sorted list of retrieval result dicts.
            Each dict has keys: chunk_id, score, snippet, file_path, chunk_index,
            doc_id, metadata (matching query_index() output format).
        result_sources: Maps chunk_id -> set of query label strings that found
            this chunk. Useful for provenance tracking and debugging.
    """
    topic: str
    query_plan: QueryPlan
    hyde_result: Optional[HydeResult]
    results: list[dict]
    result_sources: dict[str, set[str]]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_for_research(
    topic: str,
    provider_name: str = "manual",
    use_hyde: bool = False,
    include_step_back: bool = False,
    max_queries: int = 5,
    query_index_kwargs: Optional[dict] = None,
    **provider_kwargs,
) -> RetrievalPlan:
    """Run multi-angle retrieval for a research topic.

    Steps:
    1. Plan queries using plan_queries() (deterministic or LLM-expanded).
    2. Optionally expand first query with HyDE to generate a hypothetical document.
    3. Build sub-queries: planned queries + optional step-back + optional HyDE doc.
    4. Run query_index() for each sub-query; catch all errors (empty result on failure).
    5. Merge results by chunk_id, keeping highest score per chunk (dedup).
    6. Track result_sources: which query labels found each chunk.
    7. Sort merged results by score descending.

    Falls back gracefully: if query_index raises (e.g., no Chroma DB present),
    returns empty results with the QueryPlan still populated.

    Args:
        topic: The research topic to retrieve for.
        provider_name: Provider for query planning and HyDE. Default "manual".
        use_hyde: If True, expand the first planned query with HyDE and include
            the hypothetical document as an additional retrieval query.
        include_step_back: If True, include a step-back query in the planned queries.
        max_queries: Maximum number of primary queries from the planner.
        query_index_kwargs: Optional dict of kwargs to pass through to query_index().
            Supports all query_index params: hybrid, lexical_only, k, embedder, etc.
        **provider_kwargs: Passed to get_provider() for the query planner / HyDE.

    Returns:
        RetrievalPlan with topic, query_plan, hyde_result, results, result_sources.
    """
    qi_kwargs = query_index_kwargs or {}

    # Step 1: Plan queries
    qplan = plan_queries(
        topic,
        provider_name=provider_name,
        include_step_back=include_step_back,
        max_queries=max_queries,
        **provider_kwargs,
    )

    # Step 2: Optional HyDE expansion on first planned query
    hyde: Optional[HydeResult] = None
    if use_hyde:
        hyde_query = qplan.queries[0] if qplan.queries else topic
        hyde = expand_hyde(hyde_query, provider_name=provider_name, **provider_kwargs)

    # Step 3: Build sub-query list with labels
    sub_queries: list[tuple[str, str]] = []  # (query_text, label)
    for i, q in enumerate(qplan.queries):
        sub_queries.append((q, f"plan_q{i}"))
    if include_step_back and qplan.step_back_query:
        sub_queries.append((qplan.step_back_query, "step_back"))
    if hyde is not None:
        sub_queries.append((hyde.hypothetical_document, "hyde"))

    # Step 4 + 5 + 6: Retrieve, merge, track sources
    merged: dict[str, dict] = {}           # chunk_id -> best result dict
    result_sources: dict[str, set[str]] = {}  # chunk_id -> set of labels

    for query_text, label in sub_queries:
        try:
            results = query_index(question=query_text, **qi_kwargs)
        except Exception:
            results = []

        for item in results:
            chunk_id = item.get("chunk_id", "")
            if not chunk_id:
                continue
            # Track source label
            if chunk_id not in result_sources:
                result_sources[chunk_id] = set()
            result_sources[chunk_id].add(label)

            # Keep highest score
            existing = merged.get(chunk_id)
            if existing is None or item.get("score", 0.0) > existing.get("score", 0.0):
                merged[chunk_id] = item

    # Step 7: Sort by score descending
    sorted_results = sorted(merged.values(), key=lambda x: x.get("score", 0.0), reverse=True)

    return RetrievalPlan(
        topic=topic,
        query_plan=qplan,
        hyde_result=hyde,
        results=sorted_results,
        result_sources=result_sources,
    )
