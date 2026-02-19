# ADR-0012 - Closing Price Definition for CLV

**Date:** 2026-02-19  
**Status:** Accepted  
**Roadmap:** 5.1 - CLV + time/price context

## Context

Roadmap 5.1 requires a deterministic CLV signal. Without a strict definition for
"closing price," CLV can drift across runs depending on timestamp source,
endpoint sparsity, and ad-hoc sample selection.

We need a rule that is:

- leakage-safe (never uses future samples)
- reproducible from local cache
- explicit about missingness when data is sparse

## Decision

1. `close_ts` is selected by this fixed ladder:
   - `onchain_resolved_at`
   - `gamma_closedTime`
   - `gamma_endDate`
   - `gamma_umaEndDate`

2. `closing_price` is the **last observed** `/prices-history` sample such that:
   - `sample_ts <= close_ts`
   - `sample_ts >= close_ts - closing_window`
   - where default `closing_window = 24h`

3. If no sample matches, `closing_price` is `null` and reason code is
   `NO_PRICE_LE_CLOSE_IN_WINDOW`.

4. CLV fields are defined as:
   - `clv = closing_price - entry_price`
   - `clv_pct = (closing_price - entry_price) / entry_price` when `entry_price > 0`
   - `beat_close = (entry_price < closing_price)` when both prices exist

5. `clv_source` is `prices_history|<close_ts_source>` when CLV is present,
   otherwise `null`.

6. No interpolation, extrapolation, or "first sample after close" fallback is
   allowed.

## Rationale

- Selecting the latest sample at or before close prevents forward leakage.
- The ladder prioritizes strongest provenance (on-chain first, then Gamma time
  fields).
- A bounded lookback window prevents stale prices from being treated as close.
- Explicit null+reason output is more trustworthy than guessed values.

## Consequences

- CLV coverage may be lower when `/prices-history` is sparse, but quality is
  explicit and auditable.
- Coverage and audit artifacts can report missing reason counts directly.
- Offline replay is possible from cached snapshots with deterministic results.

## Alternatives Rejected

1. Nearest sample by absolute time distance (before or after close)  
   Rejected: may use post-close data and introduce leakage.

2. First sample after close  
   Rejected: directionally biased and violates strict pre-close definition.

3. Linear interpolation around close  
   Rejected: model-based estimate, not observed market data.

4. Settlement price as close proxy  
   Rejected: settlement is an outcome value, not a pre-close market price.
