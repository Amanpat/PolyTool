"""Create a watchlist + watcher-compatible session plan for a capture session.

Produces a JSON session pack that includes:
  - A watchlist of market slugs sourced from an existing report-to-watchlist file
    or from explicit --markets CLI input.
  - A ``watch_config`` block with ``near_edge_threshold`` set from the regime-aware
    capture defaults unless the operator explicitly supplies ``--near-edge``.
  - Provenance fields (``threshold_source``, ``regime``) so downstream artifacts
    can trace exactly which threshold was used and why.

Regime-aware thresholds (capture only; Gate 2 eligibility NOT changed):
  - sports     : 0.99  (current default, unchanged)
  - politics   : 1.03  (looser — politics edges are fleeting; capture early)
  - new_market : 1.015 (slightly looser — wider net for shallow-book markets)

Gate 2 eligibility, sweep pass criteria, and Gate 2 scoring are NOT affected.
This tool only sets the *watcher capture threshold* for tape collection.

Usage
-----
  # Session pack for a politics watchlist:
  python -m polytool make-session-pack --regime politics --markets slug1,slug2

  # Load watchlist from an existing report-derived file:
  python -m polytool make-session-pack --regime politics \\
      --watchlist-file artifacts/watchlist.json

  # Explicit operator override (wins over regime default):
  python -m polytool make-session-pack --regime politics --near-edge 0.995 \\
      --markets slug1,slug2

  # Sports (threshold stays 0.99):
  python -m polytool make-session-pack --regime sports --markets slug1,slug2

  # Write pack to a specific file:
  python -m polytool make-session-pack --regime politics --markets slug1,slug2 \\
      --output artifacts/debug/session_packs/politics_2026-03-11.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_DURATION: float = 300.0
_DEFAULT_NEAR_EDGE_OVERRIDE: Optional[float] = None  # None means "use regime default"
_DEFAULT_OUTPUT_DIR = Path("artifacts/debug/session_packs")

# Valid regime choices for --regime
_REGIME_CHOICES = ("politics", "sports", "new_market")


# ---------------------------------------------------------------------------
# Core: resolve threshold with provenance
# ---------------------------------------------------------------------------


def resolve_session_threshold(
    *,
    regime: Optional[str],
    near_edge_override: Optional[float],
) -> tuple[float, str]:
    """Return (near_edge_threshold, threshold_source) for a session pack.

    Priority: operator ``near_edge_override`` > regime default > global default.

    Args:
        regime:              One of "politics", "sports", "new_market", or None.
        near_edge_override:  If provided, this value wins unconditionally.

    Returns:
        ``(threshold, source_label)`` where source_label is one of:
        "operator-override", "regime-default", "global-default".
    """
    from packages.polymarket.market_selection.regime_policy import (
        _DEFAULT_CAPTURE_THRESHOLD,
        get_regime_capture_threshold,
    )

    if near_edge_override is not None:
        return near_edge_override, "operator-override"
    if regime is not None:
        return get_regime_capture_threshold(regime), "regime-default"
    return _DEFAULT_CAPTURE_THRESHOLD, "global-default"


# ---------------------------------------------------------------------------
# Session pack builder
# ---------------------------------------------------------------------------


def build_session_pack(
    *,
    regime: Optional[str],
    watchlist: list[dict[str, Any]],
    near_edge_threshold: float,
    threshold_source: str,
    duration_seconds: float,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Assemble the session pack dict.

    Args:
        regime:               Regime label ("politics", "sports", "new_market", or None).
        watchlist:            List of watchlist entry dicts, each with at minimum
                              ``market_slug``.
        near_edge_threshold:  The resolved capture threshold (already derived from
                              regime or operator override).
        threshold_source:     Provenance label for the threshold.
        duration_seconds:     Default tape recording duration in seconds.
        created_at:           ISO-8601 string; defaults to now (UTC) if None.

    Returns:
        Session pack dict ready for JSON serialisation.
    """
    ts = created_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "session_pack_v1",
        "created_at": ts,
        "session": {
            "regime": regime,
            "near_edge_threshold_used": near_edge_threshold,
            "threshold_source": threshold_source,
        },
        "watch_config": {
            "near_edge_threshold": near_edge_threshold,
            "threshold_source": threshold_source,
            "duration_seconds": duration_seconds,
        },
        "watchlist": watchlist,
    }


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------


def _parse_markets_to_watchlist(markets: Optional[str]) -> list[dict[str, Any]]:
    """Parse --markets comma-separated slugs into watchlist entries."""
    if not markets:
        return []
    return [
        {"market_slug": slug.strip()}
        for slug in markets.split(",")
        if slug.strip()
    ]


