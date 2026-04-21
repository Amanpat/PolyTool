---
tags: [research, open-source, wallet-monitoring, pmxt]
date: 2026-04-10
status: complete
topics: [wallet-watchlist, copy-trading, pmxt-api, Loop-B]
---

# Deep Dive: realfishsam/Polymarket-Copy-Trader

## TL;DR: Low Value for PolyTool — We're Already Ahead

This repo is a minimal wrapper (~200 lines estimated) around pmxt's Python API. It polls target wallets, detects position changes, and mirrors trades with configurable sizing. Our existing 4-loop wallet monitoring architecture ([[01-Wallet-Discovery-Pipeline]]) is dramatically more sophisticated. The Copy Trader adds almost nothing we haven't already designed.

## What the Repo Actually Does

- `config.json`: list of wallet addresses to track, copy percentage, rate limit, trading toggle
- `src/main.py`: polling loop that checks target wallet positions via pmxt, compares to last known state, places proportional orders when changes detected
- Uses pmxt Python SDK (`pip install pmxt`) for all API calls
- `.env` for `POLYMARKET_PRIVATE_KEY` and `POLYMARKET_PROXY_ADDRESS`
- `trading_enabled: false` mode = log-only (dry run)

That's it. 2 commits, 5 stars. It's essentially a demo app for the pmxt library.

## Critical API Limitation Confirmed

From our own research in [[01-Wallet-Discovery-Pipeline]]:

> "Cannot monitor other wallets' CLOB orders before on-chain fill. Polymarket User Channel WebSocket only works with your own API key. Earliest signal for OTHER wallets is always on-chain OrderFilled logs."

The Copy Trader likely uses the Polymarket Data API (REST polling of trade history) to detect target wallet trades — NOT the authenticated `fetchPositions()` which only returns YOUR positions. This means it has inherent latency: the target wallet's trade must appear in the public trade history API before the bot detects it.

Our Loop B design uses Alchemy Polygon WebSocket for <1-3 second detection from block production. The Copy Trader's REST polling approach would be 15-60+ seconds behind.

## Comparison With Our Architecture

| Feature | Copy Trader | Our Loop B Design |
|---------|------------|-------------------|
| Detection method | REST polling (slow) | Alchemy WS `eth_subscribe("logs")` (<3s) |
| Wallet capacity | Unlimited (config.json list) | 20-50 watched addresses (WS filter) |
| Action on detection | Mirror trade (execute) | Discord alert (notify) |
| Market attribution | Via pmxt market lookup | Via OrderFilled event fields |
| Maker/taker classification | Not available | Available from indexed event fields |
| Anomaly detection | None | Loop D (platform-wide CLOB monitoring) |
| Deep analysis trigger | None | Auto-triggers Loop C (LLM hypothesis) |
| Position sizing | Proportional (`copy_percentage`) | Conviction score (whale_count × dollar_size) |
| Dry run mode | Yes (`trading_enabled: false`) | Yes (Discord alerts = inherently dry run) |

## pmxt Python API Patterns Worth Noting

The Copy Trader's value is really as a pmxt API reference. From realfishsam's DomeAPI migration article, the relevant pmxt Python patterns for our codebase:

```python
import pmxt
poly = pmxt.Polymarket()

# Market search (no auth needed)
markets = poly.fetch_markets(query='Trump', status='active', limit=20)

# Events (multi-outcome groups)
events = poly.fetch_events(query='Fed Chair')
market = events[0].markets.match('Kevin Warsh')

# OHLCV candles (by outcome_id, NOT market_id)
candles = poly.fetch_ohlcv(outcome_id, resolution='1h', start='2025-01-01')

# Trade history
trades = poly.fetch_trades(outcome_id, start='2025-01-01', limit=100)

# Order book
book = poly.fetch_order_book(outcome_id)

# Positions (AUTHENTICATED - YOUR positions only)
positions = poly.fetch_positions()  # requires private key

# Order placement (AUTHENTICATED)
order = poly.create_order(outcome_id, side='buy', size=10, price=0.65)
```

**Key insight for PolyTool:** pmxt uses a Node.js sidecar architecture — a local Node.js server runs on port 3847 and handles all exchange communication. This adds operational overhead (persistent Node.js process required alongside our Python stack). We need to evaluate whether this sidecar requirement conflicts with our Docker deployment pattern.

## pmxt Sidecar Architecture — Potential Issue

From the pmxt tutorial: pmxt requires both Python AND Node.js. The Python SDK communicates with a local Node.js sidecar on port 3847. This means:

- Our Docker containers need Node.js installed alongside Python
- The sidecar must be running before any pmxt API call
- Network isolation in Docker Compose may complicate sidecar communication
- The sidecar is a single point of failure for all pmxt-dependent code

**This is worth a decision note.** Our roadmap references pmxt extensively (tape recorder rewrite, market discovery, Kalshi integration), but we haven't evaluated the sidecar operational overhead. If it's problematic, we may want to use py-clob-client directly for Polymarket and build our own Kalshi adapter.

## What We Should Actually Pull (Very Little)

### SKIP entirely:
- The Copy Trader repo itself — our architecture is ahead
- The position mirroring logic — we want alerts, not trade execution
- The polling-based detection — our WS approach is faster

### WORTH NOTING (not pulling, but informing decisions):
1. **pmxt sidecar requirement** — needs evaluation before we commit to pmxt for production code. Add to decision queue.
2. **`trading_enabled: false` pattern** — we already have this (SimTrader dry run, paper_runner), but good to confirm pmxt supports it natively.
3. **`copy_percentage` sizing** — simple proportional sizing. Our conviction score (whale_count × dollar_size) from dylanpersonguy is more sophisticated.

### FROM OTHER realfishsam REPOS (already in roadmap v5.1):
- **`matcher.js`** from `prediction-market-arbitrage-bot` — fuzzy market matching between Polymarket and Kalshi. This is Phase 3 Kalshi integration. Already planned.
- **`arb_bot.py`** from `Risk-Free-Prediction-Market-Trading-Bot` — binary complement arb scanner. Already planned.

## New Decision Needed: pmxt Sidecar Architecture

**Should we commit to pmxt as our unified prediction market SDK, given the Node.js sidecar requirement?**

Arguments FOR:
- Unified API across Polymarket + Kalshi + others
- Already referenced extensively in roadmap v5.1
- Used by all pmxt showcase projects (proven in production)
- DomeAPI was acquired by Polymarket — pmxt is the only remaining independent SDK
- 622 GitHub stars, 68 forks, actively maintained

Arguments AGAINST:
- Node.js sidecar adds operational complexity to our Python monorepo
- Docker Compose needs to manage an additional service
- Single point of failure (port 3847)
- We already use py-clob-client for direct Polymarket CLOB access
- Kalshi integration is Phase 3+ — we don't need multi-exchange today
- The sidecar architecture is unusual and may have undocumented edge cases

**Recommendation:** Defer decision until Phase 3. Continue using py-clob-client directly for Phase 1A/1B. When Kalshi integration becomes active, evaluate pmxt vs building our own thin Kalshi adapter.

## Cross-References

- [[01-Wallet-Discovery-Pipeline]] — Our existing 4-loop wallet monitoring design (far ahead of Copy Trader)
- [[07-Backtesting-Repo-Deep-Dive]] — Other pmxt showcase project analysis
- [[Track-1A-Crypto-Pair-Bot]] — Uses py-clob-client directly, not pmxt
