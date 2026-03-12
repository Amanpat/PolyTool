#!/usr/bin/env python3
"""Re-execute RAG queries from a bundle's rag_queries.json and write results back.

Usage:
    python -m polytool rag-run --rag-queries <bundle_dir>/rag_queries.json
    python -m polytool rag-run --rag-queries <path>/rag_queries.json --out <path>/rag_queries_new.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket.rag.defaults import RAG_DEFAULT_COLLECTION, RAG_DEFAULT_PERSIST_DIR

try:
    from polymarket.rag.embedder import SentenceTransformerEmbedder
    from polymarket.rag.query import query_index
    from polymarket.rag.reranker import CrossEncoderReranker
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

# Fallback defaults if RAG not importable (mirrors llm_bundle.py defaults)
_DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_DEFAULT_COLLECTION = RAG_DEFAULT_COLLECTION
_DEFAULT_PERSIST_DIR = RAG_DEFAULT_PERSIST_DIR.as_posix()


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_rag_queries(path: Path) -> List[Dict[str, Any]]:
    """Load rag_queries.json. Expects a JSON array of query objects."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(
            f"Expected a JSON array in {path}, got {type(raw).__name__}. "
            "Only the list format produced by llm-bundle is supported."
        )
    return raw


def _load_bundle_settings(bundle_manifest_path: Optional[Path]) -> Dict[str, Any]:
    """Load rag_query_settings from bundle_manifest.json, falling back to safe defaults."""
    defaults: Dict[str, Any] = {
        "model": _DEFAULT_EMBED_MODEL,
        "rerank_model": _DEFAULT_RERANK_MODEL,
        "collection": _DEFAULT_COLLECTION,
        "persist_dir": _DEFAULT_PERSIST_DIR,
        "device": "auto",
        "top_k_vector": 25,
        "top_k_lexical": 25,
        "rrf_k": 60,
        "rerank_top_n": 50,
    }
    if bundle_manifest_path is None or not bundle_manifest_path.exists():
        return defaults
    try:
        payload = json.loads(bundle_manifest_path.read_text(encoding="utf-8"))
        rag_settings = payload.get("rag_query_settings") or {}
        return {**defaults, **{k: v for k, v in rag_settings.items() if v is not None}}
    except (json.JSONDecodeError, OSError):
        return defaults


def _parse_mode(mode: str):
    """Parse mode string into (hybrid, lexical_only, use_rerank) booleans."""
    mode_lower = mode.lower()
    lexical_only = mode_lower == "lexical"
    hybrid = "hybrid" in mode_lower and not lexical_only
    use_rerank = "rerank" in mode_lower
    return hybrid, lexical_only, use_rerank


