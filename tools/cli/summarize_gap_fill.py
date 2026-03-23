"""CLI: summarize-gap-fill — read-only diagnostic summary for gap_fill_run.json artifacts.

Loads a benchmark_gap_fill_run_v1 artifact and prints:
  - Top-level totals (targets attempted / tapes created / failures / skips)
  - Per-bucket breakdown (success / failure / skip counts + confidence distribution)
  - Normalized failure reasons (grouped by warning class + error class)
  - Success classes (confidence tier, fill vs. price_2min-only, etc.)
  - Referenced artifact paths

No network access. No ClickHouse. No writes.

Usage:
    python -m polytool summarize-gap-fill --path artifacts/silver/.../gap_fill_run.json
    python -m polytool summarize-gap-fill --path artifacts/silver/.../gap_fill_run.json --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SUPPORTED_SCHEMA = "benchmark_gap_fill_run_v1"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalize_warning(warning: str) -> str:
    """Strip per-token token IDs and timestamps from a warning string.

    Returns a short canonical warning class string, e.g. 'pmxt_anchor_missing'.
    """
    # Most warnings start with <class>: …  — keep only the class prefix.
    colon_idx = warning.find(":")
    if colon_idx != -1:
        class_part = warning[:colon_idx].strip()
        # Strip any trailing whitespace / common suffix noise
        return class_part
    # Fallback: strip hex token IDs and ISO timestamps, truncate
    cleaned = re.sub(r"\b[0-9]{20,}\b", "<TOKEN>", warning)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s]*", "<TS>", cleaned)
    return cleaned[:80]


def _normalize_error(error: str) -> str:
    """Reduce a free-form error string to a short normalized class."""
    if not error:
        return ""
    cleaned = re.sub(r"\b[0-9]{20,}\b", "<TOKEN>", error)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s]*", "<TS>", cleaned)
    # Grab up to first 120 chars
    return cleaned[:120]


# ---------------------------------------------------------------------------
# Core summariser
# ---------------------------------------------------------------------------

def summarize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Produce a structured summary dict from a gap_fill_run_v1 artifact dict."""
    outcomes: List[dict] = data.get("outcomes", [])

    # --- top-level totals ---
    totals = {
        "targets_attempted": data.get("targets_attempted", len(outcomes)),
        "tapes_created": data.get("tapes_created", 0),
        "failure_count": data.get("failure_count", 0),
        "skip_count": data.get("skip_count", 0),
        "dry_run": data.get("dry_run", False),
        "started_at": data.get("started_at"),
        "ended_at": data.get("ended_at"),
        "batch_run_id": data.get("batch_run_id"),
    }

    # --- per-bucket breakdown ---
    bucket_stats: Dict[str, Dict] = defaultdict(lambda: {
        "success": 0,
        "failure": 0,
        "skip": 0,
        "confidence": Counter(),
    })

    # --- warning + error accumulators ---
    warning_counts: Counter = Counter()
    error_counts: Counter = Counter()

    # --- success classes ---
    success_classes: Counter = Counter()

    # --- artifact paths ---
    artifact_paths: List[str] = []
    seen_paths: set = set()

    for outcome in outcomes:
        bucket = outcome.get("bucket") or "unknown"
        status = outcome.get("status", "unknown")
        confidence = outcome.get("reconstruction_confidence") or "none"

        bs = bucket_stats[bucket]
        if status == "success":
            bs["success"] += 1
        elif status == "failure":
            bs["failure"] += 1
        elif status == "skip":
            bs["skip"] += 1

        bs["confidence"][confidence] += 1

        # Warnings -> normalized classes
        for w in outcome.get("warnings") or []:
            warning_counts[_normalize_warning(w)] += 1

        # Errors -> normalized classes
        err = outcome.get("error")
        if err:
            error_counts[_normalize_error(err)] += 1

        # Success classes
        if status == "success":
            fills = outcome.get("fill_count", 0) or 0
            p2m = outcome.get("price_2min_count", 0) or 0
            if fills > 0 and p2m > 0:
                label = f"confidence={confidence}, has_fills+price_2min"
            elif fills == 0 and p2m > 0:
                label = f"confidence={confidence}, price_2min_only"
            elif fills > 0:
                label = f"confidence={confidence}, fills_only"
            else:
                label = f"confidence={confidence}, empty_tape"
            success_classes[label] += 1

        # Artifact paths
        for path_key in ("events_path", "out_dir"):
            p = outcome.get(path_key)
            if p and p not in seen_paths:
                artifact_paths.append(p)
                seen_paths.add(p)

    # Convert bucket_stats counters to plain dicts for serialisation
    bucket_summary = {}
    for bucket, stats in sorted(bucket_stats.items()):
        bucket_summary[bucket] = {
            "success": stats["success"],
            "failure": stats["failure"],
            "skip": stats["skip"],
            "confidence_breakdown": dict(stats["confidence"]),
        }

    # Benchmark refresh outcome
    refresh = data.get("benchmark_refresh") or {}

    return {
        "schema_version": data.get("schema_version"),
        "totals": totals,
        "by_bucket": bucket_summary,
        "warning_classes": dict(warning_counts.most_common()),
        "error_classes": dict(error_counts.most_common()),
        "success_classes": dict(success_classes.most_common()),
        "metadata_summary": data.get("metadata_summary"),
        "benchmark_refresh": refresh,
        "artifact_paths": artifact_paths[:20],  # cap to avoid overwhelming output
    }


