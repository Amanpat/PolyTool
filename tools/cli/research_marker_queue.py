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
            "On Linux/Docker, models reload per paper (subprocess mode; "
            "warm IPC worker is v1)."
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
    elif args.subcommand == "counts":
        return _cmd_counts(args)
    else:
        print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
