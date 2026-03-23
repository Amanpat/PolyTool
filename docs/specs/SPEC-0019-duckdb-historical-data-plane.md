# SPEC-0019 — DuckDB Historical Data-Plane Foundation

**Version:** 1.0
**Date:** 2026-03-16
**Status:** Accepted
**Supersedes:** SPEC-0018 is now off the critical path (ClickHouse bulk import not needed for pmxt/Jon)

---

## 1. Context

Master Roadmap v4.2 establishes a two-database rule:

> **DuckDB = historical Parquet reads.  ClickHouse = live streaming writes.**

This spec covers the Phase 1 foundation: a minimal shared DuckDB helper and a CLI
smoke command that proves direct Parquet access works end-to-end for both the
`pmxt_archive` and `jon_becker` historical sources — without any ClickHouse
dependency, server process, or data import step.

---

## 2. Components

### 2.1 `packages/polymarket/duckdb_helper.py`

Thin, reusable wrapper around the DuckDB Python API.  Exposes:

| Symbol | Description |
|--------|-------------|
| `connection(db_path=":memory:")` | Context manager; opens a DuckDB connection and closes on exit. |
| `ScanSummary` | Dataclass: `row_count`, `min_ts`, `max_ts`, `ts_col`, `error`, `ok`. |
| `detect_ts_column(columns, candidates)` | Case-insensitive first-match search for timestamp columns. |
| `scan_parquet(conn, glob, ts_candidates)` | Count rows and timestamp range from a Parquet glob. |
| `scan_csv(conn, glob, ts_candidates)` | Count rows and timestamp range from a CSV/CSV.GZ glob. |

**Design constraints:**
- Zero ClickHouse imports.
- DuckDB operates fully in-memory unless a `db_path` is specified.
- Glob normalisation (`\` → `/`) handles Windows paths transparently.
- Uses `read_parquet(..., union_by_name=true)` to handle files with varying schemas.
- Empty-glob errors are caught and returned as `ScanSummary(error=...)`.

### 2.2 `tools/cli/smoke_historical.py`

CLI command registered as `smoke-historical`.

```
python -m polytool smoke-historical [--pmxt-root PATH] [--jon-root PATH]
```

**Behaviour:**

1. For `--pmxt-root`: globs `<root>/Polymarket/**/*.parquet`, queries via
   `scan_parquet` with timestamp candidates `["snapshot_ts", "timestamp_received",
   "timestamp_created_at", "ts", "timestamp", "datetime"]`.

2. For `--jon-root`: tries `data/polymarket/trades/**/*.parquet` first; falls back
   to `*.csv` then `*.csv.gz` if no Parquet files exist.

3. For each source prints a compact summary:
   - File pattern with count
   - `row_count`
   - `ts_range` (min → max) if a timestamp column is detected
   - `status: OK` or `status: ERROR`

4. **Exit codes:**
   - `0` if at least one source is readable (prints `PASS` or `PARTIAL`)
   - `1` if no sources are readable (prints `FAIL`)
   - `1` if `--pmxt-root` / `--jon-root` are both absent

5. Fails fast with a helpful install message if `duckdb` is not installed.

---

## 3. File Layout Expected by Each Source

### pmxt_archive

```
<pmxt_root>/
  Polymarket/           ← required
    YYYY/
      YYYY-MM-DD/
        *.parquet       ← hourly L2 snapshots
  Kalshi/               ← optional (ignored by smoke command)
  Opinion/              ← optional (ignored by smoke command)
```

Timestamp column candidates (in priority order):
`snapshot_ts`, `timestamp_received`, `timestamp_created_at`, `ts`, `timestamp`, `datetime`

### jon_becker

```
<jon_root>/
  data/
    polymarket/
      trades/
        *.parquet       ← preferred; OR
        *.csv           ← fallback
        *.csv.gz        ← last resort
```

Timestamp column candidates: `timestamp`, `ts`, `time`, `t`, `_fetched_at`

---

## 4. Dependency

```toml
[project.optional-dependencies]
historical = [
    "duckdb>=1.0.0",
]
```

Install with:
```
pip install 'polytool[historical]'
```

DuckDB is zero-config — no server, no port, no credentials.

---

## 5. Out of Scope for This Spec

- Silver tape reconstruction (joins pmxt + jon + price_history)
- ClickHouse bulk import (SPEC-0018 — off critical path under v4.2)
- `price_2min` / `price_history_2min` integration
- Any write path to DuckDB persistent storage
- FastAPI or n8n wrappers

---

## 6. Verification

**Unit tests:** `tests/test_smoke_historical.py`
- Marked `optional_dep`; skipped when `duckdb` is not installed
- All fixtures are self-contained (no network, no ClickHouse)
- Parquet fixtures created with `duckdb` itself (no `pyarrow` dependency in tests)

**Manual smoke (real data):**
```bash
python -m polytool smoke-historical \
    --pmxt-root "D:/Coding Projects/Polymarket/PolyToolData/raw/pmxt_archive" \
    --jon-root  "D:/Coding Projects/Polymarket/PolyToolData/raw/jon_becker"
```

Expected output: `row_count`, `ts_range`, and `status: OK` for each source found.
