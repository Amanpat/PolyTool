"""CLI: fetch 2-minute price history and ingest into polytool.price_2min.

Usage:
    python -m polytool fetch-price-2min --token-id <TOKEN_ID> [--token-id <ID2>...]
    python -m polytool fetch-price-2min --token-file tokens.txt
    python -m polytool fetch-price-2min --token-id <ID> --dry-run

Options:
    --token-id ID       Token ID to fetch (repeatable)
    --token-file PATH   File with one token ID per line (# comments and blank lines ignored)
    --dry-run           Normalize rows but do not write to ClickHouse
    --out PATH          Write run record JSON to this path
    --clob-url URL      Override CLOB base URL (default: https://clob.polymarket.com)
    --clickhouse-host H ClickHouse host (default: localhost)
    --clickhouse-port P ClickHouse port (default: 8123)
    --clickhouse-user U ClickHouse user (default: polytool_admin)
    --clickhouse-password P ClickHouse password (reads CLICKHOUSE_PASSWORD env var if not set)

Table written:
    polytool.price_2min  (canonical live-updating 2-min series, v4.2)

NOTE: This writes to polytool.price_2min, NOT polytool.price_history_2min.
    price_2min           = this command (live-updating ClickHouse series)
    price_history_2min   = legacy bulk import from local JSONL/CSV files (import-historical)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from packages.polymarket.price_2min_fetcher import FetchAndIngestEngine, FetchConfig


def _load_token_ids_from_file(path: str) -> List[str]:
    """Read token IDs from a file, one per line. Skip blanks and # comments."""
    token_ids: List[str] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            token_ids.append(line)
    return token_ids


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polytool fetch-price-2min",
        description=(
            "Fetch 2-minute price history from the Polymarket CLOB API "
            "and ingest into polytool.price_2min (ClickHouse)."
        ),
    )
    parser.add_argument(
        "--token-id",
        dest="token_ids",
        action="append",
        default=[],
        metavar="ID",
        help="Token ID to fetch (repeatable)",
    )
    parser.add_argument(
        "--token-file",
        metavar="PATH",
        help="File with one token ID per line (# comments ignored)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Normalize rows but do not write to ClickHouse",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="Write run record JSON to this path",
    )
    parser.add_argument(
        "--clob-url",
        default="https://clob.polymarket.com",
        metavar="URL",
        help="Override CLOB base URL (default: https://clob.polymarket.com)",
    )
    parser.add_argument(
        "--clickhouse-host",
        default="localhost",
        metavar="HOST",
    )
    parser.add_argument(
        "--clickhouse-port",
        default=8123,
        type=int,
        metavar="PORT",
    )
    parser.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        metavar="USER",
    )
    parser.add_argument(
        "--clickhouse-password",
        default=None,
        metavar="PASSWORD",
        help="ClickHouse password (falls back to CLICKHOUSE_PASSWORD env var)",
    )

    args = parser.parse_args(argv)

    # Collect token IDs
    token_ids: List[str] = list(args.token_ids)

    if args.token_file:
        try:
            from_file = _load_token_ids_from_file(args.token_file)
        except OSError as exc:
            print(f"Error: cannot read token file: {exc}", file=sys.stderr)
            return 1
        token_ids.extend(from_file)

    if not token_ids:
        print(
            "Error: no token IDs provided. Use --token-id or --token-file.",
            file=sys.stderr,
        )
        return 1

    # Deduplicate while preserving order
    seen = set()
    unique_token_ids = []
    for tid in token_ids:
        if tid not in seen:
            seen.add(tid)
            unique_token_ids.append(tid)
    token_ids = unique_token_ids

    # Resolve CH password — fail fast if not provided; no silent fallback
    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not ch_password:
        print(
            "Error: ClickHouse password not set.\n"
            "  Pass --clickhouse-password PASSWORD, or export CLICKHOUSE_PASSWORD=<password>.",
            file=sys.stderr,
        )
        return 1

    # Build config and engine
    config = FetchConfig(
        clob_base_url=args.clob_url,
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        clickhouse_user=args.clickhouse_user,
        clickhouse_password=ch_password,
    )
    engine = FetchAndIngestEngine(config)

    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(
        f"fetch-price-2min [{mode_label}]: {len(token_ids)} token(s) -> polytool.price_2min",
        flush=True,
    )

    result = engine.run(token_ids, dry_run=args.dry_run)

    # Print per-token summary
    for tr in result.tokens:
        status = "ERROR" if tr.error else "ok"
        if args.dry_run:
            detail = f"{tr.rows_fetched} fetched, {tr.rows_skipped} skipped (dry-run, not inserted)"
        else:
            detail = f"{tr.rows_fetched} fetched, {tr.rows_inserted} inserted, {tr.rows_skipped} skipped"
        print(f"  [{status}] {tr.token_id}: {detail}")
        if tr.error:
            print(f"          error: {tr.error}", file=sys.stderr)

    print(
        f"\nTotal: {result.total_rows_fetched} rows fetched, "
        f"{result.total_rows_inserted} inserted, "
        f"{result.total_rows_skipped} skipped"
    )
    if result.errors:
        print(f"Errors: {len(result.errors)}", file=sys.stderr)

    # Write artifact if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Run record written to: {out_path}")

    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
