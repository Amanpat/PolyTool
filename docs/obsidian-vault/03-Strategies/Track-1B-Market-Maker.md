---
type: strategy
track: 1B
tags: [strategy, market-maker, status/todo]
created: 2026-04-08
---

# Track 1B — Market Maker

Source: CLAUDE.md "Track 1 — Market Maker" + roadmap Phase 1B + audit SimTrader strategies.

**Purpose:** Long-term revenue engine. Avellaneda-Stoikov style quoting and inventory control.

---

## Strategy Description

**MarketMakerV1** — Logit Avellaneda-Stoikov market maker (canonical Phase 1 strategy).

- Transforms mid-price to log-odds: `x = ln(p/(1-p))`
- Computes reservation price and spread in unbounded log-odds domain
- Back-transforms via sigmoid for binary probability markets
- σ² estimated from realized variance of logit-mid first-differences
- κ calibrated via trade-arrival proxy from Jon-Becker 72M trades per category
- Spread clamped to `[min_spread, max_spread]` in probability space after sigmoid
- Bid/ask hard-clamped to `[0.01, 0.98]` × `[0.02, 0.99]`

**MarketMakerV0** — Simple symmetric market maker (conservative baseline).

---

## Validation Path

Gate 2 → Gate 3 → Stage 0 → Stage 1+

| Gate | Threshold | Status |
|------|-----------|--------|
| Gate 1 — Replay Pass | Positive net PnL across broad tape set | **PASSED** |
| Gate 2 — Parameter Sweep | ≥70% of 50 tapes show positive net PnL after fees | **FAILED** (7/50 = 14%) |
| Gate 3 — Shadow Run | Shadow PnL within 25% of Gate 2 replay prediction | **BLOCKED** |
| Gate 4 — Dry-Run Pass | 72-hour zero-error paper live run | **PASSED** |

**Root cause of Gate 2 failure:** Silver tapes produce zero fills for politics/sports categories. Crypto bucket positive (7/10) but blocked on new markets.

---

## Current Status

- **benchmark_v1 CLOSED** 2026-03-21 — 50 tapes, DO NOT MODIFY
- **WAIT_FOR_CRYPTO** policy active (ADR: `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`)
- Gate 2 corpus: 10/50 qualifying tapes (need ≥35 positive for 70% threshold)
- Escalation deadline for benchmark_v2 consideration: **2026-04-12**

---

## Key Strategy Files

| File | Lines | Purpose |
|------|-------|---------|
| `simtrader/strategies/market_maker_v0.py` | — | Simple symmetric market maker |
| `simtrader/strategies/market_maker_v1.py` | — | Logit A-S market maker (canonical) |
| `simtrader/execution/kill_switch.py` | 53 | Hardware kill switch |
| `simtrader/execution/risk_manager.py` | 252 | Inventory limits, daily loss caps |
| `simtrader/execution/rate_limiter.py` | 90 | API rate limiter (token bucket) |
| `simtrader/execution/live_executor.py` | 155 | Live order executor |
| `simtrader/execution/live_runner.py` | 183 | Live strategy runner |

---

## Phase 1B Checklist (from roadmap)

- [x] MarketMakerV1 — Logit A-S upgrade
- [x] Benchmark tape set — benchmark_v1 (50 tapes, closed 2026-03-21)
- [x] Market Selection Engine (7-factor composite scorer)
- [x] Discord alert system — Phase 1
- [ ] Complete Silver tape generation end-to-end
- [ ] Pass Gate 2 (≥70% positive PnL)
- [ ] Begin Gate 3 — Shadow run
- [ ] Stage 0 — Paper Live (72-hour dry-run)
- [ ] Stage 1 — $500 live deployment
- [ ] Bulk data import (pmxt + Jon-Becker)
- [ ] DuckDB setup and integration

---

## Cross-References

- [[Risk-Framework]] — Gate definitions, capital progression, validation ladder
- [[Gates]] — Gate management scripts and current status
- [[SimTrader]] — Simulation engine that validates the strategy
- [[Phase-1B-Market-Maker-Gates]] — Phase checklist detail
