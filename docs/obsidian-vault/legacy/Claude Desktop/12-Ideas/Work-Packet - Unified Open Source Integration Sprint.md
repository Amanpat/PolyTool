---
tags: [work-packet, unified, fees, sports, RIS, integration]
date: 2026-04-10
status: complete
priority: high
tracks-affected: [1A, 1B, 1C, Phase-3, RIS]
source-repos:
  - evan-kolberg/prediction-market-backtesting (MIT)
  - 0xharryriddle/hermes-pmxt (MIT)
  - realfishsam/prediction-market-arbitrage-bot (MIT)
assignee: architect → Claude Code / Codex agents
supersedes: "Work-Packet - Fee Model Maker-Taker + Kalshi.md"
---

# Unified Work Packet: Open-Source Integration Sprint

## Overview

This packet consolidates findings from four open-source repo deep-dives and one GLM-5 Turbo research session into actionable implementation tasks. It covers three deliverable groups:

1. **Deliverable A: SimTrader Fee Model Overhaul** — Fix systematically wrong fee calculations affecting all three strategy tracks
2. **Deliverable B: Track 1C Sports Strategy Foundations** — Extract signal logic and parameters from proven reference implementations
3. **Deliverable C: RIS Knowledge Seeding** — Seed validated external findings into the knowledge store

Each deliverable is independently shippable. No cross-dependencies between A, B, and C.

## Research Sources (Architect Must Clone)

| Repo | URL | License | Clone For |
|------|-----|---------|-----------|
| prediction-market-backtesting | `https://github.com/evan-kolberg/prediction-market-backtesting` | MIT (root), LGPL (nautilus_pm/) | Fee models, sports strategies, strategy patterns |
| hermes-pmxt | `https://github.com/0xharryriddle/hermes-pmxt` | MIT | LEARNINGS.md, Jaccard matching logic |
| prediction-market-arbitrage-bot | `https://github.com/realfishsam/prediction-market-arbitrage-bot` | MIT | matcher.js (Jaccard + Levenshtein hybrid) |

**CRITICAL LICENSING RULE:** Do NOT copy ANY files from `nautilus_pm/` directory (LGPL-3.0). All strategy logic must be reimplemented from scratch in our framework. Reference MIT-licensed `strategies/` and `backtests/` directories only. Attribution headers required on any derived code.

## Research Documentation

All findings are stored in Obsidian:

| Note | Path | Contents |
|------|------|----------|
| Backtesting Deep Dive | `08-Research/07-Backtesting-Repo-Deep-Dive.md` | Full analysis + Codex fill engine comparison |
| Copy Trader Deep Dive | `08-Research/08-Copy-Trader-Deep-Dive.md` | pmxt sidecar findings |
| Hermes PMXT Deep Dive | `08-Research/09-Hermes-PMXT-Deep-Dive.md` | Arb scan, Jaccard matching, Metaculus |
| GLM-5 Gap Fill | `11-Prompt-Archive/2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md` | Fee formulas verified, sports params verified |
| pmxt Sidecar Decision | `12-Ideas/Idea - pmxt Sidecar Architecture Evaluation.md` | Parked — Phase 3 |
| Cross-Platform RIS Signal | `12-Ideas/Idea - Cross-Platform Price Divergence as RIS Signal.md` | Parked — Phase 3+ |

---

## DELIVERABLE A: SimTrader Fee Model Overhaul

### Problem Statement

SimTrader's fee module (`packages/polymarket/simtrader/portfolio/fees.py`) has three bugs:

1. **Taker-only fees** — ALL fills charged as taker. Makers pay zero fees and receive rebates on Polymarket. Our A-S market maker (Track 1B) and crypto pair bot (Track 1A) both place maker orders.
2. **Single fee rate** — Uses 200bps default for all markets. Actual rates are category-specific: Crypto=0.072, Sports=0.03, Politics=0.04, Geopolitics=0 (free).
3. **No Kalshi model** — Zero Kalshi fee code in codebase. Needed for Phase 3.

