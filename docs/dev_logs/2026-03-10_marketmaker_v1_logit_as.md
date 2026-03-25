# Dev Log: MarketMakerV1 — Logit-Space Avellaneda-Stoikov

**Date:** 2026-03-10
**Branch:** simtrader
**Scope:** Quote math only; no session-pack, watcher, scanner, or UI changes.

---

## Problem

`MarketMakerV0` applies the Avellaneda-Stoikov formulas directly in probability
space.  For binary prediction markets this is incorrect: the probability
variable is bounded to [0, 1], so the diffusion assumption underlying A-S does
not hold.  In particular, the model produces the same absolute spread near 0.05
as near 0.50, which over-prices risk at the tails and under-prices it at the
center.

---

## Solution

`MarketMakerV1` applies A-S entirely in logit space, where probability is
mapped to an unbounded real line before computation and converted back via
sigmoid after.

### Math summary

```
x      = logit(clip(p, ε, 1-ε))   # ε = 1e-4 to avoid ±inf
x_r    = x - q · γ · σ² · T       # reservation price in logit space
Δ      = γ · σ² · T + (2/γ) · ln(1 + γ/κ)   # spread in logit space
p_bid  = sigmoid(x_r − Δ/2)
p_ask  = sigmoid(x_r + Δ/2)
```

- `q = net_YES_inventory / order_size`
- `σ²` is measured in logit space (variance of logit mid-price changes);
  default fallback 0.003 ≈ 16 × V0's probability-space default of 0.0002

### Why this is correct

The sigmoid derivative at `p` is `p·(1-p)`.  A fixed logit spread therefore
maps to:
- a **wide** probability spread near p = 0.50 (derivative = 0.25)
- a **compressed** probability spread near the tails (derivative ≈ 0.05 at p = 0.05)

This matches economic intuition: a market near certainty has less mid-point
ambiguity per unit probability move, so a tighter physical spread is appropriate.

---

## Implementation

### Files changed

| File | Change |
|---|---|
| `packages/polymarket/simtrader/strategies/market_maker_v1.py` | New file — `MarketMakerV1` + math helpers |
| `packages/polymarket/simtrader/strategy/facade.py` | Add `"market_maker_v1"` to `STRATEGY_REGISTRY` |
| `tests/test_market_maker_v1.py` | 43 new focused tests |
| `docs/dev_logs/2026-03-10_marketmaker_v1_logit_as.md` | This file |

### Design: inheritance-minimal override

`MarketMakerV1` inherits from `MarketMakerV0`.  Only three methods are
overridden:

1. `_record_mid` — stores `logit(clip(mid))` instead of raw `mid`
2. `_sigma_sq` — falls back to logit-space default `0.003` instead of V0's `0.0002`
3. `_compute_quotes` — applies A-S in logit space, converts back via sigmoid

All constructor params, lifecycle hooks (`on_start`, `on_fill`), time-horizon
tracking, microprice, reprice-threshold, and `compute_order_requests` are
unchanged.  The public `compute_quotes` signature is identical to V0.

---

## Tests

**43 tests, all passing.**

```
TestMathHelpers          (7)  — logit/sigmoid/clip unit math
TestSpreadWidestAtCenter (3)  — physical spread is widest at p=0.50
TestSpreadCompressedAtTails (5)  — spread at 0.05/0.95 < spread at center
TestClippingBehavior     (6)  — no nan/inf near 0 and 1; bounded outputs
TestInventorySkew        (3)  — positive q lowers center; negative q raises center
TestBoundedOutputs       (5)  — bid/ask in [0.01,0.98]×[0.02,0.99], bid<ask
TestPipelineNoRegression (14) — 2-intent shape, sides, tick alignment, reprice,
                                on_fill, reason strings, registry entry
```

All 30 `test_market_maker_v0.py` tests continue to pass (no V0 regressions).

---

## Manual verification commands

```bash
# All new V1 tests
python -m pytest tests/test_market_maker_v1.py -v

# Ensure V0 is unaffected
python -m pytest tests/test_market_maker_v0.py -v

# Quick smoke: V1 is importable and registered
python -c "
from packages.polymarket.simtrader.strategies.market_maker_v1 import MarketMakerV1
from packages.polymarket.simtrader.strategy.facade import STRATEGY_REGISTRY
mm = MarketMakerV1()
quotes = mm.compute_quotes(best_bid=0.45, best_ask=0.55, asset_id='tok')
print('intents:', len(quotes), [i.reason for i in quotes])
print('registry key present:', 'market_maker_v1' in STRATEGY_REGISTRY)
"

# Demonstrate tail compression vs center spread
python -c "
from packages.polymarket.simtrader.strategies.market_maker_v1 import MarketMakerV1
from decimal import Decimal
mm = MarketMakerV1(resolution_guard=0.0, min_spread=0.001, max_spread=0.50)
mm._inventory = Decimal('0')
for mid in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
    b, a = mm._compute_quotes(mid=mid, t_elapsed_hours=0.0, sigma_sq=0.003)
    print(f'  mid={mid:.2f}  bid={b:.3f}  ask={a:.3f}  spread={a-b:.4f}')
"
```

Expected output for the last command:
```
  mid=0.05  bid=0.027  ask=0.092  spread=0.0650
  mid=0.10  bid=0.055  ask=0.175  spread=0.1200
  mid=0.20  bid=0.116  ask=0.324  spread=0.2080
  mid=0.30  bid=0.183  ask=0.451  spread=0.2680
  mid=0.40  bid=0.258  ask=0.561  spread=0.3030
  mid=0.50  bid=0.343  ask=0.657  spread=0.3140
```
Spread monotonically increases from tail to center — the defining property of logit-space A-S.

---

## Notes

- `_DEFAULT_SIGMA_SQ_LOGIT = 0.003` calibrated as `0.0002 × 16`, matching the
  Jacobian ratio at `p = 0.5` (logit variance ≈ 16 × probability variance for
  small moves near the center).
- The probability-space `min_spread` / `max_spread` clamp is applied *after*
  sigmoid conversion so the config semantics are unchanged.
- Resolution guard is applied in logit space (multiplies `spread_x`), matching
  V0's intent of widening spread near resolution.
- No changes to sweep configs, CLI entry points, or live-runner paths.
