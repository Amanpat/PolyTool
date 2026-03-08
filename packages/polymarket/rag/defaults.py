"""Shared defaults for local RAG collection and persistence."""

from __future__ import annotations

from pathlib import Path

RAG_DEFAULT_COLLECTION = "polytool_rag"
RAG_DEFAULT_PERSIST_DIR = Path("kb") / "rag" / "index"
