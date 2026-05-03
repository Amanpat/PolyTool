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


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FILTER_CONFIG_PATH = _REPO_ROOT / "config" / "research_relevance_filter_v1.json"


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _score_candidate_for_filter(title: str, abstract: str, source_id: str, args) -> object:
    """Score a candidate against the relevance filter.

    Returns a FilterDecision if prefetch_filter_mode != 'off', else None.
    Returns None and prints a warning if imports fail.
    """
    if getattr(args, "prefetch_filter_mode", "off") == "off":
        return None
    try:
        from packages.research.relevance_filter.scorer import (
            CandidateInput,
            RelevanceScorer,
            load_filter_config,
        )
        config_path = getattr(args, "prefetch_filter_config", None)
        filter_cfg = load_filter_config(Path(config_path) if config_path else None)
        scorer = RelevanceScorer(filter_cfg)
        candidate = CandidateInput(title=title, abstract=abstract, source_id=source_id)
        return scorer.score(candidate)
    except Exception as exc:
        print(f"WARNING: prefetch filter scoring failed: {exc}", file=sys.stderr)
        return None


def _write_to_review_queue(decision, source_url: str, abstract: str, queue_dir: str):
    """Write a REVIEW-decision candidate to the hold-review queue.

    Returns
    -------
    tuple[bool, Optional[str]]
        (True, None) on successful write (including idempotent already-queued).
        (False, error_message) if the write raised an exception.
    """
    try:
        from packages.research.relevance_filter.queue_store import (
            ReviewQueueStore,
            candidate_id_from_url,
        )
        queue_path = Path(queue_dir) / "review_queue.jsonl"
        store = ReviewQueueStore(queue_path)
        record = {
            "candidate_id": candidate_id_from_url(source_url),
            "source_url": source_url,
            "title": decision.candidate_title,
            "abstract": abstract,
            "score": decision.score,
            "raw_score": decision.raw_score,
            "decision": decision.decision,
            "reason_codes": decision.reason_codes,
            "matched_terms": decision.matched_terms,
            "allow_threshold": decision.allow_threshold,
            "review_threshold": decision.review_threshold,
            "config_version": decision.config_version,
        }
        written = store.enqueue(record)
        if not written:
            print(
                f"[filter:hold-review] already queued: {source_url}",
                file=sys.stderr,
            )
        return True, None
    except Exception as exc:
        return False, str(exc)


