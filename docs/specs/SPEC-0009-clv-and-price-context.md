# SPEC-0009 - CLV and Time/Price Context Signals

**Status:** Proposed (Roadmap 5.1)  
**Date:** 2026-02-19

## 1. Purpose

Define the canonical, deterministic contract for Roadmap 5.1:

- Closing Line Value (CLV) capture
- Time/price context fields around entry and close
- Explicit missingness reason codes (no guessing)
- Offline-safe snapshot caching and reproducible computation

This is a docs-only specification. No implementation changes are made here.

---

## 2. Scope

In scope:

- Field definitions for CLV and time/price context in position-level outputs
- Source ladders for `close_ts` and price-point selection
- Coverage and audit surfacing rules for missingness
- Minimal ClickHouse cache design for `/prices-history` snapshots
- Offline test plan and Roadmap 5.1 acceptance/kill criteria

Out of scope:

- Backtesting or strategy recommendations
- Real-time streaming market data
- Predictive interpolation of missing prices

---

## 3. Canonical Definitions

### 3.1 Base terms

| Field | Type | Definition |
|---|---|---|
| `entry_price` | nullable float | Existing field. Average buy price from lifecycle (`entry_price_avg`). No semantic change in 5.1. |
| `entry_ts` | nullable timestamp | Existing entry timestamp from lifecycle. |
| `close_ts` | nullable timestamp | Canonical market close timestamp selected via the ladder in section 3.2. |
| `close_ts_source` | nullable string | Label identifying which ladder source produced `close_ts`. |
| `closing_window_minutes` | int | Max lookback from `close_ts` for selecting `closing_price`. Default: `1440` (24h). |
| `closing_price` | nullable float | Last observed price sample `<= close_ts` and `>= close_ts - closing_window_minutes`. |
| `closing_price_ts` | nullable timestamp | Timestamp of the selected `closing_price` sample. |
| `clv` | nullable float | Absolute CLV: `closing_price - entry_price`. |
| `clv_pct` | nullable float | Relative CLV: `(closing_price - entry_price) / entry_price`. |
| `beat_close` | nullable bool | `true` when `entry_price < closing_price`, else `false` when both are present. |
| `clv_source` | nullable string | `prices_history|<close_ts_source>` when CLV is computed; else `null`. |

Notes:

- `clv_pct` is `null` when `entry_price <= 0` or required inputs are missing.
- CLV fields are position-level and only for binary probability-priced outcomes.

### 3.2 `close_ts` source ladder (strict priority)

`close_ts` MUST be selected from the first available source below:

1. On-chain resolution timestamp (`resolved_at`)  
   `close_ts_source = "onchain_resolved_at"`
2. Gamma `closedTime`  
   `close_ts_source = "gamma_closedTime"`
3. Gamma `endDate`  
   `close_ts_source = "gamma_endDate"`
4. Gamma `umaEndDate`  
   `close_ts_source = "gamma_umaEndDate"`

If none are available:

- `close_ts = null`
- `close_ts_source = null`
- reason code MUST be `MISSING_CLOSE_TS`

No inferred or synthetic timestamp is allowed.

### 3.3 `closing_price` selector

Source endpoint: `/prices-history` (or cached rows originally fetched from it).

Candidate set for each position:

- price samples with same `outcome_token_id`
- `sample_ts <= close_ts`
- `sample_ts >= close_ts - closing_window_minutes`

Selection rule:

- choose the candidate with the greatest `sample_ts` (nearest prior to close)

If candidate set is empty:

- `closing_price = null`
- `closing_price_ts = null`
- `clv = null`
- `clv_pct = null`
- `beat_close = null`
- reason code MUST be `NO_PRICE_LE_CLOSE_IN_WINDOW`

No interpolation and no "first sample after close" fallback are allowed.

---

## 4. Time/Price Context Fields

Defaults:

- `lookback_window_minutes = 1440` (24h before `entry_ts`)
- `one_hour_anchor_minutes = 60`
- `one_hour_anchor_window_minutes = 180` (max age for 1h anchor lookup)

