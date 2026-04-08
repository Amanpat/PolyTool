---
type: phase
phase: 1A
status: blocked
tags: [phase, status/blocked, crypto]
created: 2026-04-08
---

# Phase 1A — Track 2: Crypto Pair Bot (Fastest Path to First Dollar)

Source: roadmap v5.1 Phase 1A + CLAUDE.md Track 2.

**Priority: HIGH. Fastest path to first dollar. Standalone — does NOT wait for Gate 2 or Gate 3.**

---

## Checklist

- [x] **Binance/Coinbase WebSocket price feed** — `BinanceFeed`, `CoinbaseFeed`, `AutoReferenceFeed` in `reference_feed.py`. 55 offline tests. Coinbase fallback resolves Binance HTTP 451 geo-restriction.
- [ ] **Polymarket 5-min/15-min market discovery** — auto-discover active crypto up-or-down markets via Gamma API
- [ ] **Asymmetric pair accumulation engine** — monitor YES/NO orderbooks, place maker limit buys at threshold, track cumulative pair cost
- [ ] **Risk controls for crypto pair bot** — max capital per window, daily loss cap, max open pairs, kill switch, position tracking to ClickHouse
- [ ] **Grafana dashboard — crypto pair bot** — active pairs, pair cost distribution, realized profit, cumulative PnL
- [ ] **Paper mode testing** — 24-48 hours against live markets with simulated fills
- [ ] **Live deployment** — Canadian partner machine, $50-100 initial capital

---

## Current Strategy: Gabagool22

- Favorite leg: fills at `ask <= max_favorite_entry` (0.75)
- Hedge leg: fills only at `ask <= max_hedge_price` (0.20)
- Original pair-cost accumulation thesis superseded in quick-046/049
- Dev logs: `2026-03-29_gabagool22_crypto_analysis.md` and `2026-03-29_gabagool_strategy_rebuild.md`

---

## Blockers

1. No active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29
2. Oracle mismatch concern (Coinbase reference feed vs Chainlink on-chain settlement)
3. Full paper soak with real signals not yet run
4. EU VPS likely required for deployment latency assumptions

Check current market availability: `python -m polytool crypto-pair-watch --one-shot`

---

## Cross-References

- [[Track-1A-Crypto-Pair-Bot]] — Strategy description and module inventory
- [[Crypto-Pairs]] — Module details

