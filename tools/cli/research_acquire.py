"""CLI entrypoint for RIS Phase 5 live source acquisition.

Fetches a source from a URL, normalizes metadata, checks dedup, caches the
raw payload, ingests into the knowledge store, and writes an acquisition
review record.

Usage:
  python -m polytool research-acquire --url https://arxiv.org/abs/2301.12345 --source-family academic --no-eval --json
  python -m polytool research-acquire --url https://github.com/polymarket/py-clob-client --source-family github --dry-run --json
  python -m polytool research-acquire --url https://blog.example.com/post --source-family blog --no-eval

Options:
  --url URL                   Source URL to fetch (required)
  --source-family FAMILY      Source family: academic, github, blog, news (required)
  --cache-dir PATH            Raw source cache directory (default: artifacts/research/raw_source_cache)
  --review-dir PATH           Acquisition review JSONL directory (default: artifacts/research/acquisition_reviews)
  --db PATH                   Knowledge store database path (default: system default)
  --no-eval                   Skip the evaluation gate (hard-stop checks still run)
  --dry-run                   Fetch and normalize only; do not cache, ingest, or write review
  --json                      Output JSON to stdout instead of human-readable text
  --provider NAME             Evaluation provider: manual, ollama (default: manual)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def main(argv: list) -> int:
    """Acquire a source from URL and ingest into the knowledge store.

    Returns:
        0 on success (including dry-run)
        1 on argument error
        2 on fetch error or unexpected exception
    """
    parser = argparse.ArgumentParser(
        prog="research-acquire",
        description="Fetch a source from a URL and ingest it into the RIS knowledge store.",
    )
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Source URL to fetch (required).",
    )
    parser.add_argument(
        "--source-family",
        metavar="FAMILY",
        dest="source_family",
        choices=["academic", "github", "blog", "news"],
        help="Source family: academic, github, blog, or news (required).",
    )
    parser.add_argument(
        "--cache-dir",
        metavar="PATH",
        dest="cache_dir",
        default="artifacts/research/raw_source_cache",
        help="Directory for raw-source cache (default: artifacts/research/raw_source_cache).",
    )
    parser.add_argument(
        "--review-dir",
        metavar="PATH",
        dest="review_dir",
        default="artifacts/research/acquisition_reviews",
        help="Directory for acquisition review JSONL (default: artifacts/research/acquisition_reviews).",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default=None,
        help="Custom knowledge store path (default: system default).",
    )
    parser.add_argument(
        "--no-eval",
        dest="no_eval",
        action="store_true",
        help="Skip evaluation gate (hard-stop checks still run).",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Fetch and normalize only; do not cache, ingest, or write review.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output JSON to stdout.",
    )
    parser.add_argument(
        "--provider",
        metavar="NAME",
        default="manual",
        choices=["manual", "ollama"],
        help="Evaluation provider (default: manual).",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Validate required arguments
    if not args.url:
        print("Error: --url is required.", file=sys.stderr)
        return 1
    if not args.source_family:
        print("Error: --source-family is required.", file=sys.stderr)
        return 1

    acquired_at = _utcnow_iso()

    # --- Step 1: Fetch raw source dict ---
    try:
        from packages.research.ingestion.fetchers import FetchError, get_fetcher
        fetcher = get_fetcher(args.source_family)
        raw_source = fetcher.fetch(args.url)
    except Exception as exc:
        from packages.research.ingestion.fetchers import FetchError
        print(f"Error: fetch failed: {exc}", file=sys.stderr)
        return 2

    # --- Step 2: Normalize and compute IDs ---
    try:
        from packages.research.ingestion.normalize import (
            canonicalize_url,
            extract_canonical_ids,
            normalize_metadata,
        )
        from packages.research.ingestion.source_cache import make_source_id

        # Determine the primary URL field for this family
        if args.source_family == "github":
            primary_url = raw_source.get("repo_url", args.url)
        else:
            primary_url = raw_source.get("url", args.url)

        canonical_url = canonicalize_url(primary_url)
        source_id = make_source_id(canonical_url)

        # Extract canonical IDs from body text + URL
        body_field = raw_source.get("abstract") or raw_source.get("readme_text") or raw_source.get("body_text") or ""
        canonical_ids = extract_canonical_ids(str(body_field), canonical_url)

        # Normalized title
        meta = normalize_metadata(raw_source, args.source_family)
        normalized_title = meta.title or ""

    except Exception as exc:
        print(f"Error: normalization failed: {exc}", file=sys.stderr)
        return 2

    # --- Step 3: Dedup check ---
    try:
        from packages.research.ingestion.source_cache import RawSourceCache
        cache = RawSourceCache(args.cache_dir)
        dedup_status = "cached" if cache.has_raw(source_id, args.source_family) else "new"
    except Exception:
        dedup_status = "new"
        cache = None

    # --- Step 4: Dry-run exit ---
    if args.dry_run:
        output = {
            "source_url": args.url,
            "source_id": source_id,
            "source_family": args.source_family,
            "normalized_title": normalized_title,
            "dedup_status": dedup_status,
            "dry_run": True,
        }
        if args.output_json:
            print(json.dumps(output, indent=2))
        else:
            print(
                f"[dry-run] {args.source_family} | {normalized_title or args.url} "
                f"| id={source_id} | dedup={dedup_status}"
            )
        return 0

    # --- Step 5: Full flow (cache + ingest + review) ---
    cached_path = ""
    doc_id = ""
    chunk_count = 0
    rejected = False
    reject_reason = None
    error_str = None

    store = None
    try:
        from packages.research.ingestion.source_cache import RawSourceCache
        from packages.research.ingestion.pipeline import IngestPipeline
        from packages.polymarket.rag.knowledge_store import (
            KnowledgeStore,
            DEFAULT_KNOWLEDGE_DB_PATH,
        )

        # Cache raw payload
        cache_obj = RawSourceCache(args.cache_dir)
        cached_path_obj = cache_obj.cache_raw(source_id, raw_source, args.source_family)
        cached_path = str(cached_path_obj)

        # Build KnowledgeStore
        db_path = args.db if args.db else DEFAULT_KNOWLEDGE_DB_PATH
        store = KnowledgeStore(db_path)

        # Build evaluator (or None if --no-eval)
        evaluator = None
        if not args.no_eval:
            from packages.research.evaluation.evaluator import DocumentEvaluator
            from packages.research.evaluation.providers import get_provider
            provider = get_provider(args.provider)
            evaluator = DocumentEvaluator(provider=provider)

        pipeline = IngestPipeline(store=store, evaluator=evaluator)

        # Ingest via adapter
        result = pipeline.ingest_external(
            raw_source,
            args.source_family,
            cache=cache_obj,
        )
        doc_id = result.doc_id
        chunk_count = result.chunk_count
        rejected = result.rejected
        reject_reason = result.reject_reason

    except Exception as exc:
        error_str = str(exc)
        print(f"Error: ingest failed: {exc}", file=sys.stderr)
        # Still write the review record with error info
    finally:
        if store is not None:
            store.close()

    # --- Step 6: Write acquisition review ---
    try:
        from packages.research.ingestion.acquisition_review import (
            AcquisitionRecord,
            AcquisitionReviewWriter,
        )
        record = AcquisitionRecord(
            acquired_at=acquired_at,
            source_url=args.url,
            source_family=args.source_family,
            source_id=source_id,
            canonical_ids=canonical_ids,
            cached_path=cached_path,
            normalized_title=normalized_title,
            dedup_status=dedup_status,
            error=error_str or (reject_reason if rejected else None),
        )
        writer = AcquisitionReviewWriter(args.review_dir)
        writer.write_review(record)
    except Exception as exc:
        print(f"Warning: failed to write acquisition review: {exc}", file=sys.stderr)

    # If ingestion itself errored out, return 2
    if error_str:
        return 2

    # --- Step 7: Output ---
    output = {
        "source_url": args.url,
        "source_id": source_id,
        "source_family": args.source_family,
        "normalized_title": normalized_title,
        "dedup_status": dedup_status,
        "cached_path": cached_path,
        "doc_id": doc_id,
        "chunk_count": chunk_count,
        "rejected": rejected,
        "reject_reason": reject_reason,
    }

    if args.output_json:
        print(json.dumps(output, indent=2))
    else:
        if rejected:
            print(f"Rejected | reason={reject_reason} | id={source_id}")
        else:
            short_id = doc_id[:12] + "..." if doc_id else "(none)"
            print(
                f"Acquired: {normalized_title or args.url} "
                f"| family={args.source_family} | source_id={source_id} "
                f"| doc_id={short_id} | chunks={chunk_count} | dedup={dedup_status}"
            )

    return 0
