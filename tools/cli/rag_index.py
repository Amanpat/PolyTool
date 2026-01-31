#!/usr/bin/env python3
"""Build a local Chroma index from kb/ + artifacts/."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.index import build_index


def _parse_roots(raw: str) -> List[str]:
    roots = [part.strip() for part in raw.split(",") if part.strip()]
    if not roots:
        raise ValueError("No roots provided.")
    return roots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local RAG index (kb + artifacts).")
    parser.add_argument(
        "--roots",
        default="kb,artifacts",
        help="Comma-separated corpus roots (default: kb,artifacts)",
    )
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the index from scratch.")
    parser.add_argument("--chunk-size", type=int, default=400, help="Chunk size (words).")
    parser.add_argument("--overlap", type=int, default=80, help="Chunk overlap (words).")
    parser.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="SentenceTransformer model name.")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, cuda.")
    parser.add_argument(
        "--persist-dir",
        default="kb/rag/index",
        help="Chroma persistence directory.",
    )
    parser.add_argument(
        "--collection",
        default="polyttool_rag",
        help="Chroma collection name.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        roots = _parse_roots(args.roots)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    if args.chunk_size <= 0 or args.overlap < 0 or args.overlap >= args.chunk_size:
        print("Error: chunk-size must be positive and overlap must be >= 0 and < chunk-size.")
        return 1

    try:
        embedder = SentenceTransformerEmbedder(model_name=args.model, device=args.device)
        summary = build_index(
            roots=roots,
            embedder=embedder,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            persist_directory=args.persist_dir,
            collection_name=args.collection,
            rebuild=args.rebuild,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1

    print("RAG index complete")
    print(f"Files indexed: {summary.files_indexed}")
    print(f"Chunks indexed: {summary.chunks_indexed}")
    print(f"Manifest: {summary.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
