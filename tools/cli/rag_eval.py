#!/usr/bin/env python3
"""Offline RAG evaluation harness CLI."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
from polymarket.rag.eval import load_suite, run_eval, write_report
from polymarket.rag.reranker import CrossEncoderReranker, DEFAULT_RERANK_MODEL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline RAG evaluation harness.")
    parser.add_argument("--suite", required=True, help="Path to JSONL eval suite.")
    parser.add_argument("--k", type=int, default=8, help="Recall/MRR cutoff (default 8).")
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
    parser.add_argument(
        "--output-dir",
        default="kb/rag/eval/reports",
        help="Base directory for eval reports.",
    )
    parser.add_argument(
        "--top-k-vector",
        type=int,
        default=25,
        help="Number of vector candidates for hybrid fusion.",
    )
    parser.add_argument(
        "--top-k-lexical",
        type=int,
        default=25,
        help="Number of lexical candidates for hybrid fusion.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF fusion constant (higher reduces rank impact).",
    )
    parser.add_argument(
        "--rerank-model",
        default=None,
        help="Cross-encoder model for hybrid+rerank mode. If omitted, hybrid+rerank is skipped.",
    )
    parser.add_argument(
        "--rerank-top-n",
        type=int,
        default=50,
        help="Number of fused results to rerank in eval (default 50).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.k <= 0:
        print("Error: --k must be positive.")
        return 1

    # Load suite
    try:
        suite = load_suite(args.suite)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Loaded {len(suite)} eval cases from {args.suite}")

    # Build embedder
    try:
        embedder = SentenceTransformerEmbedder(model_name=args.model, device=args.device)
    except RuntimeError as exc:
        print(f"Warning: Could not load embedder ({exc}). Vector/hybrid modes will be skipped.")
        embedder = None

    # Build reranker if requested
    reranker = None
    if args.rerank_model:
        try:
            reranker = CrossEncoderReranker(
                model_name=args.rerank_model,
                device=args.device,
                cache_folder="kb/rag/models",
            )
        except RuntimeError as exc:
            print(f"Warning: Could not load reranker ({exc}). hybrid+rerank mode will be skipped.")

    # Run eval
    try:
        report = run_eval(
            suite,
            k=args.k,
            embedder=embedder,
            persist_directory=args.persist_dir,
            collection_name=args.collection,
            top_k_vector=args.top_k_vector,
            top_k_lexical=args.top_k_lexical,
            rrf_k=args.rrf_k,
            reranker=reranker,
            rerank_top_n=args.rerank_top_n,
            suite_path=args.suite,
        )
    except Exception as exc:
        print(f"Error during eval: {exc}")
        return 1

    # Write report
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir = os.path.join(args.output_dir, ts)
    try:
        json_path, md_path = write_report(report, report_dir)
    except Exception as exc:
        print(f"Error writing report: {exc}")
        return 1

    # Console summary
    print()
    print(f"{'Mode':<15} {'Recall@' + str(args.k):<12} {'MRR@' + str(args.k):<10} {'Violations':<12} {'Latency (ms)':<14}")
    print("-" * 63)

    has_violations = False
    for mode_name in ("vector", "lexical", "hybrid", "hybrid+rerank"):
        agg = report.modes.get(mode_name)
        if agg is None:
            continue
        if agg.total_scope_violations > 0:
            has_violations = True
        print(
            f"{mode_name:<15} "
            f"{agg.mean_recall_at_k:<12.3f} "
            f"{agg.mean_mrr_at_k:<10.3f} "
            f"{agg.total_scope_violations:<12} "
            f"{agg.mean_latency_ms:<14.1f}"
        )

    print()
    print(f"Report: {json_path}")
    print(f"Summary: {md_path}")

    if has_violations:
        print("\nScope violations detected. See report for details.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
