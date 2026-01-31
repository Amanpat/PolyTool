"""Query the local Chroma index."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .embedder import BaseEmbedder
from .index import DEFAULT_COLLECTION, DEFAULT_PERSIST_DIR


def _resolve_repo_root() -> Path:
    return Path.cwd()


def query_index(
    *,
    question: str,
    embedder: BaseEmbedder,
    k: int = 8,
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    filter_prefixes: Optional[List[str]] = None,
) -> List[dict]:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required. Install requirements-rag.txt.") from exc

    if k <= 0:
        return []

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
    search_k = max(k * 4, k)
    result = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=search_k,
        include=["documents", "metadatas", "distances"],
    )

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    outputs: List[dict] = []
    for idx, doc_id in enumerate(ids):
        metadata = metadatas[idx] if idx < len(metadatas) else {}
        file_path = metadata.get("file_path", "")
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
                "chunk_id": metadata.get("chunk_id", doc_id),
                "score": score,
                "snippet": snippet,
                "metadata": metadata or {},
            }
        )
        if len(outputs) >= k:
            break

    return outputs
