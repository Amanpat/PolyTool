"""L2 Academic RAG Query — Marker-only corpus query with multi-angle retrieval.

PaperQA2-inspired agentic control flow (Apache-2.0, future-house/paper-qa)
implemented over the existing KnowledgeStore + query_planner stack.

Algorithm (adapted from PaperQA2):
1. Plan multi-angle queries from the question (deterministic or LLM-expanded)
2. Query KnowledgeStore with source_family="academic" for each planned query
3. Merge results by claim_id, keeping best effective_score per claim
4. Group claims by source_document (paper-level aggregation)
5. For each paper, attach citation metadata (title, arxiv_id, source_url, body_source)
6. Return AcademicQueryResult with ranked citations
7. Graceful fallback: had_fallback=True + actionable warning when KS empty

Scope guards (from Work-Packet - PaperQA2 RAG Control Flow.md):
- Only queries KnowledgeStore with source_family="academic"
  (Marker-gate enforced at ingest time by IngestPipeline.ingest_external)
- Does NOT query ChromaDB vector index in this version
  (body_source not stored in Chroma metadata; future L2.1 can add that path)
- Does NOT change the corpus ingestion path
- Embeddings and LLM synthesis are optional (provider_name="manual" by default)
- Existing rag-query command is unchanged
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.ingestion.retriever import query_knowledge_store_for_rrf
from packages.research.synthesis.query_planner import plan_queries

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AcademicCitation:
    """A single citation from the academic corpus.

    Maps to a source_document (paper) in the KnowledgeStore. Confirmed
    Marker-quality: all academic docs pass IngestPipeline's body_source=marker gate.
    """
    title: str
    arxiv_id: Optional[str]
    source_url: Optional[str]
    best_snippet: str
    paper_score: float
    body_source: str   # "marker" for canonical corpus; "unknown" if metadata missing
    claim_count: int   # how many claims from this paper matched the query


@dataclass
class AcademicQueryResult:
    """Result of an academic corpus query."""
    question: str
    citations: list[AcademicCitation]
    marker_only_count: int     # papers with body_source=marker
    total_claims_found: int    # raw claim hits before paper-level grouping
    had_fallback: bool         # True when no academic docs found in KS
    warning: Optional[str]
    query_angles: list[str]    # which query angles were actually executed


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_arxiv_id(metadata_json: Optional[str]) -> Optional[str]:
    """Return arxiv_id from a metadata_json string, or None."""
    if not metadata_json:
        return None
    try:
        meta = json.loads(metadata_json)
        canonical_ids = meta.get("canonical_ids", {})
        if isinstance(canonical_ids, dict):
            aid = canonical_ids.get("arxiv_id")
            return str(aid) if aid else None
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_body_source(metadata_json: Optional[str]) -> str:
    """Return body_source from metadata_json, defaulting to 'unknown'."""
    if not metadata_json:
        return "unknown"
    try:
        meta = json.loads(metadata_json)
        return str(meta.get("body_source", "unknown"))
    except (json.JSONDecodeError, TypeError):
        return "unknown"


def _build_sub_queries(question: str, max_angles: int, include_step_back: bool) -> list[tuple[str, str]]:
    """Build (query_text, label) pairs for multi-angle retrieval.

    Uses plan_queries() for deterministic angle generation. Deduplicates
    against the primary question to avoid redundant KS calls.
    """
    sub_queries: list[tuple[str, str]] = [(question, "primary")]

    if max_angles <= 1:
        return sub_queries

    qplan = plan_queries(
        question,
        provider_name="manual",
        include_step_back=include_step_back,
        max_queries=max_angles,
    )

    seen: set[str] = {question}
    for i, q in enumerate(qplan.queries[:max_angles]):
        if q and q not in seen:
            sub_queries.append((q, f"angle_{i}"))
            seen.add(q)

    if include_step_back and qplan.step_back_query and qplan.step_back_query not in seen:
        sub_queries.append((qplan.step_back_query, "step_back"))

    return sub_queries


def _merge_claims(
    raw_results: list[dict],
) -> dict[str, dict]:
    """Merge claim results by chunk_id, keeping best score per claim."""
    merged: dict[str, dict] = {}
    for item in raw_results:
        cid = item.get("chunk_id", "")
        if not cid:
            continue
        existing = merged.get(cid)
        if existing is None or item.get("score", 0.0) > existing.get("score", 0.0):
            merged[cid] = item
    return merged


def _group_by_paper(
    merged_claims: dict[str, dict],
) -> dict[str, list[dict]]:
    """Group merged claims by doc_id (paper). Returns doc_id -> [claim, ...]."""
    by_paper: dict[str, list[dict]] = {}
    for item in merged_claims.values():
        doc_id = item.get("doc_id", "") or ""
        if doc_id not in by_paper:
            by_paper[doc_id] = []
        by_paper[doc_id].append(item)
    return by_paper


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def query_academic_corpus(
    question: str,
    *,
    ks_path: Optional[Path] = None,
    k: int = 8,
    max_query_angles: int = 3,
    include_step_back: bool = False,
    _store: Optional[KnowledgeStore] = None,   # injectable for testing
) -> AcademicQueryResult:
    """Query the academic corpus (KnowledgeStore, source_family='academic').

    Uses multi-angle query planning (PaperQA2-inspired paper-level search).
    Only returns results from Marker-quality ingests — enforced at ingest time
    by IngestPipeline.ingest_external's academic gate.

    Graceful fallback: returns had_fallback=True when the KS has no academic
    documents, with an actionable warning.

    Parameters
    ----------
    question:
        Research question to answer.
    ks_path:
        Path to KnowledgeStore SQLite. Defaults to DEFAULT_KNOWLEDGE_DB_PATH.
    k:
        Maximum number of paper-level citations to return.
    max_query_angles:
        Number of query angles for multi-angle retrieval (1 = primary only).
    include_step_back:
        If True, include a broader step-back query angle.
    _store:
        Test injection: if provided, use this KS instance instead of ks_path.
    """
    from packages.polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH

    # Step 1: Resolve KS
    if _store is not None:
        ks = _store
        _owns_ks = False
    else:
        resolved = ks_path or DEFAULT_KNOWLEDGE_DB_PATH
        ks = KnowledgeStore(resolved)
        _owns_ks = True

    # Step 2: Build multi-angle queries
    sub_queries = _build_sub_queries(question, max_query_angles, include_step_back)
    query_angles = [q for q, _ in sub_queries]

    # Step 3: Query KS for each angle, merge by claim_id
    all_raw: list[dict] = []
    try:
        for query_text, _label in sub_queries:
            try:
                results = query_knowledge_store_for_rrf(
                    ks,
                    text_query=query_text,
                    source_family="academic",
                    top_k=k * 4,
                )
            except Exception:
                results = []
            all_raw.extend(results)
    finally:
        if _owns_ks:
            ks.close()

    total_claims_found = len(all_raw)
    merged = _merge_claims(all_raw)

    # Step 4: Check fallback condition
    if not merged:
        return AcademicQueryResult(
            question=question,
            citations=[],
            marker_only_count=0,
            total_claims_found=0,
            had_fallback=True,
            warning=(
                "No academic documents found in the KnowledgeStore. "
                "To add papers: python -m polytool research-marker-queue enqueue --url ARXIV_ID"
            ),
            query_angles=query_angles,
        )

    # Step 5: Group by paper, rank by max claim score
    by_paper = _group_by_paper(merged)
    paper_scores: list[tuple[str, float, list[dict]]] = []
    for doc_id, claims in by_paper.items():
        best_score = max(c.get("score", 0.0) for c in claims)
        paper_scores.append((doc_id, best_score, claims))
    paper_scores.sort(key=lambda x: x[1], reverse=True)

    # Step 6: Attach citation metadata, take top-k papers
    if _store is not None:
        ks2 = _store
        _owns_ks2 = False
    else:
        resolved2 = ks_path or DEFAULT_KNOWLEDGE_DB_PATH
        ks2 = KnowledgeStore(resolved2)
        _owns_ks2 = True

    citations: list[AcademicCitation] = []
    marker_only_count = 0

    try:
        for doc_id, best_score, claims in paper_scores[:k]:
            title = "(unknown)"
            source_url: Optional[str] = None
            arxiv_id: Optional[str] = None
            body_source = "unknown"

            if doc_id:
                src_doc = ks2.get_source_document(doc_id)
                if src_doc:
                    title = src_doc.get("title") or "(unknown)"
                    source_url = src_doc.get("source_url")
                    metadata_json = src_doc.get("metadata_json")
                    arxiv_id = _extract_arxiv_id(metadata_json)
                    body_source = _extract_body_source(metadata_json)

            if body_source == "marker":
                marker_only_count += 1

            # Best snippet from highest-scoring claim for this paper
            best_claim = max(claims, key=lambda c: c.get("score", 0.0))
            snippet = best_claim.get("snippet", "")

            citations.append(AcademicCitation(
                title=title,
                arxiv_id=arxiv_id,
                source_url=source_url,
                best_snippet=snippet,
                paper_score=best_score,
                body_source=body_source,
                claim_count=len(claims),
            ))
    finally:
        if _owns_ks2:
            ks2.close()

    return AcademicQueryResult(
        question=question,
        citations=citations,
        marker_only_count=marker_only_count,
        total_claims_found=total_claims_found,
        had_fallback=False,
        warning=None,
        query_angles=query_angles,
    )
