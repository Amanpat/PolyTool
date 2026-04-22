---
type: index
tags: [index, status/done]
created: 2026-04-08
---

# Done Items

All completed milestones and notes tagged `#status/done`.

---

## Dataview — All Done Notes

```dataview
LIST
FROM ""
WHERE contains(tags, "status/done")
SORT file.name ASC
```

---

## Manually Curated Completed Milestones

Source: `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` Phase checklists and `docs/CURRENT_STATE.md`.

### Phase 0

- [x] Rebuild CLAUDE.md — rewritten to comprehensive project context file
- [x] Write `docs/OPERATOR_SETUP_GUIDE.md`

### Research Pipeline

- [x] ClickHouse schema + ingest pipeline for Polymarket data
- [x] Grafana dashboards (Trades, Detectors, PnL, Arb Feasibility)
- [x] `scan` CLI — one-shot ingestion + trust artifact emission
- [x] Strategy detectors: HOLDING_STYLE, DCA_LADDERING, MARKET_SELECTION_BIAS, COMPLETE_SET_ARBISH
- [x] PnL computation with fee model (FIFO realized + MTM)
- [x] Resolution enrichment — 4-stage cascade (CH → OnChainCTF → Subgraph → Gamma)
- [x] CLV capture (Closing Line Value per position)
- [x] `wallet-scan` + `alpha-distill` — batch scan, hypothesis distillation
- [x] Hypothesis Registry (register, status, experiment-init, experiment-run, validate, diff, summary)
- [x] Local RAG (ChromaDB + FTS5 + RRF + cross-encoder rerank)
- [x] LLM Bundle + MCP server (FastMCP SDK)

### SimTrader

- [x] Tape recorder — records live Polymarket WS → deterministic replay files
- [x] L2 book reconstruction from tape events
- [x] Replay runner + BrokerSim
- [x] Parameter sweeps + local HTML reports
- [x] Shadow mode (live WS, simulated fills)
- [x] OrderManager (quote reconciliation, rate caps)
- [x] MarketMakerV0 (symmetric quoting, inventory skew, binary guards)
- [x] MarketMakerV1 — Logit Avellaneda-Stoikov (canonical Phase 1 strategy)
- [x] Execution primitives: KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner
- [x] SimTrader Studio (browser-based replay UI)

### Benchmark Pipeline

- [x] benchmark_v1 manifest closed 2026-03-21 — 50 tapes across 5 buckets
- [x] Silver tape reconstructor (operational v1)
- [x] benchmark_v1.tape_manifest, lock.json, audit.json finalized (DO NOT MODIFY)

### Phase 1B — Completed Sub-Items

- [x] MarketMakerV1 — Logit A-S upgrade
- [x] Market Selection Engine (7-factor composite scorer)
- [x] Discord alert system — Phase 1 outbound alerting
- [x] Binance/Coinbase WebSocket price feed for crypto pair bot

### Infrastructure (2026-04-05)

- [x] pair-bot-live Docker profile gate fix
- [x] API Dockerfile curl fix
- [x] Full build matrix verified (3695+ tests passing)
- [x] Docker build context tightened (~12MB actual source)
- [x] BuildKit cache mounts for apt and pip
- [x] Dockerfile.bot adopted for pair-bot services

### Gate Status

- [x] Gate 1: PASSED (multi-tape replay)
- [x] Gate 4: PASSED
