"""CLI entrypoint for Wallet Discovery v1 commands.

Usage:
    python -m polytool discovery run-loop-a [options]

SPEC: docs/specs/SPEC-wallet-discovery-v1.md
"""
from __future__ import annotations

import argparse
import os
import sys


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

    args = parser.parse_args(argv)

    if args.subcommand == "run-loop-a":
        return _run_loop_a(args)

    print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 1


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
