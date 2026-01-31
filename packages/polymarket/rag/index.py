"""Build and persist a local Chroma index from kb/ + artifacts/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .chunker import TextChunk, chunk_text
from .embedder import BaseEmbedder
from .manifest import write_manifest

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


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


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
        text = _load_text(path)
        if not text.strip():
            continue
        chunks: List[TextChunk] = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            continue
        embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
        rel_path = path.relative_to(repo_root).as_posix()

        ids: List[str] = []
        metadatas: List[dict] = []
        documents: List[str] = []
        for chunk in chunks:
            ids.append(f"{rel_path}::chunk_{chunk.chunk_id}")
            metadatas.append(
                {
                    "file_path": rel_path,
                    "chunk_id": chunk.chunk_id,
                    "start_word": chunk.start_word,
                    "end_word": chunk.end_word,
                    "root": rel_path.split("/", 1)[0],
                }
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
    )

    return IndexSummary(
        files_indexed=files_indexed,
        chunks_indexed=chunks_indexed,
        manifest_path=str(final_manifest_path),
    )