**Impact:** Every SimTrader backtest overestimates fees for maker strategies. Gate 2 results are pessimistic. Track 1A paper testing ignores maker rebate income entirely.

### Corrected Fee Formulas (Verified April 2026)

#### Polymarket Taker Fee
```
fee = C × feeRate × p × (1 − p)

Where:
  C = number of shares filled
  p = fill price (0 to 1)
  feeRate = category-specific rate (see table below)
```

Category fee rates (from official Polymarket docs):

| Category | feeRate | Peak fee at p=0.50 |
|----------|---------|-------------------|
| Crypto | 0.072 | 1.80% |
| Sports | 0.03 | 0.75% |
| Finance / Politics / Mentions / Tech | 0.04 | 1.00% |
| Economics / Culture / Weather / Other | 0.05 | 1.25% |
| Geopolitics | 0 | 0% (fee-free) |

**Dynamic crypto surcharge:** On 15-min crypto markets, effective taker fee can reach ~3.15% at p=0.50. The architect should use the `/fee-rate` API endpoint (returns `base_fee` in bps per token_id) for crypto markets rather than hardcoding.

**IMPORTANT CORRECTION:** Our original work packet assumed the formula was `shares × price × (fee_rate_bps / 10000) × (price × (1-price))²` with an exponent of 2. The verified formula is `C × feeRate × p × (1-p)` with exponent 1. The architect MUST verify which is correct by:
1. Querying Polymarket `/fee-rate` endpoint for a known token
2. Computing expected fee with both formulas
3. Comparing against the fee tables published in Polymarket docs

Our existing `fees.py` uses exponent 2 (`FEE_CURVE_EXPONENT = 2`). If the official formula is exponent 1, this is a separate bug that predates this work packet.

#### Polymarket Maker Rebate

**CORRECTION from original work packet:** Maker rebates are NOT flat — they use the SAME p(1−p) curve as taker fees.

```
Makers pay ZERO fees.

Maker rebate pool per market per day:
  pool = rebate_share × total_taker_fees_collected_in_market

Your daily rebate in market M:
  your_fee_equivalent = C × feeRate × p × (1 − p)  [for each of your maker fills]
  your_rebate = (your_fee_equivalent / total_fee_equivalent_all_makers) × pool
```

Rebate share by category:

| Category | Rebate Share of Taker Fees |
|----------|---------------------------|
| Crypto | 20% |
| Sports / Finance / Politics / Economics / Culture / Weather / Other / Mentions / Tech | 25% |
| Geopolitics | N/A (no fees collected) |

