---
type: module
status: done
tags: [module, status/done, simtrader]
lines: 6000+
test-coverage: high
created: 2026-04-08
---

# SimTrader

Source: audit Section 1.1 — `packages/polymarket/simtrader/` (multi-subpackage simulation engine).

---

## Subpackage Overview

| Subpackage | Purpose |
|------------|---------|
| `batch/` | Batch replay runner |
| `broker/` | SimBroker, fill engine, order validation |
| `execution/` | Safety modules — kill switch, risk manager, rate limiter, live executor |
| `orderbook/` | L2 book reconstruction |
| `portfolio/` | Fee calc, mark-to-market, portfolio ledger |
| `replay/` | Tape replay runner |
| `shadow/` | Live WS shadow mode with simulated fills |
| `strategies/` | Concrete strategy implementations |
| `strategy/` | Abstract base interfaces |
| `studio/` | Browser-based replay UI |
| `sweeps/` | Parameter sweep across tape set |
| `tape/` | Live tape recorder |

---

## Execution Safety Modules (`execution/`)

| Module | Lines | Purpose |
|--------|-------|---------|
| `kill_switch.py` | 53 | Hardware kill switch — file-based halt |
| `risk_manager.py` | 252 | Inventory limits, daily loss caps, max order caps |
| `rate_limiter.py` | 90 | API rate limiter (token bucket) |
| `live_executor.py` | 155 | Live order executor (wraps py_clob_client) |
| `live_runner.py` | 183 | Live strategy runner with session management |
| `order_manager.py` | 286 | Order lifecycle management and tracking |
| `adverse_selection.py` | 589 | Adverse selection detection and mitigation |
| `wallet.py` | 108 | Wallet balance and position reader |

---

## Strategies

| Strategy | Module | Description |
|----------|--------|-------------|
| MarketMakerV0 | `strategies/market_maker_v0.py` | Simple symmetric market maker (baseline) |
| MarketMakerV1 | `strategies/market_maker_v1.py` | Logit Avellaneda-Stoikov (canonical Phase 1) |
| BinaryComplementArb | `strategies/binary_complement_arb.py` | Binary complement arbitrage |
| CopyWalletReplay | `strategies/copy_wallet_replay.py` | Copy-wallet replay strategy |

Registered via `STRATEGY_REGISTRY` dict in `strategy/facade.py`.

---

## Broker (`broker/`)

| Module | Lines | Purpose |
|--------|-------|---------|
| `sim_broker.py` | 414 | SimBroker — order lifecycle, fills, position tracking |
| `fill_engine.py` | 176 | Fill matching engine against L2 book |
| `rules.py` | 111 | Order validation and risk rules |
| `latency.py` | 47 | Latency simulation (150ms benchmark) |

---

## Studio (`studio/`)

Browser-based replay UI for interactive strategy analysis.

| Module | Lines | Purpose |
|--------|-------|---------|
| `app.py` | 1422 | Studio app — WebSocket server + session management |
| `ondemand.py` | 884 | On-demand session runner |

---

## Top-Level SimTrader Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `tape/recorder.py` | 300 | Live tape recorder — writes Gold tapes |
| `activeness_probe.py` | ~250 | Live market activeness probe via WS |
| `config_loader.py` | ~200 | Strategy config loader with BOM fix |
| `market_picker.py` | ~300 | Market picker — resolve slug, validate book, auto-pick |

---

## Test Coverage

| Test File | Count |
|-----------|-------|
| `test_market_maker_v1.py` | 30 |
| `test_simtrader_shadow.py` | 41 |
| `test_simtrader_portfolio.py` | 64 |
| `test_simtrader_quickrun.py` | 20 |
| `test_simtrader_arb.py` | 22 |
| `test_simtrader_activeness_probe.py` | 31 |

---

## Cross-References

- [[Track-1B-Market-Maker]] — Uses SimTrader for validation
- [[Risk-Framework]] — Gate definitions and capital progression
- [[Tape-Tiers]] — Gold, Silver, Bronze tapes that SimTrader replays
- [[Gates]] — Gate scripts that run SimTrader sweeps
