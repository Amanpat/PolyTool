"""Tests for the DuckDB historical data-plane helper and smoke-historical CLI.

All tests use tmp_path fixtures only — no network, no ClickHouse, no real D: paths.
Tests are marked optional_dep and skipped when duckdb is not installed.

Run:
    pip install 'polytool[historical]'
    pytest tests/test_smoke_historical.py -v
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

import pytest

pytestmark = pytest.mark.optional_dep

# ---------------------------------------------------------------------------
# DuckDB availability guard
# ---------------------------------------------------------------------------

try:
    import duckdb  # noqa: F401

    _DUCKDB_AVAILABLE = True
except ImportError:
    _DUCKDB_AVAILABLE = False

skip_no_duckdb = pytest.mark.skipif(
    not _DUCKDB_AVAILABLE,
    reason="duckdb not installed — run: pip install 'polytool[historical]'",
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _write_parquet(path: Path, rows: int = 10, ts_col: str = "snapshot_ts") -> None:
    """Create a minimal Parquet file using DuckDB (no pyarrow dependency)."""
    import duckdb as ddb

    conn = ddb.connect(":memory:")
    conn.execute(
        f"""COPY (
            SELECT
                (TIMESTAMP '2024-01-01 00:00:00' + INTERVAL (i * 3600) SECOND)
                    AS "{ts_col}",
                'polymarket'              AS platform,
                ('market_' || i::TEXT)   AS market_id,
                ('token_'  || i::TEXT)   AS token_id,
                'BID'                    AS side,
                0.5::DOUBLE              AS price,
                100.0::DOUBLE            AS size
            FROM generate_series(0, {rows - 1}) t(i)
        ) TO '{path.as_posix()}' (FORMAT PARQUET)"""
    )
    conn.close()


def _write_csv(path: Path, rows: int = 10, ts_col: str = "timestamp") -> None:
    """Create a minimal CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=[ts_col, "market_id", "price", "size"]
        )
        writer.writeheader()
        for i in range(rows):
            writer.writerow(
                {
                    ts_col: f"2024-01-01T{i % 24:02d}:00:00",
                    "market_id": f"market_{i}",
                    "price": 0.5,
                    "size": 100.0,
                }
            )


# ===========================================================================
# duckdb_helper module tests
# ===========================================================================


@skip_no_duckdb
def test_connection_opens_and_closes():
    """DuckDB in-memory connection opens cleanly via context manager."""
    from packages.polymarket.duckdb_helper import connection

    with connection() as conn:
        row = conn.execute("SELECT 42 AS val").fetchone()
    assert row == (42,)


@skip_no_duckdb
def test_detect_ts_column_first_match():
    """detect_ts_column returns the first matching candidate."""
    from packages.polymarket.duckdb_helper import detect_ts_column

    cols = ["platform", "snapshot_ts", "price", "ts"]
    result = detect_ts_column(cols, ["snapshot_ts", "ts", "timestamp"])
    assert result == "snapshot_ts"


@skip_no_duckdb
def test_detect_ts_column_case_insensitive():
    """detect_ts_column matches regardless of case."""
    from packages.polymarket.duckdb_helper import detect_ts_column

    cols = ["Platform", "SnapShot_TS", "Price"]
    result = detect_ts_column(cols, ["snapshot_ts"])
    assert result == "SnapShot_TS"


@skip_no_duckdb
def test_detect_ts_column_no_match():
    """detect_ts_column returns None when no candidate is present."""
    from packages.polymarket.duckdb_helper import detect_ts_column

    cols = ["platform", "price", "size"]
    assert detect_ts_column(cols, ["snapshot_ts", "ts"]) is None


@skip_no_duckdb
def test_scan_parquet_row_count(tmp_path: Path):
    """scan_parquet returns the correct row count."""
    from packages.polymarket.duckdb_helper import connection, scan_parquet

    pfile = tmp_path / "data.parquet"
    _write_parquet(pfile, rows=50)

    with connection() as conn:
        summary = scan_parquet(conn, str(tmp_path / "*.parquet"))

    assert summary.error is None
    assert summary.row_count == 50
    assert summary.ok


