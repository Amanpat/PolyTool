---
type: phase
phase: 2
status: partial
tags: [phase, status/partial]
created: 2026-04-08
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

## Partial Status Notes

The RIS system (research scraper backbone) is already built and operational. `research-acquire`, `research-ingest`, and `research-precheck` all work. The full candidate scanner CLI is not yet implemented.

---

## Cross-References

- [[RIS]] — Research Intelligence System (built backbone for Phase 2 scraper)
- [[LLM-Policy]] — Provider tier routing
- [[Notifications]] — Discord webhook (Phase 1 outbound built; Phase 2 adds two-way approval)

