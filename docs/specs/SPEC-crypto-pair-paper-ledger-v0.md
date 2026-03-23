# SPEC: Crypto Pair Paper Ledger v0

**Status:** Accepted
**Created:** 2026-03-23
**Authors:** PolyTool Contributors
**Package:** `packages/polymarket/crypto_pairs/`

---

## 1. Purpose and scope

Define the deterministic Phase 1A paper-mode contract for the crypto pair bot.

This packet covers:
- Paper-mode config models for BTC/ETH/SOL 5m/15m pair decisions.
- Explicit JSON-serializable ledger records for observed opportunities, generated intents, fills, exposure state, settlement, and summaries.
- Pure accounting helpers for pair settlement, partial-leg exposure, and rollups.

This packet does **not** cover:
- CLI wiring
- live order submission
- dry-run/live executor integration
- scanner implementation details
- Gate 2 artifacts or simtrader integration

The design goal is simple: the scanner should later be able to hand a deterministic
quote snapshot into this ledger without redesigning the accounting schema.

---

## 2. Config contract

Phase 1A config lives in `config_models.py` and is nested into three submodels:

### 2.1 `CryptoPairFilterConfig`

- `symbols: tuple[str, ...]`
- `durations_min: tuple[int, ...]`

Validation:
- Symbols must be a non-empty subset of `BTC | ETH | SOL`
- Durations must be a non-empty subset of `5 | 15`

### 2.2 `CryptoPairFeeAssumptionConfig`

- `maker_rebate_bps`
- `maker_fee_bps`
- `taker_fee_bps`

Important: these are **strategy assumptions**, not proof of current exchange behavior.
The config allows the operator to make the assumption explicit and serializable.

Validation:
- All values must be `>= 0`
- `maker_rebate_bps` and `maker_fee_bps` cannot both be positive

### 2.3 `CryptoPairSafetyConfig`

- `stale_quote_timeout_seconds`
- `max_unpaired_exposure_seconds`
- `block_new_intents_with_open_unpaired`
- `require_fresh_quotes`

These are gating knobs only. They do not imply any live cancel/replace path in this packet.

### 2.4 `CryptoPairPaperModeConfig`

Top-level fields:
- `filters`
- `max_capital_per_market_usdc`
- `max_open_paired_notional_usdc`
- `target_pair_cost_threshold`
- `fees`
- `safety`

Validation:
- Per-market capital and global open paired notional must be positive
- `max_capital_per_market_usdc <= max_open_paired_notional_usdc`
- `target_pair_cost_threshold` must be `> 0` and `<= 1`

Serialized shape:

```json
{
  "schema_version": "crypto_pair_paper_mode_v0",
  "filters": {
    "symbols": ["BTC", "ETH"],
    "durations_min": [5, 15]
  },
  "max_capital_per_market_usdc": "25",
  "max_open_paired_notional_usdc": "50",
  "target_pair_cost_threshold": "0.97",
  "fees": {
    "maker_rebate_bps": "20",
    "maker_fee_bps": "0",
    "taker_fee_bps": "0",
    "maker_adjustment_bps": "20"
  },
  "safety": {
    "stale_quote_timeout_seconds": 15,
    "max_unpaired_exposure_seconds": 120,
    "block_new_intents_with_open_unpaired": true,
    "require_fresh_quotes": true
  }
}
```

---

## 3. Ledger record contract

All ledger records are explicit dataclasses with `to_dict()` methods that emit
JSON-safe output and include:
- `record_type`
- `schema_version: "crypto_pair_paper_ledger_v0"`

All monetary fields use `Decimal` in memory and serialize as strings.

### 3.1 `PaperOpportunityObservation`

Represents a scanner-visible pair quote snapshot:
- market identity
- YES/NO token IDs
- YES/NO quote prices
- paired quote cost
- target threshold
- quote age
- threshold pass/fail

### 3.2 `PaperOrderIntent`

Represents a deterministic intent to paper-buy a full set:
- pair size
- intended YES/NO prices
- intended pair cost
- intended paired notional
- capital caps captured from config
- fee assumptions captured from config
- stale-quote guard snapshot

An intent exists only if the opportunity survives all gating rules.

### 3.3 `PaperLegFill`

Represents a single paper fill on one leg:
- YES or NO
- token ID
- side
- price
- size
- gross notional
- signed `fee_adjustment_usdc`
- signed `net_cash_delta_usdc`