def _execute_queries(
    queries: List[Dict[str, Any]],
    settings: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Execute each query entry using the provided settings and return updated entries.

    Designed to be monkeypatched in tests.
    """
    if not _RAG_AVAILABLE:
        executed_at = _utcnow_str()
        return [
            {
                **entry,
                "results": [],
                "execution_status": "not_executed",
                "execution_reason": "rag_unavailable",
                "executed_at_utc": executed_at,
            }
            for entry in queries
        ]

    model = settings.get("model", _DEFAULT_EMBED_MODEL)
    device = settings.get("device", "auto")
    rerank_model = settings.get("rerank_model", _DEFAULT_RERANK_MODEL)
    persist_dir = settings.get("persist_dir", _DEFAULT_PERSIST_DIR)
    collection = settings.get("collection", _DEFAULT_COLLECTION)
    top_k_vector = int(settings.get("top_k_vector", 25))
    top_k_lexical = int(settings.get("top_k_lexical", 25))
    rrf_k = int(settings.get("rrf_k", 60))
    rerank_top_n = int(settings.get("rerank_top_n", 50))

    embedder = SentenceTransformerEmbedder(model_name=model, device=device)

    # Build reranker once and share across all queries
    reranker_cache: Dict[bool, Optional[Any]] = {}

    def _get_reranker(use_rerank: bool) -> Optional[Any]:
        if use_rerank not in reranker_cache:
            if use_rerank:
                reranker_cache[use_rerank] = CrossEncoderReranker(
                    model_name=rerank_model,
                    device=device,
                    cache_folder="kb/rag/models",
                )
            else:
                reranker_cache[use_rerank] = None
        return reranker_cache[use_rerank]

    executed_at = _utcnow_str()
    updated: List[Dict[str, Any]] = []

    for entry in queries:
        question = entry.get("question", "")
        k = int(entry.get("k", 8))
        mode_str = entry.get("mode", "hybrid+rerank")
        filters = entry.get("filters") or {}

        user_slug = filters.get("user_slug")
        private_only = bool(filters.get("private_only", True)) and not bool(filters.get("public_only", False))
        public_only = bool(filters.get("public_only", False))
        prefixes = filters.get("prefix_backstop") or None  # None disables prefix filter
        include_archive = bool(filters.get("include_archive", False))
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        doc_types = filters.get("doc_types")

        hybrid, lexical_only, use_rerank = _parse_mode(mode_str)

        try:
            reranker = _get_reranker(use_rerank)
            results = query_index(
                question=question,
                embedder=embedder,
                k=k,
                persist_directory=persist_dir,
                collection_name=collection,
                filter_prefixes=prefixes,
                user_slug=user_slug,
                doc_types=doc_types,
                private_only=private_only,
                public_only=public_only,
                date_from=date_from,
                date_to=date_to,
                include_archive=include_archive,
                hybrid=hybrid,
                lexical_only=lexical_only,
                top_k_vector=top_k_vector,
                top_k_lexical=top_k_lexical,
                rrf_k=rrf_k,
                reranker=reranker,
                rerank_top_n=rerank_top_n,
            )
            updated.append({
                **entry,
                "results": results,
                "execution_status": "executed",
                "execution_reason": None if results else "no_matches_under_filters",
                "executed_at_utc": executed_at,
            })
        except RuntimeError as exc:
            updated.append({
                **entry,
                "results": [],
                "execution_status": "error",
                "execution_reason": str(exc),
                "executed_at_utc": executed_at,
            })

    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Re-execute RAG queries from a bundle's rag_queries.json and write results back. "
            "Run after 'polytool rag-index' to populate query results for a bundle."
        ),
    )
    parser.add_argument(
        "--rag-queries",
        required=True,
        metavar="PATH",
        help="Path to rag_queries.json produced by llm-bundle.",
    )
    parser.add_argument(
        "--bundle-manifest",
        metavar="PATH",
        help=(
            "Path to bundle_manifest.json for RAG settings (model, collection, persist_dir). "
            "Defaults to bundle_manifest.json in the same directory as --rag-queries."
        ),
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help=(
            "Output path. Defaults to overwriting --rag-queries in place. "
            "Use a different path to keep the original."
        ),
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    rag_queries_path = Path(args.rag_queries)
    if not rag_queries_path.exists():
        print(f"Error: not found: {rag_queries_path}", file=sys.stderr)
        return 1

    # Auto-locate bundle_manifest.json in same directory
    if args.bundle_manifest:
        bundle_manifest_path: Optional[Path] = Path(args.bundle_manifest)
    else:
        bundle_manifest_path = rag_queries_path.parent / "bundle_manifest.json"
        if not bundle_manifest_path.exists():
            bundle_manifest_path = None

    out_path = Path(args.out) if args.out else rag_queries_path

    # Load queries
    try:
        queries = _load_rag_queries(rag_queries_path)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Error reading {rag_queries_path}: {exc}", file=sys.stderr)
        return 1

    if not queries:
        print("Warning: rag_queries.json contains no queries. Nothing to execute.")
        return 0

    # Load RAG settings from manifest
    settings = _load_bundle_settings(bundle_manifest_path)
    if bundle_manifest_path and bundle_manifest_path.exists():
        print(f"Settings from: {bundle_manifest_path}")
    else:
        print("Warning: bundle_manifest.json not found; using default RAG settings.")
    print(f"  collection={settings['collection']}  persist_dir={settings['persist_dir']}")

    # Check RAG availability before executing
    if not _RAG_AVAILABLE:
        print(
            "Error: RAG library not installed. Run:  pip install 'polytool[rag]'",
            file=sys.stderr,
        )
        # Still write explicit not_executed status so file is not silently stale
        updated = [
            {
                **q,
                "results": [],
                "execution_status": "not_executed",
                "execution_reason": "rag_unavailable",
                "executed_at_utc": _utcnow_str(),
            }
            for q in queries
        ]
        out_path.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote {len(updated)} not_executed entries to: {out_path}")
        return 1

    # Execute queries
    updated = _execute_queries(queries, settings)

    # Write results
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(updated, indent=2, sort_keys=True), encoding="utf-8")

    # Summary
    n_executed = sum(1 for q in updated if q.get("execution_status") == "executed")
    n_with_results = sum(1 for q in updated if q.get("results"))
    n_empty = n_executed - n_with_results
    n_errors = sum(1 for q in updated if q.get("execution_status") == "error")
    n_not_executed = sum(1 for q in updated if q.get("execution_status") == "not_executed")

    print(
        f"rag-run: {len(updated)} queries — "
        f"{n_executed} executed, {n_with_results} with results, "
        f"{n_empty} empty, {n_errors} errors, {n_not_executed} not_executed"
    )
    if n_empty > 0:
        print(
            f"  {n_empty} query/queries returned no matches under the stored filters. "
            "Run 'polytool rag-index' to ensure the index is fresh, then retry."
        )
    print(f"Output: {out_path}")
    return 0 if n_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
