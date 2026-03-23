## Summary

Track 2 Phase 1A now has a deterministic paper-ledger foundation for crypto
pair decisions and accounting.

The packet ships:
- nested paper-mode config models
- explicit paper ledger records
- pure helpers for intent gating, exposure accounting, settlement, and rollups

It does **not** ship:
- CLI wiring
- live orders
- dry-run executor integration

## What shipped

### Config contract

`packages/polymarket/crypto_pairs/config_models.py` defines:
- symbol / duration filters
- per-market capital cap
- max open paired notional
- target pair-cost threshold
- maker rebate / fee assumptions
- stale-quote and unpaired-exposure safety knobs

### Paper ledger contract

`packages/polymarket/crypto_pairs/paper_ledger.py` defines record types for:
- observed opportunity
- generated order intent
- recorded leg fill
- paired or partial exposure state
- settled pair result
- per-market rollup
- per-run summary

All records are JSON-serializable through explicit `to_dict()` methods.

## Handoff from scanner to paper mode

The intended future flow is:

1. Scanner produces a deterministic YES/NO quote snapshot.
2. That snapshot becomes `PaperOpportunityObservation`.
3. `generate_order_intent(...)` decides whether paper mode should open a pair.
4. Future execution plumbing records `PaperLegFill` rows.
5. The ledger computes exposure, settlement, and summaries without needing scanner redesign.

This keeps the scanner focused on discovery and quoting, while the ledger owns accounting.

## Safety and assumption notes

- Fee and rebate fields are explicit strategy assumptions only.
- Full-pair settlement is modeled as `$1.00` per paired YES+NO share.
- Partial-leg exposure is tracked but not auto-unwound in this packet.
- All helpers are offline and deterministic; there are no network calls or live execution paths here.

## References

- `docs/specs/SPEC-crypto-pair-paper-ledger-v0.md`
- `docs/dev_logs/2026-03-22_phase1a_crypto_pair_paper_ledger_v0.md`
