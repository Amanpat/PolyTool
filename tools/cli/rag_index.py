#!/usr/bin/env python3
"""Build a local Chroma index from kb/ + artifacts/."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.rag.defaults import RAG_DEFAULT_COLLECTION, RAG_DEFAULT_PERSIST_DIR
from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.index import DEFAULT_MAX_BYTES, IndexProgress, build_index, reconcile_index


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
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help="Remove stale index entries for files that no longer exist on disk.",
    )
    parser.add_argument("--chunk-size", type=int, default=400, help="Chunk size (words).")
    parser.add_argument("--overlap", type=int, default=80, help="Chunk overlap (words).")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Skip files larger than this many bytes (default: {DEFAULT_MAX_BYTES}). Use 0 to disable.",
    )
    parser.add_argument(
        "--progress-every-files",
        type=int,
        default=100,
        help="Emit progress every N scanned files (0 to disable file-based ticks).",
    )
    parser.add_argument(
        "--progress-every-chunks",
        type=int,
        default=100,
        help="Emit progress every N embedded chunks (0 to disable chunk-based ticks).",
    )
    parser.add_argument("--model", default=DEFAULT_EMBED_MODEL, help="SentenceTransformer model name.")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, cuda.")
    parser.add_argument(
        "--persist-dir",
        default=RAG_DEFAULT_PERSIST_DIR.as_posix(),
        help="Chroma persistence directory.",
    )
    parser.add_argument(
        "--collection",
        default=RAG_DEFAULT_COLLECTION,
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

    if args.reconcile and args.rebuild:
        print("Error: --reconcile and --rebuild are mutually exclusive.")
        return 1

    if args.reconcile:
        try:
            summary = reconcile_index(
                roots=roots,
                persist_directory=args.persist_dir,
                collection_name=args.collection,
            )
        except (ValueError, RuntimeError) as exc:
            print(f"Error: {exc}")
            return 1

        print("RAG reconcile complete")
        print(f"Disk files: {summary.disk_files}")
        print(f"Indexed files: {summary.indexed_files}")
        print(f"Stale files removed: {summary.stale_files}")
        print(f"  Vector entries cleaned: {summary.vector_deleted}")
        print(f"  Lexical entries cleaned: {summary.lexical_deleted}")
        for warning in summary.warnings:
            print(f"WARNING: {warning}")
        return 0

    if args.chunk_size <= 0 or args.overlap < 0 or args.overlap >= args.chunk_size:
        print("Error: chunk-size must be positive and overlap must be >= 0 and < chunk-size.")
        return 1
    if args.max_bytes < 0:
        print("Error: --max-bytes must be >= 0.")
        return 1
    if args.progress_every_files < 0 or args.progress_every_chunks < 0:
        print("Error: progress intervals must be >= 0.")
        return 1

    def _print_progress(progress: IndexProgress) -> None:
        last_path = progress.last_path.replace('"', '\\"')
        prefix = "RAG final progress" if progress.is_final else "RAG progress"
        print(
            f'{prefix} scanned_files={progress.scanned_files} '
            f"embedded_chunks={progress.embedded_chunks} "
            f"skipped_binary={progress.skipped_binary} "
            f"skipped_too_big={progress.skipped_too_big} "
            f"skipped_decode={progress.skipped_decode} "
            f'last_path="{last_path}"'
        )

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
            max_bytes=args.max_bytes,
            progress_every_files=args.progress_every_files,
            progress_every_chunks=args.progress_every_chunks,
            progress_callback=_print_progress,
        )
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1

    print("RAG index complete")
    print(f"Scanned files: {summary.scanned_files}")
    print(f"Files indexed: {summary.files_indexed}")
    print(f"Chunks indexed: {summary.chunks_indexed}")
    print(f"Skipped binary/non-text: {summary.skipped_binary}")
    print(f"Skipped too big: {summary.skipped_too_big}")
    print(f"Skipped decode failures: {summary.skipped_decode}")
    print(f"Manifest: {summary.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
