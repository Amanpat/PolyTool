---
title: "Track 1A — Crypto Pair Bot"
type: concept
status: superseded
superseded_by: repo-docs/specs/spec-0012-phase1-tracka-live-bot-program.md
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: stale
tags: [strategy, crypto, status/blocked]
---

# Track 1A — Crypto Pair Bot

Source: CLAUDE.md "Track 2 — Crypto Pair Bot" + audit Section 1.1 crypto_pairs/ inventory + roadmap Phase 1A checklist.

**Purpose:** Fastest path to first dollar. Standalone — does NOT wait for Gate 2 or Gate 3.

---

## Strategy Description

Directional momentum entries based on the gabagool22 pattern analysis (quick-049).

- **Favorite leg:** fills at `ask <= max_favorite_entry` (0.75)
- **Hedge leg:** fills only at `ask <= max_hedge_price` (0.20)
- Pair-cost accumulation (original thesis) was superseded in quick-046/049

Markets targeted: 5-minute and 15-minute BTC, ETH, SOL up-or-down binary markets on Polymarket.

---

## Blockers

**Live deployment blockers (updated 2026-04-22):**

1. ~~No active BTC/ETH/SOL 5m/15m markets on Polymarket~~ — **Resolved 2026-04-14.** 12 active markets confirmed (BTC×4, ETH×4, SOL×4).
2. Full paper soak with real signals not yet run
3. Oracle mismatch concern — Coinbase reference feed vs Chainlink on-chain settlement oracle
4. EU VPS likely required for deployment latency assumptions

Check current market availability: `python -m polytool crypto-pair-watch --one-shot`

---

## Module Inventory (crypto_pairs/ — 20 files, ~10,599 lines)

| Module | Lines | Purpose |
|--------|-------|---------|
| `accumulation_engine.py` | 576 | Pair-cost accumulation logic (superseded) |
| `await_soak.py` | 366 | Paper-soak wait loop |
| `backtest_harness.py` | 325 | Offline backtesting harness |
| `clickhouse_sink.py` | 262 | ClickHouse write path for crypto pair events |
| `clob_order_client.py` | 160 | CLOB order placement (wraps py_clob_client) |
| `clob_stream.py` | 379 | WebSocket stream client for CLOB L2 events |
| `config_models.py` | 506 | Pydantic config models |
| `dev_seed.py` | 380 | Development seed data generator |
| `event_models.py` | 1441 | Event model definitions (fills, quotes, market events) |
| `fair_value.py` | 204 | Fair value from reference feed + CLOB |
| `live_execution.py` | 175 | Live order execution wrapper |
| `live_runner.py` | 476 | Live trading runner — main orchestration loop |
| `market_discovery.py` | 312 | Active BTC/ETH/SOL pair market discovery |
| `market_watch.py` | 151 | One-shot market watch |
| `opportunity_scan.py` | 198 | Entry opportunity scanner (gabagool22 pattern) |
| `paper_ledger.py` | 1478 | Paper trading position ledger |
| `paper_runner.py` | 1339 | Paper trading runner |
| `position_store.py` | 324 | Persistent position state store |
| `reference_feed.py` | 550 | Coinbase price reference feed via WebSocket |
| `reporting.py` | 996 | Trade reporting, CSV export, session summaries |

**Largest files:** `event_models.py` (1441), `paper_ledger.py` (1478), `paper_runner.py` (1339)

---

## Phase 1A Checklist (from roadmap)

- [x] Binance/Coinbase WebSocket price feed (BinanceFeed, CoinbaseFeed, AutoReferenceFeed)
- [ ] Polymarket 5-min/15-min market discovery
- [ ] Asymmetric pair accumulation engine
- [ ] Risk controls (max capital, daily loss cap, max open pairs, kill switch)
- [ ] Grafana dashboard — crypto pair bot
- [ ] Paper mode testing (24-48 hours)
- [ ] Live deployment on Canadian partner's machine

---

## Cross-References

- [[legacy/PolyTool/02-Modules/Crypto-Pairs]] — Full module inventory for this track
- [[legacy/PolyTool/02-Modules/SimTrader]] — Shared execution safety modules (kill switch, risk manager)
- [[legacy/PolyTool/01-Architecture/Risk-Framework]] — Kill switch model, capital progression
- [[legacy/PolyTool/05-Roadmap/Phase-1A-Crypto-Pair-Bot]] — Phase checklist detail

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
