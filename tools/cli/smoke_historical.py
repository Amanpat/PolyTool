"""DuckDB smoke command — validate raw historical files directly without ClickHouse.

CLI: python -m polytool smoke-historical [options]

Sources:
  pmxt_archive  Polymarket pmxt hourly L2 Parquet snapshots
                Expected layout: <root>/Polymarket/**/*.parquet

  jon_becker    Jon-Becker 72M-trade dataset
                Expected layout: <root>/data/polymarket/trades/**/*.parquet
                Fallback (no parquet):  trades/**/*.csv  or  trades/**/*.csv.gz

Output:
  Compact validation summary per source — file pattern, row count, min/max ts.
  Exits nonzero if no readable source files are found across all provided roots.

Examples::

    python -m polytool smoke-historical \\
        --pmxt-root D:/PolyToolData/raw/pmxt_archive \\
        --jon-root  D:/PolyToolData/raw/jon_becker

    python -m polytool smoke-historical --pmxt-root /data/raw/pmxt_archive
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Timestamp column candidates (mirrors the ClickHouse importer heuristics)
# ---------------------------------------------------------------------------

_PMXT_TS_CANDIDATES = [
    "snapshot_ts",
    "timestamp_received",
    "timestamp_created_at",
    "ts",
    "timestamp",
    "datetime",
]

_JON_TS_CANDIDATES = [
    "timestamp",
    "ts",
    "time",
    "t",
    "_fetched_at",
]


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------


def _find_pmxt_parquet(root: Path) -> List[Path]:
    """Return all .parquet files under <root>/Polymarket/."""
    poly_dir = root / "Polymarket"
    if not poly_dir.is_dir():
        return []
    return sorted(poly_dir.rglob("*.parquet"))


def _find_jon_parquet(root: Path) -> List[Path]:
    """Return .parquet files under <root>/data/polymarket/trades/."""
    trades_dir = root / "data" / "polymarket" / "trades"
    if not trades_dir.is_dir():
        return []
    return sorted(trades_dir.rglob("*.parquet"))


def _find_jon_csv(root: Path) -> Tuple[List[Path], str]:
    """Return CSV or CSV.GZ files under trades/ and the detected extension.

    Returns (files, ext) where ext is ``"csv"`` or ``"csv.gz"``.
    Prefers plain CSV; falls back to CSV.GZ.
    """
    trades_dir = root / "data" / "polymarket" / "trades"
    if not trades_dir.is_dir():
        return [], ""
    csvs = sorted(trades_dir.rglob("*.csv"))
    if csvs:
        return csvs, "csv"
    gz = sorted(trades_dir.rglob("*.csv.gz"))
    return gz, "csv.gz" if gz else ""


# ---------------------------------------------------------------------------
# Per-source smoke routines
# ---------------------------------------------------------------------------


def _fmt_count(n: int) -> str:
    return f"{n:,}"


def _smoke_pmxt(root_str: str) -> Tuple[bool, str]:
    """Smoke-test the pmxt_archive source.

    Returns:
        Tuple of (ok: bool, report: str).
    """
    from packages.polymarket import duckdb_helper as dh

    root = Path(root_str).resolve()
    label = "pmxt_archive"
    files = _find_pmxt_parquet(root)

    if not files:
        poly_dir = root / "Polymarket"
        report = (
            f"[smoke-historical] {label}\n"
            f"  root:    {root}\n"
            f"  status:  NO FILES — {poly_dir} not found or contains no .parquet files\n"
        )
        return False, report

    glob = str(root / "Polymarket" / "**" / "*.parquet")
    pattern_display = f"<pmxt_root>/Polymarket/**/*.parquet  ({len(files)} file(s))"

    with dh.connection() as conn:
        summary = dh.scan_parquet(conn, glob, ts_candidates=_PMXT_TS_CANDIDATES)

    if summary.error:
        report = (
            f"[smoke-historical] {label}\n"
            f"  pattern:   {pattern_display}\n"
            f"  status:    ERROR — {summary.error}\n"
        )
        return False, report

    ts_line = _ts_line(summary)
    report = (
        f"[smoke-historical] {label}\n"
        f"  pattern:   {pattern_display}\n"
        f"  row_count: {_fmt_count(summary.row_count)}\n"
        f"{ts_line}"
        f"  status:    OK\n"
    )
    return True, report


def _smoke_jon(root_str: str) -> Tuple[bool, str]:
    """Smoke-test the jon_becker source.

    Returns:
        Tuple of (ok: bool, report: str).
    """
    from packages.polymarket import duckdb_helper as dh

    root = Path(root_str).resolve()
    label = "jon_becker"
    trades_dir = root / "data" / "polymarket" / "trades"

    parquet_files = _find_jon_parquet(root)
    csv_files, csv_ext = _find_jon_csv(root)

    if not parquet_files and not csv_files:
        report = (
            f"[smoke-historical] {label}\n"
            f"  root:    {root}\n"
            f"  status:  NO FILES — {trades_dir} not found or"
            f" contains no .parquet / .csv / .csv.gz files\n"
        )
        return False, report

    with dh.connection() as conn:
        if parquet_files:
            glob = str(trades_dir / "**" / "*.parquet")
            pattern_display = (
                f"<jon_root>/data/polymarket/trades/**/*.parquet"
                f"  ({len(parquet_files)} file(s))"
            )
            summary = dh.scan_parquet(conn, glob, ts_candidates=_JON_TS_CANDIDATES)
        else:
            glob = str(trades_dir / "**" / f"*.{csv_ext}")
            pattern_display = (
                f"<jon_root>/data/polymarket/trades/**/*.{csv_ext}"
                f"  ({len(csv_files)} file(s))"
            )
            summary = dh.scan_csv(conn, glob, ts_candidates=_JON_TS_CANDIDATES)

    if summary.error:
        report = (
            f"[smoke-historical] {label}\n"
            f"  pattern:   {pattern_display}\n"
            f"  status:    ERROR — {summary.error}\n"
        )
        return False, report

    ts_line = _ts_line(summary)
    report = (
        f"[smoke-historical] {label}\n"
        f"  pattern:   {pattern_display}\n"
        f"  row_count: {_fmt_count(summary.row_count)}\n"
        f"{ts_line}"
        f"  status:    OK\n"
    )
    return True, report


def _ts_line(summary) -> str:  # type: ignore[no-untyped-def]
    """Format timestamp range line for the report."""
    if summary.min_ts and summary.max_ts:
        return f"  ts_range:  {summary.min_ts}  ->  {summary.max_ts}\n"
    return "  ts_range:  (no timestamp column detected)\n"


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smoke-historical",
        description=(
            "Validate raw historical files directly with DuckDB — no ClickHouse needed.\n\n"
            "For each provided root, prints: file pattern, row count, and min/max\n"
            "timestamp (if a known timestamp column is present).\n\n"
            "Exits nonzero if no readable source files are found."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--pmxt-root",
        default=None,
        metavar="PATH",
        help=(
            "Root of the pmxt_archive dataset.  "
            "Expects a Polymarket/ subdirectory containing .parquet files."
        ),
    )
    p.add_argument(
        "--jon-root",
        default=None,
        metavar="PATH",
        help=(
            "Root of the jon_becker dataset.  "
            "Expects data/polymarket/trades/ with .parquet or .csv/.csv.gz files."
        ),
    )
    return p


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    # Fail fast with a helpful message if duckdb is absent
    try:
        import duckdb  # noqa: F401
    except ImportError:
        print(
            "[smoke-historical] ERROR: duckdb is not installed.\n"
            "  Install:  pip install duckdb>=1.0.0\n"
            "  Or:       pip install 'polytool[historical]'",
            file=sys.stderr,
        )
        return 1

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.pmxt_root and not args.jon_root:
        parser.print_help()
        print(
            "\nError: at least one of --pmxt-root or --jon-root must be provided.",
            file=sys.stderr,
        )
        return 1

    results: List[Tuple[str, bool]] = []

    if args.pmxt_root:
        ok, report = _smoke_pmxt(args.pmxt_root)
        print(report, end="")
        results.append(("pmxt_archive", ok))

    if args.jon_root:
        ok, report = _smoke_jon(args.jon_root)
        print(report, end="")
        results.append(("jon_becker", ok))

    readable = sum(1 for _, ok in results if ok)
    total = len(results)

    if readable == 0:
        print(
            f"[smoke-historical] FAIL - 0/{total} source(s) readable",
            file=sys.stderr,
        )
        return 1

    if readable < total:
        failed = [label for label, ok in results if not ok]
        print(
            f"[smoke-historical] PARTIAL - {readable}/{total} source(s) readable"
            f"  (no files: {', '.join(failed)})",
            file=sys.stderr,
        )
        # Still return 0 - at least one source is readable; caller sees the report

    print(f"[smoke-historical] PASS - {readable}/{total} source(s) readable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
