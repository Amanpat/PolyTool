---
type: phase
phase: 3
status: todo
tags: [phase, status/todo]
created: 2026-04-08
---

# Phase 3 — Hybrid RAG Brain + Kalshi + n8n

Source: roadmap v5.1 Phase 3.

**Upgrade infrastructure after revenue is flowing.**

---

## Checklist

- [ ] Unified Chroma collection (`polytool_brain`) — four partition tags: `user_data`, `external_knowledge`, `research`, `signals`
- [ ] Kalshi integration (pmxt-enabled) — market sync, L2 recording, cross-platform calibration, arb detector, resolution condition parser
- [ ] Signals ingest pipeline (adapt existing storage, add RSS feeds: AP, Reuters, BBC, ESPN, Bloomberg)
- [ ] RTDS comment stream (Polymarket real-time-data-client WebSocket for comment sentiment)
- [ ] Market linker (entity extraction + Gamma API lookup + LLM disambiguation)
- [ ] Reaction measurement (price change tracking at t+5min, t+30min, t+2hr)
- [ ] Signals partition write (proven patterns only — >= 10 historical events with > 3% move)
- [ ] n8n local setup — replace APScheduler with n8n for complex workflows
- [ ] FastAPI wrapper — first endpoints (thin wrappers: candidate-scan, wallet-scan, llm-bundle, simtrader/run, market-scan, bot/status, strategy/promote)
- [ ] Multi-LLM Specialist Routing — four specialist tasks to best free model each

---

## Key Notes

- FastAPI wrapper is a Phase 3 deliverable — do not build before Phase 1 raw CLI paths work
- A scoped n8n RIS pilot (ADR 0013) is already shipped as opt-in via `--profile ris-n8n`. Broad n8n orchestration remains Phase 3.
- Kalshi: CFTC-regulated (US-legal). Polymarket restricts US access. Resolution condition parsing is required to avoid cross-platform position risk.

---

## Cross-References

- [[RAG]] — ChromaDB and SQLite FTS5 backends that Phase 3 upgrades
- [[FastAPI-Service]] — The island that Phase 3 brings online
- [[LLM-Policy]] — Multi-LLM specialist routing policy