def _load_watchlist_entries(path: str | Path) -> list[dict[str, Any]]:
    """Load watchlist entries from a report-to-watchlist JSON file.

    Expects a JSON object with a top-level ``watchlist`` array, each item
    containing at minimum ``market_slug``.

    Raises:
        ValueError: If the file is missing, unparseable, or malformed.
    """
    watchlist_path = Path(path)
    try:
        payload = json.loads(watchlist_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"watchlist file not found: {watchlist_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"watchlist file is not valid JSON: {watchlist_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("watchlist file must be a JSON object with a top-level 'watchlist' array.")

    watchlist = payload.get("watchlist")
    if not isinstance(watchlist, list):
        raise ValueError("watchlist file must include a top-level 'watchlist' array.")

    for i, item in enumerate(watchlist, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"watchlist[{i}] must be an object.")
        if not isinstance(item.get("market_slug"), str) or not item["market_slug"].strip():
            raise ValueError(f"watchlist[{i}] missing required 'market_slug'.")

    return watchlist


def _merge_watchlist(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge watchlist entries from multiple sources, deduplicating by market_slug."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        for entry in source:
            slug = entry.get("market_slug", "").strip()
            if slug and slug not in seen:
                seen.add(slug)
                merged.append(entry)
    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="make-session-pack",
        description=(
            "Create a watchlist + watcher-compatible session plan for a capture session.\n\n"
            "Sets watch_config.near_edge_threshold from the regime-aware default unless\n"
            "the operator explicitly supplies --near-edge. Gate 2 eligibility, sweep\n"
            "criteria, and Gate 2 scoring are NOT affected by this command."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--regime",
        choices=_REGIME_CHOICES,
        default=None,
        metavar="REGIME",
        help=(
            "Target regime: politics | sports | new_market. "
            "Sets near_edge_threshold from the regime-aware default: "
            "sports=0.99, politics=1.03, new_market=1.015. "
            "Overridden by --near-edge if both are supplied."
        ),
    )
    p.add_argument(
        "--markets",
        metavar="SLUG[,SLUG...]",
        help="Comma-separated market slugs to include in the watchlist.",
    )
    p.add_argument(
        "--watchlist-file",
        metavar="PATH",
        help=(
            "Path to a report-to-watchlist JSON file with a top-level 'watchlist' array. "
            "Merged with --markets (duplicates removed)."
        ),
    )
    p.add_argument(
        "--near-edge",
        type=float,
        default=None,
        metavar="F",
        help=(
            "Explicit capture threshold (operator override). "
            "When set, overrides the regime-aware default. "
            "threshold_source will be set to 'operator-override'."
        ),
    )
    p.add_argument(
        "--duration",
        type=float,
        default=_DEFAULT_DURATION,
        metavar="SECS",
        help="Default tape recording duration per triggered market (default: %(default)s).",
    )
    p.add_argument(
        "--output",
        metavar="PATH",
        help=(
            "Output path for the session pack JSON. "
            f"Default: {_DEFAULT_OUTPUT_DIR}/<timestamp>_session_pack.json"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the session pack to stdout instead of writing a file.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint: python -m polytool make-session-pack [options]."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate
    if not args.markets and not args.watchlist_file:
        print(
            "Error: supply at least one market via --markets or --watchlist-file.",
            file=sys.stderr,
        )
        return 1

    if args.near_edge is not None and not (0.0 < args.near_edge <= 2.0):
        print("Error: --near-edge must be between 0 and 2.", file=sys.stderr)
        return 1

    if args.duration <= 0:
        print("Error: --duration must be positive.", file=sys.stderr)
        return 1

    # Resolve threshold
    near_edge_threshold, threshold_source = resolve_session_threshold(
        regime=args.regime,
        near_edge_override=args.near_edge,
    )

    # Build watchlist
    direct_entries = _parse_markets_to_watchlist(args.markets)
    file_entries: list[dict[str, Any]] = []
    if args.watchlist_file:
        try:
            file_entries = _load_watchlist_entries(args.watchlist_file)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    watchlist = _merge_watchlist(direct_entries, file_entries)
    if not watchlist:
        print("Error: no markets in watchlist after merging.", file=sys.stderr)
        return 1

    # Build pack
    pack = build_session_pack(
        regime=args.regime,
        watchlist=watchlist,
        near_edge_threshold=near_edge_threshold,
        threshold_source=threshold_source,
        duration_seconds=args.duration,
    )

    pack_json = json.dumps(pack, indent=2)

    if args.dry_run:
        print(pack_json)
        return 0

    # Write output
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = _DEFAULT_OUTPUT_DIR / f"{ts}_session_pack.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pack_json, encoding="utf-8")

    regime_label = args.regime or "(no regime)"
    print(
        f"[make-session-pack] Session pack written: {output_path}\n"
        f"  regime={regime_label}  near_edge_threshold={near_edge_threshold:.4f}"
        f"  threshold_source={threshold_source}"
        f"  markets={len(watchlist)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
