"""Build and persist a local Chroma index from kb/ + artifacts/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder
from .manifest import write_manifest
from .metadata import build_chunk_metadata, canonicalize_rel_path, compute_chunk_id, compute_doc_id

ALLOWED_ROOTS = {"kb", "artifacts"}
DEFAULT_COLLECTION = "polyttool_rag"
DEFAULT_PERSIST_DIR = Path("kb") / "rag" / "index"
DEFAULT_MANIFEST_PATH = Path("kb") / "rag" / "manifests" / "index_manifest.json"

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".ndjson",
    ".csv",
    ".tsv",
    ".yaml",
    ".yml",
    ".log",
}

SKIP_DIR_PARTS = {
    ".git",
    "__pycache__",
}


@dataclass
class IndexSummary:
    files_indexed: int
    chunks_indexed: int
    manifest_path: str


def sanitize_collection_name(name: str) -> str:
    """Normalize a Chroma collection name to match allowed constraints."""
    if not name:
        return DEFAULT_COLLECTION

    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    cleaned = re.sub(r"^[^a-zA-Z0-9]+", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9]+$", "", cleaned)

    if not cleaned or len(cleaned) < 3:
        return DEFAULT_COLLECTION

    if len(cleaned) > 512:
        cleaned = cleaned[:512]
        cleaned = re.sub(r"[^a-zA-Z0-9]+$", "", cleaned)
        cleaned = re.sub(r"^[^a-zA-Z0-9]+", "", cleaned)

    if not cleaned or len(cleaned) < 3:
        return DEFAULT_COLLECTION

    return cleaned


def _resolve_repo_root() -> Path:
    return Path.cwd()


def _resolve_root(root: str, repo_root: Path) -> Tuple[Path, str]:
    root_path = Path(root)
    if not root_path.is_absolute():
        root_path = (repo_root / root_path).resolve()
    else:
        root_path = root_path.resolve()

    try:
        rel = root_path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Root must be inside repo: {root}") from exc

    if not rel.parts:
        raise ValueError(f"Root must be under kb/ or artifacts/: {root}")
    if rel.parts[0] not in ALLOWED_ROOTS:
        raise ValueError(f"Root must be under kb/ or artifacts/: {root}")

    return root_path, rel.as_posix()


def _should_skip(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    rel_posix = rel.as_posix()
    if rel_posix.startswith("kb/rag/index/") or rel_posix.startswith("kb/rag/manifests/"):
        return True
    if any(part in SKIP_DIR_PARTS for part in rel.parts):
        return True
    return False


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _iter_files(roots: Iterable[Path], repo_root: Path) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if _should_skip(path, repo_root):
                continue
            if not _is_text_file(path):
                continue
            yield path


def _load_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:
        return b""


def build_index(
    *,
    roots: List[str],
    embedder: BaseEmbedder,
    chunk_size: int = 400,
    overlap: int = 80,
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    rebuild: bool = False,
    manifest_path: Optional[Path] = None,
) -> IndexSummary:
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required. Install requirements-rag.txt.") from exc

    collection_name = sanitize_collection_name(collection_name)

    repo_root = _resolve_repo_root()
    resolved_roots: List[Path] = []
    indexed_roots: List[str] = []
    for root in roots:
        resolved, rel = _resolve_root(root, repo_root)
        resolved_roots.append(resolved)
        indexed_roots.append(rel)

    persist_path = Path(persist_directory)
    if not persist_path.is_absolute():
        persist_path = (repo_root / persist_path).resolve()
    persist_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_path))
    if rebuild:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    files_indexed = 0
    chunks_indexed = 0

    for path in _iter_files(resolved_roots, repo_root):
        raw_bytes = _load_bytes(path)
        text = raw_bytes.decode("utf-8", errors="ignore")
        if not text.strip():
            continue
        chunks: List[TextChunk] = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            continue
        embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
        rel_path = canonicalize_rel_path(path.relative_to(repo_root).as_posix())
        doc_id = compute_doc_id(rel_path, raw_bytes)

        # --- delete-before-insert: remove stale chunks for this file ---
        # This handles content changes (different chunks) and file shrinkage
        # (fewer chunks) without leaving orphans.  On a fresh/rebuild index
        # the delete is a harmless no-op.
        if not rebuild:
            try:
                collection.delete(where={"file_path": rel_path})
            except Exception:
                # Chroma versions < 0.4 may not support where-delete;
                # fall through to upsert which is still safe for same-count
                # changes (but may leave orphans on shrinkage).
                pass

        ids: List[str] = []
        metadatas: List[dict] = []
        documents: List[str] = []
        for chunk in chunks:
            cid = compute_chunk_id(doc_id, chunk.chunk_id, chunk.text)
            ids.append(cid)
            metadatas.append(
                build_chunk_metadata(
                    rel_path=rel_path,
                    abs_path=path,
                    doc_id=doc_id,
                    chunk_index=chunk.chunk_id,
                    start_word=chunk.start_word,
                    end_word=chunk.end_word,
                )
            )
            documents.append(chunk.text)

        if hasattr(collection, "upsert"):
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
            )
        else:
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
            )

        files_indexed += 1
        chunks_indexed += len(chunks)

    final_manifest_path = manifest_path or DEFAULT_MANIFEST_PATH
    if not final_manifest_path.is_absolute():
        final_manifest_path = repo_root / final_manifest_path

    write_manifest(
        final_manifest_path,
        embed_model=embedder.model_name,
        embed_dim=embedder.dimension,
        chunk_size=chunk_size,
        overlap=overlap,
        indexed_roots=indexed_roots,
        repo_root=repo_root,
        collection_name=collection_name,
    )

    return IndexSummary(
        files_indexed=files_indexed,
        chunks_indexed=chunks_indexed,
        manifest_path=str(final_manifest_path),
    )
