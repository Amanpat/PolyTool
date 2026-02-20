# Feature: Dual CLV Variants (clv_settlement + clv_pre_event)

## Motivation

The original CLV implementation uses a single timestamp ladder that walks through all available
close-time sources in priority order: `onchain_resolved_at` → `closedTime` → `endDate` →
`umaEndDate`. This conflates two distinct signals:

- **Settlement signal** — the on-chain resolution timestamp reflects when the contract was
  definitively settled. This can lag the actual market close by hours or days due to on-chain
  finalization delays, UMA optimistic oracle disputes, etc.
- **Pre-event signal** — the gamma market close or scheduled end date reflects when the
  underlying event concluded. This is the more meaningful edge measurement anchor for
  hypothesis testing because it measures how well the entry price predicted the outcome
  *before* the event ended, not before the blockchain settlement.

Separating these two variants enables cleaner hypothesis segmentation: is the edge from
better pre-event pricing, or just from catching favorable settlement timing?

## Two Variants

### clv_settlement

- **Anchor:** `onchain_resolved_at` only (reads `resolved_at`, `resolvedAt`,
  `resolution_resolved_at`)
- **Use case:** Measures edge relative to price at the moment of on-chain settlement
- **Missing reason when not applicable:** `NO_SETTLEMENT_CLOSE_TS`

### clv_pre_event

- **Anchor:** `gamma_closedTime` → `gamma_endDate` → `gamma_umaEndDate` ladder (skips
  on-chain resolution stage entirely)
- **Use case:** Measures edge relative to price at market close / scheduled event end —
  the cleaner signal for pre-event edge
- **Missing reason when not applicable:** `NO_PRE_EVENT_CLOSE_TS`

## Per-Position Fields Added

Each position dict gains 12 new fields after `enrich_position_with_dual_clv()`:

| Field | Type | Description |
|---|---|---|
| `closing_price_settlement` | float or None | Price observed near settlement close_ts |
| `closing_ts_settlement` | ISO string or None | Timestamp of the observed price |
| `clv_pct_settlement` | float or None | (closing_price - entry_price) / entry_price |
| `beat_close_settlement` | bool or None | True if entry_price < closing_price_settlement |
| `clv_source_settlement` | string or None | `"prices_history|onchain_resolved_at"` |
| `clv_missing_reason_settlement` | string or None | Reason code if missing |
| `closing_price_pre_event` | float or None | Price observed near pre-event close_ts |
| `closing_ts_pre_event` | ISO string or None | Timestamp of the observed price |
| `clv_pct_pre_event` | float or None | (closing_price - entry_price) / entry_price |
| `beat_close_pre_event` | bool or None | True if entry_price < closing_price_pre_event |
| `clv_source_pre_event` | string or None | `"prices_history|gamma_closedTime"` etc. |
| `clv_missing_reason_pre_event` | string or None | Reason code if missing |

The existing base CLV fields (`clv`, `clv_pct`, `beat_close`, `clv_source`, etc.) remain
unchanged (computed via the full combined ladder as before).

## Coverage Report Rendering

`_build_clv_coverage()` now embeds two sub-dicts under `"settlement"` and `"pre_event"` keys,
each with:

- `variant` (label)
- `eligible_positions`, `clv_present_count`, `clv_missing_count`, `coverage_rate`
- `clv_source_counts`, `missing_reason_counts`

The markdown render (`_render_clv_coverage`) emits two additional sub-sections:

```
### CLV Settlement
- Coverage: 72.00% (18/25 eligible positions)
- Missing: 7
- Top missing reasons:
  - NO_SETTLEMENT_CLOSE_TS: 7

### CLV Pre-Event
- Coverage: 88.00% (22/25 eligible positions)
- Missing: 3
- Top missing reasons:
  - NO_PRE_EVENT_CLOSE_TS: 3
```

## Hypothesis Ranking Logic

`_build_hypothesis_candidates()` uses a preference cascade to select the best CLV metric
for ranking each segment:

1. **pre_event** — `notional_weighted_avg_clv_pct_pre_event` when its weight > 0
2. **settlement** — `notional_weighted_avg_clv_pct_settlement` when its weight > 0
3. **combined** — `notional_weighted_avg_clv_pct` (base, full ladder) when its weight > 0
4. **count-weighted fallback** — `avg_clv_pct_pre_event` → `avg_clv_pct_settlement` →
   `avg_clv_pct` when all notional weights are zero

Each candidate dict includes a `clv_variant_used` field (`"pre_event"`, `"settlement"`, or
`"combined"`) indicating which metric drove the ranking.

## Missing Reason Codes

| Code | Meaning |
|---|---|
| `NO_SETTLEMENT_CLOSE_TS` | Position has no `resolved_at`/`resolvedAt`/`resolution_resolved_at` field |
| `NO_PRE_EVENT_CLOSE_TS` | Position has no `closedTime`/`endDate`/`umaEndDate` field |

These codes are distinct from `NO_CLOSE_TS` (the base ladder failure) to aid targeted
debugging.

## Backward Compatibility

- `enrich_position_with_clv()` and `enrich_positions_with_clv()` are **unchanged**
- Existing `clv`, `clv_pct`, `beat_close`, `close_ts`, `close_ts_source`,
  `close_ts_failure_reason`, and entry-context fields are preserved by
  `enrich_position_with_dual_clv()`, which calls the base function first
- `enrich_positions_with_dual_clv()` returns the same summary keys as `enrich_positions_with_clv()`
  plus `settlement_present_count`, `settlement_missing_count`, `pre_event_present_count`,
  `pre_event_missing_count`