| Field | Type | Definition |
|---|---|---|
| `open_price` | nullable float | Earliest observed sample in `[entry_ts - lookback_window_minutes, entry_ts]`. |
| `open_price_ts` | nullable timestamp | Timestamp for `open_price`. |
| `nearest_prior_to_entry` | nullable float | Latest observed sample `<= entry_ts` in lookback window. |
| `nearest_prior_to_entry_ts` | nullable timestamp | Timestamp for `nearest_prior_to_entry`. |
| `price_1h_before_entry` | nullable float | Latest sample `<= (entry_ts - 60m)` and `>= (entry_ts - 60m - one_hour_anchor_window_minutes)`. |
| `price_1h_before_entry_ts` | nullable timestamp | Timestamp for `price_1h_before_entry`. |
| `movement_direction` | nullable string | `"up"`, `"down"`, or `"flat"` from `open_price` to `nearest_prior_to_entry`. |
| `minutes_to_close` | nullable int | Integer minutes from `entry_ts` to `close_ts` when `close_ts >= entry_ts`. |

`movement_direction` rule:

- `up` if `nearest_prior_to_entry - open_price > 1e-9`
- `down` if `nearest_prior_to_entry - open_price < -1e-9`
- `flat` otherwise

---

## 5. Eligibility and No-Guessing Rules

A position is CLV-eligible only when all are true:

- binary/outcome-probability market
- `entry_price` present and in `(0, 1]`
- `entry_ts` present
- `outcome_token_id` present
- `close_ts` resolved by ladder

When eligibility fails, fields remain `null` and reason codes MUST be recorded.

Hard no-guessing constraints:

- no synthetic `close_ts`
- no interpolation/extrapolation of missing prices
- no substitution from settlement price for pre-close CLV
- no silent default to zero for missing CLV/context values

---

## 6. Missingness Reason Codes

Reason codes are machine-readable enums. They MUST appear exactly as listed.

| Code | Condition | Affects |
|---|---|---|
| `NOT_BINARY_MARKET` | Position is not binary/outcome-probability | CLV + context |
| `MISSING_OUTCOME_TOKEN_ID` | No token identifier to query price history | CLV + context |
| `MISSING_ENTRY_TS` | `entry_ts` absent | CLV + context |
| `MISSING_ENTRY_PRICE` | `entry_price` absent | CLV |
| `INVALID_ENTRY_PRICE_RANGE` | `entry_price <= 0` or `entry_price > 1` | `clv_pct`, `beat_close` |
| `MISSING_CLOSE_TS` | All close timestamp ladder sources absent | CLV + `minutes_to_close` |
| `INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE` | `entry_ts > close_ts` | `minutes_to_close` and CLV gating |
| `PRICES_HISTORY_UNAVAILABLE` | `/prices-history` request failed/unavailable and no cached rows | CLV + context |
| `NO_PRICE_LE_CLOSE_IN_WINDOW` | No sample in closing selector window | CLV |
| `NO_PRICE_IN_LOOKBACK_WINDOW` | No sample in entry lookback window | `open_price` |
| `NO_PRIOR_PRICE_BEFORE_ENTRY` | No sample `<= entry_ts` in lookback | `nearest_prior_to_entry` |
| `NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW` | No sample in 1h anchor window | `price_1h_before_entry` |
| `INVALID_PRICE_VALUE` | Sample exists but non-numeric or outside `[0,1]` | CLV + context |

Per-position representation:

- each nullable computed field gets `<field>_missing_reason` when null
- for CLV aggregate fields, `clv_missing_reason` is required when `clv` is null

---

## 7. Coverage and Audit Surfacing

### 7.1 `coverage_reconciliation_report.json`

Add top-level sections:

```json
{
  "clv_coverage": {
    "eligible_positions": 0,
    "clv_present_count": 0,
    "clv_missing_count": 0,
    "coverage_rate": 0.0,
    "close_ts_source_counts": {},
    "clv_source_counts": {},
    "missing_reason_counts": {}
  },
  "time_price_context_coverage": {
    "eligible_positions": 0,
    "open_price_present_count": 0,
    "nearest_prior_to_entry_present_count": 0,
    "price_1h_before_entry_present_count": 0,
    "minutes_to_close_present_count": 0,
    "movement_direction_present_count": 0,
    "missing_reason_counts": {}
  }
}
```

Rules:

- `coverage_rate = clv_present_count / eligible_positions` (0 when denominator is 0)
- missingness is counted by exact reason code only (no free text)

### 7.2 `coverage_reconciliation_report.md`

Add:

- CLV coverage summary (`present/missing/rate`)
- source split (`close_ts_source_counts`)
- top missing reason codes
- warning if CLV coverage is below 30%

### 7.3 `audit_coverage_report.md`