@skip_no_duckdb
def test_scan_parquet_detects_timestamp(tmp_path: Path):
    """scan_parquet populates min_ts / max_ts when ts column is detected."""
    from packages.polymarket.duckdb_helper import connection, scan_parquet

    _write_parquet(tmp_path / "snap.parquet", rows=10, ts_col="snapshot_ts")

    with connection() as conn:
        summary = scan_parquet(
            conn,
            str(tmp_path / "*.parquet"),
            ts_candidates=["snapshot_ts", "ts"],
        )

    assert summary.error is None
    assert summary.row_count == 10
    assert summary.ts_col == "snapshot_ts"
    assert summary.min_ts is not None
    assert summary.max_ts is not None
    assert summary.min_ts <= summary.max_ts


@skip_no_duckdb
def test_scan_parquet_no_files(tmp_path: Path):
    """scan_parquet returns an error ScanSummary when glob matches nothing."""
    from packages.polymarket.duckdb_helper import connection, scan_parquet

    with connection() as conn:
        summary = scan_parquet(conn, str(tmp_path / "missing" / "**" / "*.parquet"))

    assert summary.error is not None
    assert summary.row_count == 0
    assert not summary.ok


@skip_no_duckdb
def test_scan_parquet_multiple_files(tmp_path: Path):
    """scan_parquet unions multiple parquet files correctly."""
    from packages.polymarket.duckdb_helper import connection, scan_parquet

    sub = tmp_path / "sub"
    sub.mkdir()
    _write_parquet(tmp_path / "a.parquet", rows=20)
    _write_parquet(sub / "b.parquet", rows=30)

    with connection() as conn:
        summary = scan_parquet(conn, str(tmp_path / "**" / "*.parquet"))

    assert summary.error is None
    assert summary.row_count == 50


@skip_no_duckdb
def test_scan_csv_row_count(tmp_path: Path):
    """scan_csv returns the correct row count."""
    from packages.polymarket.duckdb_helper import connection, scan_csv

    _write_csv(tmp_path / "trades.csv", rows=25, ts_col="timestamp")

    with connection() as conn:
        summary = scan_csv(
            conn,
            str(tmp_path / "*.csv"),
            ts_candidates=["timestamp", "ts"],
        )

    assert summary.error is None
    assert summary.row_count == 25
    assert summary.ts_col == "timestamp"


@skip_no_duckdb
def test_scan_csv_no_files(tmp_path: Path):
    """scan_csv returns an error ScanSummary when glob matches nothing."""
    from packages.polymarket.duckdb_helper import connection, scan_csv

    with connection() as conn:
        summary = scan_csv(conn, str(tmp_path / "missing" / "*.csv"))

    assert summary.error is not None
    assert not summary.ok


# ===========================================================================
# smoke-historical CLI tests
# ===========================================================================


@skip_no_duckdb
def test_cli_no_args_exits_nonzero():
    """smoke-historical with no arguments exits nonzero."""
    from tools.cli.smoke_historical import main

    assert main([]) != 0


@skip_no_duckdb
def test_cli_pmxt_valid_fixture(tmp_path: Path):
    """smoke-historical --pmxt-root passes with a valid pmxt parquet fixture."""
    from tools.cli.smoke_historical import main

    poly_dir = tmp_path / "Polymarket" / "2024"
    poly_dir.mkdir(parents=True)
    _write_parquet(poly_dir / "snapshot.parquet", rows=100, ts_col="snapshot_ts")

    rc = main(["--pmxt-root", str(tmp_path)])
    assert rc == 0


@skip_no_duckdb
def test_cli_pmxt_no_files_exits_nonzero(tmp_path: Path):
    """smoke-historical --pmxt-root exits nonzero when Polymarket/ is absent."""
    from tools.cli.smoke_historical import main

    rc = main(["--pmxt-root", str(tmp_path)])
    assert rc != 0


