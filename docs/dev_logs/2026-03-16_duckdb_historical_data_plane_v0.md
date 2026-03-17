# Dev Log — DuckDB Historical Data-Plane Foundation v0

**Date:** 2026-03-16
**Branch:** phase-1
**Goal:** Phase 1 historical data-plane — DuckDB helper + smoke-historical CLI

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `packages/polymarket/duckdb_helper.py` | Created | Minimal shared DuckDB helper: `connection()`, `ScanSummary`, `detect_ts_column()`, `scan_parquet()`, `scan_csv()`, `_ts_range()` |
| `tools/cli/smoke_historical.py` | Created | `smoke-historical` CLI command — validates pmxt and jon files directly via DuckDB |
| `tests/test_smoke_historical.py` | Created | 20 focused unit tests covering helper + CLI (all fixture-based, no network) |
| `docs/specs/SPEC-0019-duckdb-historical-data-plane.md` | Created | Spec for the DuckDB data-plane foundation |
| `pyproject.toml` | Modified | Added `historical = ["duckdb>=1.0.0"]` optional dep group; updated `all` |
| `polytool/__main__.py` | Modified | Registered `smoke-historical` command + updated `print_usage()` |

---

## CLI Command Added

```
python -m polytool smoke-historical [--pmxt-root PATH] [--jon-root PATH]
```

**Exit codes:** 0 if at least one source readable, 1 if zero sources readable.

**Example:**
```
python -m polytool smoke-historical \
    --pmxt-root "D:/Coding Projects/Polymarket/PolyToolData/raw/pmxt_archive" \
    --jon-root  "D:/Coding Projects/Polymarket/PolyToolData/raw/jon_becker"
```

---

## Test Results

```
pytest tests/test_smoke_historical.py -v
20 passed in 0.80s
```

All 20 tests pass with `duckdb==1.5.0`.

Fixture creation uses DuckDB's `COPY ... TO` with `generate_series()` — no pyarrow
dependency in tests.

---

## Real Local Smoke Run

Both D: paths are present. Smoke run output:

```
[smoke-historical] pmxt_archive
  pattern:   <pmxt_root>/Polymarket/**/*.parquet  (5 file(s))
  row_count: 78,264,878
  ts_range:  2026-03-15 06:00:00-04:00  ->  2026-03-15 10:59:59.999000-04:00
  status:    OK
[smoke-historical] jon_becker
  pattern:   <jon_root>/data/polymarket/trades/**/*.parquet  (40454 file(s))
  row_count: 404,540,000
  ts_range:  2026-01-29 15:48:12.728779  ->  2026-02-01 20:05:28.044902
  status:    OK
[smoke-historical] PASS - 2/2 source(s) readable
```

**PASS.** DuckDB reads both sources directly from Parquet with no ClickHouse and no
import step.

---

## Observations

### pmxt
- 5 Parquet files under `Polymarket/`; 78.2M rows in the current slice.
- `snapshot_ts` column detected and non-null.  Timezone-aware timestamps
  (`-04:00`), which DuckDB surfaces as-is in the string output.
- ts_range spans a single day (2026-03-15) — this is likely a partial slice.

### jon_becker
- 40,454 Parquet files under `data/polymarket/trades/`; 404.5M rows total.
  (Average ~10,000 rows/file.)
- `timestamp` column exists but is **all-null** in the dataset.
- `_fetched_at` column used as fallback; range 2026-01-29 to 2026-02-01 —
  this is the fetch date, not the trade date.
- The `_ts_range()` helper in `duckdb_helper.py` was extended to fall through
  candidates when the first match returns all-null MIN.

---

## Open Questions for Next Packet

1. **pmxt date range**: Only 5 files (one day?). Are more archive files expected or
   is this the full local slice? Needs confirmation before Silver reconstruction.

2. **jon_becker trade date**: The `timestamp` column is all-null.  The actual trade
   date may be derivable from file naming (`trades_<start>_<end>.parquet`) or from
   block timestamps via on-chain lookup.  Investigation needed before Silver joins.

3. **jon row count sanity**: 404.5M rows against the documented 72M-trade dataset
   suggests each parquet file (~10k rows) may represent individual blocks/events, not
   unique trades.  Deduplication/distinct trade count TBD.

4. **pmxt schema variance**: `union_by_name=true` is used; actual schema
   consistency across files not yet audited.

5. **Silver reconstruction start conditions**: Both sources readable.  Silver
   reconstruction can begin once the above questions are answered and a schema
   mapping for the join keys (`market_id` / `token_id`) is confirmed.
