"""Metadata extraction for RAG index chunks.

Derives structured metadata from file paths at index time so that
Chroma ``where`` filters can enforce user isolation, privacy scope,
and document-type scoping at query time.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 0x-prefixed Ethereum address (40 hex chars)
_WALLET_RE = re.compile(r"(0x[0-9a-fA-F]{40})")

# Date patterns in paths: YYYY-MM-DD or YYYYMMDD
_DATE_RE = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")


def derive_doc_type(rel_path: str) -> str:
    """Derive document type from the repo-relative file path.

    Mapping:
        docs/archive/**  -> "archive"
        docs/**          -> "docs"
        kb/users/**      -> "user_kb"
        kb/**            -> "kb"
        artifacts/dossiers/** -> "dossier"
        artifacts/**     -> "artifact"
    """
    parts = rel_path.split("/")
    if not parts:
        return "unknown"

    root = parts[0]
    if root == "docs":
        if len(parts) > 1 and parts[1] == "archive":
            return "archive"
        return "docs"
    if root == "kb":
        if len(parts) > 1 and parts[1] == "users":
            return "user_kb"
        return "kb"
    if root == "artifacts":
        if len(parts) > 1 and parts[1] == "dossiers":
            return "dossier"
        return "artifact"
    return "unknown"


def derive_user_slug(rel_path: str) -> Optional[str]:
    """Extract user slug from path conventions, or *None* if not user-scoped.

    Recognised patterns:
        kb/users/<slug>/...
        artifacts/dossiers/<slug>/...          (slug != "users")
        artifacts/dossiers/users/<slug>/...
    """
    parts = rel_path.split("/")

    # kb/users/<slug>/...
    if len(parts) >= 3 and parts[0] == "kb" and parts[1] == "users":
        return parts[2].lower()

    if len(parts) >= 3 and parts[0] == "artifacts" and parts[1] == "dossiers":
        # artifacts/dossiers/users/<slug>/...
        if len(parts) >= 4 and parts[2] == "users":
            return parts[3].lower()
        # artifacts/dossiers/<slug>/...
        candidate = parts[2].lower()
        if candidate not in ("users", "shared", "common", "templates"):
            return candidate

    return None


def derive_proxy_wallet(rel_path: str) -> Optional[str]:
    """Extract a proxy-wallet (0x address) embedded in the path, if any."""
    match = _WALLET_RE.search(rel_path)
    return match.group(1).lower() if match else None


def derive_is_private(rel_path: str) -> bool:
    """``True`` for kb/ and artifacts/ paths, ``False`` for docs/."""
    root = rel_path.split("/", 1)[0]
    return root in ("kb", "artifacts")


def derive_created_at(rel_path: str, abs_path: Path) -> Optional[str]:
    """Best-effort ISO-8601 creation date.

    First tries to parse a date from the path (e.g. dossier directories
    named by date).  Falls back to the file's mtime.
    """
    match = _DATE_RE.search(rel_path)
    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            dt = datetime(year, month, day, tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, OverflowError):
            pass

    try:
        mtime = abs_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except (OSError, ValueError):
        return None


def canonicalize_rel_path(rel_path: str) -> str:
    """Normalize to forward slashes so Windows and POSIX produce the same IDs."""
    return rel_path.replace("\\", "/")


def compute_doc_id(rel_path: str, file_bytes: bytes) -> str:
    """Deterministic document ID from canonicalized path and raw file bytes.

    ::

        file_hash = sha256(raw_file_bytes)
        doc_id    = sha256(canonical_rel_path + '\\0' + file_hash)

    Including the path prevents collisions when two different files happen
    to contain identical bytes.
    """
    canonical = canonicalize_rel_path(rel_path)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    return hashlib.sha256((canonical + "\0" + file_hash).encode("utf-8")).hexdigest()


def compute_chunk_id(doc_id: str, chunk_index: int, chunk_text: str) -> str:
    """Deterministic chunk ID (used as Chroma document ID).

    ::

        chunk_text_hash = sha256(chunk_text_utf8)
        chunk_id        = sha256(doc_id + '\\0' + str(chunk_index) + '\\0' + chunk_text_hash)

    Including ``chunk_index`` prevents collisions when the same text appears
    at different positions within a file.
    """
    chunk_text_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
    payload = doc_id + "\0" + str(chunk_index) + "\0" + chunk_text_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_chunk_metadata(
    rel_path: str,
    abs_path: Path,
    doc_id: str,
    chunk_index: int,
    start_word: int,
    end_word: int,
) -> dict:
    """Build the complete metadata dict stored per chunk in Chroma.

    Nullable fields (``user_slug``, ``proxy_wallet``, ``created_at``) are
    **omitted** when their value is *None* so that Chroma where-filters
    correctly skip documents without those fields.
    """
    meta: dict = {
        "file_path": rel_path,
        "doc_id": doc_id,
        "chunk_index": chunk_index,
        "start_word": start_word,
        "end_word": end_word,
        "root": rel_path.split("/", 1)[0],
        "doc_type": derive_doc_type(rel_path),
        "is_private": derive_is_private(rel_path),
    }

    user_slug = derive_user_slug(rel_path)
    if user_slug is not None:
        meta["user_slug"] = user_slug

    proxy_wallet = derive_proxy_wallet(rel_path)
    if proxy_wallet is not None:
        meta["proxy_wallet"] = proxy_wallet

    created_at = derive_created_at(rel_path, abs_path)
    if created_at is not None:
        meta["created_at"] = created_at

    return meta
