---
tags: [work-packet, unified, integration, fees, sports, RIS]
date: 2026-04-10
status: draft
priority: high
tracks-affected: [1A, 1B, 1C, Phase-3, RIS]
source-repos:
  - evan-kolberg/prediction-market-backtesting (MIT)
  - 0xharryriddle/hermes-pmxt (MIT)
assignee: architect → Claude Code / Codex agents
supersedes: "Work-Packet - Fee Model Maker-Taker + Kalshi.md (OBSOLETE — fee design was wrong)"
---

# Unified Work Packet: Open-Source Repo Integration

## Overview

Four open-source repos from the pmxt ecosystem were deep-dived on 2026-04-10. This packet consolidates all actionable integration work into sub-tasks for the architect. Each sub-task is independent — they can be assigned to parallel agents.

**Research notes (Zone B, read these first):**
- [[07-Backtesting-Repo-Deep-Dive]] — evan-kolberg/prediction-market-backtesting
- [[08-Copy-Trader-Deep-Dive]] — realfishsam/Polymarket-Copy-Trader (LOW value, skip)
- [[09-Hermes-PMXT-Deep-Dive]] — 0xharryriddle/hermes-pmxt
- [[2026-04-10 GLM5 - Unified Gap Fill Open Source Integration]] — Verified facts + corrections

**Repos to clone for reference:**
```bash
git clone https://github.com/evan-kolberg/prediction-market-backtesting.git
# Commit a550fd61 (indexed April 1 2026). 155 stars, MIT license (except nautilus_pm/ which is LGPL-3.0).
# DO NOT copy anything from nautilus_pm/ directory.

git clone https://github.com/0xharryriddle/hermes-pmxt.git
# 2 commits. MIT license. Author is pmxt core contributor.
```

---

## Sub-Task A: SimTrader Fee Model Rewrite (HIGH PRIORITY)

### Why the Previous Fee Packet Is Obsolete

The draft work packet `Work-Packet - Fee Model Maker-Taker + Kalshi.md` was based on incorrect assumptions. GLM-5 research on 2026-04-10 revealed:

| Assumption | Reality |
|-----------|---------|
| Our formula `C × p × (bps/10000) × (p(1-p))²` matches Polymarket | **WRONG.** Polymarket uses `fee = C × feeRate × p × (1-p)`. Our exponent is 2, theirs is 1. Different curve entirely. |
| Default fee_rate_bps is 200 (universal) | **WRONG.** feeRate is category-specific: Crypto=0.072, Sports=0.03, Politics=0.04, etc. |
| Maker rebate is a flat per-fill negative fee | **WRONG.** Makers pay ZERO fees. Rebates are a separate daily pool redistribution proportional to your share of fee_equivalent generated across each market. |
| Maker rebate is linear (not curved) | **WRONG.** Rebate allocation uses the same p(1-p) curve as taker fees. |
| Kalshi has 7%/5%/4% volume tiers | **WRONG.** Standard formula is `round_up(0.07 × C × P × (1-P))`. No volume tiers found. |

### Corrected Fee Architecture for SimTrader

**Polymarket Taker Fee (per-fill, applied immediately):**
```
fee = C × feeRate × p × (1 - p)

where:
  C = fill_size (shares)
  p = fill_price (0-1)
  feeRate = category-specific:
    crypto:     0.072
    sports:     0.03
    politics:   0.04
    finance:    0.04
    economics:  0.05
    culture:    0.05
    weather:    0.05
    geopolitics: 0.0 (fee-free)
    mentions:   0.04
    tech:       0.04
    other:      0.05
```

Peak taker fee at p=0.50:
- Crypto: C × 0.072 × 0.25 = 1.8% of notional
- Sports: C × 0.03 × 0.25 = 0.75% of notional
- Politics: C × 0.04 × 0.25 = 1.0% of notional

**Polymarket Maker Fee: ZERO. Makers are never charged fees.**

**Polymarket Maker Rebates (daily pool, modeled as post-simulation bonus):**
- Rebate pool per market per day = taker_fees_collected × rebate_share
  - Crypto: 20% of taker fees redistributed
  - Sports/Politics/Finance/etc: 25% of taker fees redistributed
  - Geopolitics: no pool (fee-free)
