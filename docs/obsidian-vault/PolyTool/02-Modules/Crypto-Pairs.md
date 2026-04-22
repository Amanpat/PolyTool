---
type: module
status: blocked
tags: [module, status/blocked, crypto]
lines: 10599
test-coverage: high
created: 2026-04-08
---

# Crypto Pairs Module

Source: audit Section 1.1 — `packages/polymarket/crypto_pairs/` (20 files, ~10,599 lines).

**Status: BLOCKED** — no active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29.

---

## Module Inventory (20 files, ~10,599 lines)

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `accumulation_engine.py` | 576 | Pair-cost accumulation logic (superseded by gabagool22) | WORKING |
| `await_soak.py` | 366 | Paper-soak wait loop | WORKING |
| `backtest_harness.py` | 325 | Offline backtesting harness | WORKING |
| `clickhouse_sink.py` | 262 | ClickHouse write path for crypto pair events | WORKING |
| `clob_order_client.py` | 160 | CLOB order placement (wraps py_clob_client) | WORKING |
| `clob_stream.py` | 379 | WebSocket stream client for CLOB L2 events | WORKING |
| `config_models.py` | 506 | Pydantic config models | WORKING |
| `dev_seed.py` | 380 | Development seed data generator | WORKING |
| `event_models.py` | 1441 | Event model definitions (fills, quotes, market events) | WORKING |
| `fair_value.py` | 204 | Fair value from reference feed + CLOB | WORKING |
| `live_execution.py` | 175 | Live order execution wrapper | WORKING |
| `live_runner.py` | 476 | Live trading runner — main orchestration loop | WORKING |
| `market_discovery.py` | 312 | Active BTC/ETH/SOL pair market discovery | WORKING |
| `market_watch.py` | 151 | One-shot market watch | WORKING |
| `opportunity_scan.py` | 198 | Entry opportunity scanner (gabagool22 pattern) | WORKING |
| `paper_ledger.py` | 1478 | Paper trading position ledger | WORKING |
| `paper_runner.py` | 1339 | Paper trading runner | WORKING |
| `position_store.py` | 324 | Persistent position state store | WORKING |
| `reference_feed.py` | 550 | Coinbase price reference feed via WebSocket | WORKING |
| `reporting.py` | 996 | Trade reporting, CSV export, session summaries | WORKING |

### Largest Files

- `event_models.py` (1441 lines) — all event type definitions
- `paper_ledger.py` (1478 lines) — paper trading position tracking
- `paper_runner.py` (1339 lines) — paper trading orchestration

---

## Strategy

**Gabagool22 directional momentum pattern:**
- Favorite leg: fills at `ask <= max_favorite_entry` (0.75)
- Hedge leg: fills at `ask <= max_hedge_price` (0.20)
- Original pair-cost accumulation thesis superseded in quick-046/049

---

## Blockers

1. No active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29
2. Oracle mismatch concern (Coinbase reference feed vs Chainlink on-chain settlement)
3. Full paper soak not yet run
4. EU VPS likely required for deployment

Check current market availability: `python -m polytool crypto-pair-watch --one-shot`

---

## Cross-References

- [[Track-1A-Crypto-Pair-Bot]] — Strategy description and phase checklist
- [[System-Overview]] — Package structure
