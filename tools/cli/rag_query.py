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
from polymarket.rag.defaults import RAG_DEFAULT_COLLECTION, RAG_DEFAULT_PERSIST_DIR
from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH
from polymarket.rag.query import query_index
from polymarket.rag.reranker import CrossEncoderReranker, DEFAULT_RERANK_MODEL


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
    parser.add_argument(
        "--rerank",
        action="store_true",
        default=False,
        help="Apply cross-encoder reranking after retrieval (requires --hybrid).",
    )
    parser.add_argument(
        "--rerank-top-n",
        type=int,
        default=50,
        help="Number of fused results to rerank (default 50).",
    )
    parser.add_argument(
        "--rerank-model",
        default=DEFAULT_RERANK_MODEL,
        help="Cross-encoder model name for reranking.",
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
    # --- KnowledgeStore (RIS) flags ---
    parser.add_argument(
        "--knowledge-store",
        dest="knowledge_store",
        default=None,
        metavar="PATH",
        help=(
            "Path to KnowledgeStore SQLite DB. When provided, enables KS as "
            "third retrieval source in hybrid mode (requires --hybrid). "
            "Special value 'default' resolves to kb/rag/knowledge/knowledge.sqlite3."
        ),
    )
    parser.add_argument(
        "--source-family",
        dest="source_family",
        default=None,
        help=(
            "Filter KS claims by source_family (e.g. 'book_foundational', "
            "'wallet_analysis', 'news'). Only effective when --knowledge-store is active."
        ),
    )
    parser.add_argument(
        "--min-freshness",
        dest="min_freshness",
        type=float,
        default=None,
        metavar="FLOAT",
        help=(
            "Minimum freshness modifier [0,1] for KS claims. Claims below this "
            "threshold are excluded. Only effective when --knowledge-store is active."
        ),
    )
    parser.add_argument(
        "--evidence-mode",
        dest="evidence_mode",
        action="store_true",
        default=False,
        help=(
            "When set, KS-sourced results include enriched provenance/contradiction "
            "annotations as top-level keys in the output (provenance_docs, "
            "contradiction_summary, staleness_note, lifecycle, is_contradicted)."
        ),
    )
    parser.add_argument(
        "--top-k-knowledge",
        dest="top_k_knowledge",
        type=int,
        default=25,
        help="Number of KnowledgeStore claim candidates for RRF fusion (default 25).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.k <= 0:
        print("Error: --k must be positive.")
        return 1

    # Resolve --knowledge-store path
    knowledge_store_path = None
    if args.knowledge_store is not None:
        from pathlib import Path as _Path
        if args.knowledge_store == "default":
            knowledge_store_path = DEFAULT_KNOWLEDGE_DB_PATH
        else:
            knowledge_store_path = _Path(args.knowledge_store)
        # Guard: requires --hybrid
        if not args.hybrid:
            print("Error: --knowledge-store requires --hybrid mode.")
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

        # Build reranker if requested
        reranker = None
        if args.rerank:
            if not args.hybrid:
                print("Warning: --rerank is most useful with --hybrid. Proceeding anyway.")
            reranker = CrossEncoderReranker(
                model_name=args.rerank_model,
                device=args.device,
                cache_folder="kb/rag/models",
            )

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
            reranker=reranker,
            rerank_top_n=args.rerank_top_n,
            knowledge_store_path=knowledge_store_path,
            source_family=args.source_family,
            min_freshness=args.min_freshness,
            top_k_knowledge=args.top_k_knowledge,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    # Determine mode string
    if args.hybrid:
        ks_suffix = "+knowledge-store" if knowledge_store_path is not None else ""
        mode = f"hybrid{ks_suffix}+rerank" if args.rerank else f"hybrid{ks_suffix}"
    elif args.lexical_only:
        mode = "lexical"
    else:
        mode = "vector+rerank" if args.rerank else "vector"

    # Post-process: evidence-mode promotes KS metadata fields to top-level
    if args.evidence_mode and knowledge_store_path is not None:
        _ks_fields = (
            "provenance_docs",
            "contradiction_summary",
            "staleness_note",
            "lifecycle",
            "is_contradicted",
        )
        promoted_results = []
        for r in results:
            meta = r.get("metadata", {})
            if meta.get("source") == "knowledge_store":
                r = dict(r)  # shallow copy
                for field in _ks_fields:
                    if field in meta:
                        r[field] = meta[field]
            promoted_results.append(r)
        results = promoted_results

    ks_path_str = None
    if knowledge_store_path is not None:
        from pathlib import Path as _Path
        ks_path_str = str(_Path(knowledge_store_path).resolve())

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
        "knowledge_store": {
            "active": knowledge_store_path is not None,
            "path": ks_path_str,
            "source_family": args.source_family,
            "min_freshness": args.min_freshness,
        },
        "results": results,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
