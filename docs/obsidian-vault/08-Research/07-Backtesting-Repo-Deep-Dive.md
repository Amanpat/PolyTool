---
tags: [research, open-source, backtesting, integration]
date: 2026-04-10
status: in-progress
topics: [SimTrader, NautilusTrader, pmxt, licensing, strategies]
---

# Deep Dive: evan-kolberg/prediction-market-backtesting

## Critical Discovery: Repo Has Evolved Dramatically

The pmxt showcase page (https://www.pmxt.dev/built-with-pmxt) shows a snapshot of this repo with 3 stars, 15 commits, and a lightweight custom engine (`src/backtesting/engine.py`, `broker.py`, `portfolio.py`). **This is outdated.**

The actual current state (April 2026, commit `a550fd61`):
- **155 stars**, 52+ PRs, active Codex-driven development
- **Rewritten to use NautilusTrader** as the core engine via a `nautilus_pm/` git subtree
- NautilusTrader is a Python/Rust hybrid architecture — Rust handles the event loop, data structures, and core calcs; Python provides the high-level API and strategy definitions
- The original lightweight engine (`src/backtesting/`) still exists as legacy

## Architecture: Two Engines

### Engine 1: Legacy (`src/backtesting/`)
- Custom lightweight engine: `engine.py`, `broker.py`, `portfolio.py`, `strategy.py`, `models.py`
- Simple event loop, trade-level fills only
- Feeds: `feeds/kalshi.py`, `feeds/polymarket.py` (read Jon-Becker Parquet via DuckDB)
- Auto-discovery: drop `.py` in `strategies/` → appears in menu
- **License: MIT** ✅

### Engine 2: NautilusTrader (`nautilus_pm/`)
- Production-grade Python/Rust hybrid
- L2 `BookType.L2_MBP` replay with `liquidity_consumption=True` (orders walk the book)
- Full OMS, portfolio tracking, indicator library
- **License: LGPL-3.0** ⚠️ — any modifications to files within this directory must comply with LGPL

## PMXT Data Layer (CRITICAL for us)

Four-tier fetch hierarchy for L2 data:

| Tier | Source | Latency |
|------|--------|---------|
| 1 | Local Parquet cache (`~/.cache/nautilus_trader/pmxt/`) | <1ms |
| 2 | Relay Prebuilt (filtered, per-token files via `pmxt_relay/`) | ~2s |
| 3 | Raw PMXT Archive (`r2.pmxt.dev`) | 30-50s |
| 4 | None (data doesn't exist) | N/A |

Key component: **`PolymarketPMXTDataLoader`** — concurrent fetching with 16 workers, handles relay↔raw archive fallback. Loads both `OrderBook` snapshots and `QuoteTick` updates.

**Comparison with our Silver reconstructor:**
- Our Silver reconstructor (`silver_reconstructor.py`, 877 lines) combines pmxt + Jon-Becker + polymarket-apis 2-min price bars
- Their loader pulls from pmxt archive directly with L2 quote-tick granularity — NO trade-level reconstruction needed
- Their relay service pre-shards pmxt archives by market/token — solves the "42GB RAM to load top 1%" problem they had

## Fee Models

- `KalshiProportionalFeeModel` — nonlinear expected-earnings model
- `PolymarketFeeModel` — CLOB fee-rate model (supports zero-fee and taker fee scenarios)
- **Our comparison:** We have fee calc in `simtrader/portfolio/` — need Codex to verify exact implementation overlap

## Strategy Catalogue (15+ strategies)

### Directly Relevant to PolyTool Tracks:

| Their Strategy | Our Track | Value |
|---------------|-----------|-------|
| `polymarket_spread_capture` | Track 1B (A-S MM) | Reference for spread capture logic in binary markets |
| `polymarket_simple_quoter` | Track 1B (A-S MM) | Simpler quoting baseline to compare against our V0/V1 |
| `polymarket_deep_value_resolution_hold` | Phase 5 (Favorite-Longshot) | Buy deep OTM, hold to resolution — matches Jon-Becker finding #3 |
| `polymarket_panic_fade` | Phase 5 (Information Advantage) | Fade overreactions to news — relevant to News Governor |
| `polymarket_sports_final_period_momentum` | Track 1C (Sports) | Sports-specific — final minutes volatility exploitation |
| `polymarket_sports_late_favorite_limit_hold` | Track 1C (Sports) | Sports-specific — late favorite position entry |
| `polymarket_sports_vwap_reversion` | Track 1C (Sports) | VWAP mean-reversion for sports markets |

### Strategies using Pydantic Config/Strategy pattern:
- Config class defines all parameters (Pydantic-based)
- Strategy class implements signal logic
- Inherits from `LongOnlyPredictionMarketStrategy` base
- **This pattern maps to our autoresearch Phase 4** — parameter tuning on Pydantic configs is clean

## Execution Modeling: Known Limitations (matches ours)

1. **No queue position for passive orders** — L2 MBP doesn't distinguish individual orders at a price level
2. **No L3 data** — individual order additions/cancellations are aggregated
3. **No latency modeling** — they assume zero latency (we're AHEAD here — our SimTrader has 150ms latency sim)
4. **No market impact / alpha decay** — liquidity consumption models existing book but not participant reactions

## Licensing Analysis

| Component | License | Can We Pull? |
|-----------|---------|-------------|
| `src/backtesting/` (legacy engine) | MIT | ✅ Yes, freely |
| `nautilus_pm/` (NautilusTrader) | LGPL-3.0 | ⚠️ Modifications must be LGPL-compliant |
| `strategies/` | MIT | ✅ Yes, freely |
| `backtests/` (runners) | MIT | ✅ Yes, freely |
| `pmxt_relay/` | MIT (assumed, root license) | ✅ Yes, freely |

**LGPL-3.0 implication:** If we copy/modify files from `nautilus_pm/`, those files must remain LGPL-3.0 and we must make source available. If we only *use* NautilusTrader as a library (import it), we're fine under LGPL. But we probably don't want to adopt NautilusTrader as a dependency — it's a massive Rust/Python hybrid with complex build requirements.

## Open Questions (Need Research / Codex)

1. **SimTrader fill_engine.py vs their broker matching** — How exactly does our 176-line fill engine compare to their L2 MBP matching with liquidity consumption? Need Codex to dump our `fill_engine.py` contents.

2. **PMXT relay service architecture** — Can we use their relay service directly (it's a hosted service?) or do we need to self-host? This could massively accelerate our Silver tape pipeline.

3. **Sports strategies backtest results** — Do their sports strategies actually show positive PnL? This would validate or invalidate our Track 1C thesis before we build anything.

4. **Pydantic Config pattern vs our strategy_config.json** — Their strategies use typed Pydantic configs with validation. Our autoresearch uses JSON configs. Adopting Pydantic would give us schema validation + parameter bounds for free.

5. **Their fee model accuracy** — Polymarket's fee structure has changed over time (taker delay removed Feb 2026, maker rebate on crypto markets). Do their fee models reflect current reality?

## RIS Seed Candidates

The following should be seeded into `external_knowledge` partition:

| Document | Confidence Tier | Rationale |
|----------|----------------|-----------|
| Their strategy catalogue (descriptions + parameters) | PRACTITIONER | 15+ prediction-market-specific strategies with parameterized configs |
| PMXT data layer architecture (4-tier hierarchy) | PRACTITIONER | Data acquisition pattern we should adopt |
| Execution modeling known limitations doc | PRACTITIONER | Validates our own known gaps, adds specificity |
| DeepWiki analysis pages | COMMUNITY | AI-generated but comprehensive architectural analysis |

## Actionable Integration Paths (Ranked)

### HIGH PRIORITY
1. **PMXT Relay Service** — If we can use their relay (or self-host it), it replaces our entire Silver tape reconstruction pipeline. Their relay pre-shards pmxt archives into per-token Parquet files. This is the single biggest time-saver.
2. **Sports strategies** — Three ready-made sports strategies for Track 1C. Even if we don't copy the code, the signal logic (final period momentum, VWAP reversion, late favorite) gives us concrete starting points.
3. **Fee models** — Pull `KalshiProportionalFeeModel` and `PolymarketFeeModel` for Phase 3 Kalshi integration and to cross-check our existing Polymarket fee calc.

### MEDIUM PRIORITY
4. **Legacy engine as Bronze-tape backtester** — The `src/backtesting/` MIT engine is lightweight, works with Jon-Becker trades via DuckDB, and could serve as an independent validation path for Bronze-tier backtests.
5. **Pydantic Config pattern** — Adopt for autoresearch Phase 4. Typed configs with validation bounds > raw JSON.
6. **Deep Value Resolution Hold** — Direct implementation of Jon-Becker finding #3 (favorite-longshot bias). Cross-validate against our Phase 5 plan.

### LOWER PRIORITY / DEFER
7. **NautilusTrader adoption** — Too heavy (Rust build chain, LGPL licensing). Reference their adapter pattern only.
8. **Panic Fade strategy** — Interesting for News Governor integration but Phase 5+.

---

## Cross-References

- [[SimTrader]] — Our existing simulation engine (comparison target)
- [[Tape-Tiers]] — Gold/Silver/Bronze tier definitions
- [[Track-1B-Market-Maker]] — Gate 2 failed on Silver tapes — relay service could help
- [[Track-1C-Sports-Directional]] — Their sports strategies are direct inputs
- [[Phase-1A-Crypto-Pair-Bot]] — No overlap with this repo


---

## UPDATED FINDINGS (2026-04-10) — Post Codex + GLM-5 Research

### Fill Engine Comparison: SimTrader vs NautilusTrader

**Our `fill_engine.py` already does walk-the-book L2 matching.** BUYs consume asks cheapest-first up to limit price; SELLs consume bids highest-first down to limit. Weighted-average fill price across consumed levels. This is functionally identical to their approach.

**Critical difference: We do NOT mutate the book after fills.** `try_fill()` reads `book._bids` and `book._asks` but never modifies them. This means if our strategy places two orders at the same seq, the second order sees the same book as the first — it doesn't see the liquidity consumed by the first fill. Their NautilusTrader engine with `liquidity_consumption=True` DOES track this depletion across orders within the same event.

**Impact assessment:** For our current use case (single market maker quoting two sides), this matters minimally — we rarely have multiple orders filling simultaneously against the same book snapshot. It would matter more at scale (Phase 8, multi-bot) or for autoresearch where aggressive parameter combinations might produce overlapping fills.

**Fee model gaps identified:**
- Our fee model is **taker-only**: `shares × price × (fee_rate_bps / 10000) × (price × (1-price))²`
- Default is conservative 200 bps (maximum typical taker fee)
- **No maker vs taker distinction** — this is a problem for Track 1A (crypto pairs use maker orders exclusively for the 20bps rebate) and Track 1B (A-S MM places maker orders)
- **No Kalshi fee model exists anywhere in our codebase** — needed for Phase 3

### PMXT Relay: MAJOR CORRECTION

**The per-token sharding pipeline was REMOVED.** The relay is now mirror-only:
- It downloads raw hourly Parquet files from `r2.pmxt.dev`
- Serves them unchanged via `/v1/raw/...`
- NO pre-filtering, NO per-token sharding, NO "2s prebuilt" tier
- All filtering (by `market_id` and `token_id` inside JSON `data` column) happens client-side

**Public instance exists:** `https://209-209-10-83.sslip.io` (author's deployment)

**VPS requirements for self-hosting:**
- 1-2 vCPU, 2-4 GiB RAM (I/O bound, not CPU)
- Disk: ~12-18 GiB/day growth, no automatic cleanup
- 7 days ≈ 85-125 GiB, 30 days ≈ 360-540 GiB

**Revised value assessment:** The relay is just a CDN/mirror. For us, DuckDB on locally-downloaded pmxt Parquet files is equally valid and more flexible. The relay adds zero processing advantage over what we'd do ourselves.

### LGPL Licensing: Fully Clear

- **Reimplementing strategy logic from scratch = ZERO LGPL concern.** Copyright protects expression, not ideas/algorithms.
- **Copying MIT strategy files, stripping NautilusTrader imports, rewiring to our framework = Fine.** Keep "derived from MIT code by X" attribution note.
- **Using NautilusTrader as a pip dependency = Our code stays proprietary.** LGPL explicitly allows this (dynamic linking via Python import).
- **We should NOT copy anything from `nautilus_pm/`.** Not needed and adds unnecessary licensing complexity.

### Revised Integration Priority

| Item | Original Priority | Revised Priority | Reason |
|------|------------------|-----------------|--------|
| PMXT Relay Service | HIGH | **LOW/SKIP** | Mirror-only, no pre-filtering. DuckDB on local Parquet is equivalent. |
| Sports strategies (logic extraction) | HIGH | **HIGH** | Unchanged — signal logic is the value, not the code |
| Fee models (Kalshi + maker/taker) | MEDIUM | **HIGH** | Codex confirmed we have NO maker/taker fee branch and NO Kalshi model |
| Legacy engine as Bronze backtester | MEDIUM | **MEDIUM** | Unchanged |
| Pydantic Config pattern | MEDIUM | **MEDIUM** | Unchanged |
| Book mutation after fills | N/A | **NEW — MEDIUM** | Our fills don't deplete book; theirs do. Matters for autoresearch accuracy. |

### New Action Items Identified

1. **Add maker fee branch to `fees.py`** — Track 1A and 1B both use maker orders. The 20bps maker rebate on crypto markets and the maker/taker fee distinction on standard markets are currently invisible to SimTrader. Every backtest overestimates fees.
2. **Add Kalshi fee model** — Needed for Phase 3. Their `KalshiProportionalFeeModel` is MIT-licensed and can be referenced.
3. **Consider book mutation for fill_engine** — Low priority now, but document as a known limitation in SimTrader. Add to Phase 4 autoresearch accuracy improvements.

---

## Cross-References

- [[SimTrader]] — Fill engine comparison details
- [[Track-1A-Crypto-Pair-Bot]] — Maker rebate not modeled in fees
- [[Track-1B-Market-Maker]] — Gate 2 results may be pessimistic due to taker-only fee model
- [[Track-1C-Sports-Directional]] — Sports strategy extraction targets
