---
tags: [prompt-archive, research, fees, pmxt, sports, cross-platform]
date: 2026-04-10
model: GLM-5-Turbo
status: complete
topics: [Polymarket-fees, Kalshi-fees, sports-strategies, pmxt-sidecar, cross-platform-arb]
---

# GLM-5 Turbo — Unified Gap Fill for Open-Source Integration

## Critical Corrections to Our Assumptions

### 1. Maker Rebates Are CURVED, Not Flat (REFUTED our assumption)
- Maker rebate calculation uses the SAME p(1−p) formula as taker fees
- Your share of daily rebate pool per market = your fee_equivalent / total fee_equivalent
- fee_equivalent = C × feeRate × p × (1−p)
- This means our work packet's "flat rebate" formula is WRONG — must use quadratic curve

### 2. Fee Rates Are Category-Specific (NOT a single 200bps)
| Category | feeRate |
|----------|---------|
| Crypto | 0.072 |
| Sports | 0.03 |
| Finance / Politics / Mentions / Tech | 0.04 |
| Economics / Culture / Weather / Other | 0.05 |
| Geopolitics | 0 (fee-free) |

Formula: fee = C × feeRate × p × (1 − p)

### 3. Dynamic Crypto Fees Peak at ~3.15%, Not 1.56%
- On 15-min crypto markets, dynamic taker fee at p=0.50 reaches ~3.15%
- The 1.56% figure is outdated/wrong

### 4. Kalshi Uses 0.07 × C × P × (1−P), Not Volume Tiers
- Same p(1−p) shape as Polymarket but fixed 0.07 multiplier
- No confirmed "Pro vs Basic" fee distinction in current docs
- Kalshi HAS maker/taker distinction — makers can avoid fees on some markets
- Kalshi has a Liquidity Incentive Program (Sept 2025 → Sept 2026)
- API: GET /series/fee_changes + per-market fee_waiver fields

### 5. Maker Rebates vs Liquidity Rewards Are SEPARATE
- **Maker Rebates:** funded by taker fees, redistributed daily, proportional to your fee_equivalent share per market. Crypto = 20% of taker fees; Sports/Politics/etc = 25%
- **Liquidity Rewards (Q-score):** separate dYdX-inspired program, rewards for tight two-sided quoting, quadratic scoring rule based on distance from midpoint

### 6. Polymarket Has /fee-rate API Endpoint
- GET /fee-rate?token_id=X → returns { "base_fee": 30 } (basis points)
- Use as feeRate = base_fee / 10000 in the formula

### 7. Dome Acquisition NOT Confirmed
- "pmxt is the only remaining SDK" claim is too strong
- Dome still listed on YC, other SDKs exist (predmarket, PolyRouter)

### 8. "50-80% of income from liquidity rewards" — UNVERIFIED
- No primary source found for this claim from our roadmap v5.1

## Sports Strategy Parameters (Verified from Source Files)

### Final Period Momentum
- final_period_minutes = 30
- entry_price = 0.80
- take_profit_price = 0.92
- stop_loss_price = 0.50
- trade_size = 100
- Sport-agnostic (not restricted to NBA/NFL)

### Late Favorite Limit Hold
- entry_price = 0.90 (favorite threshold)
- activation_start_time_ns = 0 (set by backtest harness)
- trade_size = 25
- Hold-to-resolution design (no explicit profit target)
- Limit buy at signal_price when in time window

### Sports VWAP Reversion
- vwap_window = 80 ticks
- entry_threshold = 0.008 (absolute price below VWAP)
- exit_threshold = 0.002
- take_profit = 0.015
- stop_loss = 0.02
- Tick-based VWAP (deque of price/size with maxlen=80)

### Backtest Results: NONE PUBLISHED
- No published PnL results for sports strategies
- Treat as reference implementations, not proven strategies

## pmxt Operational Details

- Sidecar port: 3847 default, lock file at ~/.pmxt/server.lock
- Multiple Python processes CAN share one sidecar
- Sidecar crash: SDKs re-resolve host/token from lock file
- No official Docker image — roll your own
- For OTHER wallet analytics: bypass pmxt, call Polymarket Profile endpoints directly (public, no auth, accepts wallet address)
- Metaculus via pmxt: auth token needed for programmatic access; community predictions are public on Metaculus website

## Cross-Platform Matching