Convention:
- positive `fee_adjustment_usdc` = rebate
- negative `fee_adjustment_usdc` = fee

### 3.4 `PaperExposureState`

Represents the final paired/unpaired state for one intent:
- aggregated YES position
- aggregated NO position
- paired size and paired cost
- paired fee adjustment and net cash outflow
- unpaired leg, size, and notional
- unpaired max loss / max gain
- status:
  - `paired`
  - `partial_yes`
  - `partial_no`
  - `flat`

### 3.5 `PaperPairSettlement`

Represents settled PnL for the paired portion only:
- paired size
- paired cost
- settlement value
- gross PnL
- net PnL after fee adjustment
- any remaining unpaired size carried through for audit clarity

### 3.6 Rollups

- `PaperMarketRollup`: per-market counts and totals
- `PaperRunSummary`: per-run aggregate counts and totals

These rollups assume `exposures` contains the final exposure state per intent for the run.

---

## 4. Pure function contract

### 4.1 Intent gating

`get_order_intent_block_reason(...) -> Optional[str]`

Deterministic block reasons:
- `filter_miss`
- `threshold_miss`
- `stale_quote`
- `open_unpaired_exposure`
- `market_cap_exceeded`
- `run_cap_exceeded`

`generate_order_intent(...) -> Optional[PaperOrderIntent]`

Returns `None` if any gate fails.

### 4.2 Partial-leg exposure accounting

`compute_partial_leg_exposure(intent, fills, as_of=...) -> PaperExposureState`

Rules:
- YES and NO fills are aggregated independently.
- `paired_size = min(yes_filled_size, no_filled_size)`
- paired fee adjustments are allocated pro-rata by filled size.
- any remaining filled size becomes unpaired exposure on one leg.

Unpaired risk metrics:
- `unpaired_max_loss_usdc = unpaired_net_cash_outflow_usdc`
- `unpaired_max_gain_usdc = unpaired_size - unpaired_net_cash_outflow_usdc`

Phase 1A scope note:
- exposure aggregation only supports BUY-side fills
- sell-side unwind accounting is intentionally out of scope for this packet

### 4.3 Pair settlement PnL

`compute_pair_settlement_pnl(exposure, settlement_id, resolved_at, winning_leg)`

For the paired portion:

```text
settlement_value_usdc = paired_size
gross_pnl_usdc = settlement_value_usdc - paired_cost_usdc
net_pnl_usdc = settlement_value_usdc - paired_net_cash_outflow_usdc
```

The recorded `winning_leg` is informational for audit. For a complete YES+NO pair,
the paired settlement value is always `$1.00` per paired share in this model.

### 4.4 Rollups

- `build_market_rollups(observations, intents, exposures, settlements)`
- `build_run_summary(run_id, generated_at, market_rollups)`

Rollups are pure sums and counts only. No external state or database access is required.

---

## 5. Scanner handoff contract

The intended next-packet handoff is:

1. Scanner discovers an eligible BTC/ETH/SOL 5m/15m market.
2. Scanner observes a YES/NO quote snapshot.
3. Scanner instantiates `PaperOpportunityObservation`.
4. Scanner calls `generate_order_intent(...)`.
5. Future paper-mode execution logic records `PaperLegFill` records as deterministic artifacts.
6. Final exposure, settlement, market rollup, and run summary are computed from those records.

Important boundary:
- the scanner should provide quotes and identifiers
- this ledger owns threshold gating, exposure accounting, settlement math, and rollups

That keeps the scanner independent from accounting evolution.

---

## 6. Assumptions and caveats

The following are explicit modeled assumptions, not proven exchange behavior:

- Maker rebate / maker fee / taker fee values are operator-configured assumptions.
- Full-pair settlement is modeled as `$1.00` per paired YES+NO share.
- Partial-leg exposure remains open inventory in this packet; there is no unwind path here.
- Quote staleness is enforced by local policy, not by exchange truth.

This packet makes **no** profitability claim. It defines deterministic accounting only.

---

## 7. Acceptance

Phase 1A paper-ledger v0 is accepted when:
- config models validate the required knobs
- all ledger records serialize cleanly to JSON
- settlement, exposure, and rollup helpers are pure and deterministic
- offline tests cover complete pair fill, threshold miss, partial exposure, settlement math, and bad inputs

