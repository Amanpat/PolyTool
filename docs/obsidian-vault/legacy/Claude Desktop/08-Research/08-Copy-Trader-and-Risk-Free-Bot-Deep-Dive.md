---
tags: [research, open-source, pmxt, wallet-monitoring, integration]
date: 2026-04-10
status: complete
topics: [copy-trading, binary-arb, pmxt-adoption, wallet-watchlist]
---

# Deep Dive: realfishsam Repos (Copy Trader + Risk-Free Bot)

## Key Context: These Are pmxt Showcase Demos

Both repos are by **realfishsam** — who is the **creator of pmxt itself**. These are small showcase demos (2-3 commits each, MIT licensed) designed to demonstrate pmxt capabilities. The realfishsam/prediction-market-arbitrage-bot (already in our roadmap v5.1) is from the same author.

**This means the real question isn't "what code to pull" — it's "should we adopt pmxt as our unified API layer?"**

---

## Repo 1: Polymarket-Copy-Trader

**URL:** https://github.com/realfishsam/Polymarket-Copy-Trader
**Size:** 2 commits, 5 stars, MIT
**What it does:** Polls tracked wallets for position changes via pmxt, mirrors trades with configurable sizing (`copy_percentage`), rate-limited API calls.

### Comparison With Our Existing Architecture

| Capability | Copy Trader | PolyTool (Current) |
|-----------|-------------|-------------------|
| Wallet monitoring | pmxt position polling | Loop B: Alchemy WebSocket on-chain OrderFilled events |
| Detection latency | Seconds-to-minutes (polling interval) | <1-3 seconds (on-chain event subscription) |
| Wallet attribution | Via pmxt wallet positions API | On-chain maker/taker fields from event logs |
| Copy execution | pmxt order placement | Not yet implemented (planned for Loop B high-confidence signals) |
| Position sizing | Simple `copy_percentage` multiplier | Not yet designed |
| SimTrader replay | N/A | `CopyWalletReplay` strategy exists |
| Discovery | Manual wallet list | Loop A: automated leaderboard + Loop D: anomaly detection |

**Verdict: Our architecture is vastly more sophisticated.** The Copy Trader is a polling-based toy compared to our 4-loop real-time pipeline. We get on-chain fills in <3 seconds; they get position snapshots whenever they poll.

### What's Actually Useful

1. **pmxt order placement patterns** — Clean Python example of placing orders through pmxt with proxy address support and rate limiting. Reference for when we go live.
2. **`copy_percentage` sizing** — Trivial but we haven't designed our copy-trade sizing yet. Their approach (simple multiplier) is a reasonable starting point for Loop B auto-copy signals.
3. **`trading_enabled: false` dry-run mode** — Same pattern as our `--dry-run` flag. Validates the approach.

### What's NOT Useful

- Position change detection via polling — our WebSocket approach is strictly superior
- Wallet discovery — we have Loop A + Loop D
- The code itself — too simple to extract anything meaningful

---

## Repo 2: Risk-Free-Prediction-Market-Trading-Bot

**URL:** https://github.com/realfishsam/Risk-Free-Prediction-Market-Trading-Bot
**Size:** 3 commits, 1 star, MIT
**What it does:** WebSocket-based scanner for binary arbitrage (YES + NO < $1.00), plus historical analysis/charting.

### Comparison With Our Existing Architecture

| Capability | Risk-Free Bot | PolyTool (Current) |
|-----------|--------------|-------------------|
| Binary arb detection | WebSocket scanner for sum < $1.00 | `arb.py` (601 lines) — `find_arb_opportunities()` |
| SimTrader strategy | N/A | `BinaryComplementArb` strategy exists |
| Historical analysis | `fetch_spread_data.py` + `visualize_prob_sum.py` | Grafana Arb Feasibility panel |
| Live execution | `arb_bot.py` | Not live yet |

**Verdict: Already covered.** Our roadmap v5.1 explicitly references this repo and notes: "Complement arb is non-viable on current Polymarket (sum_ask floors above 1.001)." We have both the detection (`arb.py`) and the SimTrader strategy (`BinaryComplementArb`) already built.

### What's Actually Useful

1. **Historical arb frequency charting** (`analysis/visualize_prob_sum.py`) — reference for Grafana dashboard panel improvements. Low priority.
2. **Confirmation of non-viability** — The repo itself is educational/showcase only. No evidence of profitable live deployment. Validates our decision to deprioritize complement arb.

---

## The Real Question: Should We Adopt pmxt?

Both repos demonstrate pmxt as a clean unified API layer. Our current stack uses:

| Layer | Current | With pmxt |
|-------|---------|-----------|
| CLOB execution | `py-clob-client` (direct) | `pmxt.Polymarket()` |
| Market data | Custom `gamma.py` (1089 lines), `data_api.py` (641 lines), `clob.py` (263 lines) | `pmxt.fetch_markets()`, `pmxt.fetch_ohlcv()` |
| Orderbook | Custom `clob_stream.py` (379 lines) + `orderbook_snapshots.py` (532 lines) | `pmxt.watchOrderBook()` |
| Tape recording | Custom `tape/recorder.py` (300 lines) | `pmxt.watchOrderBook()` → tape format |
| Kalshi | Not built | `pmxt.Kalshi()` — immediate |
| Wallet positions | Alchemy on-chain + custom code | `pmxt.fetch_positions()` |

