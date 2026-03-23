# Dev Log: Silver Reconstructor Foundation v0

**Date:** 2026-03-16
**Branch:** phase-1
**Status:** Complete — 58/58 tests passing, CLI smoke passing

---

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `packages/polymarket/silver_reconstructor.py` | Created | Core reconstruction module: `SilverReconstructor`, `ReconstructConfig`, `SilverResult` |
| `tools/cli/reconstruct_silver.py` | Created | CLI command: `python -m polytool reconstruct-silver` |
| `tests/test_silver_reconstructor.py` | Created | 58 offline tests covering all sources, confidence model, warnings, output files, CLI |
| `docs/specs/SPEC-silver-reconstructor-v0.md` | Created | Spec doc for the reconstruction contract |
| `polytool/__main__.py` | Modified | Registered `reconstruct-silver` command and added to help text |

---

## Reconstruction Contract Implemented

### Three-Source Fusion

**Source 1 — pmxt anchor (DuckDB):**
- Reads pmxt Parquet snapshots from `<pmxt_root>/Polymarket/**/*.parquet`
- Query: nearest snapshot at or before `window_start` for the token
- Emits one `book` event with `silver_source: "pmxt_anchor"`
- Column auto-detection: tries `["token_id", "asset_id", "condition_id", "market_id"]` for token; `["snapshot_ts", "timestamp_received", "timestamp_created_at", "ts", "timestamp", "datetime"]` for timestamp

**Source 2 — Jon-Becker fills (DuckDB):**
- Reads trade Parquet/CSV from `<jon_root>/data/polymarket/trades/**/*.{parquet,csv}`
- Query: fills in `[window_start, window_end]` for the token, ordered by timestamp ASC
- Emits one `last_trade_price` event per fill with `silver_source: "jon_fill"`
- Column auto-detection: tries `["asset_id", "token_id", "market_id", "condition_id"]` for token; `["timestamp", "ts", "time", "t", "_fetched_at"]` for timestamp

**Source 3 — price_2min guide (ClickHouse):**
- Reads from `polytool.price_2min` via raw HTTP GET to `<host>:8123` with `FORMAT JSONEachRow`
- Emits `price_2min_guide` events with `silver_source: "price_2min"` and explicit note:
  `"2-min midpoint constraint; NOT synthetic tick data"`
- This is a guide only — NOT synthetic tick data — and ReplayRunner will skip it correctly
  (the type is not in `KNOWN_EVENT_TYPES`)

### Output

- `silver_events.jsonl`: events sorted by `ts_recv` ASC, seq reassigned monotonically
- `silver_meta.json`: machine-readable metadata with `schema_version: "silver_tape_v0"`, confidence, warnings, event counts, source diagnostics

---

## Source Assumptions Made

1. **pmxt Parquet schema is unknown.** Column names are heuristic-detected, not hardcoded. If no candidate matches, the anchor query fails gracefully with `pmxt_anchor_missing` warning. The actual pmxt columns found are logged to `source_inputs.pmxt_columns_found` for diagnosis.

2. **pmxt anchor is pre-window, not at window_start.** The anchor query takes the most recent snapshot at or before `window_start`. Book state may have drifted between the anchor timestamp and window_start. This is noted as a known limitation in the spec.

3. **Jon timestamps may be bucketized.** Jon-Becker trades are often bucketed to the minute or second. Equal-timestamp rows are ordered by file order (deterministic but not clock-accurate). The `jon_timestamp_ambiguity` warning surfaces this condition when multiple fills share the same timestamp.

4. **price_2min must be pre-populated.** The `polytool.price_2min` table is populated by `fetch-price-2min --token-id`. The reconstructor reads what is there; it does not backfill automatically.

5. **DuckDB connection is ephemeral per call.** Each fetch function opens a fresh `duckdb.connect()` (in-memory) and uses `INSTALL httpfs`/`LOAD httpfs` for Parquet reading. No persistent DuckDB file is used.

6. **ClickHouse HTTP read uses raw GET.** The `ClickHouseClient` in `historical_import/importer.py` only exposes `insert_rows`, not a query method. price_2min reads use `urllib.request` with `FORMAT JSONEachRow` directly to `http://<host>:<port>/`.

---

## Confidence / Warning Rules

### Confidence Model

| Level | Condition |
|-------|-----------|
| `high` | All three sources contributed data |
| `medium` | pmxt anchor present + at least one of (Jon fills OR price_2min) |
| `low` | Exactly one source contributed data |
| `none` | No data from any source |

Confidence is not a gate — operator decides acceptability for Gate 2.

### Warning Contract

| Prefix | Cause |
|--------|-------|
| `pmxt_anchor_missing` | No pmxt snapshot at or before window_start |
| `pmxt_root_not_configured` | `pmxt_root` not set in config |
| `jon_fills_missing` | No Jon fills found in window |
| `jon_root_not_configured` | `jon_root` not set in config |
| `jon_timestamp_ambiguity` | Multiple fills with identical timestamps |
| `price_2min_missing` | No price_2min rows found in window |
| `price_2min_skipped` | `skip_price_2min=True` was set |