**SimTrader modeling approach:** Exact rebate calculation requires knowing total maker activity in the market (we don't have this in simulation). Two options:

- **Option A (Recommended):** Model maker fills as fee = 0 (zero cost). This is accurate — makers never pay fees. The rebate is bonus income we can't simulate without market-wide data, so we conservatively ignore it.
- **Option B:** Estimate rebate as a configurable `maker_rebate_estimate_bps` applied as a negative fee. Default 0, adjustable per strategy config for sensitivity analysis.

#### Kalshi Fee Model

```
fee = round_up(0.07 × C × P × (1 − P))

Where:
  C = number of contracts
  P = price in dollars (0.01 to 0.99)
  round_up = ceiling to nearest cent
```

- Same p(1−p) shape as Polymarket but with fixed 0.07 multiplier
- Kalshi HAS maker/taker distinction — makers can avoid fees on some markets
- Per-market `fee_waiver` fields available via Kalshi API
- API endpoint: `GET /series/fee_changes` for fee change history
- Kalshi also runs a Liquidity Incentive Program (Sept 2025 → Sept 2026) — separate from fee waivers

### Scope

#### In Scope
1. Replace single `fee_rate_bps` with category-aware `feeRate` lookup
2. Add `role: Literal["maker", "taker"]` parameter — maker role returns `Decimal("0")` fee (Option A)
3. Add optional `maker_rebate_estimate_bps` for sensitivity analysis (Option B, default 0)
4. Add `KalshiFeeModel` class implementing `round_up(0.07 × C × P × (1-P))`
5. Verify and fix `FEE_CURVE_EXPONENT` — is our exponent=2 correct or should it be exponent=1?
6. Add `force_taker: bool = False` to Order model for directional strategies
7. Update SimBroker to pass role based on order resting state
8. Add fee config to strategy config JSON with `platform` and `category` fields
9. Tests: maker/taker for each Polymarket category, Kalshi model, exponent verification
10. Add `/fee-rate` endpoint fetcher for live execution (separate from SimTrader, but same module)

#### Out of Scope (Don't Do List)
- Do NOT modify `fill_engine.py` or `sim_broker.py` fill matching logic
- Do NOT refactor `packages/polymarket/fees.py` (float-based, non-SimTrader)
- Do NOT modify any execution-critical files (`execution/`, `kill_switch.py`, `risk_manager.py`)
- Do NOT touch `crypto_pairs/` fee handling
- Do NOT implement the full maker rebate pool simulation (requires market-wide data we don't have)
- Do NOT implement Kalshi's Liquidity Incentive Program (separate from fees)

### Files to Modify

| File | Change | Review Level |
|------|--------|-------------|
| `packages/polymarket/simtrader/portfolio/fees.py` | Category-aware feeRate, maker role, KalshiFeeModel, exponent fix | **Mandatory adversarial review** (price-reading logic) |
| `packages/polymarket/simtrader/broker/sim_broker.py` | Pass role to fee computation | Recommended |
| `packages/polymarket/simtrader/broker/rules.py` | Add `force_taker`, `market_category` to Order | Skip |
| `packages/polymarket/simtrader/config_loader.py` | Load fee config (platform, category) | Skip |
| `tests/test_simtrader_portfolio.py` | New test cases | Mandatory |

### Reference Materials

1. Clone `evan-kolberg/prediction-market-backtesting`, read:
   - `backtests/kalshi_trade_tick/_kalshi_single_market_trade_runner.py` lines 19, 93 — KalshiProportionalFeeModel
   - `backtests/polymarket_quote_tick/_polymarket_single_market_pmxt_runner.py` lines 21, 142 — PolymarketFeeModel
2. Polymarket fee docs (fetch live): query `/fee-rate` endpoint for a known token to verify formula
3. Our current `fees.py` (full source in `07-Backtesting-Repo-Deep-Dive.md` updated findings section)

### Attribution
```python
# Kalshi fee model approach derived from evan-kolberg/prediction-market-backtesting
# (MIT License, https://github.com/evan-kolberg/prediction-market-backtesting)
# Reimplemented in Decimal-safe arithmetic for SimTrader compatibility.
```

### Acceptance Criteria

1. `compute_fill_fee(size=100, price=0.50, category="sports", role="taker")` uses feeRate=0.03 → fee = 100 × 0.03 × 0.50 × 0.50 = 0.75 USDC
2. `compute_fill_fee(size=100, price=0.50, category="crypto", role="taker")` uses feeRate=0.072 → fee = 100 × 0.072 × 0.50 × 0.50 = 1.80 USDC
3. `compute_fill_fee(..., role="maker")` returns `Decimal("0")` (makers pay no fees)
4. `KalshiFeeModel.compute_fee(contracts=10, price=0.60)` returns `round_up(0.07 × 10 × 0.60 × 0.40)` = round_up(0.168) = 0.17
5. `compute_fill_fee(..., category="geopolitics", role="taker")` returns `Decimal("0")` (fee-free category)
6. FEE_CURVE_EXPONENT verified against live `/fee-rate` endpoint data
7. All existing `test_simtrader_portfolio.py` tests pass unchanged
8. ≥12 new test cases covering all categories, both roles, Kalshi, edge cases
9. Dev log at `docs/dev_logs/YYYY-MM-DD_fee-model-overhaul.md`

### Downstream Impact

- **Gate 2 re-run:** After landing, re-run Gate 2 sweep with `role="maker"` and correct category feeRates. Crypto bucket (7/10 positive) should show improved PnL. Politics/sports zero-fill problem is unrelated.
- **Track 1A paper soak:** Use `category="crypto", role="maker"` → zero fee per fill (plus potential rebate income we conservatively ignore).
- **Phase 3 Kalshi:** KalshiFeeModel is prerequisite for any Kalshi backtesting.
- **Phase 4 Autoresearch:** Fee accuracy directly impacts experiment ledger. Land this BEFORE autoresearch starts.


---

## DELIVERABLE B: Track 1C Sports Strategy Signal Foundations

### Problem Statement

Track 1C (Sports Directional Model) has zero implementation. The roadmap calls for logistic regression on `nba_api` data, but we have no concrete signal features defined. Three MIT-licensed sports strategies from `evan-kolberg/prediction-market-backtesting` provide verified parameter baselines and signal logic that accelerate Track 1C from "design from scratch" to "reimplement with known starting points."

**No code is copied.** We reimplement the signal logic in our own framework using our own code patterns. The value is the PARAMETERS and SIGNAL DESIGN, not the implementation.

### Strategy Extraction Targets

#### Strategy B1: Final Period Momentum

**Concept:** Buy late-game momentum above a hard price threshold, exit on target or stop.

**Verified Parameters (from v2 source files):**
- `final_period_minutes = 30` — activation window before market close
- `entry_price = 0.80` — only enter if price ≥ 0.80 (strong momentum)
- `take_profit_price = 0.92` — exit at +12 points
- `stop_loss_price = 0.50` — exit at -30 points
- `trade_size = 100` shares

**Signal Logic:**
- Compute `start_ns = market_close_time - (30 minutes)`
- If current timestamp is between start_ns and close_time → strategy is active
- If price ≥ 0.80 → enter long
- Exit on take_profit (0.92) or stop_loss (0.50)
- Sport-agnostic (works for NBA, NFL, any timed event)

**PolyTool Implementation Notes:**
- Maps to a SimTrader strategy (new file in `simtrader/strategies/`)
- Requires market close time from Gamma API (`end_date_iso` field)
- For Track 1C, this is a STANDALONE directional strategy — does not require the logistic regression model
- Can be paper-tested immediately on any live sports market

#### Strategy B2: Late Favorite Limit Hold

**Concept:** Place limit buy on strong favorites late in the event, hold to resolution.

**Verified Parameters:**
- `entry_price = 0.90` — favorite threshold (only buy if ask ≥ 0.90)
- `trade_size = 25` shares
- `activation_start_time_ns` — set per market by backtest harness
- Hold-to-resolution (no explicit exit — settles at $1 or $0)

**Signal Logic:**
- In activation window, monitor price
- When signal_price reaches 0.90, submit limit buy at that price
- Hold position until market resolves
- Profit if favorite wins ($1.00 - $0.90 = $0.10/share). Loss if upset ($0.00 - $0.90 = -$0.90/share)
- Edge comes from favorite-longshot bias: favorites at 90¢ resolve YES more than 90% of the time empirically

**PolyTool Implementation Notes:**
- Directly related to Jon-Becker finding #3 (favorite-longshot bias)
- Risk/reward is asymmetric: small wins, large losses. Requires Kelly sizing.
- Should be combined with our probability model (Track 1C logistic regression) — only enter when MODEL says probability > market price

#### Strategy B3: VWAP Reversion

**Concept:** Buy when price drops below tick-VWAP, exit when it reverts to mean.

**Verified Parameters:**
- `vwap_window = 80` ticks (rolling deque)
- `entry_threshold = 0.008` (buy when price is 0.8¢ below VWAP)
- `exit_threshold = 0.002` (exit when price is within 0.2¢ of VWAP)
- `take_profit = 0.015` (1.5¢ above entry)
- `stop_loss = 0.02` (2¢ below entry)
- Tick-based VWAP: weighted average of (price × size) over last 80 trade ticks

**Signal Logic:**
- Maintain rolling VWAP over deque of (price, size) with maxlen=80
- VWAP = sum(price_i × size_i) / sum(size_i) over window
- Entry: current_price < VWAP - 0.008
- Exit: current_price > VWAP - 0.002 OR take_profit OR stop_loss

**PolyTool Implementation Notes:**
- Requires tick-level data (Gold tapes or live WS feed)
- Silver tapes may be too coarse (~2 min) for an 80-tick VWAP window
- Best suited for high-volume sports markets with frequent trades
- Can be used as a microstructure signal WITHIN our A-S market maker (not just standalone)

### Scope

#### In Scope
1. Create three new strategy files in `simtrader/strategies/`:
   - `sports_momentum.py` — Final Period Momentum
   - `sports_favorite.py` — Late Favorite Limit Hold
   - `sports_vwap.py` — VWAP Reversion
2. Each strategy inherits from our existing `Strategy` base class (in `strategy/facade.py`)
3. Register in `STRATEGY_REGISTRY`
4. Each strategy uses Pydantic config models (NOT raw JSON dicts) — establishes the pattern for Phase 4 autoresearch
5. Basic tests: strategy instantiation, signal logic with synthetic tick data
6. Add to CLI: `python -m polytool simtrader replay --strategy sports_momentum --tape <path>`

#### Out of Scope
- Do NOT build the logistic regression probability model (that's the rest of Track 1C)
- Do NOT build Polymarket sports market discovery (already partially built in market_discovery.py)
- Do NOT run backtests or publish results — these are reference implementations for the architect to validate
- Do NOT modify SimTrader core (broker, fill_engine, orderbook)
- Do NOT build Grafana dashboards for sports (separate task)

### Reference Materials

Clone `evan-kolberg/prediction-market-backtesting`, read on the **v2 branch**:
- `strategies/final_period_momentum.py` — signal logic and config
- `strategies/late_favorite_limit_hold.py` — entry mechanism
- `strategies/vwap_reversion.py` — VWAP calculation with deque

**DO NOT copy code. Reimplement from scratch.** The value is parameters and signal design. Use our Strategy base class, our Order model, our SimBroker integration.

### Attribution
```python
# Signal logic and default parameters derived from sports strategy research
# in evan-kolberg/prediction-market-backtesting (MIT License).
# Reimplemented from scratch for PolyTool SimTrader.
```

### Acceptance Criteria

1. All three strategies instantiate without error and register in STRATEGY_REGISTRY
2. Each strategy has a Pydantic config with typed, bounded parameters
3. `sports_momentum` activates only within `final_period_minutes` of market close
4. `sports_vwap` maintains a rolling VWAP over configurable tick window
5. Each strategy produces at least one fill when replayed against a synthetic 100-event tape
6. ≥6 test cases (2 per strategy: basic signal trigger, edge case)
7. Dev log at `docs/dev_logs/YYYY-MM-DD_sports-strategies.md`

---

## DELIVERABLE C: RIS Knowledge Seeding (Phase R0 Supplement)

### Problem Statement

RIS Phase R0 calls for manual seeding of ~17 foundational documents. This deep-dive produced additional verified findings that should be seeded into `external_knowledge` partition alongside the R0 documents.

### Documents to Seed

| Document | Content | Confidence Tier | Source |
|----------|---------|----------------|--------|
| Polymarket Fee Structure (April 2026) | Category-specific feeRates, taker formula, maker rebate mechanics, liquidity rewards vs rebates | PRACTITIONER | GLM-5 research + Polymarket docs |
| Kalshi Fee Structure (April 2026) | 0.07 × C × P × (1-P) formula, maker/taker distinction, Liquidity Incentive Program | PRACTITIONER | GLM-5 research + Kalshi docs |
| pmxt SDK Operational Gotchas | 8 empirical findings from LEARNINGS.md — fetch_market broken, slug lookups fail, sidecar behavior | PRACTITIONER | 0xharryriddle/hermes-pmxt (pmxt core contributor) |
| Sports Strategy Catalogue | 3 strategy descriptions with verified parameters + signal logic | PRACTITIONER | evan-kolberg/prediction-market-backtesting |
| Cross-Platform Price Divergence Empirics | >5% divergence occurs ~15-20% of time, convergence speed varies, no directional bias | PRACTITIONER | AhaSignals March 2026 tracker |
| SimTrader Known Limitations (verified) | No queue position, no L3, no market impact, fills don't deplete book — confirmed by both our Codex audit and external repo analysis | PRACTITIONER | Internal + evan-kolberg comparison |
| Cross-Platform Market Matching | Jaccard + Levenshtein hybrid at 40% threshold, known failure modes, no published accuracy metrics | COMMUNITY | hermes-pmxt + realfishsam/arbitrage-bot |

### Scope

#### In Scope
1. Create 7 markdown documents formatted for RIS ingestion
2. Each document includes: title, content, metadata fields (`freshness_tier: CURRENT`, `confidence_tier`, `validation_status: UNTESTED`)
3. Seed into ChromaDB `polytool_brain` collection with `partition: external_knowledge`
4. Verify retrieval: query each document by keyword and confirm it appears in results

#### Out of Scope
- Do NOT seed into `research` partition (that requires validation_gate_pass)
- Do NOT modify RIS evaluation gate logic
- Do NOT seed the full repo READMEs — only the distilled findings above

### Acceptance Criteria

1. 7 documents ingested into `external_knowledge` partition
2. Each document has `freshness_tier: CURRENT`, appropriate `confidence_tier`
3. `python -m polytool rag query "Polymarket maker rebate formula"` returns the fee structure document
4. `python -m polytool rag query "sports VWAP prediction market"` returns the strategy catalogue document
5. No existing documents in `external_knowledge` are modified or overwritten

---

## Execution Order

1. **Deliverable A (Fee Model)** — FIRST. Affects all backtest accuracy. Land before any Gate 2 re-runs or autoresearch.
2. **Deliverable B (Sports Strategies)** — SECOND. Independent of A. Enables Track 1C paper prediction tracking.
3. **Deliverable C (RIS Seeding)** — THIRD. Independent of A and B. Can be done in parallel with B if agent capacity allows.

Each deliverable is a single Claude Code work packet. Do NOT combine into one session — scope discipline per Principle #4.

---

## Open Items for Architect Review

Before generating agent prompts, the architect should resolve:

1. **FEE_CURVE_EXPONENT:** Our `fees.py` uses exponent=2. GLM-5 research says the official formula is exponent=1. One of these is wrong. The architect must query `/fee-rate` and compute a test case against the published fee tables to determine the correct exponent. This is a prerequisite for Deliverable A.

2. **Maker rebate modeling (Option A vs B):** Option A (fee=0 for makers, ignore rebate) is simpler and conservatively correct. Option B (estimate rebate as negative fee) is more accurate but requires a `maker_rebate_estimate_bps` config that we can't validate without market-wide data. Recommend Option A for now, Option B as Phase 4 autoresearch parameter.

3. **Pydantic Config adoption scope:** Deliverable B introduces Pydantic configs for sports strategies. Should ALL new strategies going forward use Pydantic configs, or just these three? If yes to all, update CLAUDE.md convention.

4. **pmxt sidecar decision (parked):** Deliverable C mentions pmxt gotchas but does NOT depend on pmxt adoption. The sidecar architecture evaluation is parked until Phase 3. See `12-Ideas/Idea - pmxt Sidecar Architecture Evaluation.md`.

---

## Cross-References

- [[07-Backtesting-Repo-Deep-Dive]] — Backtesting repo full analysis
- [[08-Copy-Trader-Deep-Dive]] — Copy Trader analysis (low value, skip)
- [[09-Hermes-PMXT-Deep-Dive]] — Hermes PMXT analysis
- [[2026-04-10 GLM5 - Unified Gap Fill Open Source Integration]] — Research results
- [[SimTrader]] — SimTrader module docs
- [[Track-1A-Crypto-Pair-Bot]] — Maker rebate impact
- [[Track-1B-Market-Maker]] — Gate 2 pessimism from taker-only fees
- [[Track-1C-Sports-Directional]] — Sports strategy foundations
- [[Risk-Framework]] — Gate definitions reference net PnL after fees
- [[Idea - pmxt Sidecar Architecture Evaluation]] — Parked decision
- [[Idea - Cross-Platform Price Divergence as RIS Signal]] — Phase 3+ idea
