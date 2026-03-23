"""CLI: new-market-capture — discover and plan Gold tape capture for new markets.

Queries the live Gamma API for recently listed markets, filters to those < 48h old,
ranks them conservatively, and writes:

  config/benchmark_v1_new_market_capture.targets.json   — when >= 1 candidate found
  config/benchmark_v1_new_market_capture.insufficiency.json — when < required

Exit codes:
  0 — targets manifest written with at least ``required`` (default 5) targets.
  2 — partial result: targets manifest written but fewer than required.
  1 — no candidates found; only insufficiency report written (or error).

Usage:
    python -m polytool new-market-capture
    python -m polytool new-market-capture --dry-run
    python -m polytool new-market-capture --limit 500 --max-age-hours 24
    python -m polytool new-market-capture --required 5 --record-duration 3600
    python -m polytool new-market-capture --output config/my_targets.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.new_market_capture_planner import (
    DEFAULT_RECORD_DURATION_SECONDS,
    DEFAULT_REQUIRED_TARGETS,
    NEW_MARKET_MAX_AGE_HOURS,
    plan_new_market_capture,
)

# Module-level import enables unittest.mock.patch to target this symbol.
try:
    from packages.polymarket.market_selection.api_client import fetch_recent_markets
except ImportError:
    fetch_recent_markets = None  # type: ignore[assignment]

_DEFAULT_TARGETS_PATH = Path("config/benchmark_v1_new_market_capture.targets.json")
_DEFAULT_INSUFFICIENCY_PATH = Path("config/benchmark_v1_new_market_capture.insufficiency.json")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, allow_nan=False),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover newly listed Polymarket markets (<48h) via the live Gamma API "
            "and write a Gold-tape capture plan for the benchmark_v1 new_market bucket."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="Maximum number of markets to fetch from Gamma API (default: 300).",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=NEW_MARKET_MAX_AGE_HOURS,
        help=f"Maximum market age in hours to qualify as new_market (default: {NEW_MARKET_MAX_AGE_HOURS}).",
    )
    parser.add_argument(
        "--required",
        type=int,
        default=DEFAULT_REQUIRED_TARGETS,
        help=f"Required number of targets to consider discovery sufficient (default: {DEFAULT_REQUIRED_TARGETS}).",
    )
    parser.add_argument(
        "--record-duration",
        type=int,
        default=DEFAULT_RECORD_DURATION_SECONDS,
        help=f"Gold tape record duration per market in seconds (default: {DEFAULT_RECORD_DURATION_SECONDS}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"Target manifest output path (default: {_DEFAULT_TARGETS_PATH}).",
    )
    parser.add_argument(
        "--insufficiency-output",
        default=None,
        help=f"Insufficiency report path (default: {_DEFAULT_INSUFFICIENCY_PATH}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and classify markets but do not write output files.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.limit <= 0:
        print("Error: --limit must be positive.", file=sys.stderr)
        return 1
    if args.max_age_hours <= 0:
        print("Error: --max-age-hours must be positive.", file=sys.stderr)
        return 1
    if args.required <= 0:
        print("Error: --required must be positive.", file=sys.stderr)
        return 1
    if args.record_duration <= 0:
        print("Error: --record-duration must be positive.", file=sys.stderr)
        return 1

    targets_path = Path(args.output) if args.output else _DEFAULT_TARGETS_PATH
    insuff_path = Path(args.insufficiency_output) if args.insufficiency_output else _DEFAULT_INSUFFICIENCY_PATH

    # ---------------------------------------------------------------------------
    # Fetch from Gamma API
    # ---------------------------------------------------------------------------
    try:
        markets = fetch_recent_markets(limit=args.limit)
    except Exception as exc:
        print(f"Error fetching markets from Gamma API: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Fetched {len(markets)} markets from Gamma API.")

    # ---------------------------------------------------------------------------
    # Run planner
    # ---------------------------------------------------------------------------
    try:
        result = plan_new_market_capture(
            markets=markets,
            required=args.required,
            record_duration_seconds=args.record_duration,
            max_age_hours=args.max_age_hours,
        )
    except Exception as exc:
        print(f"Error running new-market capture planner: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # ---------------------------------------------------------------------------
    # Print summary
    # ---------------------------------------------------------------------------
    print(f"Candidates found (age < {args.max_age_hours}h): {result.candidates_found}")
    print(f"Required: {result.required}")
    if result.targets:
        print(f"Targets selected: {len(result.targets)}")
        print()
        print(f"{'#':>3}  {'slug':<40}  {'age_h':>6}  {'listed_at'}")
        print("-" * 80)
        for t in result.targets:
            print(f"{t.priority:>3}  {t.slug[:40]:<40}  {t.age_hours:>6.2f}  {t.listed_at}")
    else:
        print("No new-market candidates found.")

    if result.insufficient:
        shortage = result.required - len(result.targets)
        print()
        print(f"INSUFFICIENT: {len(result.targets)}/{result.required} targets found (shortage={shortage}).")
        print(f"Reason: {result.insufficiency_reason}")

    if args.dry_run:
        print()
        print("--dry-run: no files written.")
        return 0 if not result.insufficient else 2

    # ---------------------------------------------------------------------------
    # Write output
    # ---------------------------------------------------------------------------
    if result.targets:
        manifest = result.to_targets_manifest()
        _write_json(targets_path, manifest)
        print()
        print(f"Targets manifest written: {targets_path}")

    if result.insufficient:
        report = result.to_insufficiency_report()
        _write_json(insuff_path, report)
        print(f"Insufficiency report written: {insuff_path}")

    if not result.targets and not result.insufficient:
        # Should not happen, but be safe
        print("Warning: no targets and not marked insufficient — this is a bug.", file=sys.stderr)
        return 1

    # Exit 0 when fully covered, 2 when partially covered, 1 when zero candidates
    if not result.insufficient:
        return 0
    if result.targets:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
