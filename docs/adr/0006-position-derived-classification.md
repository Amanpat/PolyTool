# ADR 0006: Position-Derived Classification for Segment Analysis

Date: 2026-02-16  
Status: Accepted

## Context

Roadmap 4.2 requires segment-level reporting in scan trust artifacts. Existing
artifacts had outcome/PnL coverage but no deterministic per-position segment tags.
We need stable classification that works locally and does not infer hidden labels.

## Decision

Use deterministic, position-derived classification at report build time:

- `league`: first token from `market_slug` if known; otherwise `unknown`
- `sport`: derived only from league mapping
- `market_type`: safe heuristic (`spread|handicap` -> `spread`; `Will .* win` -> `moneyline`; else `unknown`)
- `entry_price_tier`: configurable via local `polytool.yaml` tiers, with fixed defaults when absent

Segment aggregates are emitted in `coverage_reconciliation_report.json` and a dedicated
`segment_analysis.json` artifact. Unknown buckets are always present and rows are never dropped.

## Consequences

- Segment outputs are reproducible and auditable.
- Users can tune local entry-price tiers without changing code.
- Unknown-rate visibility makes coverage gaps explicit.
- Classification stays conservative (no fuzzy sport/league guessing from question text).

