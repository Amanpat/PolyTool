"""CLI: reconstruct a Silver tape for a single market/token over a bounded window.

Silver tapes fuse three source tiers:
  1. pmxt anchor   — DuckDB reads pmxt Parquet snapshots (L2 book state at window open)
  2. Jon-Becker    — DuckDB reads Jon-Becker trade Parquet/CSV (fill events in window)
  3. price_2min    — ClickHouse polytool.price_2min (2-min midpoint guide series)

Output (written to --out-dir):
  silver_events.jsonl  — deterministic Silver tape events
  silver_meta.json     — reconstruction metadata (confidence, warnings, counts, paths)

Confidence model:
  high   — all three sources present
  medium — pmxt anchor + one other source
  low    — exactly one source
  none   — no data from any source

Usage:
    python -m polytool reconstruct-silver \\
        --token-id <TOKEN_ID> \\
        --window-start "2024-01-01T00:00:00Z" \\
        --window-end   "2024-01-01T02:00:00Z" \\
        --pmxt-root    /data/raw/pmxt_archive \\
        --jon-root     /data/raw/jon_becker \\
        [--out-dir     artifacts/silver/<token>/2024-01] \\
        [--dry-run]

    # Skip ClickHouse price_2min (offline mode):
    python -m polytool reconstruct-silver \\
        --token-id <TOKEN_ID> \\
        --window-start 1700000000 \\
        --window-end   1700007200 \\
        --pmxt-root /data/raw/pmxt_archive \\
        --jon-root  /data/raw/jon_becker \\
        --skip-price-2min

Notes:
  - --window-start and --window-end accept ISO 8601 strings or Unix epoch floats.
  - price_2min rows must be pre-populated via 'fetch-price-2min --token-id <ID>'
    before this command can include midpoint constraints.
  - The price_2min series is used as a guide only — it is NOT treated as tick data.
  - Jon timestamp ambiguity (bucketized timestamps) is surfaced in warnings.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def _parse_ts(value: str) -> float:
    """Parse a timestamp string as ISO 8601 or Unix epoch float.

    Returns Unix epoch seconds as a float.
    Raises ValueError on parse failure.
    """
    text = value.strip()
    if not text:
        raise ValueError("timestamp string is empty")

    # Try numeric epoch first
    try:
        f = float(text)
        if math.isfinite(f):
            return f
    except ValueError:
        pass

    # Try ISO 8601
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError as exc:
        raise ValueError(
            f"Cannot parse timestamp {value!r} as epoch float or ISO 8601: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reconstruct-silver",
        description=(
            "Reconstruct a Silver tape for one market/token over a bounded window.\n\n"
            "Fuses pmxt anchor state (DuckDB), Jon-Becker fills (DuckDB), and\n"
            "price_2min midpoint series (ClickHouse) into a deterministic tape."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--token-id",
        required=True,
        metavar="ID",
        help="Polymarket CLOB token ID (hex string).",
    )
    p.add_argument(
        "--window-start",
        required=True,
        metavar="TS",
        help="Window start as ISO 8601 (e.g. '2024-01-01T00:00:00Z') or Unix epoch float.",
    )
    p.add_argument(
        "--window-end",
        required=True,
        metavar="TS",
        help="Window end as ISO 8601 or Unix epoch float.",
    )
    p.add_argument(
        "--pmxt-root",
        default=None,
        metavar="PATH",
        help=(
            "Root of the pmxt_archive dataset. "
            "Expects a Polymarket/ subdirectory with .parquet files. "
            "Omit to skip pmxt anchor source."
        ),
    )
    p.add_argument(
        "--jon-root",
        default=None,
        metavar="PATH",
        help=(
            "Root of the jon_becker dataset. "
            "Expects data/polymarket/trades/ with .parquet or .csv files. "
            "Omit to skip Jon-Becker fill source."
        ),
    )
    p.add_argument(
        "--out-dir",
        default=None,
        metavar="PATH",
        help=(
            "Directory to write silver_events.jsonl and silver_meta.json. "
            "Auto-generated under artifacts/silver/ if not specified. "
            "Ignored when --dry-run is set."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run all fetch logic but do not write output files.",
    )
    p.add_argument(
        "--skip-price-2min",
        action="store_true",
        default=False,
        help="Skip the ClickHouse price_2min query (offline/test mode).",
    )
    p.add_argument(
        "--clickhouse-host",
        default="localhost",
        metavar="HOST",
        help="ClickHouse host for price_2min reads (default: localhost).",
    )
    p.add_argument(
        "--clickhouse-port",
        default=8123,
        type=int,
        metavar="PORT",
        help="ClickHouse HTTP port (default: 8123).",
    )
    p.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        metavar="USER",
        help="ClickHouse user (default: polytool_admin).",
    )
    p.add_argument(
        "--clickhouse-password",
        default=None,
        metavar="PASSWORD",
        help="ClickHouse password (falls back to CLICKHOUSE_PASSWORD env var).",
    )
    p.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="Write run record JSON to this path (in addition to --out-dir artifacts).",
    )
    return p


def _default_out_dir(token_id: str, window_start: float) -> Path:
    """Generate a default output directory under artifacts/silver/."""
    token_prefix = token_id[:8] if token_id else "unknown"
    try:
        dt = datetime.fromtimestamp(window_start, tz=timezone.utc)
        date_label = dt.strftime("%Y-%m-%dT%H%M%SZ")
    except Exception:
        date_label = str(int(window_start))
    return Path("artifacts") / "silver" / token_prefix / date_label


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint: python -m polytool reconstruct-silver [options]."""
    import os

    from packages.polymarket.silver_reconstructor import ReconstructConfig, SilverReconstructor

    parser = _build_parser()
    args = parser.parse_args(argv)

    # Parse timestamps
    try:
        window_start = _parse_ts(args.window_start)
    except ValueError as exc:
        print(f"Error: --window-start: {exc}", file=sys.stderr)
        return 1
    try:
        window_end = _parse_ts(args.window_end)
    except ValueError as exc:
        print(f"Error: --window-end: {exc}", file=sys.stderr)
        return 1

    if window_end <= window_start:
        print("Error: --window-end must be after --window-start.", file=sys.stderr)
        return 1

    # Resolve CH password
    ch_password = args.clickhouse_password
    if ch_password is None:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")

    # Resolve output directory
    if args.dry_run:
        out_dir = None
    elif args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = _default_out_dir(args.token_id, window_start)

    config = ReconstructConfig(
        pmxt_root=args.pmxt_root,
        jon_root=args.jon_root,
        clickhouse_host=args.clickhouse_host,
        clickhouse_port=args.clickhouse_port,
        clickhouse_user=args.clickhouse_user,
        clickhouse_password=ch_password,
        skip_price_2min=args.skip_price_2min,
    )

    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    print(
        f"[reconstruct-silver] [{mode_label}] token={args.token_id}",
        flush=True,
    )
    print(
        f"  window: {args.window_start} -> {args.window_end}",
        flush=True,
    )
    if config.pmxt_root:
        print(f"  pmxt-root:  {config.pmxt_root}")
    else:
        print("  pmxt-root:  (not set - pmxt source disabled)")
    if config.jon_root:
        print(f"  jon-root:   {config.jon_root}")
    else:
        print("  jon-root:   (not set - Jon-Becker source disabled)")
    if config.skip_price_2min:
        print("  price_2min: skipped")
    else:
        print(f"  price_2min: ClickHouse {config.clickhouse_host}:{config.clickhouse_port}")

    reconstructor = SilverReconstructor(config)
    result = reconstructor.reconstruct(
        token_id=args.token_id,
        window_start=window_start,
        window_end=window_end,
        out_dir=out_dir,
        dry_run=args.dry_run,
    )

    # Print result
    print(f"\n[reconstruct-silver] confidence={result.reconstruction_confidence}")
    print(f"  events:     {result.event_count}")
    print(f"  fills:      {result.fill_count}")
    print(f"  price_2min: {result.price_2min_count}")
    if result.warnings:
        print(f"  warnings:   {len(result.warnings)}")
        for w in result.warnings:
            print(f"    - {w}")
    if not args.dry_run and result.events_path:
        print(f"\n  silver_events.jsonl: {result.events_path}")
        print(f"  silver_meta.json:    {result.meta_path}")
    elif args.dry_run:
        print("\n  [dry-run] No files written.")

    if result.error:
        print(f"\nError: {result.error}", file=sys.stderr)
        return 1

    # Write run record if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Run record written to: {out_path}")

    # Exit code: 0 on success (even "none" confidence is not a hard failure;
    # the operator can decide based on confidence and warnings).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
