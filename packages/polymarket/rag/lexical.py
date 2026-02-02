"""SQLite FTS5 lexical index for hybrid retrieval.

Persists a full-text search index under ``kb/rag/lexical/lexical.sqlite3`` that mirrors
the Chroma vector index.  Provides :func:`lexical_search` for keyword
retrieval and :func:`reciprocal_rank_fusion` for combining vector and
lexical ranked lists.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_LEXICAL_DB_PATH = Path("kb") / "rag" / "lexical" / "lexical.sqlite3"

# Reciprocal Rank Fusion constant.  k=60 is the value from the original
# Cormack, Clarke & Buettcher (2009) RRF paper and is widely used.
RRF_K = 60


# ---------------------------------------------------------------------------
# FTS5 query sanitization
# ---------------------------------------------------------------------------

def _sanitize_fts_query(query: str) -> str:
    """Wrap each token in double-quotes to neutralise FTS5 operator syntax.

    Without quoting, user input like ``OR``, ``NOT``, or ``NEAR`` would be
    interpreted as FTS5 operators.  Quoting forces literal matching.
    """
    tokens = query.split()
    if not tokens:
        return '""'
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)


# ---------------------------------------------------------------------------
# Database lifecycle
# ---------------------------------------------------------------------------

def open_lexical_db(lexical_db_path: Path) -> sqlite3.Connection:
    """Open (or create) the FTS5 lexical database at *lexical_db_path*."""
    lexical_db_path = Path(lexical_db_path)
    if lexical_db_path.suffix == "":
        lexical_db_path = lexical_db_path / "lexical.sqlite3"
    lexical_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(lexical_db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id     TEXT PRIMARY KEY,
            doc_id       TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            chunk_index  INTEGER NOT NULL,
            doc_type     TEXT,
            user_slug    TEXT,
            proxy_wallet TEXT,
            is_private   INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT,
            chunk_text   TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_file_path  ON chunks(file_path);
        CREATE INDEX IF NOT EXISTS idx_chunks_is_private ON chunks(is_private);
        CREATE INDEX IF NOT EXISTS idx_chunks_user_slug  ON chunks(user_slug);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_type   ON chunks(doc_type);
    """)
    # FTS5 content-sync table backed by the chunks table.
    # porter: English stemming.  unicode61: unicode-aware tokeniser.
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_text,
            content='chunks',
            content_rowid='rowid',
            tokenize='porter unicode61'
        )
    """)
    # Triggers keep the FTS index in sync with the content table.
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, chunk_text)
            VALUES (new.rowid, new.chunk_text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text)
            VALUES ('delete', old.rowid, old.chunk_text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, chunk_text)
            VALUES ('delete', old.rowid, old.chunk_text);
            INSERT INTO chunks_fts(rowid, chunk_text)
            VALUES (new.rowid, new.chunk_text);
        END;
    """)
    conn.commit()


def clear_all(conn: sqlite3.Connection) -> None:
    """Drop all data and rebuild the FTS index (for full rebuilds)."""
    conn.execute("DELETE FROM chunks")
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()


# ---------------------------------------------------------------------------
# Index-time helpers (called from index.py)
# ---------------------------------------------------------------------------

def delete_file_chunks(conn: sqlite3.Connection, file_path: str) -> None:
    """Remove all chunks for *file_path*.  Triggers update FTS automatically."""
    conn.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))


def insert_chunks(conn: sqlite3.Connection, chunks: List[dict]) -> None:
    """Batch-insert chunk rows.  Caller is responsible for committing."""
    conn.executemany(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, doc_id, file_path, chunk_index, doc_type,
            user_slug, proxy_wallet, is_private, created_at, chunk_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                c["chunk_id"],
                c["doc_id"],
                c["file_path"],
                c["chunk_index"],
                c.get("doc_type"),
                c.get("user_slug"),
                c.get("proxy_wallet"),
                1 if c.get("is_private", True) else 0,
                c.get("created_at"),
                c["chunk_text"],
            )
            for c in chunks
        ],
    )


# ---------------------------------------------------------------------------
# Lexical search
# ---------------------------------------------------------------------------