### Arguments FOR pmxt Adoption

1. **Kalshi for free** — Phase 3 Kalshi integration becomes trivial. pmxt already has `pmxt.Kalshi()` with the same API surface.
2. **Platform Abstraction Layer exists** — Our Phase 8 `PlatformAdapter` interface is exactly what pmxt already is. Why build it?
3. **Roadmap already references it** — v5.1 mentions `pmxt.watchOrderBook()` for tape recording, pmxt archive for data, pmxt for Kalshi. We're half-committed already.
4. **Dome API is dead** — Polymarket acquired Dome (YC W25) in Feb 2026. pmxt is the only remaining independent unified SDK. Industry convergence point.
5. **622 GitHub stars, 68 forks, 9 contributors, 70 releases** — actively maintained, not a toy.

### Arguments AGAINST pmxt Adoption

1. **Node.js sidecar requirement** — pmxt uses a sidecar architecture: a persistent Node.js process on port 3847 handles all exchange communication. This adds operational complexity to our Docker deployment. Every container needs Node.js + Python.
2. **We already built the hard parts** — Our `gamma.py` (1089 lines), `clob.py` (263 lines), `data_api.py` (641 lines) are working, tested, battle-hardened. Replacing them with pmxt is a rewrite with no immediate capability gain.
3. **Execution-critical code on third-party dependency** — Our live executor wraps `py-clob-client` directly. Adding pmxt as an intermediary layer between us and the CLOB adds latency and a failure point for execution-critical operations.
4. **EIP-712 signing** — We already handle this via `py-clob-client`. pmxt uses its own signing path through the Node.js sidecar. Switching is non-trivial and adds risk.
5. **Tight coupling risk** — If pmxt breaks or changes API, our entire stack is affected. With `py-clob-client` direct, we own the execution path.

### Recommendation: Selective Adoption, Not Full Migration

**Use pmxt for READ operations and new platform integrations. Keep `py-clob-client` for WRITE (execution) operations.**

Specifically:
- **Phase 3 Kalshi:** Use `pmxt.Kalshi()` for read operations (market data, orderbook, positions). Build Kalshi execution separately if needed.
- **Tape recording:** Use `pmxt.watchOrderBook()` for the tape recorder rewrite (already in roadmap).
- **Cross-platform arb detection:** Use pmxt for scanning prices across platforms (Phase 3/5).
- **DO NOT replace** `py-clob-client` for order placement, `gamma.py` for market data, or `clob_stream.py` for CLOB WebSocket. These work and are execution-critical.

**This is a DECISION-LEVEL topic.** Should be discussed and logged in `09-Decisions/` before any implementation.

---

## Integration Summary (Both Repos)

| Item | Priority | Action |
|------|----------|--------|
| Copy Trader code | **SKIP** | Our 4-loop pipeline is strictly superior |
| Risk-Free Bot code | **SKIP** | Already have `arb.py` + `BinaryComplementArb` |
| pmxt order placement patterns | **LOW** | Reference when building live execution |
| `copy_percentage` sizing pattern | **LOW** | Note for Loop B auto-copy design |
| pmxt selective adoption question | **HIGH — DECISION NEEDED** | Discuss before Phase 3 Kalshi work starts |

---

## GLM-5 Research Prompt (if pursuing pmxt adoption)

```
I'm evaluating adopting pmxt (github.com/pmxt-dev/pmxt) as a dependency in my Python trading system.

Key concerns:
1. The sidecar architecture requires a persistent Node.js process on port 3847. My system deploys via Docker containers. What are the operational implications? Can the sidecar run in the same container or does it need its own?
2. For order placement on Polymarket: pmxt wraps py-clob-client internally. If I'm already using py-clob-client directly for order execution, is there any benefit to switching to pmxt for execution? Or does it add latency?
3. pmxt was the only remaining unified SDK after Polymarket acquired Dome in Feb 2026. Is there any risk that Polymarket will acquire or break pmxt as well?
4. What is the actual latency overhead of the sidecar architecture vs direct API calls?
5. Can pmxt's Python client be used WITHOUT the Node.js sidecar for read-only operations?

Search for: pmxt sidecar architecture latency, pmxt Docker deployment, pmxt vs py-clob-client performance, Dome API acquisition pmxt impact.
```

---

## Cross-References

- [[01-Wallet-Discovery-Pipeline]] — Our 4-loop architecture (vastly superior to Copy Trader)
- [[Core-Library]] — arb.py and SimTrader BinaryComplementArb already exist
- [[SimTrader]] — CopyWalletReplay strategy already exists
- [[07-Backtesting-Repo-Deep-Dive]] — Backtesting repo (higher value than these)
- [[Track-1A-Crypto-Pair-Bot]] — Uses custom clob_stream.py, not pmxt