@skip_no_duckdb
def test_cli_jon_parquet_fixture(tmp_path: Path):
    """smoke-historical --jon-root passes with parquet files in trades/."""
    from tools.cli.smoke_historical import main

    trades_dir = tmp_path / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True)
    _write_parquet(trades_dir / "trades.parquet", rows=200, ts_col="timestamp")

    rc = main(["--jon-root", str(tmp_path)])
    assert rc == 0


@skip_no_duckdb
def test_cli_jon_csv_fallback(tmp_path: Path):
    """smoke-historical --jon-root falls back to CSV when no parquet present."""
    from tools.cli.smoke_historical import main

    trades_dir = tmp_path / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True)
    _write_csv(trades_dir / "trades.csv", rows=50, ts_col="timestamp")

    rc = main(["--jon-root", str(tmp_path)])
    assert rc == 0


@skip_no_duckdb
def test_cli_jon_no_files_exits_nonzero(tmp_path: Path):
    """smoke-historical --jon-root exits nonzero when trades/ is empty."""
    from tools.cli.smoke_historical import main

    (tmp_path / "data" / "polymarket" / "trades").mkdir(parents=True)
    rc = main(["--jon-root", str(tmp_path)])
    assert rc != 0


@skip_no_duckdb
def test_cli_both_sources_pass(tmp_path: Path):
    """smoke-historical passes when both pmxt and jon roots are valid."""
    from tools.cli.smoke_historical import main

    # pmxt fixture
    poly_dir = tmp_path / "pmxt" / "Polymarket"
    poly_dir.mkdir(parents=True)
    _write_parquet(poly_dir / "snap.parquet", rows=10, ts_col="snapshot_ts")

    # jon fixture
    trades_dir = tmp_path / "jon" / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True)
    _write_parquet(trades_dir / "trades.parquet", rows=10, ts_col="timestamp")

    rc = main(
        [
            "--pmxt-root", str(tmp_path / "pmxt"),
            "--jon-root",  str(tmp_path / "jon"),
        ]
    )
    assert rc == 0


@skip_no_duckdb
def test_cli_one_valid_one_missing_exits_zero(tmp_path: Path):
    """smoke-historical exits 0 (PARTIAL) when at least one source is readable."""
    from tools.cli.smoke_historical import main

    # Only pmxt is valid
    poly_dir = tmp_path / "pmxt" / "Polymarket"
    poly_dir.mkdir(parents=True)
    _write_parquet(poly_dir / "snap.parquet", rows=5, ts_col="snapshot_ts")

    jon_root = tmp_path / "jon"
    (jon_root / "data" / "polymarket" / "trades").mkdir(parents=True)
    # Empty trades dir — jon will fail

    rc = main(
        [
            "--pmxt-root", str(tmp_path / "pmxt"),
            "--jon-root",  str(jon_root),
        ]
    )
    # At least one source readable → exit 0
    assert rc == 0


@skip_no_duckdb
def test_cli_output_contains_row_count(tmp_path: Path, capsys):
    """smoke-historical prints row_count in the summary output."""
    from tools.cli.smoke_historical import main

    poly_dir = tmp_path / "Polymarket"
    poly_dir.mkdir()
    _write_parquet(poly_dir / "data.parquet", rows=77, ts_col="snapshot_ts")

    main(["--pmxt-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert "77" in captured.out


@skip_no_duckdb
def test_cli_output_contains_ts_range(tmp_path: Path, capsys):
    """smoke-historical prints a ts_range line when timestamp column detected."""
    from tools.cli.smoke_historical import main

    poly_dir = tmp_path / "Polymarket"
    poly_dir.mkdir()
    _write_parquet(poly_dir / "data.parquet", rows=5, ts_col="snapshot_ts")

    main(["--pmxt-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert "ts_range" in captured.out
    assert "->" in captured.out