All warnings degrade gracefully — no exceptions raised.

---

## Commands Run + Output

### Full test suite (silver only):
```
python -m pytest tests/test_silver_reconstructor.py -v --tb=short
============================= 58 passed in 0.33s ==============================
```

### Manual smoke — dry-run, no data sources, skip ClickHouse:
```
python -m polytool reconstruct-silver \
    --token-id 0xtest \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z" \
    --skip-price-2min \
    --dry-run

[reconstruct-silver] [DRY-RUN] token=0xtest
  window: 2024-01-01T00:00:00Z -> 2024-01-01T02:00:00Z
  pmxt-root:  (not set - pmxt source disabled)
  jon-root:   (not set - Jon-Becker source disabled)
  price_2min: skipped

[reconstruct-silver] confidence=none
  events:     0
  fills:      0
  price_2min: 0
  warnings:   3
    - pmxt_root_not_configured: ...
    - jon_root_not_configured: ...
    - price_2min_skipped: ...

  [dry-run] No files written.

exit=0
```

Confidence `none` and three warnings are correct — no data sources were configured. The graceful-degradation path is working.

---

## Test Results

**58/58 new tests passing.** Test classes:

| Class | Count | What it covers |
|-------|-------|----------------|
| `TestComputeConfidence` | 6 | All confidence levels from source combinations |
| `TestDetectCol` | 4 | Column auto-detection against candidate lists |
| `TestToFloatTs` | 5 | Timestamp parsing (epoch, ISO, datetime strings) |
| `TestReconstructorConfidence` | 8 | Confidence from injectable fetch functions |
| `TestReconstructorEventCounts` | 6 | Event/fill/price_2min counts in result |
| `TestReconstructorWarnings` | 6 | Each warning type triggered correctly |
| `TestDeterminism` | 2 | Two calls with same inputs produce identical output |
| `TestOutputFiles` | 7 | File contents, seq monotonicity, silver_source tags, price_2min note |
| `TestSilverResultToDict` | 4 | JSON round-trips, path serialization |
| `TestErrorPath` | 2 | Error field set when out_dir missing in non-dry-run |
| `TestCLISmoke` | 8 | CLI: dry-run, missing args, window ordering, out-dir, ISO timestamps, skip flag |

**Pre-existing failures (not introduced by this work):**
- `test_polytool_main_module_help_surface_smoke[argv0]` — UnicodeEncodeError on `→` in pre-existing help text
- 3x `TestResolvedWatchRegime`/`TestPrepareGate2RegimeWritten` — pre-existing failures unrelated to Silver

---

## Manual Smoke Result

**Blocker:** No local `pmxt_root` or `jon_root` data present in this environment. The full three-source reconstruction cannot be exercised without the raw datasets.

**What was verified offline:**
- CLI entrypoint routing works end-to-end (exit=0)
- Graceful degradation when all three sources are absent (confidence=none, 3 warnings)
- No exceptions on dry-run path with no data
- All 58 offline unit tests exercise the fetch-inject hooks with fixture data

**To run a real reconstruction:**
```bash
# 1. Pre-populate price_2min (if not already done):
python -m polytool fetch-price-2min --token-id <TOKEN_ID>

# 2. Reconstruct:
python -m polytool reconstruct-silver \
    --token-id <TOKEN_ID> \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z" \
    --pmxt-root    /path/to/pmxt_archive \
    --jon-root     /path/to/jon_becker
```

---

## Open Questions for Next Packet

1. **pmxt column schema.** The heuristic candidate lists were written against the column names visible in `smoke_historical.py`. If the actual pmxt Parquet files use different column names, the anchor query will fail gracefully (warning emitted) but no book state will be available. Needs validation against real pmxt files.

2. **Jon timestamp resolution.** Jon-Becker trades are expected to have bucketized timestamps (minute or second resolution). The `jon_timestamp_ambiguity` warning will fire frequently. The question is whether this is acceptable for Gate 2 scenario sweeping or if higher-resolution fill data is needed.

3. **ClickHouse HTTP credentials.** The raw HTTP GET uses basic auth with `polytool_admin`. If the ClickHouse instance uses a different user or password, the `price_2min` fetch will fail gracefully with a `price_2min_missing` warning (the HTTP error is caught). The `--clickhouse-password` flag or `CLICKHOUSE_PASSWORD` env var handles this.

4. **Batch reconstruction.** v0 is single-market only. Gate 2 requires one reconstruction per candidate market. A batch wrapper (`reconstruct-silver-batch`) should be planned for a future packet once the single-market path is validated end-to-end on real data.

5. **Gold tape.** Gold requires live WS recording (not reconstruction). The Silver foundation is complete; Gold is explicitly out of scope for v0.
