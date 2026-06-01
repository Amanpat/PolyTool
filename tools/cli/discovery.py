"""CLI entrypoint for Wallet Discovery v1 commands.

Usage:
    python -m polytool discovery run-loop-a [options]

SPEC: docs/specs/SPEC-wallet-discovery-v1.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main(argv: list[str]) -> int:
    """Main entrypoint for the discovery command group."""
    parser = argparse.ArgumentParser(
        prog="polytool discovery",
        description="Wallet Discovery v1 — Loop A leaderboard discovery",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")
    subparsers.required = True

    # --- run-loop-a ---
    loop_a_parser = subparsers.add_parser(
        "run-loop-a",
        help="Run one Loop A fetch cycle: leaderboard fetch -> churn detection -> scan queue",
    )
    loop_a_parser.add_argument(
        "--order-by",
        default="PNL",
        choices=["PNL", "VOL"],
        help="Leaderboard sort field (default: PNL)",
    )
    loop_a_parser.add_argument(
        "--time-period",
        default="DAY",
        choices=["DAY", "WEEK", "MONTH", "ALL"],
        help="Leaderboard time window (default: DAY)",
    )
    loop_a_parser.add_argument(
        "--category",
        default="OVERALL",
        choices=["OVERALL", "POLITICS", "SPORTS", "CRYPTO"],
        help="Leaderboard category (default: OVERALL)",
    )
    loop_a_parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to fetch from the leaderboard API (default: 5)",
    )
    loop_a_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and detect churn without writing to ClickHouse",
    )
    loop_a_parser.add_argument(
        "--clickhouse-host",
        default="localhost",
        help="ClickHouse host (default: localhost)",
    )
    loop_a_parser.add_argument(
        "--clickhouse-port",
        type=int,
        default=8123,
        help="ClickHouse HTTP port (default: 8123)",
    )
    loop_a_parser.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        help="ClickHouse user (default: polytool_admin)",
    )
    loop_a_parser.add_argument(
        "--clickhouse-password",
        default=None,
        help="ClickHouse password. Falls back to CLICKHOUSE_PASSWORD env var.",
    )

    # --- run-worker ---
    worker_parser = subparsers.add_parser(
        "run-worker",
        help=(
            "Drain the scan_queue: lease a pending wallet -> scan -> dossier "
            "extract + RIS ingest -> advance watchlist to 'scanned' -> complete. "
            "Bounded run only (--once / --max-items); no scheduling (WP-3)."
        ),
    )
    worker_parser.add_argument(
        "--once",
        action="store_true",
        help="Process a single pending item then exit (equivalent to --max-items 1).",
    )
    worker_parser.add_argument(
        "--max-items",
        type=int,
        default=1,
        help="Maximum number of queue items to process this run (default: 1).",
    )
    worker_parser.add_argument(
        "--owner",
        default="scan-worker",
        help="Lease owner identifier recorded on leased rows (default: scan-worker).",
    )
    worker_parser.add_argument(
        "--lease-seconds",
        type=int,
        default=300,
        help="Lease TTL in seconds (default: 300).",
    )
    worker_parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help="Attempt ceiling before a row is dead-lettered to 'dropped' (default: 5).",
    )
    worker_parser.add_argument(
        "--profile",
        default="lite",
        choices=["lite", "full"],
        help="Scan profile applied to each leased wallet (default: lite).",
    )
    worker_parser.add_argument(
        "--extract-dossier-db",
        default="kb/rag/knowledge/knowledge.sqlite3",
        help="KnowledgeStore SQLite path for dossier ingestion.",
    )
    worker_parser.add_argument(
        "--no-extract-dossier",
        action="store_true",
        help="Scan only; skip dossier extraction + RIS ingestion.",
    )
    worker_parser.add_argument(
        "--no-advance-watchlist",
        action="store_true",
        help="Do not advance the watchlist lifecycle to 'scanned' on success.",
    )
    worker_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load queue from ClickHouse and report pending items without scanning or writing.",
    )
    worker_parser.add_argument(
        "--clickhouse-host",
        default="localhost",
        help="ClickHouse host (default: localhost)",
    )
    worker_parser.add_argument(
        "--clickhouse-port",
        type=int,
        default=8123,
        help="ClickHouse HTTP port (default: 8123)",
    )
    worker_parser.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        help="ClickHouse user (default: polytool_admin)",
    )
    worker_parser.add_argument(
        "--clickhouse-password",
        default=None,
        help="ClickHouse password. Falls back to CLICKHOUSE_PASSWORD env var.",
    )

    # --- scheduler (WI-3) ---
    sched_parser = subparsers.add_parser(
        "scheduler",
        help=(
            "Discovery + rescan scheduler (WI-3). Reuses the RIS APScheduler "
            "pattern. Jobs: discovery_loop_a, watchlist_rescan, queue_drain."
        ),
    )
    sched_sub = sched_parser.add_subparsers(dest="sched_command", metavar="ACTION")
    sched_sub.required = True

    s_status = sched_sub.add_parser("status", help="List registered discovery jobs")
    s_status.add_argument("--json", action="store_true", help="Output as JSON list")

    s_start = sched_sub.add_parser(
        "start", help="Start the discovery background scheduler loop (blocking)"
    )
    s_start.add_argument(
        "--dry-run",
        action="store_true",
        help="Register jobs and print schedule, then exit (no scheduler started)",
    )
    s_start.add_argument(
        "--exclude-jobs",
        nargs="+",
        default=[],
        metavar="JOB_ID",
        help="Job ids to skip (space-separated).",
    )
    _add_ch_args(s_start)

    s_run = sched_sub.add_parser(
        "run-job", help="Invoke a single discovery job callable immediately"
    )
    s_run.add_argument("job_id", help="Job id to run (see 'scheduler status' for ids)")
    s_run.add_argument("--json", action="store_true", help="Output result as JSON")
    _add_ch_args(s_run)

    args = parser.parse_args(argv)

    if args.subcommand == "run-loop-a":
        return _run_loop_a(args)
    if args.subcommand == "run-worker":
        return _run_worker(args)
    if args.subcommand == "scheduler":
        return _run_scheduler(args)

    print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 1


def _add_ch_args(p: argparse.ArgumentParser) -> None:
    """Attach the standard ClickHouse connection args to a subparser."""
    p.add_argument("--clickhouse-host", default="localhost", help="ClickHouse host")
    p.add_argument("--clickhouse-port", type=int, default=8123, help="ClickHouse HTTP port")
    p.add_argument("--clickhouse-user", default="polytool_admin", help="ClickHouse user")
    p.add_argument(
        "--clickhouse-password",
        default=None,
        help="ClickHouse password. Falls back to CLICKHOUSE_PASSWORD env var.",
    )


def _run_loop_a(args: argparse.Namespace) -> int:
    """Execute Loop A and print a summary."""
    # Resolve password: CLI arg > env var > fail-fast (unless dry-run)
    password = args.clickhouse_password or os.environ.get("CLICKHOUSE_PASSWORD", "")

    if not args.dry_run and not password:
        print(
            "Error: CLICKHOUSE_PASSWORD is required for a live run.\n"
            "Set the CLICKHOUSE_PASSWORD environment variable or use --clickhouse-password.\n"
            "Use --dry-run to test without writing to ClickHouse.",
            file=sys.stderr,
        )
        return 1

    try:
        from packages.polymarket.discovery.loop_a import run_loop_a
    except ImportError as exc:
        print(f"Error: could not import discovery loop_a: {exc}", file=sys.stderr)
        return 1

    print(
        f"Loop A: order_by={args.order_by} time_period={args.time_period} "
        f"category={args.category} max_pages={args.max_pages} "
        f"dry_run={args.dry_run}"
    )

    try:
        result = run_loop_a(
            order_by=args.order_by,
            time_period=args.time_period,
            category=args.category,
            max_pages=args.max_pages,
            ch_host=args.clickhouse_host,
            ch_port=args.clickhouse_port,
            ch_user=args.clickhouse_user,
            ch_password=password,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error during Loop A execution: {exc}", file=sys.stderr)
        return 1

    # Print summary
    print("")
    print("--- Loop A Result ---")
    print(f"  fetch_run_id  : {result.fetch_run_id}")
    print(f"  snapshot_ts   : {result.snapshot_ts.isoformat()}")
    print(f"  rows_fetched  : {result.rows_fetched}")
    print(f"  new_wallets   : {len(result.churn.new_wallets)}")
    print(f"  dropped_wallets: {len(result.churn.dropped_wallets)}")
    print(f"  rising_wallets : {len(result.churn.rising_wallets)}")
    print(f"  rows_enqueued : {result.rows_enqueued}")
    print(f"  dry_run       : {result.dry_run}")
    if result.dry_run:
        print("")
        print("  (dry-run: no ClickHouse writes performed)")
    print("")
    return 0


def _run_worker(args: argparse.Namespace) -> int:
    """Drain the scan queue: lease -> scan -> dossier -> watchlist -> complete.

    Bounded run only (--once / --max-items). No scheduling loop here (WP-3).
    Uses the same fail-fast CLICKHOUSE_PASSWORD handling as run-loop-a.
    """
    # Resolve password: CLI arg > env var > fail-fast (always required: the
    # worker hydrates the queue from ClickHouse and persists state back).
    password = args.clickhouse_password or os.environ.get("CLICKHOUSE_PASSWORD", "")
    if not password:
        print(
            "Error: CLICKHOUSE_PASSWORD is required to run the scan-queue worker.\n"
            "Set the CLICKHOUSE_PASSWORD environment variable or use --clickhouse-password.",
            file=sys.stderr,
        )
        return 1

    try:
        from packages.polymarket.discovery.scan_queue import ScanQueueManager
        from packages.polymarket.discovery.scan_worker import (
            DEFAULT_SCAN_FLAGS,
            ScanWorker,
            make_clickhouse_watchlist_advancer,
        )
    except ImportError as exc:
        print(f"Error: could not import discovery scan_worker: {exc}", file=sys.stderr)
        return 1

    ch_kwargs = dict(
        host=args.clickhouse_host,
        port=args.clickhouse_port,
        user=args.clickhouse_user,
        password=password,
    )

    max_items = 1 if args.once else max(1, int(args.max_items))

    queue = ScanQueueManager()
    loaded = queue.load_from_clickhouse(**ch_kwargs)
    pending = queue.get_pending(limit=max_items * 4 or 1)

    print(
        f"Scan worker: loaded={loaded} rows, pending={len(pending)}, "
        f"max_items={max_items}, dry_run={args.dry_run}"
    )

    if args.dry_run:
        print("")
        print("  (dry-run: no scan, no ClickHouse writes performed)")
        for row in pending[:max_items]:
            print(f"    pending: {row.dedup_key} (attempts={row.attempt_count})")
        print("")
        return 0

    # Build scan profile flags.
    scan_flags = dict(DEFAULT_SCAN_FLAGS)
    if args.profile == "full":
        scan_flags = {
            "full": True,
            "ingest_positions": True,
            "compute_pnl": True,
            "enrich_resolutions": True,
            "compute_clv": True,
        }

    # Dossier extractor (RIS ingestion) unless disabled.
    post_scan_extractor = None
    if not args.no_extract_dossier:
        from tools.cli.wallet_scan import _make_dossier_extractor

        post_scan_extractor = _make_dossier_extractor(store_path=args.extract_dossier_db)

    # Watchlist advancer (discovered/queued -> scanned) unless disabled.
    watchlist_advancer = None
    if not args.no_advance_watchlist:
        watchlist_advancer = make_clickhouse_watchlist_advancer(**ch_kwargs)

    worker = ScanWorker(
        queue,
        post_scan_extractor=post_scan_extractor,
        watchlist_advancer=watchlist_advancer,
        owner=args.owner,
        lease_seconds=args.lease_seconds,
        max_attempts=args.max_attempts,
        scan_flags=scan_flags,
    )

    try:
        result = worker.run(max_items=max_items)
    except Exception as exc:
        print(f"Error during scan-worker execution: {exc}", file=sys.stderr)
        return 1

    # Persist the updated queue state (leases/completes/fails/drops) back.
    flushed = queue.flush_to_clickhouse(**ch_kwargs)

    print("")
    print("--- Scan Worker Result ---")
    print(f"  requeued    : {result.requeued}")
    print(f"  leased      : {result.leased}")
    print(f"  completed   : {result.completed}")
    print(f"  failed      : {result.failed}")
    print(f"  dropped     : {result.dropped}")
    print(f"  skipped     : {result.skipped}")
    print(f"  flushed_ch  : {flushed}")
    print("")
    return 0


def _run_scheduler(args: argparse.Namespace) -> int:
    """Handle 'discovery scheduler {status,start,run-job}' (WI-3)."""
    if args.sched_command == "status":
        return _scheduler_status(args)
    if args.sched_command == "start":
        return _scheduler_start(args)
    if args.sched_command == "run-job":
        return _scheduler_run_job(args)
    print(f"Unknown scheduler action: {args.sched_command}", file=sys.stderr)
    return 1


def _scheduler_status(args: argparse.Namespace) -> int:
    from packages.research.scheduling.discovery_scheduler import DISCOVERY_JOB_REGISTRY

    if args.json:
        print(json.dumps(DISCOVERY_JOB_REGISTRY, indent=2))
        return 0
    print(f"Discovery Scheduler -- Registered Jobs ({len(DISCOVERY_JOB_REGISTRY)})")
    print()
    for job in DISCOVERY_JOB_REGISTRY:
        print(f"  {job['id']:<20} {job['name']:<45} {job['trigger_description']}")
    print()
    print("Run 'python -m polytool discovery scheduler start' to launch the loop.")
    return 0


def _scheduler_start(args: argparse.Namespace) -> int:
    from packages.research.scheduling.discovery_scheduler import (
        DISCOVERY_JOB_REGISTRY,
        load_config,
    )

    exclude = args.exclude_jobs or []

    if args.dry_run:
        config = load_config()
        cadences = config.get("cadences", {})
        active = [j for j in DISCOVERY_JOB_REGISTRY if j["id"] not in exclude]
        print("Discovery Scheduler -- Dry-run mode (no scheduler started)")
        print(f"Registered jobs ({len(active)}):")
        for job in active:
            cad = cadences.get(job["id"], {})
            print(f"  {job['id']:<20} {job['trigger_description']:<28} cron={cad}")
        if exclude:
            print(f"Excluded jobs: {', '.join(exclude)}")
        return 0

    # Real start path requires CLICKHOUSE_PASSWORD (jobs touch ClickHouse).
    password = args.clickhouse_password or os.environ.get("CLICKHOUSE_PASSWORD", "")
    if not password:
        print(
            "Error: CLICKHOUSE_PASSWORD is required to start the discovery scheduler.\n"
            "Set the CLICKHOUSE_PASSWORD environment variable or use --clickhouse-password.\n"
            "Use --dry-run to inspect the schedule without starting.",
            file=sys.stderr,
        )
        return 1
    # Make it visible to the no-arg job callables (fail-fast pattern).
    os.environ["CLICKHOUSE_PASSWORD"] = password

    try:
        from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        scheduler = start_discovery_scheduler(
            ch_host=args.clickhouse_host,
            ch_port=args.clickhouse_port,
            ch_user=args.clickhouse_user,
            exclude_job_ids=exclude if exclude else None,
        )
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if exclude:
        print(f"Excluded jobs: {', '.join(exclude)}")
    print("Discovery scheduler started. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Discovery scheduler stopped.")
    return 0


def _scheduler_run_job(args: argparse.Namespace) -> int:
    from packages.research.scheduling.discovery_scheduler import (
        DISCOVERY_JOB_REGISTRY,
        run_discovery_job,
    )

    job_id = args.job_id
    job_entry = next((j for j in DISCOVERY_JOB_REGISTRY if j["id"] == job_id), None)
    if job_entry is None:
        if args.json:
            print(json.dumps({"job_id": job_id, "exit_code": 1, "error": "unknown job id"}))
        else:
            print(
                f"Error: unknown job id {job_id!r}. "
                f"Run 'discovery scheduler status' for valid ids.",
                file=sys.stderr,
            )
        return 1

    # Resolve password into env for the no-arg job callable (fail-fast).
    password = args.clickhouse_password or os.environ.get("CLICKHOUSE_PASSWORD", "")
    if password:
        os.environ["CLICKHOUSE_PASSWORD"] = password

    if not args.json:
        print(f"Running discovery job: {job_id} ({job_entry['name']})")

    exit_code = run_discovery_job(job_id)

    if args.json:
        print(json.dumps({"job_id": job_id, "exit_code": exit_code}))
    elif exit_code == 0:
        print("Done.")
    else:
        print(f"Error: job {job_id!r} failed (exit_code={exit_code}).", file=sys.stderr)
    return exit_code
