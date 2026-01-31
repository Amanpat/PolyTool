#!/usr/bin/env python3
"""Query the local RAG index."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.llm_research_packets import _username_to_slug
from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.query import query_index


def _build_user_prefixes(user: str) -> List[str]:
    slug = _username_to_slug(user)
    if not slug:
        return []
    return [
        f"kb/users/{slug}/",
        f"artifacts/dossiers/{slug}/",
        f"artifacts/dossiers/users/{slug}/",
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the local RAG index.")
    parser.add_argument("--question", required=True, help="Question to search for.")
    parser.add_argument("--k", type=int, default=8, help="Number of results.")
    parser.add_argument("--user", help="Optional username to scope results (e.g. @Pimping).")
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

    if args.k <= 0:
        print("Error: --k must be positive.")
        return 1

    prefixes = _build_user_prefixes(args.user) if args.user else None
    try:
        embedder = SentenceTransformerEmbedder(model_name=args.model, device=args.device)
        results = query_index(
            question=args.question,
            embedder=embedder,
            k=args.k,
            persist_directory=args.persist_dir,
            collection_name=args.collection,
            filter_prefixes=prefixes,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    payload = {
        "question": args.question,
        "k": args.k,
        "filters": prefixes or [],
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
