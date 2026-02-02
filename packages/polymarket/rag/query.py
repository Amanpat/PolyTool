"""Query the local Chroma index."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .embedder import BaseEmbedder
from .index import DEFAULT_COLLECTION, DEFAULT_PERSIST_DIR, sanitize_collection_name


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


def query_index(
    *,
    question: str,
    embedder: BaseEmbedder,
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
) -> List[dict]:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required. Install requirements-rag.txt.") from exc

    if k <= 0:
        return []

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

    # Build Chroma where-filter from structured metadata params.
    where_filter = build_chroma_where(
        user_slug=user_slug,
        doc_types=doc_types,
        private_only=private_only,
        public_only=public_only,
        date_from=date_from,
        date_to=date_to,
        include_archive=include_archive,
    )

    query_embedding = embedder.embed_query(question)
    search_k = max(k * 4, k)

    query_kwargs: dict = {
        "query_embeddings": [query_embedding.tolist()],
        "n_results": search_k,
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
        if len(outputs) >= k:
            break

    return outputs
