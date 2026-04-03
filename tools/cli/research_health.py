"""CLI entrypoint for RIS v1 health status reporting.

Usage:
  python -m polytool research-health
  python -m polytool research-health --json
  python -m polytool research-health --window-hours 24
  python -m polytool research-health --run-log artifacts/research/run_log.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list) -> int:
    """Print a health status summary from stored RIS run data.

    Loads pipeline run records from the run log, evaluates all 6 health
    checks, and fires log-only alerts for any YELLOW/RED conditions.

    Returns:
        0 always — health output is informational; non-zero would break cron.
    """
    parser = argparse.ArgumentParser(
        prog="research-health",
        description="Print a RIS health status summary from stored run data.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output raw JSON instead of human-readable table.",
    )
    parser.add_argument(
        "--window-hours",
        dest="window_hours",
        metavar="N",
        type=int,
        default=48,
        help="Look-back window in hours for run history (default: 48).",
    )
    parser.add_argument(
        "--run-log",
        dest="run_log",
        metavar="PATH",
        default="artifacts/research/run_log.jsonl",
        help="Path to the run log JSONL file (default: artifacts/research/run_log.jsonl).",
    )
    parser.add_argument(
        "--eval-artifacts",
        dest="eval_artifacts",
        metavar="PATH",
        default="artifacts/research/eval_artifacts/eval_artifacts.jsonl",
        help="Path to eval artifacts JSONL (reserved for future use).",
    )

    args = parser.parse_args(argv)

    run_log_path = Path(args.run_log)
    window_hours = args.window_hours

    # Load runs (graceful empty if file absent)
    try:
        from packages.research.monitoring.run_log import list_runs
        runs = list_runs(path=run_log_path, window_hours=window_hours)
    except Exception as exc:
        print(f"Error loading run log: {exc}", file=sys.stderr)
        runs = []

    # Evaluate health checks
    try:
        from packages.research.monitoring.health_checks import evaluate_health
        results = evaluate_health(runs, window_hours=window_hours)
    except Exception as exc:
        print(f"Error evaluating health: {exc}", file=sys.stderr)
        results = []

    # Fire log-only alerts for YELLOW/RED
    try:
        from packages.research.monitoring.alert_sink import LogSink, fire_alerts
        sink = LogSink()
        fire_alerts(results, sink)
    except Exception:
        pass  # Alert failure is non-fatal

    run_count = len(runs)

    if args.output_json:
        return _output_json(results, run_count)
    else:
        return _output_table(results, run_count, window_hours)


def _output_json(results: list, run_count: int) -> int:
    """Print JSON summary to stdout."""
    # Determine overall summary status
    if run_count == 0:
        overall = "no_data"
    elif any(r.status == "RED" for r in results):
        overall = "RED"
    elif any(r.status == "YELLOW" for r in results):
        overall = "YELLOW"
    else:
        overall = "GREEN"

    checks_data = [
        {
            "check_name": r.check_name,
            "status": r.status,
            "message": r.message,
            "data": r.data,
        }
        for r in results
    ]

    output = {
        "checks": checks_data,
        "summary": overall,
        "run_count": run_count,
    }
    print(json.dumps(output, indent=2))
    return 0


def _output_table(results: list, run_count: int, window_hours: int) -> int:
    """Print human-readable health summary table to stdout."""
    if run_count == 0:
        print(f"RIS Health Summary ({window_hours}h window, 0 runs)")
        print("No run data available. Run 'research-ingest' or 'research-scheduler' first.")
        return 0

    # Determine overall
    if any(r.status == "RED" for r in results):
        overall = "RED"
    elif any(r.status == "YELLOW" for r in results):
        overall = "YELLOW"
    else:
        overall = "GREEN"

    print(f"RIS Health Summary ({window_hours}h window, {run_count} runs) — {overall}")
    print("")
    # Column widths
    col_check = 40
    col_status = 8
    header = f"{'CHECK':<{col_check}} {'STATUS':<{col_status}} MESSAGE"
    print(header)
    print("-" * max(80, len(header)))

    for r in results:
        status_display = r.status
        print(f"{r.check_name:<{col_check}} {status_display:<{col_status}} {r.message}")

    return 0
