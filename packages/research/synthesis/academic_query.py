"""L2 Academic RAG Query — Marker-only corpus query with multi-angle retrieval.

PaperQA2-inspired agentic control flow (Apache-2.0, future-house/paper-qa)
implemented over the existing KnowledgeStore + query_planner stack.

Algorithm (adapted from PaperQA2):
1. Plan multi-angle queries from the question (deterministic or LLM-expanded)
2. Try semantic retrieval via ChromaDB academic_papers collection (L2.1 path):
   - If Chroma returns hits, resolve ks_doc_id back to KS source documents,
     filter to Marker-ready metadata, return semantic citations directly.
   - If Chroma is unavailable or returns no hits, fall through to lexical.
3. Lexical retrieval: Query KnowledgeStore with source_family="academic" for
   each planned query angle; merge by claim_id, keeping best effective_score.
4. Filter papers to Marker/RAG-ready metadata (body_source=marker, length >= 5000)
5. Group claims by source_document (paper-level aggregation)
6. For each paper, attach citation metadata (title, arxiv_id, source_url, body_source)
7. Return AcademicQueryResult with ranked citations and retrieval_mode

Scope guards:
- Only queries KnowledgeStore with source_family="academic" and defensively
  re-checks Marker-ready metadata at query time for legacy/bad KS rows
- Chroma semantic path requires the academic_papers collection populated by
  research-marker-queue index-done --reindex-chroma (Deliverable A)
- Does NOT change the corpus ingestion path
- Embeddings and LLM synthesis are optional (provider_name="manual" by default)
- Existing rag-query command is unchanged
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.ingestion.retriever import query_knowledge_store_for_rrf
from packages.research.synthesis.query_planner import plan_queries

_MIN_MARKER_BODY_LENGTH = 5000

# ---------------------------------------------------------------------------
# Snippet sanitation — display-only, stored claim_text is never modified
# ---------------------------------------------------------------------------

# Whitelist of known Marker HTML tags (not a general <[^>]+> to avoid stripping
# math inequality signs like a < b or LaTeX expressions).
_KNOWN_MARKER_TAGS = re.compile(
    r"</?(?:sup|sub|br|a|span)(?:\s[^>]*)?/?>",
    re.IGNORECASE,
)
# Marker internal cross-reference anchors: (#page-N-M)
_PAGE_REF = re.compile(r"\(#page-\d+-\d+\)")
# Orphaned page-anchor prefix produced by claim_text[:400] mid-pattern truncation.
# Matches "(#pag..." at end of string when the closing ")" was cut off.
_PAGE_REF_ORPHAN = re.compile(r"\(#pag[^\)]*$")
# Markdown heading markers at line start OR inline after whitespace.
# The inline variant catches Marker OCR artifacts like " #### **Abstract** "
# embedded in the middle of a snippet (not at a line boundary).
_MD_HEADING = re.compile(r"(?m)(?:^#{1,6}[ \t]*|(?<=\s)#{1,6}[ \t]+)")
# Three or more consecutive newlines collapsed to two
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
# Three or more consecutive spaces/tabs collapsed to one
_EXCESS_SPACES = re.compile(r"[ \t]{3,}")


def _sanitize_snippet(text: str) -> str:
    """Strip Marker/markdown OCR artifacts from operator-facing snippets.

    Display-only: stored claim_text in KnowledgeStore is never mutated.
    Strips known Marker HTML tags (sup, sub, br, a), Marker page cross-reference
    anchors (#page-N-M), orphaned partial anchors at truncation boundaries,
    markdown heading markers (line-start and inline), and excessive whitespace.
    Math expressions using bare < or > are preserved because only named Marker
    tag patterns are targeted.
    """
    text = _KNOWN_MARKER_TAGS.sub("", text)
    text = _PAGE_REF.sub("", text)
    text = _PAGE_REF_ORPHAN.sub("", text)
    text = _MD_HEADING.sub("", text)
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    text = _EXCESS_SPACES.sub(" ", text)
    return text.strip()


if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AcademicCitation:
    """A single citation from the academic corpus.

    Maps to a source_document (paper) in the KnowledgeStore. Query results are
    defensively filtered to Marker/RAG-ready source documents.
    """
    title: str
    arxiv_id: Optional[str]
    source_url: Optional[str]
    best_snippet: str
    paper_score: float
    body_source: str   # "marker" for canonical corpus; "unknown" if metadata missing
    claim_count: int   # how many claims (or Chroma chunks) from this paper matched


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
    retrieval_mode: str = "lexical"  # "lexical" | "semantic"
    semantic_unavailable_reason: Optional[str] = None  # why Chroma was skipped, or None if used


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


def _extract_body_length(metadata_json: Optional[str]) -> int:
    """Return body_length from metadata_json, defaulting to 0."""
    if not metadata_json:
        return 0
    try:
        meta = json.loads(metadata_json)
        return int(meta.get("body_length") or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def _is_marker_ready_metadata(metadata_json: Optional[str]) -> bool:
    """Return whether metadata proves the paper is Marker/RAG-ready."""
    return (
        _extract_body_source(metadata_json) == "marker"
        and _extract_body_length(metadata_json) >= _MIN_MARKER_BODY_LENGTH
    )


def _has_academic_documents(ks: KnowledgeStore) -> bool:
    """Return True if the KS contains at least one academic source document.

    Used to distinguish Case A (empty corpus) from Case B (docs exist but
    query had no matching claims). Accesses ks._conn directly since
    KnowledgeStore exposes no public count-by-family API.
    """
    try:
        row = ks._conn.execute(
            "SELECT 1 FROM source_documents WHERE source_family = 'academic' LIMIT 1"
        ).fetchone()
        return row is not None
    except Exception:
        return False


_QUESTION_PREAMBLES: tuple[str, ...] = (
    "what is ",
    "what are ",
    "what does ",
    "what do ",
    "how does ",
    "how do ",
    "how is ",
    "how are ",
    "why does ",
    "why do ",
    "why is ",
    "why are ",
    "explain ",
    "define ",
    "describe ",
    "tell me about ",
    "can you explain ",
    "what's ",
    "whats ",
)


def _normalize_question(question: str) -> str:
    """Strip common leading question phrases to produce a core keyword phrase.

    Used for retrieval only — the original question is always preserved in
    output and as the primary query angle. Stripping is applied once: the
    first matching prefix wins, and trailing punctuation is cleaned.

    Returns the original question if no preamble is stripped or the result
    would be empty after stripping.
    """
    q = question.strip()
    q_lower = q.lower()
    for prefix in _QUESTION_PREAMBLES:
        if q_lower.startswith(prefix):
            core = q[len(prefix):].strip().rstrip("?.,!")
            if core:
                return core
            break
    return q


def _build_sub_queries(question: str, max_angles: int, include_step_back: bool) -> list[tuple[str, str]]:
    """Build (query_text, label) pairs for multi-angle retrieval.

    Inserts a normalized (preamble-stripped) core phrase as an extra angle
    when the question starts with a common question prefix and normalization
    produces a meaningfully shorter result. This ensures natural-language
    questions like "what are prediction markets" also hit claims that contain
    "prediction markets" as a substring.

    Uses plan_queries() for deterministic angle generation. Deduplicates
    against the primary question to avoid redundant KS calls.
    """
    sub_queries: list[tuple[str, str]] = [(question, "primary")]
    seen: set[str] = {question}

    # Insert normalized core before plan_queries angles so it gets highest
    # retrieval priority after the primary question itself.
    core = _normalize_question(question)
    if core != question and core not in seen:
        sub_queries.append((core, "normalized"))
        seen.add(core)

    if max_angles <= 1:
        return sub_queries

    qplan = plan_queries(
        question,
        provider_name="manual",
        include_step_back=include_step_back,
        max_queries=max_angles,
    )

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


def _open_chroma_collection(chroma_path: Optional[Path] = None):
    """Open the academic_papers ChromaDB collection. Returns (collection, reason).

    Returns (None, reason_str) on any failure so callers can surface why semantic
    retrieval was skipped. Checks collection existence BEFORE any model init so
    that missing-collection queries fail fast without Hugging Face retries.

    Order of operations (critical for fast-fail):
    1. Import chromadb (cheap — just a module lookup if already imported).
    2. Open PersistentClient (reads local SQLite, no network).
    3. list_collections() — lightweight, no model init.
    4. If academic_papers absent → return early, no model ever touched.
    5. If present → open collection WITHOUT an embedding function; query-time
       embeddings are computed manually in _query_chroma_semantic using the same
       SentenceTransformerEmbedder used at index time (avoids EF conflict since
       index-done upserts pre-computed embeddings with no Chroma EF attached).
    """
    try:
        import chromadb  # type: ignore
    except ImportError:
        return None, "chromadb not installed; pip install chromadb"
    try:
        path = chroma_path or Path("kb/rag/index")
        client = chromadb.PersistentClient(path=str(path))
        existing = {c.name for c in client.list_collections()}
        if "academic_papers" not in existing:
            return None, (
                "academic_papers collection not found; "
                "run: python -m polytool research-marker-queue index-done --reindex-chroma"
            )
        # Open without specifying an EF — the collection was created by index-done
        # which upserts pre-computed BAAI/bge-large-en-v1.5 embeddings directly.
        # Attaching a different EF here would cause a Chroma EF conflict error.
        return client.get_collection(name="academic_papers"), None
    except Exception as exc:
        return None, f"Chroma unavailable: {exc}"


def _query_chroma_semantic(
    collection,
    question: str,
    n_results: int = 20,
    min_similarity: float = 0.18,
    _embed_fn=None,
) -> list[tuple[str, float, str]]:
    """Query ChromaDB for the question. Returns (ks_doc_id, similarity, chunk_text).

    Deduplicates by ks_doc_id so each paper appears at most once (best chunk).
    Hits below min_similarity are discarded so unrelated nearest-neighbor results
    do not satisfy queries that have no relevant paper in the corpus.
    Returns [] on any Chroma error so the caller falls through to lexical.

    Model loading uses local_files_only=True to fail immediately when the BGE
    model is not locally cached — avoiding HuggingFace network retries and the
    resulting 120 s+ hang. If the model is absent, falls back to query_texts=
    (Chroma EF-less collections reject this too, returning [] → lexical fallback).

    _embed_fn: optional callable(str) -> list[float] | None for testing. When
    provided, bypasses the real model load entirely. Return None to force the
    query_texts= path (useful for fake-Chroma collection tests).
    """
    query_embedding = None
    if _embed_fn is not None:
        try:
            query_embedding = _embed_fn(question)
        except Exception:
            pass
    else:
        # Fast-fail: only loads from local cache, never downloads.
        try:
            from sentence_transformers import SentenceTransformer
            from packages.polymarket.rag.embedder import DEFAULT_EMBED_MODEL
            _model = SentenceTransformer(DEFAULT_EMBED_MODEL, local_files_only=True)
            _raw = _model.encode(question, convert_to_numpy=True, normalize_embeddings=True)
            query_embedding = _raw.astype("float32").tolist()
        except Exception:
            pass  # Model not locally cached — use query_texts= path immediately

    try:
        if query_embedding is not None:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["metadatas", "distances", "documents"],
            )
        else:
            results = collection.query(
                query_texts=[question],
                n_results=n_results,
                include=["metadatas", "distances", "documents"],
            )
    except Exception:
        return []

    hits: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]

    for meta, dist, doc_text in zip(metadatas, distances, documents):
        if not isinstance(meta, dict):
            continue
        ks_doc_id = meta.get("ks_doc_id")
        if not ks_doc_id or ks_doc_id in seen:
            continue
        seen.add(ks_doc_id)
        similarity = max(0.0, 1.0 - float(dist))
        if similarity < min_similarity:
            continue  # below relevance threshold — unrelated nearest-neighbor hit
        hits.append((str(ks_doc_id), similarity, doc_text or ""))

    return hits


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
    _store: Optional[KnowledgeStore] = None,      # injectable for testing
    _chroma_collection=None,                       # injectable for testing; bypasses _open_chroma_collection
    _embed_fn=None,                                # injectable for testing; overrides model load in _query_chroma_semantic
    chroma_path: Optional[Path] = None,
) -> AcademicQueryResult:
    """Query the academic corpus with semantic-first retrieval (L2.1).

    Tries ChromaDB semantic retrieval first: if the academic_papers collection
    is available and returns hits, those results are returned directly (semantic
    mode). If Chroma is unavailable or returns no hits, falls back to
    KnowledgeStore multi-angle lexical retrieval (lexical mode).

    Only returns results from Marker-quality ingests. The ingest gate enforces
    this for new rows, and this query path re-checks source metadata so legacy
    pdfplumber or short-body academic rows cannot be cited.

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
        Number of query angles for multi-angle lexical retrieval (1 = primary only).
    include_step_back:
        If True, include a broader step-back query angle (lexical path only).
    _store:
        Test injection: if provided, use this KS instance instead of ks_path.
    _chroma_collection:
        Test injection: if provided, use this Chroma collection instead of
        opening the real one. Allows offline unit tests with a fake collection.
    _embed_fn:
        Test injection: callable(str) -> list[float] | None. When provided,
        bypasses the real sentence-transformer model load. Pass ``lambda q: None``
        to force the query_texts= path so fake collections match by text key.
    chroma_path:
        Override ChromaDB persist directory (default: kb/rag/index).
    """
    from packages.polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH

    # Resolve KS — single connection, single close in finally
    if _store is not None:
        ks = _store
        _owns_ks = False
    else:
        resolved = ks_path or DEFAULT_KNOWLEDGE_DB_PATH
        ks = KnowledgeStore(resolved)
        _owns_ks = True

    # Injected collection takes precedence; else try to open the real one.
    # _open_chroma_collection now returns (collection_or_None, reason_or_None)
    # so that callers can surface why semantic retrieval was skipped.
    _semantic_reason: Optional[str] = None
    if _chroma_collection is not None:
        coll = _chroma_collection
    else:
        coll, _semantic_reason = _open_chroma_collection(chroma_path)

    citations: list[AcademicCitation] = []
    marker_only_count = 0
    total_claims_found = 0
    query_angles: list[str] = [question]
    retrieval_mode = "lexical"

    try:
        # ------------------------------------------------------------------
        # Semantic-first path: Chroma available → skip lexical entirely
        # ------------------------------------------------------------------
        if coll is not None:
            chroma_hits = _query_chroma_semantic(coll, question, _embed_fn=_embed_fn)
            if chroma_hits:
                retrieval_mode = "semantic"
                total_claims_found = len(chroma_hits)
                for ks_doc_id, score, chunk_text in chroma_hits[:k]:
                    src_doc = ks.get_source_document(ks_doc_id)
                    if not src_doc:
                        continue
                    metadata_json = src_doc.get("metadata_json")
                    if not _is_marker_ready_metadata(metadata_json):
                        continue
                    body_source = _extract_body_source(metadata_json)
                    if body_source == "marker":
                        marker_only_count += 1
                    citations.append(AcademicCitation(
                        title=src_doc.get("title") or "(unknown)",
                        arxiv_id=_extract_arxiv_id(metadata_json),
                        source_url=src_doc.get("source_url"),
                        best_snippet=_sanitize_snippet(chunk_text),
                        paper_score=score,
                        body_source=body_source,
                        claim_count=1,
                    ))
                if citations:
                    return AcademicQueryResult(
                        question=question,
                        citations=citations,
                        marker_only_count=marker_only_count,
                        total_claims_found=total_claims_found,
                        had_fallback=False,
                        warning=None,
                        query_angles=query_angles,
                        retrieval_mode="semantic",
                        semantic_unavailable_reason=None,
                    )
                # All Chroma hits failed Marker gate — fall through to lexical
                citations = []
                marker_only_count = 0
                total_claims_found = 0
                retrieval_mode = "lexical"

        # ------------------------------------------------------------------
        # Lexical path: KS substring multi-angle retrieval
        # ------------------------------------------------------------------
        sub_queries = _build_sub_queries(question, max_query_angles, include_step_back)
        query_angles = [q for q, _ in sub_queries]

        all_raw: list[dict] = []
        _academic_docs_exist = False
        for query_text, _label in sub_queries:
            try:
                results = query_knowledge_store_for_rrf(
                    ks,
                    text_query=query_text,
                    source_family="academic",
                    top_k=max(k * 50, 250),
                )
            except Exception:
                results = []
            all_raw.extend(results)

        # Probe corpus existence only when needed — distinguishes empty corpus
        # (Case A) from populated corpus with no matching claims (Case B).
        if not all_raw:
            _academic_docs_exist = _has_academic_documents(ks)

        total_claims_found = len(all_raw)
        merged = _merge_claims(all_raw)

        if not merged:
            if _academic_docs_exist:
                _warning = (
                    "Academic documents exist in the KnowledgeStore, but no relevant "
                    "claims matched this question. Try a more specific question or "
                    "add more related papers: "
                    "python -m polytool research-marker-queue enqueue --url ARXIV_ID"
                )
            else:
                _warning = (
                    "No academic documents found in the KnowledgeStore. "
                    "To add papers: python -m polytool research-marker-queue enqueue --url ARXIV_ID"
                )
            return AcademicQueryResult(
                question=question,
                citations=[],
                marker_only_count=0,
                total_claims_found=0,
                had_fallback=True,
                warning=_warning,
                query_angles=query_angles,
                retrieval_mode=retrieval_mode,
                semantic_unavailable_reason=_semantic_reason,
            )

        by_paper = _group_by_paper(merged)
        paper_scores_list: list[tuple[str, float, list[dict]]] = []
        for doc_id, claims in by_paper.items():
            best_score = max(c.get("score", 0.0) for c in claims)
            paper_scores_list.append((doc_id, best_score, claims))
        paper_scores_list.sort(key=lambda x: x[1], reverse=True)

        for doc_id, best_score, claims in paper_scores_list:
            if not doc_id:
                continue
            src_doc = ks.get_source_document(doc_id)
            if not src_doc:
                continue
            title = src_doc.get("title") or "(unknown)"
            source_url: Optional[str] = src_doc.get("source_url")
            metadata_json = src_doc.get("metadata_json")
            if not _is_marker_ready_metadata(metadata_json):
                continue
            arxiv_id = _extract_arxiv_id(metadata_json)
            body_source = _extract_body_source(metadata_json)
            if body_source == "marker":
                marker_only_count += 1
            best_claim = max(claims, key=lambda c: c.get("score", 0.0))
            snippet = _sanitize_snippet(best_claim.get("snippet", ""))
            citations.append(AcademicCitation(
                title=title,
                arxiv_id=arxiv_id,
                source_url=source_url,
                best_snippet=snippet,
                paper_score=best_score,
                body_source=body_source,
                claim_count=len(claims),
            ))
            if len(citations) >= k:
                break

    finally:
        if _owns_ks:
            ks.close()

    if not citations:
        return AcademicQueryResult(
            question=question,
            citations=[],
            marker_only_count=0,
            total_claims_found=total_claims_found,
            had_fallback=True,
            warning=(
                "Academic claim hits were found, but none came from Marker-ready "
                "papers (body_source=marker and body_length >= 5000). Reprocess "
                "papers through research-marker-queue before querying."
            ),
            query_angles=query_angles,
            retrieval_mode=retrieval_mode,
            semantic_unavailable_reason=_semantic_reason,
        )

    return AcademicQueryResult(
        question=question,
        citations=citations,
        marker_only_count=marker_only_count,
        total_claims_found=total_claims_found,
        had_fallback=False,
        warning=None,
        query_angles=query_angles,
        retrieval_mode=retrieval_mode,
        semantic_unavailable_reason=_semantic_reason,
    )