def lexical_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    k: int = 32,
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
) -> List[dict]:
    """FTS5 MATCH query with the same metadata filters as the Chroma path.

    Returns results in the same dict format as :func:`query_index` so they
    can be passed directly to :func:`reciprocal_rank_fusion`. Adds
    ``lexical_rank`` (1-based) and ``lexical_score`` (bm25).
    """
    if private_only and public_only:
        raise ValueError("private_only and public_only are mutually exclusive")

    fts_q = _sanitize_fts_query(query)
    conditions = ["chunks_fts MATCH ?"]
    params: list = [fts_q]

    if user_slug:
        conditions.append("c.user_slug = ?")
        params.append(user_slug)

    if doc_types:
        placeholders = ",".join("?" for _ in doc_types)
        conditions.append(f"c.doc_type IN ({placeholders})")
        params.extend(doc_types)

    if private_only:
        conditions.append("c.is_private = 1")
    elif public_only:
        conditions.append("c.is_private = 0")

    if not include_archive:
        if not doc_types or "archive" not in doc_types:
            conditions.append("(c.doc_type IS NULL OR c.doc_type != 'archive')")

    if date_from:
        conditions.append("c.created_at >= ?")
        params.append(date_from + "T00:00:00+00:00")

    if date_to:
        conditions.append("c.created_at <= ?")
        params.append(date_to + "T23:59:59+00:00")

    where = " AND ".join(conditions)
    params.append(k)

    sql = f"""
        SELECT c.chunk_id, c.doc_id, c.file_path, c.chunk_index,
               c.doc_type, c.user_slug, c.proxy_wallet, c.is_private,
               c.created_at, c.chunk_text, bm25(chunks_fts) AS fts_rank
        FROM chunks_fts
        JOIN chunks c ON c.rowid = chunks_fts.rowid
        WHERE {where}
        ORDER BY bm25(chunks_fts)
        LIMIT ?
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []

    results: List[dict] = []
    for rank, row in enumerate(rows, 1):
        snippet = (row["chunk_text"] or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400].rstrip() + "..."
        meta: dict = {
            "file_path": row["file_path"],
            "doc_id": row["doc_id"],
            "chunk_index": row["chunk_index"],
            "doc_type": row["doc_type"],
            "is_private": bool(row["is_private"]),
        }
        if row["user_slug"]:
            meta["user_slug"] = row["user_slug"]
        if row["proxy_wallet"]:
            meta["proxy_wallet"] = row["proxy_wallet"]
        if row["created_at"]:
            meta["created_at"] = row["created_at"]
        results.append({
            "file_path": row["file_path"],
            "chunk_id": row["chunk_id"],
            "chunk_index": row["chunk_index"],
            "doc_id": row["doc_id"],
            "score": None,
            "lexical_score": row["fts_rank"],
            "lexical_rank": rank,
            "snippet": snippet,
            "metadata": meta,
        })
    return results


def lexical_query(
    query: str,
    *,
    lexical_db_path: Path = DEFAULT_LEXICAL_DB_PATH,
    k: int = 32,
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
) -> List[dict]:
    """Open the lexical DB at *lexical_db_path*, run FTS5 search, close."""
    conn = open_lexical_db(lexical_db_path)
    try:
        return lexical_search(
            conn,
            query,
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


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    vector_results: List[dict],
    lexical_results: List[dict],
    *,
    rrf_k: int = RRF_K,
) -> List[dict]:
    """Fuse two ranked lists via Reciprocal Rank Fusion.

    For each chunk *c* present in any list::

        rrf_score(c) = Σ_list  1 / (rrf_k + rank_in_list)

    *rrf_k* = 60 is the standard constant from the original paper
    (Cormack, Clarke & Buettcher, 2009).

    Returns a list sorted by descending ``fused_score`` with explainable
    fields: ``vector_rank``, ``lexical_rank``, ``fused_score``,
    ``final_rank``.
    """
    scores: Dict[str, float] = {}
    all_results: Dict[str, dict] = {}
    v_ranks: Dict[str, int] = {}
    l_ranks: Dict[str, int] = {}

    for rank, r in enumerate(vector_results, 1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
        v_ranks[cid] = rank
        all_results[cid] = r

    for rank, r in enumerate(lexical_results, 1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
        l_ranks[cid] = rank
        if cid not in all_results:
            all_results[cid] = r

    sorted_ids = sorted(scores, key=lambda c: scores[c], reverse=True)

    fused: List[dict] = []
    for final_rank, cid in enumerate(sorted_ids, 1):
        entry = all_results[cid].copy()
        entry["vector_rank"] = v_ranks.get(cid)
        entry["lexical_rank"] = l_ranks.get(cid)
        entry["fused_score"] = scores[cid]
        entry["final_rank"] = final_rank
        entry["score"] = scores[cid]
        fused.append(entry)
    return fused