- realfishsam uses hybrid Jaccard + Levenshtein (not pure Jaccard)
- >5% divergence between Polymarket and Kalshi occurs ~15-20% of the time
- Convergence: bot-captured within minutes; structural gaps persist weeks/months
- No consistent directional bias — divergence is event-specific
---
tags: [prompt-archive, research, fees, pmxt, sports, cross-platform]
date: 2026-04-10
model: GLM-5-Turbo
status: archived
topics: [polymarket-fees, kalshi-fees, sports-strategies, pmxt-sdk, cross-platform-arb]
---

# GLM-5 Turbo — Unified Gap Fill for Open-Source Integration

## Key Corrections to Prior Analysis

### CORRECTION 1: Maker Rebates Are CURVED, Not Flat
**Prior claim (REFUTED):** "Polymarket maker rebates are flat percentage of notional, not curved"
**Actual:** Maker rebates use the SAME p(1-p) formula as taker fees. Your share of a daily rebate pool per market is proportional to your fee_equivalent = C × feeRate × p × (1-p). This is pool-based redistribution, NOT a direct per-fill credit.

### CORRECTION 2: Fee Rates Are Category-Specific
**Prior claim:** "Default fee_rate_bps: 200 (conservative)"
**Actual category-specific base feeRates:**
- Crypto: 0.072 (720 bps equivalent)
- Sports: 0.03 (300 bps)
- Finance / Politics / Mentions / Tech: 0.04 (400 bps)
- Economics / Culture / Weather / Other: 0.05 (500 bps)
- Geopolitics: 0 (fee-free)
Formula: fee = C × feeRate × p × (1-p) — NOT fee = C × p × (fee_rate_bps/10000) × (p(1-p))²

### CORRECTION 3: Dynamic Taker Fees Peak at ~3.15%, Not ~1.56%
On 15-minute crypto markets, dynamic taker fee at p=0.50 can reach ~3.15%.

### CORRECTION 4: Kalshi Uses 0.07 × C × P × (1-P), Not Volume Tiers
No 7%/5%/4% volume tiers found. Standard formula is round_up(0.07 × C × P × (1-P)). Kalshi DOES have maker/taker distinction — makers can avoid fees on some markets.

### CORRECTION 5: Dome Acquisition Unverified
"pmxt is the only remaining independent unified SDK" is too strong. Dome, PolyRouter, and predmarket also exist. No reliable source confirms Dome acquisition by Polymarket.

### CORRECTION 6: Liquidity Rewards 50-80% Claim Unverified
No authoritative source found. Polymarket docs describe both Maker Rebates and Liquidity Rewards (Q-score) but don't quantify income shares.

## Verified Facts

- 500ms taker delay removed February 18, 2026 ✅
- Kalshi internally uses cents (integer), pmxt normalizes ✅
- Polymarket CLOB API has GET /fee-rate endpoint returning { "base_fee": 30 } per token_id ✅
- Maker Rebates and Liquidity Rewards (Q-score) are SEPARATE programs ✅
- Kalshi has GET /series/fee_changes API + per-market fee_waiver fields ✅
- Cross-platform >5% divergence occurs ~15-20% of the time (AhaSignals March 2026) ✅
- Convergence: bot-captured within minutes, structural gaps persist weeks/months ✅
- realfishsam matcher.js uses hybrid Jaccard + Levenshtein, not Jaccard alone ✅

## Sports Strategy Parameters (Verified from v2 branch source code)

### Final Period Momentum
- final_period_minutes: 30
- entry_price: 0.80
- take_profit_price: 0.92
- stop_loss_price: 0.50
- trade_size: 100
- Sport-agnostic (not NBA/NFL specific)

### Late Favorite Limit Hold
- entry_price: 0.90 (favorite threshold)
- trade_size: 25
- activation_start_time_ns: 0 (set by backtest harness)
- Hold-to-resolution design (no explicit exit)

### Sports VWAP Reversion
- vwap_window: 80 (ticks, not time)
- entry_threshold: 0.008 (absolute price below VWAP)
- exit_threshold: 0.002 (close to VWAP)
- take_profit: 0.015
- stop_loss: 0.02
- Tick-based VWAP, not time bars

### No Published Results
No backtest results published for sports strategies. Reference implementations only.

## pmxt Operational Details (Verified)

- Sidecar: port 3847 default, fallback via ~/.pmxt/server.lock
- Multiple Python processes CAN share one sidecar
- No official Docker image — roll your own
- Other wallet positions: bypass pmxt, use Polymarket Profile endpoints directly (public, no auth)
- Metaculus: auth likely needed for pmxt programmatic access; public HTML/JSON available without auth
