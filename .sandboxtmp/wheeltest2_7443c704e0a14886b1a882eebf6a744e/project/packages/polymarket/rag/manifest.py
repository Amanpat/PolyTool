"""Manifest helpers for local RAG index metadata."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Bump when the indexing schema changes in a way that requires re-indexing.
SCHEMA_VERSION = 3


def _git_sha(repo_root: Path) -> str:
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.strip() or "unknown"


def write_manifest(
    manifest_path: Path,
    *,
    embed_model: str,
    embed_dim: int,
    chunk_size: int,
    overlap: int,
    indexed_roots: List[str],
    repo_root: Path,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id_scheme": {
            "hash": "sha256",
            "doc_id": "sha256(canonical_rel_path + '\\0' + sha256(file_bytes))",
            "chunk_id": "sha256(doc_id + '\\0' + str(chunk_index) + '\\0' + sha256(chunk_text_utf8))",
        },
        "embed_model": embed_model,
        "embed_dim": int(embed_dim),
        "chunk_size": int(chunk_size),
        "overlap": int(overlap),
        "indexed_roots": indexed_roots,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_sha": _git_sha(repo_root),
    }
    if collection_name is not None:
        manifest["collection_name"] = collection_name
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
