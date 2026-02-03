"""Build and persist a local Chroma index from kb/ + artifacts/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder
from .lexical import (
    DEFAULT_LEXICAL_DB_PATH,
    clear_all as _lexical_clear_all,
    delete_file_chunks as _lexical_delete_file,
    insert_chunks as _lexical_insert,
    list_indexed_file_paths as _lexical_list_paths,
    open_lexical_db,
)
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


@dataclass
class ReconcileSummary:
    disk_files: int
    indexed_files: int
    stale_files: int
    vector_deleted: int
    lexical_deleted: int
    warnings: List[str]


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
    if rel_posix.startswith("kb/rag/index/") or rel_posix.startswith("kb/rag/manifests/") or rel_posix.startswith("kb/rag/lexical/"):
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
    lexical_db_path: Optional[Path] = DEFAULT_LEXICAL_DB_PATH,
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

    # --- lexical (FTS5) index ---
    lex_conn = None
    if lexical_db_path is not None:
        lex_path = Path(lexical_db_path)
        if not lex_path.is_absolute():
            lex_path = (repo_root / lex_path).resolve()
        lex_conn = open_lexical_db(lex_path)
        if rebuild:
            _lexical_clear_all(lex_conn)

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
            if lex_conn is not None:
                _lexical_delete_file(lex_conn, rel_path)

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

        # --- lexical: mirror the same chunks into FTS5 ---
        if lex_conn is not None:
            lex_rows = []
            for i, chunk in enumerate(chunks):
                lex_rows.append({
                    "chunk_id": ids[i],
                    "doc_id": doc_id,
                    "file_path": rel_path,
                    "chunk_index": chunk.chunk_id,
                    "doc_type": metadatas[i].get("doc_type"),
                    "user_slug": metadatas[i].get("user_slug"),
                    "proxy_wallet": metadatas[i].get("proxy_wallet"),
                    "is_private": metadatas[i].get("is_private", True),
                    "created_at": metadatas[i].get("created_at"),
                    "chunk_text": chunk.text,
                })
            _lexical_insert(lex_conn, lex_rows)
            lex_conn.commit()

        files_indexed += 1
        chunks_indexed += len(chunks)

    if lex_conn is not None:
        lex_conn.close()

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


def _chroma_indexed_file_paths(collection) -> set[str]:
    """Return the set of distinct ``file_path`` values stored in a Chroma collection."""
    result = collection.get(include=["metadatas"])
    paths: set[str] = set()
    for meta in result.get("metadatas", []):
        fp = meta.get("file_path")
        if fp:
            paths.add(fp)
    return paths


def reconcile_index(
    *,
    roots: List[str],
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    lexical_db_path: Optional[Path] = DEFAULT_LEXICAL_DB_PATH,
) -> ReconcileSummary:
    """Remove index entries whose source files no longer exist on disk.

    Scans *roots* for files that **should** be indexed, then compares against
    the file paths currently stored in both the Chroma vector index and the
    SQLite FTS5 lexical index.  Any file path present in an index but absent
    from disk is deleted from both indexes.
    """
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required. Install requirements-rag.txt.") from exc

    collection_name = sanitize_collection_name(collection_name)

    repo_root = _resolve_repo_root()
    resolved_roots: List[Path] = []
    for root in roots:
        resolved, _rel = _resolve_root(root, repo_root)
        resolved_roots.append(resolved)

    # --- build set of file_paths that SHOULD exist on disk ---
    disk_paths: set[str] = set()
    for path in _iter_files(resolved_roots, repo_root):
        rel_path = canonicalize_rel_path(path.relative_to(repo_root).as_posix())
        disk_paths.add(rel_path)

    # --- get indexed paths from Chroma ---
    persist_path = Path(persist_directory)
    if not persist_path.is_absolute():
        persist_path = (repo_root / persist_path).resolve()

    client = chromadb.PersistentClient(path=str(persist_path))
    try:
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        raise RuntimeError(f"Cannot open Chroma collection {collection_name!r}: {exc}") from exc

    chroma_paths = _chroma_indexed_file_paths(collection)

    # --- get indexed paths from lexical DB ---
    lex_conn = None
    lexical_paths: set[str] = set()
    if lexical_db_path is not None:
        lex_path = Path(lexical_db_path)
        if not lex_path.is_absolute():
            lex_path = (repo_root / lex_path).resolve()
        lex_conn = open_lexical_db(lex_path)
        lexical_paths = _lexical_list_paths(lex_conn)

    # --- compute stale ---
    all_indexed = chroma_paths | lexical_paths
    stale = all_indexed - disk_paths

    warnings: List[str] = []
    vector_deleted = 0
    lexical_deleted = 0

    for stale_path in sorted(stale):
        # --- Chroma deletion ---
        if stale_path in chroma_paths:
            try:
                collection.delete(where={"file_path": stale_path})
                vector_deleted += 1
            except Exception as exc:
                warnings.append(
                    f"Chroma delete-by-where failed for {stale_path!r}: {exc}. "
                    "Run --rebuild to fully clean the vector index."
                )

        # --- Lexical deletion ---
        if stale_path in lexical_paths and lex_conn is not None:
            _lexical_delete_file(lex_conn, stale_path)
            lexical_deleted += 1

    if lex_conn is not None:
        lex_conn.commit()
        lex_conn.close()

    return ReconcileSummary(
        disk_files=len(disk_paths),
        indexed_files=len(all_indexed),
        stale_files=len(stale),
        vector_deleted=vector_deleted,
        lexical_deleted=lexical_deleted,
        warnings=warnings,
    )
