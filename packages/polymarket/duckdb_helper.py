"""Minimal DuckDB helper for the v4.2 historical data-plane.

DuckDB = historical Parquet reads.  ClickHouse = live streaming writes.
The two databases never share data and never communicate.

This module is the Phase 1 historical data-plane foundation.  It provides
a context-managed connection plus two scan helpers that return a compact
ScanSummary without any ClickHouse dependency.

Usage::

    from packages.polymarket.duckdb_helper import connection, scan_parquet, scan_csv

    with connection() as conn:
        summary = scan_parquet(
            conn,
            "/data/raw/pmxt_archive/Polymarket/**/*.parquet",
            ts_candidates=["snapshot_ts", "ts", "timestamp"],
        )
        print(summary.row_count, summary.min_ts, summary.max_ts)
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, List, Optional

import duckdb


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ScanSummary:
    """Result of a DuckDB scan over a file glob.

    Attributes:
        row_count: Total rows found (0 on error or empty result).
        min_ts:    String representation of the minimum timestamp value, or None.
        max_ts:    String representation of the maximum timestamp value, or None.
        ts_col:    The column name that was used for min/max, or None if undetected.
        error:     Human-readable error string, or None on success.
    """

    row_count: int = 0
    min_ts: Optional[str] = None
    max_ts: Optional[str] = None
    ts_col: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True when the scan completed without error and found at least one row."""
        return self.error is None and self.row_count > 0


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@contextmanager
def connection(
    db_path: str = ":memory:",
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager that opens a DuckDB connection and closes it on exit.

    Args:
        db_path: Path to a persistent DuckDB database, or ``:memory:`` (default).

    Yields:
        An open ``duckdb.DuckDBPyConnection``.
    """
    conn = duckdb.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------


def detect_ts_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Return the first column from *candidates* that appears in *columns*.

    Comparison is case-insensitive; the original casing from *columns* is
    returned so it can be used safely in quoted SQL identifiers.

    Returns ``None`` if no candidate is found.
    """
    lower_map: dict[str, str] = {c.lower(): c for c in columns}
    for cand in candidates:
        match = lower_map.get(cand.lower())
        if match is not None:
            return match
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_duckdb_glob(path: str) -> str:
    """Normalise a glob pattern to forward slashes (Windows compat for DuckDB)."""
    return path.replace("\\", "/")


def _parquet_columns(
    conn: duckdb.DuckDBPyConnection, ddb_glob: str
) -> Optional[List[str]]:
    """Return column names from a parquet glob, or None if no files match."""
    try:
        rel = conn.execute(
            f"SELECT * FROM read_parquet('{ddb_glob}', union_by_name=true) LIMIT 0"
        )
        return [d[0] for d in rel.description]
    except Exception:
        return None


def _csv_columns(
    conn: duckdb.DuckDBPyConnection, ddb_glob: str
) -> Optional[List[str]]:
    """Return column names from a CSV glob, or None if no files match."""
    try:
        rel = conn.execute(
            f"SELECT * FROM read_csv('{ddb_glob}', auto_detect=true) LIMIT 0"
        )
        return [d[0] for d in rel.description]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public scan helpers
# ---------------------------------------------------------------------------


def _ts_range(
    conn: duckdb.DuckDBPyConnection,
    read_expr: str,
    columns: List[str],
    ts_candidates: List[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Try each ts_candidate in order; return (ts_col, min_ts, max_ts).

    Falls through to the next candidate when a column exists but MIN returns NULL
    (e.g. the column is all-null in the dataset).  Returns (None, None, None) if
    no candidate yields a non-null range.
    """
    for cand in ts_candidates:
        col = detect_ts_column(columns, [cand])
        if col is None:
            continue
        try:
            row = conn.execute(
                f'SELECT MIN("{col}") AS min_ts, MAX("{col}") AS max_ts FROM {read_expr}'
            ).fetchone()
        except Exception:
            continue
        if row and row[0] is not None:
            return col, str(row[0]), str(row[1]) if row[1] is not None else None
    return None, None, None


def scan_parquet(
    conn: duckdb.DuckDBPyConnection,
    glob: str,
    ts_candidates: Optional[List[str]] = None,
) -> ScanSummary:
    """Scan a Parquet glob and return row count + optional timestamp range.

    Uses ``read_parquet(..., union_by_name=true)`` so files with slightly
    different schemas are merged safely.

    Timestamp detection falls through candidates in order: if the first matching
    column is all-null (MIN returns NULL), the next candidate is tried.

    Args:
        conn:          Open DuckDB connection from :func:`connection`.
        glob:          Filesystem glob, e.g. ``/data/pmxt/Polymarket/**/*.parquet``.
                       Backslashes are normalised to forward slashes automatically.
        ts_candidates: Ordered list of column names to probe for timestamp range.
                       Pass ``None`` to skip timestamp detection.

    Returns:
        :class:`ScanSummary` with ``row_count``, ``min_ts`` / ``max_ts`` (as
        strings), ``ts_col``, and ``error``.
    """
    ddb_glob = _to_duckdb_glob(glob)
    read_expr = f"read_parquet('{ddb_glob}', union_by_name=true)"

    columns = _parquet_columns(conn, ddb_glob)
    if columns is None:
        return ScanSummary(error=f"no readable parquet files matching: {glob}")

    try:
        row_count = conn.execute(f"SELECT COUNT(*) FROM {read_expr}").fetchone()
        count = row_count[0] if row_count else 0
    except Exception as exc:
        return ScanSummary(error=str(exc))

    ts_col, min_ts, max_ts = None, None, None
    if ts_candidates:
        ts_col, min_ts, max_ts = _ts_range(conn, read_expr, columns, ts_candidates)

    return ScanSummary(row_count=count, min_ts=min_ts, max_ts=max_ts, ts_col=ts_col)


def scan_csv(
    conn: duckdb.DuckDBPyConnection,
    glob: str,
    ts_candidates: Optional[List[str]] = None,
) -> ScanSummary:
    """Scan a CSV / CSV.GZ glob and return row count + optional timestamp range.

    Uses ``read_csv(..., auto_detect=true)``.  DuckDB handles ``.gz``
    decompression transparently.

    Timestamp detection falls through candidates in order: if the first matching
    column is all-null (MIN returns NULL), the next candidate is tried.

    Args:
        conn:          Open DuckDB connection from :func:`connection`.
        glob:          Filesystem glob, e.g.
                       ``/data/jon/data/polymarket/trades/**/*.csv``.
        ts_candidates: Ordered list of column names to probe for timestamp range.

    Returns:
        :class:`ScanSummary` with ``row_count``, ``min_ts`` / ``max_ts`` (as
        strings), ``ts_col``, and ``error``.
    """
    ddb_glob = _to_duckdb_glob(glob)
    read_expr = f"read_csv('{ddb_glob}', auto_detect=true)"

    columns = _csv_columns(conn, ddb_glob)
    if columns is None:
        return ScanSummary(error=f"no readable csv files matching: {glob}")

    try:
        row_count = conn.execute(f"SELECT COUNT(*) FROM {read_expr}").fetchone()
        count = row_count[0] if row_count else 0
    except Exception as exc:
        return ScanSummary(error=str(exc))

    ts_col, min_ts, max_ts = None, None, None
    if ts_candidates:
        ts_col, min_ts, max_ts = _ts_range(conn, read_expr, columns, ts_candidates)

    return ScanSummary(row_count=count, min_ts=min_ts, max_ts=max_ts, ts_col=ts_col)
