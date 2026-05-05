"""CLI entrypoint for RIS v1 background scheduler management.

Subcommands:
  status     List all registered jobs with id, name, trigger description
  start      Start the APScheduler background loop (blocking; Ctrl-C to stop)
  run-job    Invoke a single job callable by id immediately (for manual triggering)

Usage:
  python -m polytool research-scheduler status
  python -m polytool research-scheduler status --json
  python -m polytool research-scheduler start
  python -m polytool research-scheduler start --dry-run
  python -m polytool research-scheduler run-job academic_ingest
  python -m polytool research-scheduler run-job weekly_digest --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> int:
    """List all registered jobs without starting APScheduler."""
    from packages.research.scheduling.scheduler import JOB_REGISTRY  # lazy import

    if args.json:
        print(json.dumps(JOB_REGISTRY, indent=2))
        return 0

    print(f"RIS Scheduler -- Registered Jobs ({len(JOB_REGISTRY)})")
    print()
    col_id = 20
    col_name = 35
    col_sched = 45
    header = f"  {'ID':<{col_id}} {'Name':<{col_name}} {'Schedule':<{col_sched}}"
    print(header)
    print("  " + "-" * (col_id + col_name + col_sched + 2))
    for job in JOB_REGISTRY:
        print(
            f"  {job['id']:<{col_id}} {job['name']:<{col_name}} {job['trigger_description']:<{col_sched}}"
        )
    print()
    print("Note: Twitter/X ingestion is not scheduled (fetcher not yet implemented).")
    print("Run 'python -m polytool research-scheduler start' to launch the background loop.")
    return 0


def _cmd_start(args: argparse.Namespace) -> int:
    """Start the APScheduler background loop."""
    from packages.research.scheduling.scheduler import JOB_REGISTRY  # lazy import

    exclude: list[str] = args.exclude_jobs or []

    if args.dry_run:
        active = [j for j in JOB_REGISTRY if j["id"] not in exclude]
        print("RIS Scheduler -- Dry-run mode (no scheduler started)")
        print(f"Registered jobs ({len(active)}):")
        for job in active:
            print(f"  {job['id']:<22} {job['trigger_description']}")
        if exclude:
            print(f"Excluded jobs: {', '.join(exclude)}")
        print()
        print("Note: Twitter/X ingestion is not scheduled (fetcher not yet implemented).")
        return 0

    # Real start path -- requires APScheduler
    try:
        from packages.research.scheduling.scheduler import start_research_scheduler
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        scheduler = start_research_scheduler(exclude_job_ids=exclude if exclude else None)
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if exclude:
        print(f"Excluded jobs: {', '.join(exclude)}")
    print("Scheduler started. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Scheduler stopped.")
    return 0


def _cmd_run_job(args: argparse.Namespace) -> int:
    """Invoke a single job callable by id."""
    from packages.research.scheduling.scheduler import JOB_REGISTRY, run_job  # lazy import

    job_id = args.job_id

    # Look up job name for display
    job_entry = next((j for j in JOB_REGISTRY if j["id"] == job_id), None)
    if job_entry is None:
        msg = f"Error: unknown job id {job_id!r}. Run 'research-scheduler status' to see valid ids."
        if args.json:
            print(json.dumps({"job_id": job_id, "exit_code": 1, "error": f"unknown job id {job_id!r}"}))
        else:
            print(msg, file=sys.stderr)
        return 1

    job_name = job_entry["name"]
    if not args.json:
        print(f"Running job: {job_id} ({job_name})")

    exit_code = run_job(job_id)

    if args.json:
        print(json.dumps({"job_id": job_id, "exit_code": exit_code}))
    else:
        if exit_code == 0:
            print("Done.")
        else:
            print(f"Error: job {job_id!r} failed (exit_code={exit_code}).", file=sys.stderr)

    return exit_code



# ---------------------------------------------------------------------------
# run-academic-url handler
# ---------------------------------------------------------------------------


def _cmd_run_academic_url(args: argparse.Namespace) -> int:
    """Fetch and parse one arXiv paper through LiveAcademicFetcher. No scheduler started."""
    import re as _re
    import time as _time

    url = args.url
    marker_timeout = args.marker_timeout

    # Accept bare arXiv IDs like "2604.24366" as well as full URLs
    if _re.match(r"^\d{4}\.\d{4,5}$", url):
        url = f"https://arxiv.org/abs/{url}"

    if not args.json:
        print(f"run-academic-url: fetching {url} (marker_timeout={marker_timeout}s)")

    result: dict = {
        "url": url,
        "arxiv_id": None,
        "title": "",
        "body_source": "unknown",
        "body_length": 0,
        "page_count": 0,
        "parse_seconds": 0.0,
        "failure_reason": None,
        "rejected": False,
        "marker_timeout": marker_timeout,
        "exit_code": 0,
    }

    # Extract arXiv ID for result
    id_match = _re.search(r"(\d{4}\.\d{4,5})", url)
    if id_match:
        result["arxiv_id"] = id_match.group(1)

    t0 = _time.monotonic()
    try:
        from packages.research.ingestion.fetchers import LiveAcademicFetcher

        fetcher = LiveAcademicFetcher(_marker_timeout_seconds=float(marker_timeout))
        raw_source = fetcher.fetch(url)

        result["title"] = raw_source.get("title", "")
        result["body_source"] = raw_source.get("body_source", "unknown")
        result["body_length"] = raw_source.get("body_length", 0)
        result["page_count"] = raw_source.get("page_count", 0)
        result["parse_seconds"] = raw_source.get("parse_seconds", 0.0)

        if result["body_source"] == "marker_failed":
            result["failure_reason"] = raw_source.get("failure_reason", "unknown")
            result["rejected"] = True
            result["exit_code"] = 1

    except Exception as exc:
        result["body_source"] = "error"
        result["failure_reason"] = str(exc)[:300]
        result["rejected"] = True
        result["exit_code"] = 1

    result["total_seconds"] = round(_time.monotonic() - t0, 2)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if not result["rejected"] else "FAIL"
        print(f"[{status}] {result['url']}")
        print(f"  body_source:   {result['body_source']}")
        if result["body_length"]:
            print(f"  body_length:   {result['body_length']:,} chars")
        if result["page_count"]:
            print(f"  page_count:    {result['page_count']}")
        if result["parse_seconds"]:
            print(f"  parse_seconds: {result['parse_seconds']:.1f}s")
        if result["failure_reason"]:
            print(f"  failure:       {result['failure_reason']}")

    return result["exit_code"]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polytool research-scheduler",
        description="Manage the RIS v1 background ingestion scheduler.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # status
    p_status = subparsers.add_parser("status", help="List registered jobs")
    p_status.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON list",
    )

    # start
    p_start = subparsers.add_parser(
        "start", help="Start background scheduler loop (blocking)"
    )
    p_start.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Register jobs and print schedule, then exit (no scheduler started)",
    )
    p_start.add_argument(
        "--exclude-jobs",
        nargs="+",
        default=[],
        dest="exclude_jobs",
        metavar="JOB_ID",
        help=(
            "Job ids to skip (space-separated). CPU scheduler uses "
            "--exclude-jobs academic_ingest so only the GPU service runs academic PDF ingest."
        ),
    )

    # run-job
    p_run = subparsers.add_parser(
        "run-job", help="Invoke a single job callable immediately"
    )
    p_run.add_argument("job_id", help="Job id to run (see 'status' for valid ids)")
    p_run.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
    )

    # run-academic-url
    p_run_url = subparsers.add_parser(
        "run-academic-url",
        help="Fetch and parse one arXiv paper through LiveAcademicFetcher (no scheduler loop)",
    )
    p_run_url.add_argument(
        "--url",
        required=True,
        metavar="URL_OR_ID",
        help="arXiv URL (https://arxiv.org/abs/XXXX.XXXXX) or bare ID (XXXX.XXXXX)",
    )
    p_run_url.add_argument(
        "--marker-timeout",
        type=float,
        default=900.0,
        dest="marker_timeout",
        metavar="SECONDS",
        help="Hard timeout for Marker extraction subprocess (default: 900s)",
    )
    p_run_url.add_argument(
        "--no-eval",
        action="store_true",
        default=False,
        dest="no_eval",
        help="No-op flag for compatibility with research-acquire conventions",
    )
    p_run_url.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
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

    if args.subcommand == "status":
        return _cmd_status(args)
    elif args.subcommand == "start":
        return _cmd_start(args)
    elif args.subcommand == "run-job":
        return _cmd_run_job(args)
    elif args.subcommand == "run-academic-url":
        return _cmd_run_academic_url(args)
    else:
        print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
