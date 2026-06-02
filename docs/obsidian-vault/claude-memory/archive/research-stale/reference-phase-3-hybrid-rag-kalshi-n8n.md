---
title: "Phase 3 — Hybrid RAG Brain + Kalshi + n8n"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
tags: [phase, status/todo]
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
- A scoped n8n RIS pilot (ADR 0013) is shipped and operational via `--profile ris-n8n`. Canonical workflow home is `infra/n8n/workflows/`. APScheduler remains the default scheduler. Broad n8n orchestration (replacing APScheduler project-wide) remains Phase 3. See [[claude-memory/decisions/decision-ris-n8n-pilot-scope]].
- Kalshi: CFTC-regulated (US-legal). Polymarket restricts US access. Resolution condition parsing is required to avoid cross-platform position risk.

---

## Cross-References

- [[legacy/PolyTool/02-Modules/RAG]] — ChromaDB and SQLite FTS5 backends that Phase 3 upgrades
- [[legacy/PolyTool/02-Modules/FastAPI-Service]] — The island that Phase 3 brings online
- [[legacy/PolyTool/01-Architecture/LLM-Policy]] — Multi-LLM specialist routing policy
- [[claude-memory/decisions/decision-ris-n8n-pilot-scope]] — Current n8n scope boundary

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
