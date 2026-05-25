"""L2 academic corpus query CLI (research-query).

Queries the KnowledgeStore academic corpus using multi-angle query planning.
Only returns results from Marker/RAG-ready papers (body_source=marker and
body_length >= 5000). The ingest gate enforces this for new rows; the query path
also re-checks metadata for legacy rows.

Usage:
  python -m polytool research-query --question "market microstructure"
  python -m polytool research-query --question "sports betting inefficiencies" --k 5
  python -m polytool research-query --question "prediction market strategies" --step-back
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the academic corpus (Marker/RAG-ready papers only). "
            "Returns ranked paper-level citations from the KnowledgeStore. "
            "L2 of the RIS academic pipeline."
        )
    )
    parser.add_argument(
        "--question",
        required=True,
        help="Research question to answer.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=8,
        help="Maximum paper citations to return (default 8).",
    )
    parser.add_argument(
        "--max-angles",
        type=int,
        default=3,
        dest="max_angles",
        help="Maximum query angles for multi-angle retrieval (default 3).",
    )
    parser.add_argument(
        "--step-back",
        action="store_true",
        default=False,
        dest="step_back",
        help="Include a step-back query for broader context retrieval.",
    )
    parser.add_argument(
        "--knowledge-store",
        dest="knowledge_store",
        default=None,
        metavar="PATH",
        help=(
            "Path to KnowledgeStore SQLite DB. "
            "Default: kb/rag/knowledge/knowledge.sqlite3"
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.k <= 0:
        print("Error: --k must be positive.", file=sys.stderr)
        return 1
    if args.max_angles < 1:
        print("Error: --max-angles must be >= 1.", file=sys.stderr)
        return 1

    # Resolve KS path
    from packages.polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH
    ks_path: Path = (
        Path(args.knowledge_store) if args.knowledge_store else DEFAULT_KNOWLEDGE_DB_PATH
    )

    # Guard: KS not found
    if not ks_path.exists():
        payload = {
            "question": args.question,
            "citations": [],
            "marker_only_count": 0,
            "total_claims_found": 0,
            "had_fallback": True,
            "retrieval_mode": "lexical",
            "semantic_unavailable_reason": None,
            "warning": (
                f"KnowledgeStore not found at {ks_path}. "
                "Run research-ingest or research-acquire to populate the store first."
            ),
            "query_angles": [],
        }
        print(json.dumps(payload, indent=2))
        return 0

    from packages.research.synthesis.academic_query import query_academic_corpus

    result = query_academic_corpus(
        args.question,
        ks_path=ks_path,
        k=args.k,
        max_query_angles=args.max_angles,
        include_step_back=args.step_back,
    )

    payload = {
        "question": result.question,
        "citations": [
            {
                "title": c.title,
                "arxiv_id": c.arxiv_id,
                "source_url": c.source_url,
                "best_snippet": c.best_snippet,
                "paper_score": c.paper_score,
                "body_source": c.body_source,
                "claim_count": c.claim_count,
            }
            for c in result.citations
        ],
        "marker_only_count": result.marker_only_count,
        "total_claims_found": result.total_claims_found,
        "had_fallback": result.had_fallback,
        "retrieval_mode": result.retrieval_mode,
        "semantic_unavailable_reason": result.semantic_unavailable_reason,
        "warning": result.warning,
        "query_angles": result.query_angles,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
