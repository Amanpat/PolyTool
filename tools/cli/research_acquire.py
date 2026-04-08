"""CLI entrypoint for RIS Phase 5 live source acquisition.

Fetches a source from a URL, normalizes metadata, checks dedup, caches the
raw payload, ingests into the knowledge store, and writes an acquisition
review record.

Usage:
  python -m polytool research-acquire --url https://arxiv.org/abs/2301.12345 --source-family academic --no-eval --json
  python -m polytool research-acquire --url https://github.com/polymarket/py-clob-client --source-family github --dry-run --json
  python -m polytool research-acquire --url https://blog.example.com/post --source-family blog --no-eval
  python -m polytool research-acquire --search "prediction markets microstructure" --source-family academic --no-eval --json
  python -m polytool research-acquire --search "market maker inventory" --max-results 10 --extract-claims --no-eval
  python -m polytool research-acquire --url https://reddit.com/r/polymarket/comments/abc/post --source-family reddit --dry-run --no-eval --json
  python -m polytool research-acquire --url https://www.youtube.com/watch?v=VIDEO_ID --source-family youtube --dry-run --no-eval --json

Options:
  --url URL                   Source URL to fetch (mutually exclusive with --search)
  --search QUERY              ArXiv topic search query (academic family only)
  --max-results N             Max results for --search (default: 5)
  --source-family FAMILY      Source family: academic, github, blog, news, book, reddit, youtube (required)
  --cache-dir PATH            Raw source cache directory (default: artifacts/research/raw_source_cache)
  --review-dir PATH           Acquisition review JSONL directory (default: artifacts/research/acquisition_reviews)
  --db PATH                   Knowledge store database path (default: system default)
  --no-eval                   Skip the evaluation gate (hard-stop checks still run)
  --dry-run                   Fetch and normalize only; do not cache, ingest, or write review
  --json                      Output JSON to stdout instead of human-readable text
  --provider NAME             Evaluation provider: manual, ollama (default: manual)
  --extract-claims            Run claim extraction after ingest (opt-in; non-fatal)
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
    """Acquire a source from URL or topic search and ingest into the knowledge store.

    Returns:
        0 on success (including dry-run)
        1 on argument error
        2 on fetch error or unexpected exception
    """
    parser = argparse.ArgumentParser(
        prog="research-acquire",
        description="Fetch a source from a URL and ingest it into the RIS knowledge store.",
    )
    # --url and --search are alternative input modes
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--url",
        metavar="URL",
        help="Source URL to fetch.",
    )
    input_group.add_argument(
        "--search",
        metavar="QUERY",
        help="ArXiv topic search query (academic family only). "
             "Fetches up to --max-results papers and ingests each one.",
    )
    parser.add_argument(
        "--max-results",
        metavar="N",
        dest="max_results",
        type=int,
        default=5,
        help="Maximum number of results for --search (default: 5).",
    )
    parser.add_argument(
        "--source-family",
        metavar="FAMILY",
        dest="source_family",
        choices=["academic", "github", "blog", "news", "book", "reddit", "youtube"],
        help="Source family: academic, github, blog, news, book, reddit, or youtube (required).",
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
    parser.add_argument(
        "--priority-tier",
        metavar="TIER",
        dest="priority_tier",
        default=None,
        choices=["priority_1", "priority_2", "priority_3", "priority_4"],
        help=(
            "Priority tier for gate thresholds (default: config default, usually priority_3). "
            "priority_1 applies lower threshold (trusted sources); "
            "priority_4 applies higher threshold (low-trust sources)."
        ),
    )
    parser.add_argument(
        "--extract-claims",
        dest="extract_claims",
        action="store_true",
        help="Run claim extraction after ingest (opt-in; non-fatal if extraction fails).",
    )
    parser.add_argument(
        "--run-log",
        dest="run_log",
        metavar="PATH",
        default="artifacts/research/run_log.jsonl",
        help="Path to run log JSONL for health tracking (default: artifacts/research/run_log.jsonl).",
    )

    if not argv:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args(argv)

    # Validate required arguments
    if not args.url and not args.search:
        print("Error: --url or --search is required.", file=sys.stderr)
        return 1
    if not args.source_family:
        print("Error: --source-family is required.", file=sys.stderr)
        return 1

    # --search only works with academic family (LiveAcademicFetcher has search_by_topic)
    if args.search and args.source_family != "academic":
        print(
            f"Error: --search is only supported with --source-family academic "
            f"(got {args.source_family!r}).",
            file=sys.stderr,
        )
        return 1

    # Route to search mode when --search is given
    if args.search:
        return _run_search_mode(args)

    acquired_at = _utcnow_iso()

    # Capture timing for run_log (health surface)
    import time as _time
    _t0 = _time.monotonic()
    _started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

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
            evaluator = DocumentEvaluator(
                provider=provider,
                priority_tier=getattr(args, "priority_tier", None),
            )

        pipeline = IngestPipeline(store=store, evaluator=evaluator)

        # Ingest via adapter
        result = pipeline.ingest_external(
            raw_source,
            args.source_family,
            cache=cache_obj,
            post_ingest_extract=args.extract_claims,
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

    # If ingestion itself errored out, write error run_log record and return 2
    if error_str:
        try:
            from packages.research.monitoring.run_log import RunRecord, append_run
            _duration = _time.monotonic() - _t0
            rec = RunRecord(
                pipeline="research_acquire",
                started_at=_started_at,
                duration_s=_duration,
                accepted=0,
                rejected=0,
                errors=1,
                exit_status="error",
                metadata={"source_family": args.source_family, "source_url": args.url},
            )
            append_run(rec, path=Path(args.run_log))
        except Exception:
            pass  # Non-fatal: health surface, not core pipeline
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

    # Write success run record (non-fatal — health surface, not core pipeline)
    try:
        from packages.research.monitoring.run_log import RunRecord, append_run
        _duration = _time.monotonic() - _t0
        _accepted = 0 if rejected else 1
        _rejected_count = 1 if rejected else 0
        rec = RunRecord(
            pipeline="research_acquire",
            started_at=_started_at,
            duration_s=_duration,
            accepted=_accepted,
            rejected=_rejected_count,
            errors=0,
            exit_status="ok",
            metadata={"source_family": args.source_family, "source_url": args.url},
        )
        append_run(rec, path=Path(args.run_log))
    except Exception:
        pass  # Non-fatal: health surface, not core pipeline

    return 0


# ---------------------------------------------------------------------------
# Search mode: --search QUERY
# ---------------------------------------------------------------------------


def _run_search_mode(args) -> int:
    """Execute ArXiv topic search and ingest each result.

    Only works with --source-family academic (LiveAcademicFetcher has
    search_by_topic; other fetchers do not).

    Returns 0 on success, 2 on fetch error.
    """
    try:
        from packages.research.ingestion.fetchers import FetchError, LiveAcademicFetcher
        fetcher = LiveAcademicFetcher()
        raw_sources = fetcher.search_by_topic(args.search, max_results=args.max_results)
    except Exception as exc:
        print(f"Error: search failed: {exc}", file=sys.stderr)
        return 2

    if not raw_sources:
        msg = f"No results for query: {args.search!r}"
        if args.output_json:
            print(json.dumps({"query": args.search, "results": [], "message": msg}, indent=2))
        else:
            print(msg)
        return 0

    results_output = []
    store = None

    try:
        from packages.research.ingestion.source_cache import RawSourceCache
        from packages.research.ingestion.pipeline import IngestPipeline
        from packages.research.ingestion.normalize import canonicalize_url, normalize_metadata
        from packages.research.ingestion.source_cache import make_source_id
        from packages.polymarket.rag.knowledge_store import (
            KnowledgeStore,
            DEFAULT_KNOWLEDGE_DB_PATH,
        )

        db_path = args.db if args.db else DEFAULT_KNOWLEDGE_DB_PATH
        store = KnowledgeStore(db_path)
        cache_obj = RawSourceCache(args.cache_dir)

        evaluator = None
        if not args.no_eval:
            from packages.research.evaluation.evaluator import DocumentEvaluator
            from packages.research.evaluation.providers import get_provider
            provider = get_provider(args.provider)
            evaluator = DocumentEvaluator(provider=provider)

        pipeline = IngestPipeline(store=store, evaluator=evaluator)

        for raw_source in raw_sources:
            paper_url = raw_source.get("url", "")
            try:
                meta = normalize_metadata(raw_source, "academic")
                normalized_title = meta.title or ""
                canonical_url = canonicalize_url(paper_url) if paper_url else ""
                source_id = make_source_id(canonical_url) if canonical_url else ""

                result = pipeline.ingest_external(
                    raw_source,
                    "academic",
                    cache=cache_obj,
                    post_ingest_extract=args.extract_claims,
                )
                paper_result = {
                    "source_url": paper_url,
                    "source_id": source_id,
                    "normalized_title": normalized_title,
                    "doc_id": result.doc_id,
                    "chunk_count": result.chunk_count,
                    "rejected": result.rejected,
                    "reject_reason": result.reject_reason,
                }
            except Exception as exc:
                paper_result = {
                    "source_url": paper_url,
                    "error": str(exc),
                    "rejected": True,
                }

            results_output.append(paper_result)

            if not args.output_json:
                if paper_result.get("rejected"):
                    reason = paper_result.get("reject_reason") or paper_result.get("error") or "?"
                    print(f"  Rejected: {paper_url} | reason={reason}")
                else:
                    short_id = (
                        paper_result["doc_id"][:12] + "..."
                        if paper_result.get("doc_id")
                        else "(none)"
                    )
                    print(
                        f"  Acquired: {paper_result.get('normalized_title') or paper_url} "
                        f"| doc_id={short_id} | chunks={paper_result.get('chunk_count', 0)}"
                    )

    except Exception as exc:
        print(f"Error: ingest setup failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                pass

    if args.output_json:
        print(
            json.dumps(
                {
                    "query": args.search,
                    "max_results": args.max_results,
                    "result_count": len(results_output),
                    "results": results_output,
                },
                indent=2,
            )
        )
    else:
        accepted = sum(1 for r in results_output if not r.get("rejected"))
        print(
            f"\nSearch complete: {accepted}/{len(results_output)} papers ingested "
            f"for query={args.search!r}"
        )

    return 0
