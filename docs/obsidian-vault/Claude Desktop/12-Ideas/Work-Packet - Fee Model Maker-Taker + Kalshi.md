---
tags:
  - work-packet
  - fees
  - simtrader
  - integration
date: 2026-04-10
status: superseded
priority: high
tracks-affected:
  - 1A
  - 1B
  - 1C
  - Phase-3
source-repo: evan-kolberg/prediction-market-backtesting (MIT)
assignee: architect → Claude Code agent
---

# Work Packet: SimTrader Maker/Taker Fee Model + Kalshi Fee Model


> [!WARNING] SUPERSEDED
> This work packet has been replaced by [[Work-Packet - Unified Open Source Integration]].
> The fee model design was based on incorrect assumptions. See [[2026-04-10 GLM5 - Unified Gap Fill Open Source Integration]] for corrections.


## Context & Motivation

### Why This Matters Now

Our SimTrader fee module (`packages/polymarket/simtrader/portfolio/fees.py`) currently computes **taker fees only**. Every fill — regardless of whether the simulated order was a resting maker order or an aggressive taker order — is charged using the Polymarket taker fee formula with a conservative 200bps default.

This is systematically wrong for our two active strategy tracks:

- **Track 1A (Crypto Pair Bot):** Uses maker orders exclusively. Crypto 5m/15m markets offer a **20bps maker REBATE** (negative fee — we get paid). Our SimTrader charges 200bps taker fee instead. Every simulated crypto pair fill overestimates costs by ~220bps.
- **Track 1B (A-S Market Maker):** Places resting limit orders (maker). The spread capture PnL is eroded by phantom taker fees that would not exist in live trading. **Gate 2 results are pessimistic** — tapes that produce fills report lower PnL than reality.
- **Phase 3 (Kalshi Integration):** Kalshi uses a completely different fee model (nonlinear expected-earnings). We have zero Kalshi fee code anywhere in the codebase.

### Discovery Source

This gap was identified during a deep-dive analysis of `evan-kolberg/prediction-market-backtesting` (MIT-licensed, 155 stars, actively maintained). Their project implements both:

1. **`PolymarketFeeModel`** — with maker/taker distinction (file: `backtests/polymarket_quote_tick/_polymarket_single_market_pmxt_runner.py`, lines 21 and 142)
2. **`KalshiProportionalFeeModel`** — nonlinear expected-earnings model (file: `backtests/kalshi_trade_tick/_kalshi_single_market_trade_runner.py`, lines 19 and 93)

Both are MIT-licensed. We are **not copying their code verbatim** — we are referencing their approach and reimplementing in our existing Decimal-safe architecture. The architect should clone their repo to review the exact fee calculation logic before writing the agent prompt.

**Reference repo:** `https://github.com/evan-kolberg/prediction-market-backtesting` (commit `a550fd61`, indexed April 1 2026)

**Deep dive research note:** [[07-Backtesting-Repo-Deep-Dive]]

---

## Scope

### In Scope

1. **Add maker/taker fee distinction to `fees.py`** — new `compute_fill_fee()` signature accepts a `role: Literal["maker", "taker"]` parameter
2. **Add maker rebate support** — when `role="maker"`, apply rebate (negative fee) using configurable `maker_rebate_bps`
3. **Add `KalshiFeeModel` class** — separate fee computation for Kalshi's expected-earnings formula
4. **Update `SimBroker` to pass order role** — SimBroker must determine if a fill is maker or taker based on whether the order was resting (maker) or aggressive (taker)
5. **Update portfolio ledger** — fees can now be negative (rebates); ledger math must handle this
6. **Config surface** — fee parameters configurable via strategy config JSON (not hardcoded)
7. **Tests** — unit tests for all new fee paths, including edge cases (price at 0/1 boundary, zero-size, rebate exceeds fill notional)

### Out of Scope (Don't Do List)

