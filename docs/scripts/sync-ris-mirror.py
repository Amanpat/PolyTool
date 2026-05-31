#!/usr/bin/env python3
"""
sync-ris-mirror.py — Sync RIS knowledge stores → docs/obsidian-vault/ris-mirror/

Source (KnowledgeStore SQLite + Chroma) is authoritative. Mirror is the write
target. Direction is strictly one-way — never reads from or writes to source data.

Partition mapping (vault name → data source):
  external_knowledge — KS source_documents + Chroma academic_papers collection
  research           — KS derived_claims grouped by source_document_id
  signals            — KS pending_review items
  user_data          — Chroma polytool_rag collection summary (no per-chunk files)

Behaviors:
  NEW       — doc in source not yet mirrored; create with full vault frontmatter
  DIVERGED  — content hash changed since last sync; overwrite
  UNCHANGED — content hash matches; skip
  DELETED   — doc removed from source; delete mirror file

Usage:
    python sync-ris-mirror.py [--dry-run] [--verbose] [--partition PARTITION]
                              [--clean] [--vault-root PATH] [--repo-root PATH]

Flags:
    --clean   Wipe existing .md files in each partition dir before rebuilding.
              Removes old-scheme filenames (64-char hashes etc.). Preserves
              _index.md scaffolding and manifest.json (both regenerated).

Exit codes:
    0 — completed (or dry-run complete)
    1 — one or more errors
    2 — fatal (required path missing, lock held, or lock file stale check failed)
"""

import argparse
import ast
import collections
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GENERATOR      = "ris-mirror-sync"
SOURCE_ZONE    = "ris_mirror"
LIFECYCLE      = "reviewed"
SCHEMA_VERSION = "1.0"

ALL_PARTITIONS: tuple[str, ...] = (
    "external_knowledge",
    "research",
    "signals",
    "user_data",
)

VALID_PARTITIONS = frozenset(ALL_PARTITIONS)

LOCK_STALE_SECONDS = 1800   # 30 min — treat older lock files as stale
MAX_STATUS_ENTRIES = 50     # rolling window in ris-mirror-status.json
BODY_PREVIEW_CHARS = 2000   # max body chars for single-doc previews


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def slugify(text: str, max_len: int = 60) -> str:
    """Convert arbitrary text to a lowercase-kebab filename segment."""
    text = str(text).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:max_len] or "unnamed"


# ---------------------------------------------------------------------------
# Frontmatter serialization (mirrors sync-repo-docs.py style)
# ---------------------------------------------------------------------------

def render_frontmatter(fm: dict) -> str:
    if HAS_YAML:
        return yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    lines: list[str] = []
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        else:
            val = str(v)
            if any(c in val for c in ":#{}[]|>&*!,?") or val.startswith(("-", "'")):
                lines.append(f'{k}: "{val}"')
            else:
                lines.append(f"{k}: {val}")
    return "\n".join(lines) + "\n"


def assemble_file(fm: dict, body: str) -> str:
    return f"---\n{render_frontmatter(fm)}---\n\n{body}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_mirror_fm(
    *,
    title: str,
    mirror_of: str,
    chroma_partition: str,
    now_iso: str,
    extra: "dict | None" = None,
) -> dict:
    """Build ordered vault frontmatter for a ris-mirror document."""
    fm: dict = {
        "title":            title,
        "type":             "mirror",
        "status":           "active",
        "source_zone":      SOURCE_ZONE,
        "mirror_of":        mirror_of,
        "last_synced":      now_iso,
        "last_updated":     now_iso,
        "lifecycle":        LIFECYCLE,
        "chroma_partition": chroma_partition,
        "generator":        GENERATOR,
    }
    if extra:
        fm.update(extra)
    return fm


# ---------------------------------------------------------------------------
# Title extraction from .md frontmatter (for wikilink display aliases)
# ---------------------------------------------------------------------------

def read_doc_title(md_path: Path) -> str:
    """Read title from frontmatter of a .md file, fallback to stem."""
    try:
        text = md_path.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("\n---\n", 3)
            if end > 0:
                fm_text = text[3:end].strip()
                if HAS_YAML:
                    fm = yaml.safe_load(fm_text)
                    if isinstance(fm, dict) and fm.get("title"):
                        return str(fm["title"])
                else:
                    for line in fm_text.splitlines():
                        if line.startswith("title:"):
                            val = line[6:].strip().strip("'\"")
                            if val:
                                return val
    except Exception:
        pass
    return md_path.stem