Each position block MUST show:

- `close_ts` + `close_ts_source`
- `closing_price`, `clv`, `clv_pct`, `beat_close`, `clv_source`
- `open_price`, `nearest_prior_to_entry`, `price_1h_before_entry`, `movement_direction`, `minutes_to_close`
- explicit reason code beside every null computed field

No field may be silently omitted.

---

## 8. ClickHouse Caching Strategy (Minimal, Reproducible, Offline-Safe)

Proposed table:

```sql
CREATE TABLE IF NOT EXISTS polyttool.market_price_history_cache (
    outcome_token_id String,
    sample_ts DateTime64(3, 'UTC'),
    price Nullable(Float64),
    source LowCardinality(String) DEFAULT 'prices_history',
    request_start_ts DateTime64(3, 'UTC'),
    request_end_ts DateTime64(3, 'UTC'),
    http_status UInt16 DEFAULT 0,
    run_id String DEFAULT '',
    payload_sha256 FixedString(64) DEFAULT '',
    fetched_at DateTime64(3, 'UTC') DEFAULT now64(3)
) ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY (outcome_token_id, sample_ts);
```

Requirements:

- dedupe key is `(outcome_token_id, sample_ts)` via `ReplacingMergeTree`
- `payload_sha256` is hash of raw endpoint payload for reproducibility
- rows with invalid price values are not used for CLV/context selection
- cache-first reads are mandatory
- offline runs MUST compute from cache only; if missing, emit reason codes instead of failing

Fetch policy:

1. Query cache for required window.
2. If empty and network allowed, call `/prices-history` with bounded window.
3. Write fetched samples + request metadata to cache.
4. Recompute selection from cached rows.

This keeps audit/coverage deterministic and replayable from local data.

---

## 9. Offline Test Plan

All tests use fixtures or seeded ClickHouse rows. No live network calls.

| ID | Scenario | Expected result |
|---|---|---|
| `CLV-01` | All `close_ts` sources present | chooses `onchain_resolved_at` |
| `CLV-02` | On-chain missing, Gamma `closedTime` present | chooses `gamma_closedTime` |
| `CLV-03` | `closedTime` missing, `endDate` present | chooses `gamma_endDate` |
| `CLV-04` | Only `umaEndDate` present | chooses `gamma_umaEndDate` |
| `CLV-05` | Multiple price samples in window | picks latest `<= close_ts` |
| `CLV-06` | No sample in closing window | `clv = null` + `NO_PRICE_LE_CLOSE_IN_WINDOW` |
| `CTX-01` | Samples in lookback | computes `open_price`, `nearest_prior_to_entry` |
| `CTX-02` | Missing 1h anchor sample | `price_1h_before_entry = null` + reason code |
| `CTX-03` | `entry_ts > close_ts` | `minutes_to_close = null` + `INVALID_TIME_ORDER_ENTRY_AFTER_CLOSE` |
| `REP-01` | Mixed missingness reasons | reason counts match exactly in coverage JSON/MD |
| `AUD-01` | Audit rendering | null fields always accompanied by explicit reason |
| `OFF-01` | Network disabled, cache populated | CLV/context identical to online replay |
| `OFF-02` | Network disabled, cache empty | fields null with deterministic missing reasons |

---

## 10. Roadmap 5.1 Acceptance and Stop Conditions

### 10.1 Acceptance criteria

Roadmap 5.1 is acceptable when all are true:

1. Position outputs contain all fields defined in sections 3 and 4 (nullable where needed).
2. Every null CLV/context field includes a valid reason code from section 6.
3. Coverage artifacts include `clv_coverage` and `time_price_context_coverage`.
4. Audit artifact renders CLV/context values and missingness reasons per position.
5. Cache-backed recomputation is deterministic for identical inputs.

### 10.2 Kill/stop conditions for endpoint sparsity

After 3 consecutive scan runs with closed-position eligibility:

- stop advancing CLV beyond observational reporting if `clv_coverage.coverage_rate < 0.30`, or
- stop advancing if `NO_PRICE_LE_CLOSE_IN_WINDOW` exceeds 70% of CLV-eligible positions, or
- stop advancing if `PRICES_HISTORY_UNAVAILABLE` exceeds 50% of CLV-eligible positions.

When stopped:

- retain fields with `null + reason` behavior
- document sparsity in debug notes and roadmap tracking
- do not add interpolation or heuristic fills without a new ADR
