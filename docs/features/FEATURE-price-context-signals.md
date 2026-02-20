# Feature: Entry Price/Time Context Signals

## Summary

This feature adds deterministic entry-context signals around each position's `entry_ts`.
It uses bounded `/prices-history` windows, prefers cached snapshots first, and always records explicit missingness reasons instead of guessing.

The new context fields are written per position in `dossier.json`, summarized in coverage artifacts, and rendered in audit reports.

## Definitions

- `open_price`: earliest valid sample in the bounded entry lookback window.
- `open_price_ts`: timestamp of `open_price`.
- `price_1h_before_entry`: nearest valid sample at or before `entry_ts - 1 hour` within the bounded core window.
- `price_1h_before_entry_ts`: timestamp of `price_1h_before_entry`.
- `price_at_entry`: nearest valid sample at or before `entry_ts`.
- `price_at_entry_ts`: timestamp of `price_at_entry`.
- `movement_direction`: derived from `price_1h_before_entry -> price_at_entry`:
  - `up`
  - `down`
  - `flat`
- `minutes_to_close`: integer minutes from `entry_ts` to `close_ts` when valid.

For every nullable field above, the run now writes `<field>_missing_reason` when the value is missing.

## Data Retrieval Rules

1. Use cache-first lookup from `polyttool.market_price_snapshots` with `kind="entry_context"`.
2. If cache is missing and online mode is enabled, call `/prices-history` with bounded `startTs/endTs`.
3. Persist fetched rows back into cache.
4. Recompute selectors from snapshot rows only.

Implementation notes:
- Core window for `price_1h_before_entry` and `price_at_entry` is tightly bounded (default 2h).
- `open_price` uses the entry lookback window with an explicit cap.
- Requests use minute fidelity and do not send `interval` when bounded timestamps are present.

## Coverage and Audit Surfacing

Coverage JSON now includes `entry_context_coverage` with:
- `eligible_positions`
- present counts for each context field
- missing reason breakdown (`missing_reason_counts`)

Coverage markdown now includes `## Entry Context Coverage`.

Audit markdown now prints all context fields per position and shows reason codes beside missing values.

## Verification Steps

1. Run scan with CLV/context enrichment:
   - `python -m polytool scan --user "@<user>" --compute-clv`
2. Verify `dossier.json` position rows include:
   - `open_price`, `price_1h_before_entry`, `price_at_entry`, `movement_direction`, `minutes_to_close`
   - matching `*_missing_reason` fields when null
3. Verify `coverage_reconciliation_report.json` includes:
   - `entry_context_coverage`
4. Verify `coverage_reconciliation_report.md` includes:
   - `## Entry Context Coverage`
5. Verify `audit_coverage_report.md` position blocks include:
   - context values and explicit reasons for missing fields