# ---------------------------------------------------------------------------
# Lockfile (mtime-based stale detection — cross-platform safe on Windows)
# ---------------------------------------------------------------------------

def acquire_lock(lock_path: Path) -> bool:
    """Write PID lock. Returns False if a live (non-stale) lock exists."""
    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                return False   # fresh lock — another sync is running
            # stale lock — take over
        except OSError:
            pass
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Status log (keep last N runs)
# ---------------------------------------------------------------------------

def append_status(status_path: Path, entry: dict) -> None:
    entries: list[dict] = []
    if status_path.exists():
        try:
            entries = json.loads(status_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError):
            entries = []
    entries.append(entry)
    entries = entries[-MAX_STATUS_ENTRIES:]
    status_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"schema_version": SCHEMA_VERSION, "last_sync": None, "documents": {}}


def save_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Clean helper — wipe old .md files before rebuild
# ---------------------------------------------------------------------------

def clean_partition_dir(partition_dir: Path, verbose: bool) -> int:
    """Remove all .md files from partition dir except _index.md. Returns count."""
    if not partition_dir.exists():
        return 0
    count = 0
    for f in partition_dir.glob("*.md"):
        if f.name == "_index.md":
            continue
        f.unlink()
        count += 1
        if verbose:
            print(f"    CLEAN      {f.name}")
    return count


# ---------------------------------------------------------------------------
# Per-file sync helper (NEW / DIVERGED / UNCHANGED)
# ---------------------------------------------------------------------------

def _sync_doc(
    out_path: Path,
    text: str,
    chash: str,
    manifest_key: str,
    partition: str,
    docs_manifest: dict,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
    fname: str,
) -> str:
    """Write/skip a single rendered document. Returns status string."""
    prev = docs_manifest.get(manifest_key, {})
    if prev.get("content_hash") == chash and out_path.exists():
        if verbose:
            print(f"    UNCHANGED  {fname}")
        return "unchanged"

    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")

    docs_manifest[manifest_key] = {
        "content_hash": chash,
        "last_synced":  now_iso,
        "partition":    partition,
    }
    label = "DIVERGED" if prev.get("content_hash") else "NEW     "
    if verbose:
        print(f"    {label}   {fname}")
    return "diverged" if prev.get("content_hash") else "new"


# ---------------------------------------------------------------------------
# KnowledgeStore reader (read-only — never writes)
# ---------------------------------------------------------------------------