def _write_filter_audit(decision, source_url: str, enforced: bool, audit_dir: str) -> None:
    """Write a JSONL audit record for the filter decision. Non-fatal on failure."""
    try:
        audit_path = Path(audit_dir) / "filter_decisions.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": _utcnow_iso(),
            "source_id": decision.source_id,
            "source_url": source_url,
            "title": decision.candidate_title,
            "decision": decision.decision,
            "score": decision.score,
            "raw_score": decision.raw_score,
            "allow_threshold": decision.allow_threshold,
            "review_threshold": decision.review_threshold,
            "reason_codes": decision.reason_codes,
            "matched_terms": decision.matched_terms,
            "config_version": decision.config_version,
            "input_fields_used": decision.input_fields_used,
            "enforced": enforced,
        }
        with audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        print(f"WARNING: failed to write filter audit record: {exc}", file=sys.stderr)


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
    parser.add_argument(
        "--prefetch-filter-mode",
        dest="prefetch_filter_mode",
        default="off",
        choices=["off", "dry-run", "enforce", "hold-review"],
        help=(
            "Relevance pre-fetch filter mode (default: off). "
            "dry-run: score and log but always ingest. "
            "enforce: skip REJECT; ingest REVIEW with audit flag. "
            "hold-review: ingest ALLOW only; skip REJECT; queue REVIEW without ingesting."
        ),
    )
    parser.add_argument(
        "--prefetch-filter-config",
        dest="prefetch_filter_config",
        default=None,
        metavar="PATH",
        help="Path to relevance filter config JSON (default: auto-discover config/research_relevance_filter_v1.json).",
    )
    parser.add_argument(
        "--prefetch-review-queue-dir",
        dest="prefetch_review_queue_dir",
        default=None,
        metavar="PATH",
        help="Directory for the hold-review JSONL queue (default: artifacts/research/prefetch_review_queue).",
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

    # --- Step 3.5: Pre-fetch relevance filter ---
    filter_decision = _score_candidate_for_filter(
        title=normalized_title,
        abstract=raw_source.get("abstract") or "",
        source_id=source_id,
        args=args,
    )
    if filter_decision is not None:
        enforced = args.prefetch_filter_mode in ("enforce", "hold-review")
        _write_filter_audit(filter_decision, args.url, enforced, args.review_dir)
        if args.prefetch_filter_mode == "dry-run":
            print(
                f"[filter:dry-run] decision={filter_decision.decision} "
                f"score={filter_decision.score:.4f} "
                f"codes={filter_decision.reason_codes[:3]}",
                file=sys.stderr,
            )
        elif args.prefetch_filter_mode in ("enforce", "hold-review") and filter_decision.decision == "reject":
            if args.output_json:
                print(json.dumps({
                    "source_url": args.url, "source_id": source_id,
                    "filter_decision": filter_decision.decision,
                    "filter_score": filter_decision.score,
                    "filter_reason_codes": filter_decision.reason_codes,
                    "skipped": True,
                }, indent=2))
            else:
                print(
                    f"[filter:{args.prefetch_filter_mode}] SKIPPED (reject) | score={filter_decision.score:.4f} "
                    f"| codes={filter_decision.reason_codes[:3]}"
                )
            return 0  # Not an error — just filtered out
        elif args.prefetch_filter_mode == "hold-review" and filter_decision.decision == "review":
            queue_dir = getattr(args, "prefetch_review_queue_dir", None) or "artifacts/research/prefetch_review_queue"
            queue_ok, queue_err = _write_to_review_queue(
                filter_decision,
                args.url,
                raw_source.get("abstract") or "",
                queue_dir,
            )
            if not queue_ok:
                print(f"WARNING: hold-review queue write failed: {queue_err}", file=sys.stderr)
            if args.output_json:
                out = {
                    "source_url": args.url, "source_id": source_id,
                    "filter_decision": filter_decision.decision,
                    "filter_score": filter_decision.score,
                    "filter_reason_codes": filter_decision.reason_codes,
                    "queued_for_review": queue_ok,
                    "skipped": True,
                }
                if not queue_ok:
                    out["queue_error"] = queue_err
                print(json.dumps(out, indent=2))
            else:
                if queue_ok:
                    print(
                        f"[filter:hold-review] QUEUED (review) | score={filter_decision.score:.4f} "
                        f"| codes={filter_decision.reason_codes[:3]}"
                    )
                else:
                    print(
                        f"[filter:hold-review] QUEUE WRITE FAILED (held out) | score={filter_decision.score:.4f} "
                        f"| error={queue_err}"
                    )
            return 0  # Held for operator review — not ingested regardless of queue write failure

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

                filter_decision = _score_candidate_for_filter(
                    title=normalized_title,
                    abstract=raw_source.get("abstract") or "",
                    source_id=source_id,
                    args=args,
                )
                if filter_decision is not None:
                    enforced = args.prefetch_filter_mode in ("enforce", "hold-review")
                    _write_filter_audit(filter_decision, paper_url, enforced, args.review_dir)
                    if (
                        args.prefetch_filter_mode in ("enforce", "hold-review")
                        and filter_decision.decision == "reject"
                    ):
                        paper_result = {
                            "source_url": paper_url,
                            "source_id": source_id,
                            "normalized_title": normalized_title,
                            "filter_decision": "reject",
                            "filter_score": filter_decision.score,
                            "filter_reason_codes": filter_decision.reason_codes,
                            "skipped_by_filter": True,
                            "rejected": True,
                            "reject_reason": "filter:reject",
                        }
                        results_output.append(paper_result)
                        if not args.output_json:
                            print(
                                f"  [filter:{args.prefetch_filter_mode}] SKIPPED {normalized_title or paper_url} "
                                f"| score={filter_decision.score:.4f}"
                            )
                        continue  # Skip ingest for this paper
                    elif (
                        args.prefetch_filter_mode == "hold-review"
                        and filter_decision.decision == "review"
                    ):
                        queue_dir = getattr(args, "prefetch_review_queue_dir", None) or "artifacts/research/prefetch_review_queue"
                        queue_ok, queue_err = _write_to_review_queue(
                            filter_decision,
                            paper_url,
                            raw_source.get("abstract") or "",
                            queue_dir,
                        )
                        if not queue_ok:
                            print(
                                f"WARNING: hold-review queue write failed for {paper_url}: {queue_err}",
                                file=sys.stderr,
                            )
                        paper_result = {
                            "source_url": paper_url,
                            "source_id": source_id,
                            "normalized_title": normalized_title,
                            "filter_decision": "review",
                            "filter_score": filter_decision.score,
                            "filter_reason_codes": filter_decision.reason_codes,
                            "queued_for_review": queue_ok,
                            "skipped_by_filter": True,
                            "rejected": True,
                            "reject_reason": "filter:hold-review",
                        }
                        if not queue_ok:
                            paper_result["queue_error"] = queue_err
                        results_output.append(paper_result)
                        if not args.output_json:
                            if queue_ok:
                                print(
                                    f"  [filter:hold-review] QUEUED {normalized_title or paper_url} "
                                    f"| score={filter_decision.score:.4f}"
                                )
                            else:
                                print(
                                    f"  [filter:hold-review] QUEUE WRITE FAILED {normalized_title or paper_url} "
                                    f"| error={queue_err}"
                                )
                        continue  # Skip ingest; held for operator review regardless of queue write failure

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
