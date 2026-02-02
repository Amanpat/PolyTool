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


def _parse_doc_types(raw: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated or repeated --doc-type values into a list."""
    if not raw:
        return None
    types = [t.strip() for t in raw.split(",") if t.strip()]
    return types or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the local RAG index.")
    parser.add_argument("--question", required=True, help="Question to search for.")
    parser.add_argument("--k", type=int, default=8, help="Number of results.")
    parser.add_argument("--user", help="User slug to scope results (e.g. @Pimping).")
    parser.add_argument(
        "--doc-type",
        dest="doc_type",
        action="append",
        help="Filter by document type (repeatable, or comma-separated). "
        "Values: user_kb, dossier, kb, artifact, docs, archive.",
    )
    privacy = parser.add_mutually_exclusive_group()
    privacy.add_argument(
        "--private-only",
        action="store_true",
        default=True,
        help="Return only private content (kb/ + artifacts/). This is the default.",
    )
    privacy.add_argument(
        "--public-only",
        action="store_true",
        default=False,
        help="Return only public content (docs/).",
    )
    parser.add_argument(
        "--date-from",
        help="Include only documents created on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--date-to",
        help="Include only documents created on or before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        default=False,
        help="Include archive documents in results (excluded by default).",
    )
    retrieval = parser.add_mutually_exclusive_group()
    retrieval.add_argument(
        "--hybrid",
        action="store_true",
        default=False,
        help="Use hybrid (vector + lexical) retrieval with RRF fusion.",
    )
    retrieval.add_argument(
        "--lexical-only",
        action="store_true",
        default=False,
        help="Use lexical (FTS5) retrieval only (no embedding model needed).",
    )
    parser.add_argument(
        "--top-k-vector",
        type=int,
        default=25,
        help="Number of vector candidates to retrieve for hybrid fusion.",
    )
    parser.add_argument(
        "--top-k-lexical",
        type=int,
        default=25,
        help="Number of lexical candidates to retrieve for hybrid fusion.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF fusion constant (higher reduces rank impact).",
    )
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

    # Resolve user slug for both metadata filter and defensive prefix backstop.
    user_slug: Optional[str] = None
    prefixes: Optional[List[str]] = None
    if args.user:
        user_slug = _username_to_slug(args.user)
        prefixes = _build_user_prefixes(args.user)

    # Flatten repeated --doc-type flags and comma-separated values.
    doc_types: Optional[List[str]] = None
    if args.doc_type:
        flat: List[str] = []
        for entry in args.doc_type:
            flat.extend(t.strip() for t in entry.split(",") if t.strip())
        doc_types = flat or None

    try:
        embedder = None
        if not args.lexical_only:
            embedder = SentenceTransformerEmbedder(model_name=args.model, device=args.device)
        results = query_index(
            question=args.question,
            embedder=embedder,
            k=args.k,
            persist_directory=args.persist_dir,
            collection_name=args.collection,
            filter_prefixes=prefixes,
            user_slug=user_slug,
            doc_types=doc_types,
            private_only=args.private_only and not args.public_only,
            public_only=args.public_only,
            date_from=args.date_from,
            date_to=args.date_to,
            include_archive=args.include_archive,
            hybrid=args.hybrid,
            lexical_only=args.lexical_only,
            top_k_vector=args.top_k_vector,
            top_k_lexical=args.top_k_lexical,
            rrf_k=args.rrf_k,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    mode = "hybrid" if args.hybrid else ("lexical" if args.lexical_only else "vector")
    payload = {
        "question": args.question,
        "k": args.k,
        "mode": mode,
        "filters": {
            "user_slug": user_slug,
            "doc_types": doc_types,
            "private_only": args.private_only and not args.public_only,
            "public_only": args.public_only,
            "date_from": args.date_from,
            "date_to": args.date_to,
            "include_archive": args.include_archive,
            "prefix_backstop": prefixes or [],
        },
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