def open_ks(ks_path: Path):
    """Open KnowledgeStore SQLite. Returns sqlite3 connection or None."""
    if not ks_path.exists():
        return None
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{ks_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        try:
            import sqlite3
            conn = sqlite3.connect(str(ks_path))
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            return None


# Tables that carry a lifecycle column whose superseded/archived rows must NOT
# be mirrored into the vault (else the vault accumulates stale snapshots even
# though the DB is clean).  WI-2 added lifecycle to source_documents;
# derived_claims has had it since RIS v1.
_LIFECYCLE_FILTERED_TABLES = {"source_documents", "derived_claims"}


def _table_has_column(conn, table: str, column: str) -> bool:
    """Return True if *table* has *column* (defensive against old schemas)."""
    try:
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(str(r["name"]) == column for r in info)
    except Exception:
        return False


def _ks_rows(conn, table: str) -> list[dict]:
    """Fetch all rows from a KS table defensively.

    For lifecycle-bearing tables (source_documents, derived_claims) the mirror
    reads rows directly (it does NOT go through KnowledgeStore.query_claims), so
    the superseded/archived exclusion is applied HERE so the lifecycle filter
    propagates to the mirror.
    """
    if conn is None:
        return []
    try:
        sql = f"SELECT * FROM {table}"
        if table in _LIFECYCLE_FILTERED_TABLES and _table_has_column(conn, table, "lifecycle"):
            sql += " WHERE lifecycle NOT IN ('superseded', 'archived')"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Chroma reader (read-only — query only, never write)
# ---------------------------------------------------------------------------

def open_chroma_collection(persist_dir: Path, collection_name: str):
    """Return Chroma collection handle or None if unavailable."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(persist_dir))
        return client.get_collection(collection_name)
    except Exception:
        return None


def chroma_get_all(collection, batch_size: int = 500) -> list[dict]:
    """Page through all documents in a Chroma collection."""
    try:
        total = collection.count()
        if total == 0:
            return []
        all_docs: list[dict] = []
        for offset in range(0, total, batch_size):
            result = collection.get(
                limit=batch_size,
                offset=offset,
                include=["documents", "metadatas"],
            )
            ids   = result.get("ids") or []
            docs  = result.get("documents") or []
            metas = result.get("metadatas") or []
            for i, doc_id in enumerate(ids):
                all_docs.append({
                    "id":       doc_id,
                    "document": docs[i]  if i < len(docs)  else "",
                    "metadata": metas[i] if i < len(metas) else {},
                })
        return all_docs
    except Exception:
        try:
            result = collection.get(include=["documents", "metadatas"])
            ids   = result.get("ids") or []
            docs  = result.get("documents") or []
            metas = result.get("metadatas") or []
            return [
                {
                    "id":       ids[i],
                    "document": docs[i]  if i < len(docs)  else "",
                    "metadata": metas[i] if i < len(metas) else {},
                }
                for i in range(len(ids))
            ]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Partition: external_knowledge
# — KS source_documents + Chroma academic_papers
# ---------------------------------------------------------------------------

def sync_external_knowledge(
    partition_dir: Path,
    ks_conn,
    chroma_persist: Path,
    manifest: dict,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    expected: set[str] = set()
    docs_manifest = manifest.setdefault("documents", {})

    # --- KS source_documents ---
    # Filename: src-{doc_id[:8]}-{slug}.md  (was: ks-src-{full_id}-{slug}.md)
    for doc in _ks_rows(ks_conn, "source_documents"):
        doc_id   = str(doc.get("id", ""))
        title    = str(doc.get("title") or f"Source Document {doc_id[:8]}")
        url      = str(doc.get("url") or "")
        s_type   = str(doc.get("source_type") or "unknown")
        s_family = str(doc.get("source_family") or "unknown")
        created  = str(doc.get("created_at") or "")
        body_raw = str(doc.get("body_text") or "")

        slug  = slugify(title)
        fname = f"src-{doc_id[:8]}-{slug}.md"
        expected.add(fname)

        body_lines = [f"# {title}", ""]
        if s_type != "unknown":
            body_lines.append(f"**Source type:** {s_type}  ")
        if s_family != "unknown":
            body_lines.append(f"**Source family:** {s_family}  ")
        if url:
            body_lines.append(f"**URL:** {url}  ")
        if created:
            body_lines.append(f"**Ingested:** {created}  ")
        body_lines += ["", "---", "", "## Abstract / Summary", ""]
        body_lines.append(body_raw[:BODY_PREVIEW_CHARS].strip() if body_raw else "_No body text stored._")
        body = "\n".join(body_lines) + "\n"

        fm   = make_mirror_fm(
            title=title,
            mirror_of=f"kb/rag/knowledge/knowledge.sqlite3#source_documents/{doc_id}",
            chroma_partition="external_knowledge",
            now_iso=now_iso,
            extra={"ks_doc_id": doc_id},
        )
        text  = assemble_file(fm, body)
        chash = content_hash(text)
        key   = f"external_knowledge/{fname}"
        status = _sync_doc(
            partition_dir / fname, text, chash, key,
            "external_knowledge", docs_manifest, dry_run, verbose, now_iso, fname,
        )
        counts[status] += 1

    # --- Chroma academic_papers ---
    # FIX: group all chunks by ks_doc_id → one vault file per source document
    acad = open_chroma_collection(chroma_persist, "academic_papers")
    if acad is None:
        if verbose:
            print("    (academic_papers Chroma collection unavailable — skipping)")
    else:
        # Collect all chunks and group by ks_doc_id (fallback: chunk's own id)
        groups: dict[str, list[dict]] = collections.defaultdict(list)
        for item in chroma_get_all(acad):
            meta     = item.get("metadata") or {}
            ks_doc_id = str(meta.get("ks_doc_id") or "")
            group_key = ks_doc_id if ks_doc_id else item["id"]
            groups[group_key].append(item)

        for group_key, items in sorted(groups.items()):
            # Sort chunks within group by chunk_index ascending
            items.sort(
                key=lambda x: int((x.get("metadata") or {}).get("chunk_index", 0))
            )

            first_meta   = items[0].get("metadata") or {}
            title        = str(
                first_meta.get("title")
                or first_meta.get("file_path")
                or f"Academic Paper {group_key[:8]}"
            )
            url          = str(first_meta.get("url") or first_meta.get("source_url") or "")
            source_family = str(first_meta.get("source_family") or "acad")
            ks_doc_id    = str(first_meta.get("ks_doc_id") or "")
            file_id      = ks_doc_id[:8] if ks_doc_id else items[0]["id"][:8]

            slug  = slugify(title)
            fname = f"acad-{file_id}-{slug}.md"
            expected.add(fname)

            # Concatenate chunk bodies separated by dividers
            chunk_parts: list[str] = []
            for item in items:
                doc_text = str(item.get("document") or "").strip()
                if doc_text:
                    chunk_parts.append(doc_text)
            concatenated = "\n\n---\n\n".join(chunk_parts) if chunk_parts else "_No content stored._"

            # Build metadata header (from first chunk; omit chunk-specific fields)
            body_lines = [f"# {title}", ""]
            if url:
                body_lines.append(f"**URL:** {url}  ")
            skip_keys = {"title", "url", "source_url", "chunk_index"}
            for k, v in first_meta.items():
                if k not in skip_keys:
                    body_lines.append(f"**{k}:** {v}  ")
            body_lines += ["", f"**Chunks:** {len(items)}  "]
            body_lines += ["", "---", "", "## Content", ""]
            body_lines.append(concatenated)
            body = "\n".join(body_lines) + "\n"

            mirror_ref = f"kb/rag/index#academic_papers/{ks_doc_id or items[0]['id']}"
            fm   = make_mirror_fm(
                title=title,
                mirror_of=mirror_ref,
                chroma_partition="external_knowledge",
                now_iso=now_iso,
                extra={"ks_doc_id": ks_doc_id or group_key, "chunk_count": len(items)},
            )
            text  = assemble_file(fm, body)
            chash = content_hash(text)
            key   = f"external_knowledge/{fname}"
            status = _sync_doc(
                partition_dir / fname, text, chash, key,
                "external_knowledge", docs_manifest, dry_run, verbose, now_iso, fname,
            )
            counts[status] += 1

    # --- Orphan deletion ---
    if partition_dir.exists():
        for f in partition_dir.glob("*.md"):
            if f.name == "_index.md" or f.name in expected:
                continue
            if not dry_run:
                f.unlink()
            docs_manifest.pop(f"external_knowledge/{f.name}", None)
            counts["deleted"] += 1
            if verbose:
                print(f"    DELETED    {f.name}")

    return dict(counts)


# ---------------------------------------------------------------------------
# Partition: research
# — KS derived_claims grouped by source_document_id
# ---------------------------------------------------------------------------

def sync_research(
    partition_dir: Path,
    ks_conn,
    manifest: dict,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    expected: set[str] = set()
    docs_manifest = manifest.setdefault("documents", {})

    if ks_conn is None:
        return dict(counts)

    src_docs = {str(d.get("id", "")): d for d in _ks_rows(ks_conn, "source_documents")}
    claims   = _ks_rows(ks_conn, "derived_claims")

    by_source: dict[str, list[dict]] = collections.defaultdict(list)
    for c in claims:
        src_id = str(c.get("source_document_id") or "unknown")
        by_source[src_id].append(c)

    for src_id, src_claims in sorted(by_source.items()):
        src_doc   = src_docs.get(src_id, {})
        src_title = str(src_doc.get("title") or f"Source {src_id[:8]}")

        slug  = slugify(src_title)
        # Short filename: claims-{src_id[:8]}-{slug}.md
        fname = f"claims-{src_id[:8]}-{slug}.md"
        expected.add(fname)

        # Cross-reference uses new src-* short format
        src_link = f"[[ris-mirror/external_knowledge/src-{src_id[:8]}-{slug}|{src_title}]]"
        body_lines = [
            f"# Claims: {src_title}",
            "",
            f"**Source document:** {src_link}  ",
            f"**Claims count:** {len(src_claims)}  ",
            "",
            "---",
            "",
            "## Derived Claims",
            "",
        ]
        for c in sorted(src_claims, key=lambda x: x.get("id", 0)):
            claim_id   = c.get("id", "")
            claim_text = str(c.get("claim_text") or "").strip()
            claim_type = str(c.get("claim_type") or "claim")
            confidence = c.get("confidence")
            conf_str   = f" *(confidence: {float(confidence):.2f})*" if confidence is not None else ""
            body_lines.append(f"### [{claim_type}] Claim {claim_id}{conf_str}")
            body_lines.append("")
            body_lines.append(claim_text or "_No claim text._")
            body_lines.append("")

        body = "\n".join(body_lines) + "\n"

        fm   = make_mirror_fm(
            title=f"Claims: {src_title}",
            mirror_of=f"kb/rag/knowledge/knowledge.sqlite3#derived_claims/source={src_id}",
            chroma_partition="research",
            now_iso=now_iso,
            extra={"claim_count": len(src_claims), "source_document_id": src_id},
        )
        text  = assemble_file(fm, body)
        chash = content_hash(text)
        key   = f"research/{fname}"
        status = _sync_doc(
            partition_dir / fname, text, chash, key,
            "research", docs_manifest, dry_run, verbose, now_iso, fname,
        )
        counts[status] += 1

    # Orphan deletion
    if partition_dir.exists():
        for f in partition_dir.glob("*.md"):
            if f.name == "_index.md" or f.name in expected:
                continue
            if not dry_run:
                f.unlink()
            docs_manifest.pop(f"research/{f.name}", None)
            counts["deleted"] += 1
            if verbose:
                print(f"    DELETED    {f.name}")

    return dict(counts)


# ---------------------------------------------------------------------------
# Partition: signals
# — KS pending_review items (structured rendering, no raw dict dumps)
# ---------------------------------------------------------------------------

def _parse_pending_review_content(row: dict) -> dict:
    """
    Extract structured fields from a pending_review row.

    The `content` column may not exist; the script falls back to str(dict(row))
    which produces a Python dict literal. Parse it via ast.literal_eval / json.loads
    so we can render structured fields instead of raw text.
    """
    content_raw = row.get("content") or str(dict(row))

    parsed: dict | None = None
    if isinstance(content_raw, dict):
        parsed = content_raw
    elif isinstance(content_raw, str):
        try:
            val = ast.literal_eval(content_raw)
            if isinstance(val, dict):
                parsed = val
        except (ValueError, SyntaxError):
            pass
        if parsed is None:
            try:
                val = json.loads(content_raw)
                if isinstance(val, dict):
                    parsed = val
            except (json.JSONDecodeError, ValueError):
                pass

    return parsed or {}


def sync_signals(
    partition_dir: Path,
    ks_conn,
    manifest: dict,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    expected: set[str] = set()
    docs_manifest = manifest.setdefault("documents", {})

    if ks_conn is None:
        return dict(counts)

    rows = _ks_rows(ks_conn, "pending_review")

    for row in rows:
        row_id  = str(row.get("id", ""))
        r_type  = str(row.get("review_type") or row.get("source_type") or "review")
        created = str(row.get("created_at") or "")
        status_val = str(row.get("status") or "pending")

        # Parse structured content (avoids raw Python dict dump in body)
        parsed = _parse_pending_review_content(row)

        # Prefer top-level row columns; fall back to parsed dict fields
        title = str(
            row.get("title")
            or parsed.get("title")
            or f"Pending Review {row_id[:8]}"
        )
        gate          = str(parsed.get("gate") or row.get("gate") or "REVIEW")
        weighted_score = parsed.get("weighted_score") or row.get("weighted_score") or "?"
        simple_sum    = parsed.get("simple_sum_score") or row.get("simple_sum_score") or "?"
        src_ref       = str(
            parsed.get("source_metadata_ref")
            or row.get("source_metadata_ref")
            or row.get("source_url")
            or ""
        )
        source_type   = str(parsed.get("source_type") or r_type)

        # Parse gate_snapshot_json for scores and body preview
        gate_snapshot_str = str(parsed.get("gate_snapshot_json") or row.get("gate_snapshot_json") or "{}")
        try:
            gate_snapshot = json.loads(gate_snapshot_str)
        except (json.JSONDecodeError, ValueError):
            gate_snapshot = {}

        scores    = gate_snapshot.get("scores") or {}
        source_doc = gate_snapshot.get("source_document") or {}
        body_preview = str(source_doc.get("body_preview") or "").strip()

        slug  = slugify(f"{r_type}-{row_id[:8]}")
        fname = f"pending-review-{slug}.md"
        expected.add(fname)

        body_lines = [f"# {title}", ""]
        body_lines.append(f"**Title:** {title}  ")
        body_lines.append(f"**Review type:** {source_type}  ")
        body_lines.append(f"**Gate:** {gate}  ")
        body_lines.append(f"**Weighted score:** {weighted_score} (simple sum: {simple_sum})  ")
        if src_ref:
            body_lines.append(f"**Source:** {src_ref}  ")
        if created:
            body_lines.append(f"**Created:** {created}  ")
        body_lines.append(f"**Status:** {status_val}  ")

        body_lines += ["", "---", "", "### Body Preview", ""]
        body_lines.append(body_preview or "_No preview available._")

        if scores:
            body_lines += [
                "",
                "### Scores",
                "",
                "| Dimension | Score |",
                "|---|---|",
                f"| Relevance | {scores.get('relevance', '?')} |",
                f"| Credibility | {scores.get('credibility', '?')} |",
                f"| Novelty | {scores.get('novelty', '?')} |",
                f"| Actionability | {scores.get('actionability', '?')} |",
            ]

        body = "\n".join(body_lines) + "\n"

        fm = make_mirror_fm(
            title=title,
            mirror_of=f"kb/rag/knowledge/knowledge.sqlite3#pending_review/{row_id}",
            chroma_partition="signals",
            now_iso=now_iso,
            extra={"gate": gate, "weighted_score": str(weighted_score)},
        )
        text  = assemble_file(fm, body)
        chash = content_hash(text)
        key   = f"signals/{fname}"
        status = _sync_doc(
            partition_dir / fname, text, chash, key,
            "signals", docs_manifest, dry_run, verbose, now_iso, fname,
        )
        counts[status] += 1

    # Orphan deletion
    if partition_dir.exists():
        for f in partition_dir.glob("*.md"):
            if f.name == "_index.md" or f.name in expected:
                continue
            if not dry_run:
                f.unlink()
            docs_manifest.pop(f"signals/{f.name}", None)
            counts["deleted"] += 1
            if verbose:
                print(f"    DELETED    {f.name}")

    return dict(counts)


# ---------------------------------------------------------------------------
# Partition: user_data
# — Chroma polytool_rag collection summary (no per-chunk files)
# ---------------------------------------------------------------------------

def sync_user_data(
    partition_dir: Path,
    chroma_persist: Path,
    manifest: dict,
    dry_run: bool,
    verbose: bool,
    now_iso: str,
) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    docs_manifest = manifest.setdefault("documents", {})
    expected: set[str] = {"polytool-rag-summary.md"}

    coll  = open_chroma_collection(chroma_persist, "polytool_rag")
    total = 0
    sample_paths: list[str] = []

    if coll is None:
        status_note = "Chroma polytool_rag collection unavailable."
        if verbose:
            print("    (polytool_rag Chroma collection unavailable — writing empty summary)")
    else:
        try:
            total = coll.count()
            sample = coll.get(limit=10, include=["metadatas"])
            for meta in (sample.get("metadatas") or []):
                fp = (meta or {}).get("file_path", "")
                if fp:
                    sample_paths.append(fp)
        except Exception:
            pass
        status_note = f"{total:,} chunks indexed."

    title = "PolyTool RAG Index — Collection Summary"
    fname = "polytool-rag-summary.md"
    out_path = partition_dir / fname

    body_lines = [
        f"# {title}",
        "",
        f"**Collection:** `polytool_rag`  ",
        f"**Total chunks:** {total:,}  ",
        f"**Status:** {status_note}  ",
        f"**Last synced:** {now_iso}  ",
        "",
        "---",
        "",
        "## About",
        "",
        "This collection holds vector embeddings of PolyTool repo documents,",
        "chunked for semantic search. Individual chunks are not mirrored to the",
        "vault (too many to enumerate — see repo-docs/ for source documents).",
        "",
        "Use the RAG CLI to query:",
        "",
        "```",
        "python -m polytool rag-query --question \"your query\" --hybrid",
        "```",
        "",
    ]
    if sample_paths:
        body_lines += ["## Sample Indexed Paths", ""]
        for p in sample_paths[:10]:
            body_lines.append(f"- `{p}`")
        body_lines.append("")

    body = "\n".join(body_lines) + "\n"
    fm   = make_mirror_fm(
        title=title,
        mirror_of="kb/rag/index#polytool_rag",
        chroma_partition="user_data",
        now_iso=now_iso,
        extra={"chunk_count": total},
    )
    text  = assemble_file(fm, body)
    chash = content_hash(text)
    key   = f"user_data/{fname}"
    status = _sync_doc(
        out_path, text, chash, key,
        "user_data", docs_manifest, dry_run, verbose, now_iso, fname,
    )
    counts[status] += 1

    # Remove any unexpected files (e.g. from old schema)
    if partition_dir.exists():
        for f in partition_dir.glob("*.md"):
            if f.name == "_index.md" or f.name in expected:
                continue
            if not dry_run:
                f.unlink()
            docs_manifest.pop(f"user_data/{f.name}", None)
            counts["deleted"] += 1
            if verbose:
                print(f"    DELETED    {f.name}")

    return dict(counts)


# ---------------------------------------------------------------------------
# Index files
# ---------------------------------------------------------------------------

def write_partition_index(partition_dir: Path, partition: str, now_iso: str) -> None:
    """Write/overwrite _index.md for a partition directory.

    Wikilink display aliases use the document title from frontmatter,
    not the filename stem.
    """
    files = sorted(p for p in partition_dir.glob("*.md") if p.name != "_index.md")
    title = f"ris-mirror/{partition}"
    link_lines = "\n".join(
        f"- [[ris-mirror/{partition}/{p.stem}|{read_doc_title(p)}]]"
        for p in files
    )
    body = f"# {title}\n\n{link_lines}\n"
    fm: dict = {
        "title":            title,
        "type":             "index",
        "status":           "active",
        "source_zone":      SOURCE_ZONE,
        "mirror_of":        f"ris-mirror/{partition}/",
        "last_synced":      now_iso,
        "last_updated":     now_iso,
        "lifecycle":        LIFECYCLE,
        "chroma_partition": partition,
        "generator":        GENERATOR,
    }
    (partition_dir / "_index.md").write_text(assemble_file(fm, body), encoding="utf-8")


def write_root_index(ris_mirror_dir: Path, partitions: list[str], now_iso: str) -> None:
    """Write/overwrite root ris-mirror/_index.md."""
    link_lines = "\n".join(
        f"- [[ris-mirror/{p}/_index|{p}]]" for p in partitions
    )
    body = f"# ris-mirror\n\n{link_lines}\n"
    fm: dict = {
        "title":        "ris-mirror",
        "type":         "index",
        "status":       "active",
        "source_zone":  SOURCE_ZONE,
        "mirror_of":    "ris-mirror/",
        "last_synced":  now_iso,
        "last_updated": now_iso,
        "lifecycle":    LIFECYCLE,
        "generator":    GENERATOR,
    }
    (ris_mirror_dir / "_index.md").write_text(assemble_file(fm, body), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sync-ris-mirror",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Survey changes only; no files written",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print per-file status",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Wipe existing .md files in each partition dir before rebuilding (removes old-scheme filenames)",
    )
    parser.add_argument(
        "--partition",
        choices=sorted(VALID_PARTITIONS),
        metavar="PARTITION",
        help=f"Sync only one partition ({', '.join(sorted(VALID_PARTITIONS))})",
    )
    parser.add_argument(
        "--vault-root", type=Path,
        default=Path(__file__).parent.parent / "obsidian-vault",
        metavar="PATH",
        help="Path to vault root (default: ../obsidian-vault)",
    )
    parser.add_argument(
        "--repo-root", type=Path,
        default=Path(__file__).parent.parent.parent,
        metavar="PATH",
        help="Path to repo root (default: ../.. from this script)",
    )
    args = parser.parse_args()

    vault_root: Path = args.vault_root.resolve()
    repo_root:  Path = args.repo_root.resolve()

    for p, label in [(vault_root, "vault-root"), (repo_root, "repo-root")]:
        if not p.is_dir():
            print(f"Error: {label} does not exist: {p}", file=sys.stderr)
            return 2

    ris_mirror_dir = vault_root / "ris-mirror"
    sync_logs_dir  = vault_root / ".sync-logs"
    lock_path      = sync_logs_dir / "ris-mirror.lock"
    status_path    = sync_logs_dir / "ris-mirror-status.json"
    manifest_path  = ris_mirror_dir / "manifest.json"
    ks_path        = repo_root / "kb" / "rag" / "knowledge" / "knowledge.sqlite3"
    chroma_persist = repo_root / "kb" / "rag" / "index"

    if not args.dry_run:
        sync_logs_dir.mkdir(parents=True, exist_ok=True)
        if not acquire_lock(lock_path):
            print(
                f"Error: sync already running (lock: {lock_path}). "
                f"Delete it if stale (older than {LOCK_STALE_SECONDS}s).",
                file=sys.stderr,
            )
            return 2

    now     = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    manifest = load_manifest(manifest_path)
    ks_conn  = open_ks(ks_path)
    if ks_conn is None:
        print(f"  Warning: KnowledgeStore not found at {ks_path}; KS partitions will be empty.",
              file=sys.stderr)

    partitions_to_run: list[str] = [args.partition] if args.partition else list(ALL_PARTITIONS)
    all_counts: dict[str, dict] = {}

    try:
        for partition in partitions_to_run:
            print(f"  [{partition}/]")
            partition_dir = ris_mirror_dir / partition
            if not args.dry_run:
                partition_dir.mkdir(parents=True, exist_ok=True)

            # --clean: wipe old .md files before rebuilding
            if args.clean and not args.dry_run:
                removed = clean_partition_dir(partition_dir, args.verbose)
                if removed:
                    print(f"    cleaned {removed} old file(s)")
                # Also clear manifest entries for this partition so nothing
                # appears UNCHANGED against stale keys from old filenames
                stale_keys = [
                    k for k in manifest.get("documents", {})
                    if k.startswith(f"{partition}/")
                ]
                for k in stale_keys:
                    manifest["documents"].pop(k, None)

            if partition == "external_knowledge":
                counts = sync_external_knowledge(
                    partition_dir, ks_conn, chroma_persist,
                    manifest, args.dry_run, args.verbose, now_iso,
                )
            elif partition == "research":
                counts = sync_research(
                    partition_dir, ks_conn, manifest,
                    args.dry_run, args.verbose, now_iso,
                )
            elif partition == "signals":
                counts = sync_signals(
                    partition_dir, ks_conn, manifest,
                    args.dry_run, args.verbose, now_iso,
                )
            elif partition == "user_data":
                counts = sync_user_data(
                    partition_dir, chroma_persist,
                    manifest, args.dry_run, args.verbose, now_iso,
                )
            else:
                counts = {}

            all_counts[partition] = counts

            if not args.dry_run:
                write_partition_index(partition_dir, partition, now_iso)

        if not args.dry_run:
            write_root_index(ris_mirror_dir, partitions_to_run, now_iso)
            manifest["last_sync"] = now_iso
            save_manifest(manifest_path, manifest)

    finally:
        if ks_conn:
            ks_conn.close()
        if not args.dry_run:
            release_lock(lock_path)

    # Summary
    totals: dict[str, int] = collections.Counter()
    for counts in all_counts.values():
        for k, v in counts.items():
            totals[k] += v

    mode = "(dry-run) " if args.dry_run else ""
    print(f"\nSync {mode}complete:")
    print(f"  {totals.get('new', 0):5d}  new")
    print(f"  {totals.get('diverged', 0):5d}  diverged (updated)")
    print(f"  {totals.get('unchanged', 0):5d}  unchanged")
    print(f"  {totals.get('deleted', 0):5d}  deleted")
    errors = totals.get("error", 0)
    if errors:
        print(f"  {errors:5d}  errors")

    if not args.dry_run:
        append_status(status_path, {
            "timestamp":  now_iso,
            "dry_run":    False,
            "clean":      args.clean,
            "partitions": partitions_to_run,
            "counts":     all_counts,
        })

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