- Do NOT modify `fill_engine.py` or `sim_broker.py` fill matching logic (book mutation is a separate work packet)
- Do NOT add dynamic fee-rate fetching from Polymarket `/fee-rate` endpoint (that's a live execution concern, not SimTrader)
- Do NOT refactor the existing `packages/polymarket/fees.py` (float-based, used by non-SimTrader code) — only modify the SimTrader Decimal-safe `portfolio/fees.py`
- Do NOT implement fee-tier progression (e.g., volume-based fee discounts) — use fixed rates per config
- Do NOT modify any execution-critical files (`execution/`, `kill_switch.py`, `risk_manager.py`) — this is a portfolio/accounting change only
- Do NOT touch crypto_pairs fee code (`packages/polymarket/crypto_pairs/`) — that module has its own fee handling

---

## Technical Design

### 1. Fee Role Determination (SimBroker responsibility)

The SimBroker must classify each fill as `maker` or `taker`. The heuristic:

```
IF the order was RESTING in the book (placed before the triggering event)
  AND the fill was triggered by an incoming book event (not the order's own arrival)
THEN role = "maker"
ELSE role = "taker"
```

In SimTrader's current architecture, ALL strategy orders are limit orders placed against a reconstructed book. The `effective_seq` delay (from `latency.py`) means orders activate AFTER the event that triggers them. Once active, they rest until a subsequent book event produces a fillable price. **This means virtually all SimTrader fills are maker fills** — the strategy's orders are always resting, never aggressive.

However, the architect should add a `force_taker: bool = False` flag to the Order model for strategies that explicitly want to model market orders or aggressive limit orders (e.g., a directional strategy that crosses the spread). Default `False` preserves backward compatibility.

### 2. Updated `compute_fill_fee()` Signature

```python
def compute_fill_fee(
    fill_size: Decimal,
    fill_price: Decimal,
    fee_rate_bps: Decimal | None = None,
    role: Literal["maker", "taker"] = "taker",
    maker_rebate_bps: Decimal | None = None,
) -> Decimal:
    """
    Returns fee in USDC. Positive = cost to trader. Negative = rebate to trader.
    
    For role="taker": applies quadratic curve formula (existing behavior).
    For role="maker": applies flat rebate (negative fee).
    """
```

### 3. Polymarket Fee Formula (Current + New)

**Taker (existing, unchanged):**
```
fee = shares × price × (fee_rate_bps / 10000) × (price × (1 - price))²
```
- Default `fee_rate_bps`: 200 (conservative)
- Curve factor peaks at 0.0625 at p=0.5, approaches 0 at extremes

**Maker (new):**
```
fee = -(shares × price × (maker_rebate_bps / 10000))
```
- Negative value = credit to trader
- Default `maker_rebate_bps`: 20 (current Polymarket maker rebate on crypto markets)
- Standard markets: `maker_rebate_bps` = 0 (no rebate, but also no fee)
- The maker formula is LINEAR (no quadratic curve) — Polymarket maker rebates are flat percentage of notional, not curved

**Note for architect:** Verify the current Polymarket maker rebate structure before finalizing. The 20bps rebate on crypto 5m/15m markets may differ from standard event markets. The config should allow per-market-category fee overrides.

### 4. Kalshi Fee Model (New Class)

Reference: `KalshiProportionalFeeModel` from `evan-kolberg/prediction-market-backtesting`

Kalshi uses an "expected earnings" model where fees are proportional to the expected payout:

```python
class KalshiFeeModel:
    """Kalshi Pro fee schedule — expected-earnings based."""
    
    def compute_fee(
        self,
        contracts: Decimal,
        price_cents: int,  # Kalshi prices are in cents (1-99)
        side: Literal["yes", "no"],
    ) -> Decimal:
        """
        Fee = contracts × fee_per_contract
        fee_per_contract = max(0, round(price_cents * fee_rate, nearest_cent))
        
        Fee rate schedule (Kalshi Pro, as of March 2026):
        - Contracts 1-24: 7%
        - Contracts 25-99: 5%  
        - Contracts 100+: 4%
        
        NOTE: The architect MUST verify current Kalshi fee schedule before 
        implementing. These rates change. Check kalshi.com/docs/fees.
        """
```

**Important:** The architect should clone the reference repo and read their `KalshiProportionalFeeModel` implementation at line 19 of `backtests/kalshi_trade_tick/_kalshi_single_market_trade_runner.py` for the exact formula. Do NOT guess — Kalshi's fee model is nonlinear and version-dependent.

### 5. Config Surface

Add to strategy config JSON:

```json
{
  "fees": {
    "platform": "polymarket",
    "taker_fee_rate_bps": 200,
    "maker_rebate_bps": 20,
    "force_taker": false
  }
}
```

For Kalshi:
```json
{
  "fees": {
    "platform": "kalshi",
    "kalshi_fee_tier": "pro"
  }
}
```

### 6. Portfolio Ledger Impact

The ledger currently adds fees to BUY cost and deducts from SELL proceeds. With maker rebates (negative fees), the ledger must:

- BUY with maker rebate: cost is REDUCED (rebate credited)
- SELL with maker rebate: proceeds are INCREASED (rebate credited)

The sign convention: `positive fee = cost`, `negative fee = credit`. The ledger's existing arithmetic should handle this naturally if it uses `cost += fee` where fee can be negative. Verify this in the implementation.

---

## Files to Modify

| File | Change | Review Level |
|------|--------|-------------|
| `packages/polymarket/simtrader/portfolio/fees.py` | Add maker branch, maker_rebate_bps param, KalshiFeeModel class | Recommended |
| `packages/polymarket/simtrader/broker/sim_broker.py` | Pass `role` to fee computation based on order type | Recommended |
| `packages/polymarket/simtrader/broker/rules.py` | Add `force_taker` field to Order model | Skip (minor) |
| `packages/polymarket/simtrader/portfolio/ledger.py` (or equivalent) | Verify negative fee handling | Recommended |
| `packages/polymarket/simtrader/config_loader.py` | Load fee config from strategy JSON | Skip (minor) |
| `tests/test_simtrader_portfolio.py` | Add maker fee, taker fee, rebate, Kalshi fee test cases | Mandatory |

**Execution-critical files NOT touched:** `execution/`, `kill_switch.py`, `risk_manager.py`, `live_executor.py` — none of these are modified.

---

## Reference Materials for Architect

### Must Read Before Writing Agent Prompt

1. **Our current fee module:** `packages/polymarket/simtrader/portfolio/fees.py` (full contents provided in Codex output from 2026-04-10 session, also in [[07-Backtesting-Repo-Deep-Dive]])
2. **Reference repo fee models:** Clone `https://github.com/evan-kolberg/prediction-market-backtesting`, read:
   - `backtests/polymarket_quote_tick/_polymarket_single_market_pmxt_runner.py` lines 21, 142
   - `backtests/kalshi_trade_tick/_kalshi_single_market_trade_runner.py` lines 19, 93
3. **Polymarket fee documentation:** Verify current maker/taker fee schedule at polymarket.com or via the `/fee-rate` CLOB API endpoint
4. **Kalshi fee documentation:** Verify current fee tiers at kalshi.com/docs/fees

### Attribution

Include in the file header of any new Kalshi fee code:

```python
# Kalshi fee model approach derived from evan-kolberg/prediction-market-backtesting
# (MIT License, https://github.com/evan-kolberg/prediction-market-backtesting)
# Reimplemented in Decimal-safe arithmetic for SimTrader compatibility.
```

---

## Acceptance Criteria

1. `compute_fill_fee(size=100, price=0.50, role="taker", fee_rate_bps=200)` returns the same value as the current implementation (backward compatible)
2. `compute_fill_fee(size=100, price=0.50, role="maker", maker_rebate_bps=20)` returns a NEGATIVE value (rebate)
3. `compute_fill_fee(size=100, price=0.50, role="maker", maker_rebate_bps=0)` returns `Decimal("0")` (no fee, no rebate)
4. Kalshi fee model produces correct fees for all three volume tiers (1-24, 25-99, 100+ contracts)
5. Portfolio ledger handles negative fees without assertion errors or sign bugs
6. All existing `test_simtrader_portfolio.py` tests pass unchanged (backward compat)
7. At least 10 new test cases covering: maker/taker for Polymarket, all three Kalshi tiers, edge cases (price=0, price=1, zero size), rebate exceeding notional guard
8. Dev log written to `docs/dev_logs/YYYY-MM-DD_fee-model-maker-taker.md`

---

## Impact on Other Work Packets

- **Gate 2 re-evaluation:** After this lands, re-run Gate 2 sweep with `role="maker"` on the crypto bucket tapes. The 7/10 positive tapes should show improved PnL (no longer penalized with phantom taker fees). This does NOT fix the zero-fills-on-politics/sports problem.
- **Track 1A paper testing:** Crypto pair bot paper soak should use `maker_rebate_bps=20` to accurately model the rebate income.
- **Phase 3 Kalshi:** KalshiFeeModel is a prerequisite for any Kalshi backtesting.
- **Phase 4 Autoresearch:** Fee accuracy directly impacts experiment ledger PnL numbers. This should land before autoresearch starts.

---

## Cross-References

- [[07-Backtesting-Repo-Deep-Dive]] — Full analysis of source repo
- [[SimTrader]] — SimTrader module documentation
- [[Track-1A-Crypto-Pair-Bot]] — Maker rebate is core to pair bot economics
- [[Track-1B-Market-Maker]] — Gate 2 results affected by taker-only fees
- [[Risk-Framework]] — Gate definitions reference net PnL after fees
