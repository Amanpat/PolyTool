"""Query the local Chroma index (vector, lexical, or hybrid)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .embedder import BaseEmbedder
from .index import DEFAULT_COLLECTION, DEFAULT_PERSIST_DIR, sanitize_collection_name
from .lexical import (
    DEFAULT_LEXICAL_DB_PATH,
    RRF_K,
    ensure_fts5_available,
    lexical_search,
    open_lexical_db,
    reciprocal_rank_fusion,
)
from .reranker import BaseReranker, rerank_results


def _resolve_repo_root() -> Path:
    return Path.cwd()


def build_chroma_where(
    *,
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
) -> Optional[dict]:
    """Build a Chroma ``where`` filter dict from query parameters.

    Returns *None* when no constraints are needed (pass-through).

    Default behaviour is **private_only=True** so that ``kb/`` and
    ``artifacts/`` content is returned but ``docs/`` content is not.
    """
    if private_only and public_only:
        raise ValueError("private_only and public_only are mutually exclusive")

    conditions: List[dict] = []

    if user_slug:
        conditions.append({"user_slug": {"$eq": user_slug}})

    if doc_types:
        if len(doc_types) == 1:
            conditions.append({"doc_type": {"$eq": doc_types[0]}})
        else:
            conditions.append({"doc_type": {"$in": doc_types}})

    if private_only:
        conditions.append({"is_private": {"$eq": True}})
    elif public_only:
        conditions.append({"is_private": {"$eq": False}})

    # Exclude archive docs by default unless explicitly requested or
    # the caller already asked for archive via doc_types.
    if not include_archive:
        if not doc_types or "archive" not in doc_types:
            conditions.append({"doc_type": {"$ne": "archive"}})

    if date_from:
        conditions.append({"created_at": {"$gte": date_from + "T00:00:00+00:00"}})

    if date_to:
        conditions.append({"created_at": {"$lte": date_to + "T23:59:59+00:00"}})

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def _run_vector_query(
    question: str,
    *,
    embedder: BaseEmbedder,
    n_results: int,
    output_limit: int,
    persist_directory: Path,
    collection_name: str,
    where_filter: Optional[dict],
    filter_prefixes: Optional[List[str]],
) -> List[dict]:
    if n_results <= 0 or output_limit <= 0:
        return []

    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required. Install requirements-rag.txt.") from exc

    collection_name = sanitize_collection_name(collection_name)

    repo_root = _resolve_repo_root()
    persist_path = Path(persist_directory)
    if not persist_path.is_absolute():
        persist_path = (repo_root / persist_path).resolve()

    client = chromadb.PersistentClient(path=str(persist_path))
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return []

    query_embedding = embedder.embed_query(question)

    query_kwargs: dict = {
        "query_embeddings": [query_embedding.tolist()],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter is not None:
        query_kwargs["where"] = where_filter

    result = collection.query(**query_kwargs)

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    outputs: List[dict] = []
    for idx, doc_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        file_path = metadata.get("file_path", "")

        # Defensive backstop: post-filter by path prefix if provided.
        if filter_prefixes:
            if not any(file_path.startswith(prefix) for prefix in filter_prefixes):
                continue

        document = documents[idx] if idx < len(documents) else ""
        distance = distances[idx] if idx < len(distances) else None
        score = None
        if distance is not None:
            try:
                score = 1.0 - float(distance)
            except (TypeError, ValueError):
                score = None
        snippet = (document or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "..."
        outputs.append(
            {
                "file_path": file_path,
                "chunk_id": doc_id,  # Chroma ID (sha256 hash)
                "chunk_index": metadata.get("chunk_index", 0),
                "doc_id": metadata.get("doc_id", ""),
                "score": score,
                "snippet": snippet,
                "metadata": metadata or {},
            }
        )
        if len(outputs) >= output_limit:
            break

    return outputs


def _run_lexical_query(
    question: str,
    *,
    k: int,
    lexical_db_path: Optional[Path],
    filter_prefixes: Optional[List[str]],
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
) -> List[dict]:
    """Open the lexical DB, run an FTS5 search, close, and return results."""
    if k <= 0:
        return []

    lex_path = Path(lexical_db_path) if lexical_db_path else DEFAULT_LEXICAL_DB_PATH
    if not lex_path.is_absolute():
        lex_path = (_resolve_repo_root() / lex_path).resolve()

    try:
        conn = open_lexical_db(lex_path)
    except Exception:
        return []

    try:
        results = lexical_search(
            conn,
            question,
            k=k,
            user_slug=user_slug,
            doc_types=doc_types,
            private_only=private_only,
            public_only=public_only,
            date_from=date_from,
            date_to=date_to,
            include_archive=include_archive,
        )
    finally:
        conn.close()

    if filter_prefixes:
        results = [
            r for r in results
            if any(r["file_path"].startswith(p) for p in filter_prefixes)
        ]
    return results


def query_index(
    *,
    question: str,
    embedder: Optional[BaseEmbedder] = None,
    k: int = 8,
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    filter_prefixes: Optional[List[str]] = None,
    # --- metadata filters (Chroma where-clause) ---
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
    # --- hybrid retrieval ---
    hybrid: bool = False,
    lexical_only: bool = False,
    lexical_db_path: Optional[Path] = None,
    top_k_vector: int = 25,
    top_k_lexical: int = 25,
    rrf_k: int = RRF_K,
    # --- reranking ---
    reranker: Optional[BaseReranker] = None,
    rerank_top_n: int = 50,
) -> List[dict]:
    if hybrid and lexical_only:
        raise ValueError("hybrid and lexical_only are mutually exclusive")

    if k <= 0:
        return []

    _filter_kw = dict(
        user_slug=user_slug,
        doc_types=doc_types,
        private_only=private_only,
        public_only=public_only,
        date_from=date_from,
        date_to=date_to,
        include_archive=include_archive,
    )

    # Build Chroma where-filter from structured metadata params.
    where_filter = build_chroma_where(**_filter_kw)

    # --- lexical-only path (no embedder needed) ---
    if lexical_only:
        ensure_fts5_available()
        final = _run_lexical_query(
            question,
            k=k,
            lexical_db_path=lexical_db_path,
            filter_prefixes=filter_prefixes,
            **_filter_kw,
        )
    # --- vector (and hybrid) path: embedder required ---
    elif embedder is None:
        raise ValueError("embedder is required for vector or hybrid queries")
    elif not hybrid:
        search_k = max(k * 4, k)
        final = _run_vector_query(
            question,
            embedder=embedder,
            n_results=search_k,
            output_limit=k,
            persist_directory=persist_directory,
            collection_name=collection_name,
            where_filter=where_filter,
            filter_prefixes=filter_prefixes,
        )
    else:
        # --- hybrid path ---
        ensure_fts5_available()
        vector_k = max(top_k_vector, k)
        lexical_k = max(top_k_lexical, k)

        vector_results = _run_vector_query(
            question,
            embedder=embedder,
            n_results=vector_k,
            output_limit=vector_k,
            persist_directory=persist_directory,
            collection_name=collection_name,
            where_filter=where_filter,
            filter_prefixes=filter_prefixes,
        )

        lexical_results = _run_lexical_query(
            question,
            k=lexical_k,
            lexical_db_path=lexical_db_path,
            filter_prefixes=filter_prefixes,
            **_filter_kw,
        )

        fused = reciprocal_rank_fusion(vector_results, lexical_results, rrf_k=rrf_k)
        final = fused[:k]

    # --- Apply reranking if requested ---
    if reranker is not None and final:
        final = rerank_results(final, query=question, reranker=reranker, top_n=rerank_top_n)

    return final
