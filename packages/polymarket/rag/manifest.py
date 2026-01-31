"""Manifest helpers for local RAG index metadata."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


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
) -> Dict[str, Any]:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "embed_model": embed_model,
        "embed_dim": int(embed_dim),
        "chunk_size": int(chunk_size),
        "overlap": int(overlap),
        "indexed_roots": indexed_roots,
        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_sha": _git_sha(repo_root),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