- Your daily rebate = (your_fee_equivalent / total_fee_equivalent) × pool
- fee_equivalent per maker fill = C × feeRate × p × (1-p) (same formula, used for allocation only)

**For SimTrader implementation:** Model rebates as an OPTIONAL post-simulation estimate, NOT as a per-fill fee adjustment. The rebate depends on other participants' activity (total_fee_equivalent), which SimTrader cannot know during replay. A reasonable approximation: assume you capture X% of the rebate pool (configurable, default 10%) and add it as a lump daily credit.

**Polymarket Q-Score Liquidity Rewards: SEPARATE from rebates.** Rewards for spread quality (two-sided quoting, tight spreads). Model as a separate optional income estimate, not part of fill-level fee calc.

**Kalshi Taker Fee (per-fill):**
```
fee = round_up(0.07 × C × P × (1 - P))

where:
  C = contracts
  P = price in dollars (0.01 - 0.99)
  round_up = ceiling to nearest cent
```

**Kalshi Maker Fee:** Some markets have maker fees, some don't. Check per-market `fee_waiver` field via API. Default assumption for SimTrader: maker fee = 0.

### CRITICAL: Verify Our Existing Formula Is Wrong

**Before any implementation, the architect MUST verify:**

Our current `fees.py` uses:
```python
curve_factor = (fill_price * (_ONE - fill_price)) ** _CURVE_EXPONENT  # exponent = 2
fee = fill_size * fill_price * rate * curve_factor
```

This expands to: `C × p × rate × (p(1-p))²` = `C × rate × p³ × (1-p)²`

Polymarket docs say: `fee = C × feeRate × p × (1-p)`

These are DIFFERENT CURVES. At p=0.50:
- Ours: C × rate × 0.125 × 0.25 = C × rate × 0.03125
- Theirs: C × rate × 0.50 × 0.50 = C × rate × 0.25

**If confirmed, our current formula undercharges by ~8x at midprice.** This means Gate 2 results may actually be MORE pessimistic on the fee side than I initially said in the research notes — but ONLY if the fee rate constant we used compensates. With our 200bps default: 0.02 × 0.03125 = 0.000625. With their crypto 0.072: 0.072 × 0.25 = 0.018. Our formula produces much lower fees per fill.

**Action for architect:** 
1. Fetch `GET /fee-rate?token_id=<any_active_token>` from the CLOB API to get the actual base_fee value
2. Compare against the category table above
3. Compute a few sample fees with both formulas and compare to actual fees charged on real trades (check ClickHouse `live_fills` if any exist, or check Polygonscan for actual fee deductions)

### Scope

**In scope:**
1. Replace `compute_fill_fee()` formula with corrected `C × feeRate × p × (1-p)`
2. Add `market_category` parameter to fee computation (maps to feeRate table)
3. Add maker/taker role: maker → fee = 0, taker → apply formula
4. Add `force_taker` flag to Order model (default False, for directional strategies)
5. Add `KalshiFeeModel` class: `round_up(0.07 × C × P × (1-P))`
6. Add optional `rebate_estimator()` for post-simulation rebate approximation
7. Config surface: `fees.platform`, `fees.market_category`, `fees.force_taker`
8. Backward compatibility: existing tests must pass (may need expected values updated if formula changes)
9. Tests: maker zero-fee, taker per-category, Kalshi model, edge cases

