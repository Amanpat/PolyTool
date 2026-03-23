# Dev Log: Silver Input Compatibility Fix

**Date:** 2026-03-18
**Branch:** `phase-1`
**Objective:** Fix two root-cause bugs in `packages/polymarket/silver_reconstructor.py`
that blocked `python -m polytool close-benchmark-v1 --skip-new-market ...` from
completing the Silver closure path. Both bugs were identified from the decoded
stderr artifact of the resumed live attempt on 2026-03-17.

---

## Outcome

Both bugs are fixed. All 13 new regression tests pass. 145 existing Silver
tests are unaffected. The repo is ready for another live closure attempt at
`close-benchmark-v1 --skip-new-market`.

---

## Root Causes Fixed

### Bug 1: `price_2min` ClickHouse HTTP 400

**Location:** `_real_fetch_price_2min()` in `silver_reconstructor.py` (lines 464–465)

**Symptom from stderr:**
```
price_2min: ClickHouse query failed: 400 Client Error: Bad Request for url:
http://localhost:8123/?query=SELECT+toUnixTimestamp%28ts%29+AS+ts%2C+price+FROM+
polytool.price_2min+WHERE+token_id+%3D+%27...%27+AND+ts+%3E%3D+toDateTime%282026-03-15T10%3A00%3A09.554000%2B00%3A00%29...
```

**Root cause:** The query was built using `toDateTime('{_ts_to_iso(window_start)}')`.
`_ts_to_iso()` calls `datetime.isoformat()` which produces strings like
`2026-03-15T10:00:09.554000+00:00`. ClickHouse's `toDateTime()` function cannot
parse this format (T separator, microseconds, `+00:00` timezone suffix) and
returns HTTP 400.

**Fix (before → after):**
```python
# Before
f"AND ts >= toDateTime('{_ts_to_iso(window_start)}') "
f"AND ts <= toDateTime('{_ts_to_iso(window_end)}') "

# After
f"AND ts >= toDateTime({int(window_start)}) "
f"AND ts <= toDateTime({int(window_end)}) "
```

`toDateTime(int_epoch)` is always accepted by ClickHouse. The `ts` column is
`DateTime64(3, 'UTC')` so comparing with a second-precision `DateTime` is valid
(ClickHouse upcasts).

---

### Bug 2: Jon-Becker `token_col=None` Schema Mismatch

**Location:** `_real_fetch_jon_fills()` in `silver_reconstructor.py` (lines 412–436)

**Symptom from stderr:**
```
jon: missing required columns. token_col=None ts_col=timestamp in ['block_number',
'transaction_hash', 'log_index', 'order_hash', 'maker', 'taker', 'maker_asset_id',
'taker_asset_id', 'maker_amount', 'taker_amount', 'fee', 'timestamp', '_fetched_at',
'_contract']
```

**Root cause:** `_JON_TOKEN_CANDIDATES = ["asset_id", "token_id", "market_id", "condition_id"]`
does not include `maker_asset_id` or `taker_asset_id`. The real local Jon-Becker
Parquet dataset uses a maker/taker schema where the trade token appears in either
`maker_asset_id` (when our token is the maker side) or `taker_asset_id` (when
our token is the taker side). When `_detect_col()` returned `None`, the guard
`if not token_col or not ts_col: return []` silently returned empty fills for
every token, causing Silver reconstruction to proceed with zero Jon fills, which
in turn left residual bucket shortages and blocked the benchmark refresh.

**Fix:** After single-column `_detect_col()` returns `None`, detect whether both
`maker_asset_id` and `taker_asset_id` exist in the schema. If they do, build an
OR query: `WHERE ("maker_asset_id" = ? OR "taker_asset_id" = ?)`. This correctly
returns all fills where our token participated on either side of the trade.

```python
# New detection block (inserted after token_col / ts_col detection)
_col_lower = {c.lower(): c for c in columns}
_maker_col = _col_lower.get("maker_asset_id")
_taker_col = _col_lower.get("taker_asset_id")
_maker_taker = bool(_maker_col and _taker_col)

if not ts_col or (not token_col and not _maker_taker):
    logger.warning(...)
    return []

if _maker_taker and not token_col:
    query = (
        f'SELECT * FROM {read_expr} '
        f'WHERE ("{_maker_col}" = ? OR "{_taker_col}" = ?) '
        f'AND "{ts_col}" >= ? AND "{ts_col}" <= ? '
        f'ORDER BY "{ts_col}" ASC'
    )
    params_prefix = [token_id, token_id]
else:
    # Existing single-column path (unchanged behavior)
    query = (
        f'SELECT * FROM {read_expr} '
        f'WHERE "{token_col}" = ? AND "{ts_col}" >= ? AND "{ts_col}" <= ? '
        f'ORDER BY "{ts_col}" ASC'
    )
    params_prefix = [token_id]
```

Legacy `asset_id`-style schemas are unaffected: single-column detection still
runs first; the maker/taker branch only activates when `token_col` is `None` and
both `maker_asset_id` + `taker_asset_id` are present.

---

## Tests Added

**New file:** `tests/test_silver_input_compatibility.py` — 13 tests

| Class | Tests | What is verified |
|---|---|---|
| `TestPrice2MinEpochQuery` | 4 | Query uses `toDateTime(int)`, rows parsed, empty on HTTP 400, empty on connection error |
| `TestJonMakerTakerSchema` | 4 | Maker/taker OR query returns both-side rows; no false positives; legacy `asset_id` schema unchanged; empty dir returns `[]` |
| `TestSilverCloseBenchmarkSmoke` | 5 | All-stubs reconstruct: no error, high confidence, correct price_2min_count, dry_run no files, both output files written |

All 13 pass. 145 existing Silver tests (`test_silver_reconstructor.py`,
`test_batch_silver.py`, `test_batch_silver_gap_fill.py`) are unaffected.

---

## Files Changed

| File | Change |
|---|---|
| `packages/polymarket/silver_reconstructor.py` | Fix 1: `toDateTime({int(epoch)})` in `_real_fetch_price_2min()`. Fix 2: maker/taker OR query in `_real_fetch_jon_fills()`. |
| `tests/test_silver_input_compatibility.py` | New — 13 regression tests |
| `docs/dev_logs/2026-03-18_silver_input_compatibility_fix.md` | This file |
| `docs/CURRENT_STATE.md` | Updated Silver closure blocker status and next step |

---

## Evidence Baseline

Both root causes were diagnosed from the decoded (UTF-16) stderr artifact:

```
D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\
  live_attempt_resume_2026-03-17_210038\
  11_close_benchmark_skip_new_market_escalated.stderr.txt
```

The orchestrator run artifact confirming `manifest_written=false` and
`benchmark_refresh.return_code=2`:

```
D:\Coding Projects\Polymarket\PolyTool\artifacts\benchmark_closure\
  2026-03-18\084f807b-789e-4cb1-9833-6536c3da822a\benchmark_closure_run_v1.json
```

---

## Next Step

Re-run the live closure command:

```powershell
python -m polytool close-benchmark-v1 --skip-new-market \
  --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" \
  --jon-root  "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

Expected: Silver gap-fill proceeds with Jon fills + price_2min rows populated,
benchmark refresh runs cleanly, `config/benchmark_v1.tape_manifest` is written,
exit code 0 or 1 (manifest_created or still bucket-blocked, but not query-failed).

If bucket shortages persist despite correct data loading, the issue will be in
the Silver tape quality / bucket quota logic, not input loading.
