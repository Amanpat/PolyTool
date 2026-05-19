"""CLI entrypoint for Marker Canonical Academic Parse Queue v0.

Subcommands:
  enqueue    Add one arXiv paper URL / ID to the parse queue
  list       Show queue items (optionally filtered by status)
  process    Process next N pending items using the Marker worker
  counts     Show item counts by status

Usage:
  python -m polytool research-marker-queue enqueue --url 2604.24366
  python -m polytool research-marker-queue enqueue --url https://arxiv.org/abs/2604.24366
  python -m polytool research-marker-queue list
  python -m polytool research-marker-queue list --status pending
  python -m polytool research-marker-queue process --max-items 5 --marker-timeout 900
  python -m polytool research-marker-queue counts
  python -m polytool research-marker-queue counts --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_enqueue(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    try:
        outcome = q.enqueue(
            args.url,
            title=args.title or "",
            force=args.force,
            pdf_url=getattr(args, "pdf_url", "") or "",
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(outcome, indent=2))
    else:
        action = outcome.get("action", "?")
        cid = outcome.get("candidate_id", "?")
        status = outcome.get("status", "?")
        if action == "added":
            print(f"Enqueued: {cid}  (status=pending)")
        elif action == "reset":
            print(f"Reset:    {cid}  (status=pending, attempts=0)")
        else:
            reason = outcome.get("reason", "")
            print(f"Skipped:  {cid}  ({reason})")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    status_filter = args.status if args.status != "all" else None
    records = q.list_queue(status_filter=status_filter)

    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    if not records:
        print("Queue is empty." if not status_filter else f"No items with status={status_filter!r}.")
        return 0

    col_cid = 28
    col_status = 12
    col_att = 5
    col_title = 40
    header = (
        f"  {'candidate_id':<{col_cid}} {'status':<{col_status}} "
        f"{'att':<{col_att}} {'title':<{col_title}}"
    )
    print(header)
    print("  " + "-" * (col_cid + col_status + col_att + col_title + 6))
    for r in records:
        cid = r.get("candidate_id", "?")[:col_cid]
        st = r.get("status", "?")[:col_status]
        att = str(r.get("attempts", 0))[:col_att]
        title = (r.get("title", "") or "")[:col_title]
        print(f"  {cid:<{col_cid}} {st:<{col_status}} {att:<{col_att}} {title:<{col_title}}")
    print()
    print(f"Total: {len(records)} item(s)")
    return 0


def _cmd_process(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts_before = q.get_counts()
    pending = counts_before.get("pending", 0)
    if pending == 0:
        if args.json:
            print(json.dumps({"processed": [], "exit_code": 0, "message": "no pending items"}))
        else:
            print("No pending items in queue.")
        return 0

    max_items: int = args.max_items
    marker_timeout: float = args.marker_timeout

    if not args.json:
        to_process = min(max_items, pending)
        print(
            f"Processing up to {to_process} item(s) "
            f"(marker_timeout={marker_timeout}s, MAX_ATTEMPTS=3)"
        )

    results = q.process_next(max_items=max_items, marker_timeout=marker_timeout)

    if args.json:
        print(json.dumps({"processed": results, "exit_code": 0}, indent=2))
        return 0

    for r in results:
        status_tag = "PASS" if r.get("marker_ready") else "FAIL"
        cid = r.get("candidate_id", "?")
        bs = r.get("body_source", "?")
        bl = r.get("body_length", 0)
        ps = r.get("parse_seconds", 0.0)
        qs = r.get("queue_status", "?")
        print(f"[{status_tag}] {cid}")
        print(f"       body_source:  {bs}")
        if bl:
            print(f"       body_length:  {bl:,} chars")
        if ps:
            print(f"       parse_seconds:{ps:.1f}s")
        if r.get("failure_reason"):
            print(f"       failure:      {r['failure_reason']}")
        print(f"       queue_status: {qs}  marker_ready={r.get('marker_ready')}")

    done_count = sum(1 for r in results if r.get("queue_status") == "done")
    fail_count = len(results) - done_count
    print()
    print(f"Processed {len(results)} item(s): {done_count} done, {fail_count} failed/retried.")
    return 0


def _cmd_warm_process(args: argparse.Namespace) -> int:
    import sys as _sys
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts_before = q.get_counts()
    pending = counts_before.get("pending", 0)
    if pending == 0:
        if args.json:
            print(json.dumps({
                "processed": [],
                "exit_code": 0,
                "message": "no pending items",
                "ipc_warm_worker_used": False,
            }))
        else:
            print("No pending items in queue.")
        return 0

    max_items: int = args.max_items
    marker_timeout: float = args.marker_timeout
    platform_note = (
        "Linux/Docker IPC warm-worker" if _sys.platform != "win32"
        else "Windows warm thread"
    )

    if not args.json:
        to_process = min(max_items, pending)
        print(
            f"Processing up to {to_process} item(s) via {platform_note} "
            f"(marker_timeout={marker_timeout}s, MAX_ATTEMPTS=3)"
        )

    results = q.process_next_ipc(max_items=max_items, marker_timeout=marker_timeout)

    if args.json:
        any_ipc = any(r.get("ipc_warm_worker_used") for r in results)
        print(json.dumps({
            "processed": results,
            "exit_code": 0,
            "ipc_warm_worker_used": any_ipc,
        }, indent=2))
        return 0

    for r in results:
        status_tag = "PASS" if r.get("marker_ready") else "FAIL"
        cid = r.get("candidate_id", "?")
        bs = r.get("body_source", "?")
        bl = r.get("body_length", 0)
        ps = r.get("parse_seconds", 0.0)
        qs = r.get("queue_status", "?")
        ipc = r.get("ipc_warm_worker_used", False)
        print(f"[{status_tag}] {cid}")
        print(f"       body_source:          {bs}")
        if bl:
            print(f"       body_length:          {bl:,} chars")
        if ps:
            print(f"       parse_seconds:        {ps:.1f}s")
        if r.get("failure_reason"):
            print(f"       failure:              {r['failure_reason']}")
        print(f"       queue_status:         {qs}  marker_ready={r.get('marker_ready')}")
        print(f"       ipc_warm_worker_used: {ipc}")

    done_count = sum(1 for r in results if r.get("queue_status") == "done")
    fail_count = len(results) - done_count
    print()
    print(
        f"Processed {len(results)} item(s): {done_count} done, {fail_count} failed/retried."
    )
    return 0


def _cmd_index_done(args: argparse.Namespace) -> int:
    """Index all marker-ready done queue items into the KnowledgeStore."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)
    ks_path = Path(args.ks_path) if getattr(args, "ks_path", None) else None
    extract_claims = not getattr(args, "no_extract_claims", False)

    if not args.json:
        force_note = " (force=True: re-indexing all)" if args.force else ""
        extract_note = "" if extract_claims else " (--no-extract-claims: skipping extraction)"
        print(f"Indexing marker-ready done items into KnowledgeStore{force_note}{extract_note}...")

    try:
        summary = q.index_done_items(
            ks_path=ks_path, force=args.force, extract_claims=extract_claims
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    indexed = summary.get("indexed", [])
    skipped_dup = summary.get("skipped_already_indexed", [])
    skipped_no_body = summary.get("skipped_no_body", [])
    failed = summary.get("failed", [])
    total_claims = summary.get("total_claims_extracted", 0)

    if indexed:
        print(f"\nIndexed {len(indexed)} paper(s):")
        for item in indexed:
            claims_note = f"  claims={item.get('claims_extracted', 0)}" if extract_claims else ""
            print(
                f"  [OK] {item['candidate_id']}  doc_id={item['doc_id']}"
                f"  chunks={item['chunk_count']}{claims_note}"
            )
    if skipped_dup:
        print(f"\nSkipped {len(skipped_dup)} already-indexed paper(s):")
        for cid in skipped_dup:
            print(f"  [skip] {cid}")
    if skipped_no_body:
        print(f"\nSkipped {len(skipped_no_body)} paper(s) — body file missing:")
        for cid in skipped_no_body:
            print(f"  [no-body] {cid}  (re-enqueue with --force to re-process)")
    if failed:
        print(f"\nFailed {len(failed)} paper(s):")
        for item in failed:
            print(f"  [FAIL] {item.get('candidate_id', '?')}  {item.get('error', '')}")

    total = len(indexed) + len(skipped_dup) + len(skipped_no_body) + len(failed)
    claims_summary = f", {total_claims} claim(s) extracted" if extract_claims else ""
    print(
        f"\nTotal: {total} done item(s) examined — "
        f"{len(indexed)} indexed, {len(skipped_dup)} already-indexed, "
        f"{len(skipped_no_body)} no-body, {len(failed)} failed{claims_summary}."
    )
    # rc=1 only when there are hard failures; empty/skipped results are valid outcomes
    return 1 if failed else 0


def _cmd_prefetch(args: argparse.Namespace) -> int:
    """Download PDFs for pending queue items to local cache before warm-process."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts = q.get_counts()
    pending = counts.get("pending", 0)

    if pending == 0:
        if args.json:
            print(
                json.dumps(
                    {
                        "cached": [],
                        "skipped_already_cached": [],
                        "failed": [],
                        "total": 0,
                        "message": "no pending items",
                    }
                )
            )
        else:
            print("No pending items to prefetch.")
        return 0

    max_items: Optional[int] = args.max_items  # None = all
    delay_seconds: float = args.delay_seconds
    effective = min(max_items, pending) if max_items is not None else pending

    if not args.json:
        print(f"Prefetching PDFs for up to {effective} pending item(s)")
        print(f"  delay between downloads: {delay_seconds}s")
        cache_note = (
            str(q.queue_dir / "pdf_cache")
            if not args.queue_dir
            else str(Path(args.queue_dir) / "pdf_cache")
        )
        print(f"  cache dir: {cache_note}")
        print()

    try:
        result = q.prefetch_pdfs(
            max_items=max_items,
            delay_seconds=delay_seconds,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    cached = result.get("cached", [])
    skipped = result.get("skipped_already_cached", [])
    failed = result.get("failed", [])

    for item in cached:
        size_kb = item.get("file_size", 0) // 1024
        print(f"  [OK]   {item['candidate_id']}  ({size_kb} KB)")
    for cid in skipped:
        print(f"  [skip] {cid}  already cached")
    for item in failed:
        print(f"  [FAIL] {item['candidate_id']}  {item.get('error', '')[:80]}")

    print()
    print(
        f"Prefetch complete: {len(cached)} downloaded, "
        f"{len(skipped)} already cached, {len(failed)} failed "
        f"(total pending considered: {result.get('total', 0)})"
    )
    if failed:
        print(
            "Tip: re-run prefetch to retry failed items. "
            "Failed items still go through live arXiv fetch during warm-process."
        )
    return 0


def _cmd_status_report(args: argparse.Namespace) -> int:
    """Print a structured status report for the queue with stuck-item detection."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    try:
        report = q.get_status_report()
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    counts = report.get("counts", {})
    print("Marker Queue Status Report")
    print("=" * 40)
    print(f"  pending:    {counts.get('pending', 0)}")
    print(f"  processing: {counts.get('processing', 0)}", end="")
    if report.get("stuck_warning"):
        print("  <-- likely stuck; no active warm-process")
    else:
        print()
    print(f"  done:       {counts.get('done', 0)}")
    print(f"  failed:     {counts.get('failed', 0)}")
    print(f"  total:      {counts.get('total', 0)}")

    ps = report.get("prefetch_stats", {})
    if ps.get("total_manifest_entries", 0) > 0:
        print(
            f"\nPrefetch cache: {ps.get('cached', 0)} cached, "
            f"{ps.get('failed', 0)} failed "
            f"({ps.get('total_manifest_entries', 0)} total entries in manifest)"
        )

    processing_items = report.get("processing_items", [])
    if processing_items:
        print("\nStuck/processing items (reset with --force):")
        queue_dir_arg = f"--queue-dir {args.queue_dir} " if args.queue_dir else ""
        for cid in processing_items:
            arxiv_id = cid.replace("arxiv:", "")
            print(f"  {cid}")
            print(
                f"    -> python -m polytool research-marker-queue "
                f"{queue_dir_arg}enqueue --url {arxiv_id} --force"
            )

    failed_details = report.get("failed_details", [])
    if failed_details:
        print(f"\nFailed items ({len(failed_details)} — all retries exhausted):")
        for item in failed_details:
            reason = (item.get("failure_reason") or "unknown")[:80]
            print(
                f"  {item.get('candidate_id', '?')}  "
                f"[{item.get('attempts', 0)} attempts]  {reason}"
            )
        print(
            "\nTip: run `prefetch` before `warm-process` to avoid arXiv rate-limit failures."
        )
        print(
            "     Then re-enqueue failed items with --force when ready to retry."
        )

    pending_ids = report.get("pending_ids", [])
    if pending_ids:
        print(f"\nPending ({len(pending_ids)} items):")
        for cid in pending_ids[:10]:
            print(f"  {cid}")
        if len(pending_ids) > 10:
            print(f"  ... and {len(pending_ids) - 10} more")

    return 0


def _cmd_counts(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)
    counts = q.get_counts()

    if args.json:
        print(json.dumps(counts, indent=2))
        return 0

    print("Marker Parse Queue — Item Counts")
    print(f"  pending:    {counts.get('pending', 0)}")
    print(f"  processing: {counts.get('processing', 0)}")
    print(f"  done:       {counts.get('done', 0)}")
    print(f"  failed:     {counts.get('failed', 0)}")
    print(f"  total:      {counts.get('total', 0)}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polytool research-marker-queue",
        description=(
            "Marker Canonical Academic Parse Queue v0. "
            "Enqueue arXiv papers, process them with Marker, "
            "and track which papers are RAG-ready (marker_ready=true). "
            "On Windows, Marker models are pre-loaded once per batch (warm). "
            "On Linux/Docker, use warm-process for the validated IPC warm-worker path."
        ),
    )
    parser.add_argument(
        "--queue-dir",
        default=None,
        metavar="PATH",
        help="Override artifact queue directory (default: artifacts/research/marker_parse_queue)",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # enqueue
    p_enqueue = subparsers.add_parser(
        "enqueue",
        help="Add one arXiv paper to the parse queue",
    )
    p_enqueue.add_argument(
        "--url",
        required=True,
        metavar="URL_OR_ID",
        help="arXiv URL or bare arXiv ID (e.g. 2604.24366)",
    )
    p_enqueue.add_argument(
        "--title",
        default="",
        metavar="TITLE",
        help="Optional title hint (fetcher resolves from API if omitted)",
    )
    p_enqueue.add_argument(
        "--pdf-url",
        default="",
        metavar="PDF_URL_OR_PATH",
        dest="pdf_url",
        help=(
            "Direct PDF URL or local file path. When set, warm-process skips the "
            "arXiv metadata API (no export.arxiv.org query) and fetches/reads the PDF "
            "directly. Useful when the Atom API is rate-limited. --url still determines "
            "candidate_id."
        ),
    )
    p_enqueue.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-enqueue even if the paper already exists (resets to pending)",
    )
    p_enqueue.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
    )

    # list
    p_list = subparsers.add_parser(
        "list",
        help="Show queue items",
    )
    p_list.add_argument(
        "--status",
        default="all",
        choices=["all", "pending", "processing", "done", "failed"],
        help="Filter by status (default: all)",
    )
    p_list.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON array",
    )

    # process
    p_process = subparsers.add_parser(
        "process",
        help=(
            "Process next N pending items using Marker. "
            "Warm batch on Windows (thread mode); cold per paper on Linux/Docker."
        ),
    )
    p_process.add_argument(
        "--max-items",
        type=int,
        default=1,
        dest="max_items",
        metavar="N",
        help="Maximum number of pending items to process (default: 1)",
    )
    p_process.add_argument(
        "--marker-timeout",
        type=float,
        default=900.0,
        dest="marker_timeout",
        metavar="SECONDS",
        help="Marker extraction subprocess timeout in seconds (default: 900)",
    )
    p_process.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    # warm-process
    p_warm = subparsers.add_parser(
        "warm-process",
        help=(
            "Process next N pending items using MarkerIPCWorker (warm IPC, Linux/Docker). "
            "On Windows, falls back to warm thread worker. "
            "L1 production path — IPC warm-worker validated 2026-05-08 (Feature 3 closed)."
        ),
    )
    p_warm.add_argument(
        "--max-items",
        type=int,
        default=1,
        dest="max_items",
        metavar="N",
        help="Maximum number of pending items to process (default: 1)",
    )
    p_warm.add_argument(
        "--marker-timeout",
        type=float,
        default=900.0,
        dest="marker_timeout",
        metavar="SECONDS",
        help="Marker extraction timeout in seconds (default: 900)",
    )
    p_warm.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    # index-done
    p_index = subparsers.add_parser(
        "index-done",
        help=(
            "Index all marker-ready done items into the KnowledgeStore. "
            "Reads body from bodies/{candidate_id}.body.txt (written by warm-process). "
            "Idempotent: skips already-indexed items unless --force."
        ),
    )
    p_index.add_argument(
        "--ks-path",
        default=None,
        dest="ks_path",
        metavar="PATH",
        help="Override KnowledgeStore SQLite path (default: project default)",
    )
    p_index.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-index even items already recorded in indexed.jsonl",
    )
    p_index.add_argument(
        "--no-extract-claims",
        action="store_true",
        default=False,
        dest="no_extract_claims",
        help=(
            "Skip automatic claim extraction after indexing. "
            "Default: extract claims from each indexed paper via body_file sidecar."
        ),
    )
    p_index.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output summary as JSON",
    )

    # counts
    p_counts = subparsers.add_parser(
        "counts",
        help="Show item counts by status",
    )
    p_counts.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output counts as JSON",
    )

    # prefetch
    p_prefetch = subparsers.add_parser(
        "prefetch",
        help=(
            "Pre-download PDFs for pending queue items to a local cache. "
            "Run this BEFORE warm-process to separate arXiv PDF fetching from "
            "GPU Marker parsing. Warm-process then reads local files and makes "
            "no arXiv network calls during the parse phase. "
            "Idempotent: already-cached PDFs are skipped."
        ),
    )
    p_prefetch.add_argument(
        "--max-items",
        type=int,
        default=None,
        dest="max_items",
        metavar="N",
        help="Max pending items to prefetch (default: all pending)",
    )
    p_prefetch.add_argument(
        "--delay-seconds",
        type=float,
        default=10.0,
        dest="delay_seconds",
        metavar="SECONDS",
        help=(
            "Seconds to sleep between successive PDF downloads (default: 10.0). "
            "Keep >= 5s to avoid arXiv rate limits under sustained load."
        ),
    )
    p_prefetch.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
    )

    # status-report
    p_status = subparsers.add_parser(
        "status-report",
        help=(
            "Print a structured status report: counts, stuck items (processing "
            "with no active worker), failed-item failure reasons, and prefetch "
            "cache stats."
        ),
    )
    p_status.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output report as JSON",
    )

    return parser


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    """CLI entrypoint. Returns int exit code."""
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help()
        return 1

    if args.subcommand == "enqueue":
        return _cmd_enqueue(args)
    elif args.subcommand == "list":
        return _cmd_list(args)
    elif args.subcommand == "process":
        return _cmd_process(args)
    elif args.subcommand == "warm-process":
        return _cmd_warm_process(args)
    elif args.subcommand == "index-done":
        return _cmd_index_done(args)
    elif args.subcommand == "counts":
        return _cmd_counts(args)
    elif args.subcommand == "prefetch":
        return _cmd_prefetch(args)
    elif args.subcommand == "status-report":
        return _cmd_status_report(args)
    else:
        print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
