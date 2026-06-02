---
title: "Phase 2 — Discovery Engine + Research Scraper"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
tags: [phase, status/done]
---

# Phase 2 — Discovery Engine + Research Scraper

Source: roadmap v5.1 Phase 2.

**Runs in parallel after Phase 1 strategies are generating revenue or in shadow.**

---

## Checklist

- [ ] Candidate Scanner CLI (`candidate-scan`) — 9 signals: new-account large position, unusual concentration, consistent early entry, high CLV, COMPLETE_SET_ARBISH, win-rate outlier, Louvain community detection, Jaccard similarity, temporal coordination
- [ ] Scheduling — APScheduler or cron (market scanning 2h, tape recording continuous, health checks 1min, candidate discovery 6h)
- [ ] Local LLM integration (DeepSeek V3 + Gemini Flash + Ollama fallback)
- [ ] Wallet Watchlist — Real-Time Alert Following (top 20-50 wallets, 15-min polling, Discord alerts)
- [ ] Market Obituary System — Stage 1 (resolution signature features in ClickHouse `resolution_signatures`)
- [ ] Discord bot — two-way approval system (button components, 48-hour timeout)
- [ ] LLM-Assisted Research Scraper (Stage A: fetch ArXiv/Reddit/GitHub/RSS; Stage B: LLM 0-100 evaluation)
- [ ] Domain Specialization Layer (category-specific CLV breakdown, Jon-Becker gap table into external_knowledge)

---

## Conditional Close (2026-04-09)

Phase 2 is **conditionally closed**. The RIS backbone is built, operator-verified, and in production use. The condition is that deferred items (full candidate scanner, wallet watchlist, market obituary, two-way Discord bot, domain specialization) remain explicitly tracked and are not lost.

### Shipped

- Weighted composite evaluation gate (fail-closed, per-priority thresholds)
- Cloud provider routing (Gemini/DeepSeek/Ollama)
- Ingest/review integration with operator review queue
- Monitoring truth (7 health checks, provider failure detection, review backlog)
- Retrieval benchmark (query class segmentation, baseline artifacts)
- Discord embed alerting via scoped n8n pilot
- Operator SOPs and runbooks

### Deferred (explicit — not abandoned)

- Full candidate scanner CLI (`candidate-scan` with 9 signals)
- Wallet watchlist real-time alert following
- Market obituary system
- Two-way Discord bot (button components, 48-hour timeout)
- Domain specialization layer
- Broad n8n orchestration (Phase 3 per ADR 0013)

---

## Cross-References

- [[legacy/PolyTool/02-Modules/RIS]] — Research Intelligence System (built backbone for Phase 2 scraper)
- [[legacy/PolyTool/01-Architecture/LLM-Policy]] — Provider tier routing
- [[legacy/PolyTool/02-Modules/Notifications]] — Discord webhook (Phase 1 outbound built; Phase 2 adds two-way approval)
- [[claude-memory/decisions/decision-ris-n8n-pilot-scope]] — n8n pilot scope boundary and canonical paths

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