**Out of scope (Don't Do List):**
- Do NOT modify `fill_engine.py` or fill matching logic
- Do NOT add dynamic fee-rate fetching from CLOB API (live execution concern, not SimTrader)
- Do NOT touch `packages/polymarket/fees.py` (float-based, used elsewhere)
- Do NOT touch `packages/polymarket/crypto_pairs/` fee code
- Do NOT modify execution-critical files (`execution/`, `kill_switch.py`, `risk_manager.py`)
- Do NOT implement Q-score liquidity reward calculation (too complex, depends on other participants)

### Files to Modify

| File | Change | Review Level |
|------|--------|-------------|
| `simtrader/portfolio/fees.py` | Replace formula, add category feeRate table, add KalshiFeeModel | Recommended |
| `simtrader/broker/sim_broker.py` | Pass role (maker/taker) to fee computation | Recommended |
| `simtrader/broker/rules.py` | Add `force_taker` field to Order model | Skip |
| `simtrader/config_loader.py` | Load `fees.market_category` and `fees.platform` from config | Skip |
| `tests/test_simtrader_portfolio.py` | Update expected fee values, add new test cases | Mandatory |

### Attribution

```python
# Fee model architecture informed by evan-kolberg/prediction-market-backtesting
# (MIT License, https://github.com/evan-kolberg/prediction-market-backtesting)
# Polymarket fee formula and category rates verified against official Polymarket
# docs (April 2026). Kalshi formula from CFTC filing.
```

### Acceptance Criteria

1. Taker fee for crypto at p=0.50, 100 shares = `100 × 0.072 × 0.50 × 0.50 = 1.80 USDC`
2. Taker fee for sports at p=0.50, 100 shares = `100 × 0.03 × 0.50 × 0.50 = 0.75 USDC`
3. Taker fee for geopolitics = `0.00 USDC` (fee-free)
4. Maker fee for ANY category = `0.00 USDC`
5. Kalshi fee for 10 contracts at P=0.50 = `round_up(0.07 × 10 × 0.50 × 0.50) = round_up(0.175) = 0.18 USD`
6. All existing portfolio tests pass (with updated expected values if formula changes)
7. At least 12 new test cases
8. Dev log at `docs/dev_logs/YYYY-MM-DD_fee-model-rewrite.md`

---

## Sub-Task B: Track 1C Sports Strategy Signal Extraction (MEDIUM PRIORITY)

### What We're Extracting

Three sports-specific prediction market strategies from evan-kolberg/prediction-market-backtesting. We are **reimplementing the signal logic from scratch** in our own framework — not copying code. This is legally clear: copyright protects expression, not algorithms. LGPL does not apply (strategies are MIT-licensed and we're reimplementing anyway).

### Strategy 1: Final Period Momentum

**Source:** `strategies/final_period_momentum.py` (v2 branch)

**Signal logic:**
- Activate only within `final_period_minutes` (default: 30) before market close
- Entry: buy when price reaches `entry_price` threshold (default: 0.80) during final period
- Exit: take_profit at 0.92, stop_loss at 0.50
- Trade size: 100 shares default

**Thesis:** In sports markets, the final period (last 30 minutes) sees increased volatility and momentum as the outcome becomes clearer. Buying above 0.80 bets on the favorite continuing to resolution.

**PolyTool implementation target:** Feature in Track 1C logistic regression model — `minutes_remaining` and `current_probability` as features, with the 30-min / 0.80 thresholds as starting points for parameter search.

### Strategy 2: Late Favorite Limit Hold

**Source:** `strategies/late_favorite_limit_hold.py` (v2 branch)

**Signal logic:**
- Entry: limit buy at 0.90 (favorite threshold) during activation window
- Hold to resolution (no explicit exit)
- Trade size: 25 shares default

**Thesis:** When a market reaches 0.90 late in the event, the favorite almost always wins. Buying at 0.90 and holding to resolution at 1.00 captures the remaining 10% with high probability.

**PolyTool implementation target:** This is a calibration thesis — test whether Polymarket sports markets at 0.90 resolve YES more than 90% of the time. If so, there's a calibration edge. Run this analysis on Jon-Becker data via DuckDB before building any strategy.

### Strategy 3: VWAP Reversion

**Source:** `strategies/vwap_reversion.py` (v2 branch)

**Signal logic:**
- VWAP: rolling window of 80 ticks (trade-level, not time-based)
- Entry: buy when price is 0.008 (0.8 cents) below VWAP
- Exit: when price returns within 0.002 of VWAP, or take_profit +0.015, or stop_loss -0.02
- Trade size: 1 share default

**Thesis:** Short-term mean reversion around VWAP in noisy intraday prediction market trading. Sports markets have wide spreads (Jon-Becker: 2.23pp maker-taker gap), so noise is tradeable.

**PolyTool implementation target:** VWAP indicator for SimTrader. Could be useful for the A-S market maker as an additional signal for reservation price adjustment — if the current price is far below VWAP, widen the ask (don't sell cheap).

### Important Caveat

**No published backtest results exist for these strategies.** They are reference implementations, not proven profitable strategies. Treat parameters as starting points for our own validation, not as gospel.

### Scope

**In scope:**
1. Document the three signal patterns in a Track 1C design spec
2. Implement VWAP indicator as a SimTrader utility (reusable across strategies)
3. Run Jon-Becker calibration analysis: at what probability threshold do sports markets resolve YES >X% of the time? (validates Late Favorite thesis)

**Out of scope:**
- Do NOT build full strategy implementations yet (Track 1C is after 1A/1B)
- Do NOT copy any code from the reference repo
- Do NOT build a sports data ingestion pipeline (that's a separate Phase 1C task)

### Files to Create

| File | Purpose | Review Level |
|------|---------|-------------|
| `docs/specs/SPEC-XXXX-sports-directional-signals.md` | Signal documentation from reference repo | Skip |
| `packages/polymarket/simtrader/indicators/vwap.py` | Tick-based VWAP indicator | Recommended |
| `tests/test_vwap_indicator.py` | Unit tests for VWAP | Mandatory |

### Acceptance Criteria

1. VWAP indicator produces correct values for a known tick sequence
2. Calibration analysis runs on Jon-Becker data and outputs: probability_threshold → actual_resolution_rate table for sports markets
3. All three strategy signal patterns documented with parameters and thesis

---

## Sub-Task C: RIS Knowledge Seeding (LOW PRIORITY)

### Documents to Seed into `external_knowledge` Partition

These documents should be added to RIS during Phase R0 manual seeding. They don't require code changes — just ChromaDB ingestion via the existing `ris ingest` CLI.

| Document | Source | Confidence Tier | Freshness Tier | Key Content |
|----------|--------|----------------|---------------|-------------|
| hermes-pmxt LEARNINGS.md | 0xharryriddle/hermes-pmxt | PRACTITIONER | CURRENT | pmxt SDK gotchas: fetch_market() broken, slug lookup broken, outcome_ids are 70+ chars, Jaccard arb matching at 40% threshold, "true arbitrage is rare" |
| Sports strategy catalogue | evan-kolberg/prediction-market-backtesting | PRACTITIONER | CURRENT | 3 sports strategies with verified parameters (Final Period Momentum, Late Favorite, VWAP Reversion) |
| Execution modeling limitations | evan-kolberg/prediction-market-backtesting DeepWiki | COMMUNITY | CURRENT | No queue position, no L3, no latency modeling, no market impact — validates our own known gaps |
| Cross-platform divergence frequency | AhaSignals March 2026 tracker | PRACTITIONER | CURRENT | >5% divergence occurs 15-20% of the time across Polymarket-Kalshi matched markets, converges within minutes for bot-captured gaps |
| Polymarket fee structure (verified April 2026) | GLM-5 research + Polymarket docs | PEER_REVIEWED | CURRENT | Category-specific feeRates, p(1-p) formula, maker zero-fee policy, rebate pool mechanics, Q-score separation |

### Scope

- Add these to the RIS Phase R0 seeding list (currently ~17 foundational documents)
- No code changes needed — use existing `ris ingest` pipeline
- Each document gets standard metadata: `freshness_tier`, `confidence_tier`, `validation_status: UNTESTED`

---

## Sub-Task D: Architectural Decisions to Record (NO CODE)

These are decisions that emerged from the research. They should be recorded in `09-Decisions/` but don't require implementation work now.

### Decision 1: pmxt SDK — Defer Until Phase 3

**Decision:** Continue using py-clob-client directly for Phase 1A/1B. Defer pmxt adoption evaluation to Phase 3 (Kalshi integration).

**Rationale:**
- pmxt requires Node.js sidecar on port 3847 — operational overhead for our Python/Docker stack
- We don't need multi-exchange today
- py-clob-client works for Polymarket direct access
- For other-wallet analytics, Polymarket Profile endpoints are public (no pmxt needed)
- pmxt is NOT the "only remaining" unified SDK — Dome, PolyRouter, predmarket also exist

**Revisit trigger:** Phase 3 Kalshi integration becomes active.

### Decision 2: Cross-Platform Market Matching — Hybrid Jaccard + Levenshtein

**Decision:** When we build Phase 3 cross-platform matching, use hybrid Jaccard word similarity + Levenshtein distance (as realfishsam's matcher.js does), not Jaccard alone.

**Rationale:**
- Pure Jaccard (40% threshold) mismatches on shared keywords with different events
- realfishsam's production arb bot uses hybrid for robustness
- AhaSignals data shows >5% divergence is common enough (15-20% of matched markets) to be actionable as a signal source for RIS

### Decision 3: Cross-Platform Price Divergence as RIS Signal — Park

**Decision:** Park the idea of using multi-platform price divergence as RIS document evaluation enrichment until Phase 3+.

**Rationale:** Requires pmxt or equivalent multi-platform API. Good idea but depends on Decision 1 (pmxt adoption). Also requires Metaculus access evaluation.

---

## Dependency Map

```
Sub-Task A (Fee Model) ─── independent, do first
                           ↓ enables
                           Gate 2 re-evaluation (crypto tapes)
                           Track 1A paper testing accuracy
                           Phase 4 autoresearch PnL accuracy

Sub-Task B (Sports Signals) ─── independent, can parallel with A
                                ↓ feeds into
                                Track 1C design spec
                                Phase 1C implementation (later)

Sub-Task C (RIS Seeding) ─── independent, can parallel with A/B
                             ↓ feeds into
                             RIS Phase R0 document list

Sub-Task D (Decisions) ─── no code, record only
```

---

## Licensing Summary

| What We're Doing | Source | License | Risk |
|-----------------|--------|---------|------|
| Reimplementing fee formula from Polymarket docs | Polymarket official docs | N/A (public documentation) | None |
| Reimplementing Kalshi fee formula from CFTC filing | Public CFTC filing | N/A (public record) | None |
| Referencing evan-kolberg fee model architecture | evan-kolberg repo | MIT | None — reimplementing, not copying |
| Reimplementing sports strategy signal logic | evan-kolberg repo (strategies/) | MIT | None — reimplementing from described parameters |
| Seeding LEARNINGS.md content into RIS | hermes-pmxt repo | MIT | None — factual information |
| NOT copying anything from nautilus_pm/ | LGPL-3.0 | N/A | Avoided entirely |

---

## Post-Implementation Impacts

After Sub-Task A lands:
1. **Re-run Gate 2 sweep** with correct fee formula and `role="maker"` → crypto bucket PnL will change (direction depends on whether current formula over- or under-charges vs correct formula)
2. **Track 1A paper soak** with maker fee = 0 (no longer penalized with phantom taker fees)
3. **All future autoresearch experiments** use correct fee model

After Sub-Task B lands:
4. **Track 1C has concrete starting point** — signal patterns + parameters documented, VWAP indicator built, calibration analysis provides empirical foundation

---

## Cross-References

- [[07-Backtesting-Repo-Deep-Dive]] — Full backtesting repo analysis
- [[08-Copy-Trader-Deep-Dive]] — Copy Trader analysis (skip, low value)
- [[09-Hermes-PMXT-Deep-Dive]] — Hermes PMXT analysis
- [[2026-04-10 GLM5 - Unified Gap Fill Open Source Integration]] — Verified research results
- [[SimTrader]] — SimTrader module docs
- [[Track-1A-Crypto-Pair-Bot]] — Maker fees affect pair bot economics
- [[Track-1B-Market-Maker]] — Gate 2 results affected by fee formula
- [[Track-1C-Sports-Directional]] — Sports strategy signals
- [[Risk-Framework]] — Gate definitions reference net PnL after fees
- [[Idea - pmxt Sidecar Architecture Evaluation]] — Deferred decision
- [[Idea - Cross-Platform Price Divergence as RIS Signal]] — Parked idea
