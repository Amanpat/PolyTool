# Feature: CLV Capture and Cache-First Closing Price Snapshots

## Summary

This feature adds deterministic Closing Line Value (CLV) fields to scan artifacts. Scan can now resolve a closing price from cached CLOB price history, optionally fetch missing history online, and always write explicit missing reasons when CLV cannot be computed.

---

## Definitions

- `close_ts`: canonical close timestamp chosen by ladder:
  - `resolved_at`
  - `gamma_closedTime`
  - `gamma_endDate`
  - `gamma_umaEndDate`
- `closing_price`: latest valid price sample `<= close_ts` inside the configured lookback window.
- `clv`: `closing_price - entry_price`.
- `clv_pct`: `clv / entry_price`.
- `beat_close`: `entry_price < closing_price`.
- `clv_source`: `prices_history|<close_ts_source>` when CLV is present.

Position-level fields added to dossier/audit/coverage flow:

- `close_ts`
- `close_ts_source`
- `closing_price`
- `closing_ts_observed`
- `clv`
- `clv_pct`
- `beat_close`
- `clv_source`
- `clv_missing_reason`

---

## Cache Behavior

Scan stage:

1. Read cached rows from ClickHouse table `polyttool.market_price_snapshots`.
2. If cache misses and CLV online mode is enabled, call CLOB `/prices-history` in a bounded window.
3. Persist fetched points into the cache table with reproducibility metadata:
   - `query_window_seconds`
   - `interval`
   - `fidelity`
4. Recompute closing-price selection from deterministic rules.

CLI flag:

- `scan --compute-clv`

Key env knobs:

- `SCAN_COMPUTE_CLV` (`true/false`)
- `SCAN_CLV_OFFLINE` (`true/false`)
- `SCAN_CLV_WINDOW_MINUTES` (default `1440`)
- `SCAN_CLV_INTERVAL` (default `1m`)
- `SCAN_CLV_FIDELITY` (default `high`)

---

## Missingness Reasons

CLV never silently drops. Null CLV fields carry explicit reasons:

- `NO_CLOSE_TS`
- `OFFLINE`
- `EMPTY_HISTORY`
- `OUTSIDE_WINDOW`
- `INVALID_PRICE_VALUE`
- `MISSING_ENTRY_PRICE`
- `INVALID_ENTRY_PRICE_RANGE`
- `MISSING_OUTCOME_TOKEN_ID`

Coverage report now includes top-level `clv_coverage` with:

- eligible count
- present count
- missing count
- coverage rate
- close-ts source counts
- CLV source counts
- missing reason counts

Segment analysis buckets now include:

- `avg_clv_pct`
- `beat_close_rate`

---

## How To Verify In A Run Root

After running scan with CLV enabled, inspect:

1. `dossier.json`
   - Confirm each lifecycle position includes CLV fields and explicit `clv_missing_reason` when null.
2. `coverage_reconciliation_report.json`
   - Confirm top-level `clv_coverage` block exists with reason counts.
3. `coverage_reconciliation_report.md`
   - Confirm `## CLV Coverage` section and low-coverage warning behavior.
4. `segment_analysis.json`
   - Confirm segment buckets contain `avg_clv_pct` and `beat_close_rate`.
5. `audit_coverage_report.md`
   - Confirm position blocks show close timestamp/source, closing price, CLV fields, and null reasons.

