"""Scoped lexical index refresh for the Scientific RAG Evaluation Benchmark v0.

Reads body text from artifacts/research/raw_source_cache/academic/*.json and
indexes only the corpus papers listed in the benchmark manifest into the FTS5
lexical DB. Avoids the global rag-refresh which scans all kb/ and artifacts/
directories.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_DEFAULT_CACHE_DIR = Path("artifacts") / "research" / "raw_source_cache" / "academic"
_DEFAULT_KNOWLEDGE_DB = Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"
_DEFAULT_LEXICAL_DB = Path("kb") / "rag" / "lexical" / "lexical.sqlite3"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RefreshResult:
    corpus_entries: int
    indexed: int
    skipped_no_body: int
    skipped_no_url: int
    total_chunks: int
    elapsed_seconds: float
    indexed_ids: List[str] = field(default_factory=list)
    skipped_ids: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _deterministic_chunk_id(doc_id: str, chunk_index: int, chunk_text: str) -> str:
    """Reproduce the id_scheme from kb/rag/manifests/index_manifest.json."""
    text_hash = _sha256_hex(chunk_text)
    raw = f"{doc_id}\x00{chunk_index}\x00{text_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _load_sid_to_url(knowledge_db_path: Path, source_ids: List[str]) -> Dict[str, str]:
    """Query KnowledgeStore for source_url of each source_id."""
    if not knowledge_db_path.exists() or not source_ids:
        return {}
    conn = sqlite3.connect(str(knowledge_db_path))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"SELECT id, source_url FROM source_documents WHERE id IN ({placeholders})",
            source_ids,
        ).fetchall()
        return {row["id"]: row["source_url"] or "" for row in rows}
    finally:
        conn.close()


def _load_url_to_body(cache_dir: Path) -> Dict[str, str]:
    """Scan cache_dir for academic JSON files; return {url: body_text} map."""
    url_to_body: Dict[str, str] = {}
    if not cache_dir.exists():
        return url_to_body
    for fname in os.listdir(cache_dir):
        if not fname.endswith(".json"):
            continue
        fpath = cache_dir / fname
        try:
            with fpath.open(encoding="utf-8") as fh:
                data = json.load(fh)
            payload = data.get("payload", {}) or {}
            body = payload.get("body_text", "") or ""
            url = payload.get("url", "") or ""
            if body and url:
                url_to_body[url] = body
        except Exception:
            continue
    return url_to_body


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def refresh_lexical_for_corpus(
    corpus_source_ids: List[str],
    *,
    lexical_db_path: Path,
    knowledge_db_path: Path = _DEFAULT_KNOWLEDGE_DB,
    cache_dir: Path = _DEFAULT_CACHE_DIR,
    chunk_size: int = 400,
    overlap: int = 80,
    verbose: bool = True,
) -> RefreshResult:
    """Index corpus papers into the lexical FTS5 DB from the raw source cache.

    Parameters
    ----------
    corpus_source_ids:
        List of source_id strings from the corpus manifest.
    lexical_db_path:
        Path to the FTS5 lexical SQLite DB (created if absent).
    knowledge_db_path:
        KnowledgeStore DB used to look up source_url per source_id.
    cache_dir:
        Directory containing academic raw source cache JSON files.
    chunk_size:
        Word-count per chunk (default 400, matching rag-refresh default).
    overlap:
        Word overlap between consecutive chunks (default 80).
    verbose:
        Print progress lines when True.
    """
    from packages.polymarket.rag.chunker import chunk_text
    from packages.polymarket.rag.lexical import open_lexical_db, insert_chunks

    t0 = time.monotonic()
    now_iso = datetime.now(timezone.utc).isoformat()

    if verbose:
        print(f"[refresh-lexical] corpus entries: {len(corpus_source_ids)}")
        print(f"[refresh-lexical] cache_dir: {cache_dir}")
        print(f"[refresh-lexical] lexical_db: {lexical_db_path}")

    # 1. Map source_id -> source_url
    sid_to_url = _load_sid_to_url(knowledge_db_path, corpus_source_ids)
    if verbose:
        print(f"[refresh-lexical] resolved {len(sid_to_url)}/{len(corpus_source_ids)} URLs from KnowledgeStore")

    # 2. Map URL -> body text from cache
    url_to_body = _load_url_to_body(cache_dir)
    if verbose:
        print(f"[refresh-lexical] found {len(url_to_body)} bodies in cache_dir")

    # 3. Open lexical DB
    lexical_db_path = Path(lexical_db_path)
    conn = open_lexical_db(lexical_db_path)

    indexed = 0
    skipped_no_body = 0
    skipped_no_url = 0
    total_chunks = 0
    indexed_ids: List[str] = []
    skipped_ids: List[str] = []

    for source_id in corpus_source_ids:
        url = sid_to_url.get(source_id, "")
        if not url:
            skipped_no_url += 1
            skipped_ids.append(source_id)
            if verbose:
                print(f"  [skip:no-url]  {source_id[:16]}...")
            continue

        body = url_to_body.get(url, "")
        if not body:
            skipped_no_body += 1
            skipped_ids.append(source_id)
            if verbose:
                print(f"  [skip:no-body] {source_id[:16]}...  (url={url})")
            continue

        # Remove stale chunks for this doc before re-indexing
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (source_id,))

        # Chunk body text
        text_chunks = chunk_text(body, chunk_size=chunk_size, overlap=overlap)
        if not text_chunks:
            skipped_no_body += 1
            skipped_ids.append(source_id)
            continue

        chunk_rows = [
            {
                "chunk_id": _deterministic_chunk_id(source_id, ch.chunk_id, ch.text),
                "doc_id": source_id,
                "file_path": source_id,  # metric 6 matches expected_paper_id against this
                "chunk_index": ch.chunk_id,
                "doc_type": "academic",
                "user_slug": None,
                "proxy_wallet": None,
                "is_private": 0,
                "created_at": now_iso,
                "chunk_text": ch.text,
            }
            for ch in text_chunks
        ]
        insert_chunks(conn, chunk_rows)
        total_chunks += len(chunk_rows)
        indexed += 1
        indexed_ids.append(source_id)

        if verbose:
            print(f"  [indexed]      {source_id[:16]}...  chunks={len(chunk_rows)}")

    conn.commit()
    conn.close()

    elapsed = time.monotonic() - t0
    result = RefreshResult(
        corpus_entries=len(corpus_source_ids),
        indexed=indexed,
        skipped_no_body=skipped_no_body,
        skipped_no_url=skipped_no_url,
        total_chunks=total_chunks,
        elapsed_seconds=elapsed,
        indexed_ids=indexed_ids,
        skipped_ids=skipped_ids,
    )
    if verbose:
        print(
            f"[refresh-lexical] done — indexed={indexed}, "
            f"skipped={skipped_no_body + skipped_no_url} "
            f"(no_body={skipped_no_body}, no_url={skipped_no_url}), "
            f"total_chunks={total_chunks}, "
            f"elapsed={elapsed:.1f}s"
        )
    return result