# ---------------------------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------------------------

def _fmt_counter(d: Dict[str, int], indent: str = "  ") -> List[str]:
    lines = []
    for k, v in sorted(d.items(), key=lambda x: -x[1]):
        lines.append(f"{indent}{k}: {v}")
    return lines


def print_summary(summary: Dict[str, Any], *, path: Optional[Path] = None) -> None:
    """Print a human-readable summary to stdout."""
    sep = "-" * 60

    print(sep)
    if path:
        print(f"  gap_fill_run: {path}")
    print(sep)

    t = summary["totals"]
    print(f"  schema          : {summary['schema_version']}")
    print(f"  batch_run_id    : {t['batch_run_id']}")
    if t.get("started_at"):
        print(f"  started_at      : {t['started_at']}")
    if t.get("ended_at"):
        print(f"  ended_at        : {t['ended_at']}")
    dry_tag = "  [DRY RUN]" if t.get("dry_run") else ""
    print(f"  dry_run         : {t['dry_run']}{dry_tag}")
    print()

    print("TOTALS")
    print(f"  targets_attempted : {t['targets_attempted']}")
    print(f"  tapes_created     : {t['tapes_created']}")
    print(f"  failure_count     : {t['failure_count']}")
    print(f"  skip_count        : {t['skip_count']}")
    print()

    print("BY BUCKET")
    by_bucket = summary.get("by_bucket") or {}
    if not by_bucket:
        print("  (no buckets found)")
    else:
        for bucket, stats in by_bucket.items():
            conf = stats.get("confidence_breakdown") or {}
            conf_str = ", ".join(f"{c}:{n}" for c, n in sorted(conf.items()))
            print(
                f"  {bucket:<20} "
                f"success={stats['success']}  "
                f"failure={stats['failure']}  "
                f"skip={stats['skip']}  "
                f"confidence=[{conf_str}]"
            )
    print()

    success_classes = summary.get("success_classes") or {}
    if success_classes:
        print("SUCCESS CLASSES")
        for line in _fmt_counter(success_classes):
            print(line)
        print()

    warning_classes = summary.get("warning_classes") or {}
    if warning_classes:
        print("WARNING CLASSES  (normalized, occurrence count)")
        for line in _fmt_counter(warning_classes):
            print(line)
        print()

    error_classes = summary.get("error_classes") or {}
    if error_classes:
        print("ERROR CLASSES  (normalized, occurrence count)")
        for line in _fmt_counter(error_classes):
            print(line)
        print()

    meta = summary.get("metadata_summary") or {}
    if meta:
        print("METADATA WRITES")
        for k, v in sorted(meta.items()):
            print(f"  {k}: {v}")
        print()

    refresh = summary.get("benchmark_refresh") or {}
    if refresh:
        print("BENCHMARK REFRESH")
        triggered = refresh.get("triggered", False)
        outcome = refresh.get("outcome", "not_requested")
        print(f"  triggered : {triggered}")
        print(f"  outcome   : {outcome}")
        if refresh.get("manifest_path"):
            print(f"  manifest  : {refresh['manifest_path']}")
        if refresh.get("gap_report_path"):
            print(f"  gap_report: {refresh['gap_report_path']}")
        if refresh.get("return_code") is not None:
            print(f"  return_code: {refresh['return_code']}")
        print()

    artifact_paths = summary.get("artifact_paths") or []
    if artifact_paths:
        print("ARTIFACT PATHS  (first 20)")
        for p in artifact_paths[:20]:
            print(f"  {p}")
        print()

    print(sep)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polytool summarize-gap-fill",
        description=(
            "Read-only diagnostic summary for gap_fill_run.json artifacts. "
            "Prints totals, bucket breakdown, normalized failure reasons, "
            "success classes, and artifact paths."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        metavar="PATH",
        help="Path to gap_fill_run.json artifact.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        default=False,
        help="Output summary as JSON instead of human-readable text.",
    )

    args = parser.parse_args(argv)
    target_path = Path(args.path)

    if not target_path.exists():
        print(f"Error: file not found: {target_path}", file=sys.stderr)
        return 1

    try:
        text = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: cannot read {target_path}: {exc}", file=sys.stderr)
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {target_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("Error: gap_fill_run.json root must be a JSON object.", file=sys.stderr)
        return 1

    sv = data.get("schema_version")
    if sv != SUPPORTED_SCHEMA:
        print(
            f"Warning: unexpected schema_version {sv!r} (expected {SUPPORTED_SCHEMA!r}). "
            "Proceeding anyway.",
            file=sys.stderr,
        )

    summary = summarize(data)

    if args.output_json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print_summary(summary, path=target_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
