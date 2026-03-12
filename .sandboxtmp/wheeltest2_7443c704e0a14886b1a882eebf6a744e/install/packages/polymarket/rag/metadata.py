"""Metadata extraction for RAG index chunks.

Derives structured metadata from file paths at index time so that
Chroma ``where`` filters can enforce user isolation, privacy scope,
and document-type scoping at query time.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 0x-prefixed Ethereum address (40 hex chars)
_WALLET_RE = re.compile(r"(0x[0-9a-fA-F]{40})")

# Date component in dossier paths: YYYY-MM-DD
_DOSSIER_DATE_PART_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MIN_YEAR = 2000
_MAX_YEAR = 2100


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


def _is_sane_year(year: int) -> bool:
    return _MIN_YEAR <= year <= _MAX_YEAR


def _parse_manifest_created_at(abs_path: Path) -> Optional[datetime]:
    try:
        payload = json.loads(abs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    raw_value = payload.get("created_at_utc")
    if not isinstance(raw_value, str):
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if not _is_sane_year(parsed.year):
        return None
    return parsed


def _extract_dossier_date(rel_path: str) -> Optional[datetime]:
    rel_posix = canonicalize_rel_path(rel_path)
    if not rel_posix.startswith("artifacts/dossiers/"):
        return None
    parts = rel_posix.split("/")
    for part in parts:
        if not _DOSSIER_DATE_PART_RE.fullmatch(part):
            continue
        try:
            year_str, month_str, day_str = part.split("-")
            year = int(year_str)
            month = int(month_str)
            day = int(day_str)
            if not _is_sane_year(year):
                return None
            return datetime(year, month, day, tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            return None
    return None


def derive_created_at(rel_path: str, abs_path: Path) -> Optional[str]:
    """Best-effort ISO-8601 creation date.

    Prefers dossier manifest timestamps, otherwise dossier path dates,
    and finally falls back to the file's mtime.
    """
    rel_posix = canonicalize_rel_path(rel_path)
    if Path(rel_posix).name == "manifest.json":
        manifest_dt = _parse_manifest_created_at(abs_path)
        if manifest_dt is not None:
            return manifest_dt.isoformat()

    dossier_dt = _extract_dossier_date(rel_posix)
    if dossier_dt is not None:
        return dossier_dt.isoformat()

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
