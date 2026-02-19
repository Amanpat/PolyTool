# ADR 0007: Fee Estimation at 2% of Positive Gross PnL

Date: 2026-02-17  
Status: Accepted

## Context

Scan trust artifacts needed fee-aware net PnL even when lifecycle rows do not carry reliable fee
data. Existing `realized_pnl_net` semantics were ambiguous (sometimes gross-like), so rewriting that
field directly would risk silent behavioral changes.

## Decision

Adopt a deterministic heuristic in the report build stage:

- Estimate fees only when `gross_pnl > 0`
- Default `profit_fee_rate = 0.02` from local config (override allowed)
- Label positive estimates with configurable `source_label` (default `estimated`)
- Label non-positive rows as `not_applicable`
- Add derived `realized_pnl_net_estimated_fees` and keep reported `realized_pnl_net` intact

Coverage and segment totals are computed from the estimated-fee net field, with gross totals emitted
alongside for auditability.

## Consequences

- Net PnL is now consistently fee-aware for profitable positions, including `PROFIT_EXIT`.
- Existing source PnL remains visible, reducing migration risk.
- `fees_source` is explicit and no longer relies on sparse upstream fee fields.
- Local users can tune fee rate/label in `polytool.yaml` without code changes.
