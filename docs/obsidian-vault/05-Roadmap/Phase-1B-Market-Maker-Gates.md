---
type: phase
phase: 1B
status: todo
tags: [phase, status/todo, market-maker]
created: 2026-04-08
---

# Phase 1B — Track 1: Market Maker (Gate Closure → Live)

Source: roadmap v5.1 Phase 1B + CLAUDE.md Track 1.

**Priority: HIGH. Runs in parallel with Phase 1A. Long-term revenue engine.**

---

## Checklist

- [x] MarketMakerV1 — Logit A-S upgrade (logit/sigmoid transform, σ² from realized variance, κ trade-arrival proxy)
- [x] Benchmark tape set — benchmark_v1 (50 tapes, closed 2026-03-21, DO NOT MODIFY)
- [x] Market Selection Engine (7-factor composite scorer)
- [x] Discord alert system — Phase 1 (outbound only, webhook-based)
- [ ] Complete Silver tape generation end-to-end
- [ ] Pass Gate 2 — Parameter sweep (>= 70% positive PnL across 50 tapes)
- [ ] Seed Jon-Becker findings into RAG `external_knowledge`
- [ ] Begin Gate 3 — Shadow run (3-5 live markets, simulated fills)
- [ ] Stage 0 — Paper Live (72-hour dry-run)
- [ ] Stage 1 — $500 live deployment
- [ ] Bulk data import (pmxt + Jon-Becker via DuckDB)
- [ ] DuckDB setup and integration
- [ ] Tape Recorder rewrite — pmxt.watchOrderBook()
- [ ] Auto-redeem — position redemption for settled markets
- [ ] Multi-window OFI (60min, 4hr, 24hr rolling windows)
- [ ] News Governor — Risk Layer (scheduled high-risk calendar)
- [ ] Parallel SimTrader — multiprocessing.Pool
- [ ] Universal Market Discovery (NegRisk + Events + Sports)
- [ ] Grafana live-bot panels

---

## Gate Status

| Gate | Threshold | Status |
|------|-----------|--------|
| Gate 1 — Replay Pass | Positive net PnL across broad tape set | PASSED |
| Gate 2 — Scenario Sweep | >= 70% tapes positive after fees | FAILED (7/50 = 14%) |
| Gate 3 — Shadow Run | Shadow PnL within 25% of replay prediction | BLOCKED |
| Gate 4 — Dry-Run Pass | 72-hour zero-error paper live run | PASSED |

**Root cause of Gate 2 failure:** Silver tapes produce zero fills for politics/sports categories. Crypto bucket (7/10 positive) blocked on new markets.

---

## Benchmark Policy

- benchmark_v1 CLOSED 2026-03-21 — DO NOT MODIFY
- WAIT_FOR_CRYPTO policy active (ADR: `docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md`)
- Escalation deadline for benchmark_v2 consideration: 2026-04-12

---

## Cross-References

- [[Track-1B-Market-Maker]] — Strategy description and gate detail
- [[Gates]] — Gate scripts and current status
- [[SimTrader]] — Simulation engine
- [[Market-Selection]] — 7-factor scorer
- [[Tape-Tiers]] — Silver tape generation is the next unblock

