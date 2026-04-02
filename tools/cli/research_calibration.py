"""RIS Phase 2 — research-calibration CLI entrypoint.

Provides the 'research-calibration' subcommand for inspecting calibration
health over the precheck ledger.

Usage::

    python -m polytool research-calibration summary [--window 30d] [--json] [--manifest PATH]
    python -m polytool research-calibration summary --window all --json
    python -m polytool research-calibration summary --window 7d --ledger PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packages.research.synthesis.precheck_ledger import (
    DEFAULT_LEDGER_PATH,
    list_prechecks,
    list_prechecks_by_window,
)
from packages.research.synthesis.calibration import (
    CalibrationSummary,
    FamilyDriftReport,
    compute_calibration_summary,
    compute_family_drift,
    format_calibration_report,
)


# ---------------------------------------------------------------------------
# Window parsing
# ---------------------------------------------------------------------------


def _parse_window(window: str) -> tuple[str | None, str | None]:
    """Parse a window spec into (start_iso, end_iso) or (None, None) for 'all'.

    Supported formats:
    - "all": no time filter
    - "<N>d": last N days (e.g. "7d", "30d")
    - "<N>h": last N hours

    Args:
        window: Window specification string.

    Returns:
        (start_iso, end_iso) tuple or (None, None) for "all".

    Raises:
        ValueError: If the window format is unrecognized.
    """
    if window.lower() == "all":
        return None, None

    now = datetime.now(timezone.utc).replace(microsecond=0)

    if window.endswith("d"):
        try:
            days = int(window[:-1])
            start = now - timedelta(days=days)
            return start.isoformat(), now.isoformat()
        except ValueError:
            pass
    elif window.endswith("h"):
        try:
            hours = int(window[:-1])
            start = now - timedelta(hours=hours)
            return start.isoformat(), now.isoformat()
        except ValueError:
            pass

    raise ValueError(
        f"Unrecognized window format: {window!r}. "
        "Use 'all', '<N>d' (e.g. '7d', '30d'), or '<N>h' (e.g. '24h')."
    )


# ---------------------------------------------------------------------------
# Subcommand: summary
# ---------------------------------------------------------------------------


def _run_summary(args: argparse.Namespace) -> int:
    """Execute the 'summary' subcommand."""
    ledger_path = Path(args.ledger) if args.ledger else DEFAULT_LEDGER_PATH

    # Parse window
    try:
        start_iso, end_iso = _parse_window(args.window)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Load events
    try:
        if start_iso is None:
            events = list_prechecks(ledger_path=ledger_path)
            window_start = "all"
            window_end = "all"
        else:
            events = list_prechecks_by_window(
                start_iso=start_iso,
                end_iso=end_iso,
                ledger_path=ledger_path,
            )
            window_start = start_iso
            window_end = end_iso
    except Exception as exc:
        print(f"Error reading ledger: {exc}", file=sys.stderr)
        return 1

    # Compute summary
    summary = compute_calibration_summary(
        events,
        window_start=window_start,
        window_end=window_end,
    )

    # Optionally compute drift
    drift: FamilyDriftReport | None = None
    if hasattr(args, "manifest") and args.manifest:
        manifest_path = Path(args.manifest)
        try:
            from packages.research.ingestion.seed import load_seed_manifest
            manifest = load_seed_manifest(manifest_path)
            drift = compute_family_drift(events, manifest=manifest)
        except FileNotFoundError:
            print(f"Warning: manifest not found at {manifest_path}", file=sys.stderr)
            drift = compute_family_drift(events)
        except Exception as exc:
            print(f"Warning: failed to load manifest: {exc}", file=sys.stderr)
            drift = compute_family_drift(events)
    else:
        drift = compute_family_drift(events)

    # Output
    if args.json:
        # Machine-readable JSON output
        output = {
            "window_start": summary.window_start,
            "window_end": summary.window_end,
            "total_prechecks": summary.total_prechecks,
            "recommendation_distribution": summary.recommendation_distribution,
            "override_count": summary.override_count,
            "override_rate": summary.override_rate,
            "outcome_distribution": summary.outcome_distribution,
            "outcome_count": summary.outcome_count,
            "stale_warning_count": summary.stale_warning_count,
            "avg_evidence_count": summary.avg_evidence_count,
        }
        if drift is not None:
            output["family_drift"] = {
                "family_counts": drift.family_counts,
                "overrepresented_in_stop": drift.overrepresented_in_stop,
                "total_prechecks": drift.total_prechecks,
            }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable text report
        report = format_calibration_report(summary, drift)
        print(report)

    return 0


# ---------------------------------------------------------------------------
# main() entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    """research-calibration CLI entrypoint.

    Args:
        argv: Argument list (without 'research-calibration' prefix).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(
        prog="polytool research-calibration",
        description="Inspect RIS precheck calibration health over the ledger.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", metavar="SUBCOMMAND")

    # --- summary subcommand ---
    summary_parser = subparsers.add_parser(
        "summary",
        help="Compute calibration summary over a time window.",
    )
    summary_parser.add_argument(
        "--window",
        default="30d",
        metavar="DURATION",
        help=(
            "Time window to analyze. Use 'all' for all time, '<N>d' for last N days "
            "(e.g. '7d', '30d'), or '<N>h' for last N hours. Default: 30d."
        ),
    )
    summary_parser.add_argument(
        "--ledger",
        default=None,
        metavar="PATH",
        help=f"Path to the precheck ledger JSONL file. Default: {DEFAULT_LEDGER_PATH}",
    )
    summary_parser.add_argument(
        "--manifest",
        default=None,
        metavar="PATH",
        help="Optional path to seed_manifest.json for family drift attribution.",
    )
    summary_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output machine-readable JSON instead of formatted text report.",
    )

    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help()
        return 1

    if args.subcommand == "summary":
        return _run_summary(args)

    parser.print_help()
    return 1
