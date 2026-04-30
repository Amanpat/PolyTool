---
tags: [meta, focus]
created: 2026-04-22
updated: 2026-04-29
---
# Current Focus

Living document — updated each session when priorities shift. Read this first to understand what matters right now.

---

## Active Priorities

1. **RIS Scientific RAG roadmap** — primary active workstream. Layer 0 shipped 2026-04-27. Layer 1 scaffold implemented but production deferred. Next active packet is **L5 (Evaluation Benchmark v0)**, refined to ready 2026-04-29 — handed to architect to convert into a Claude Code prompt. Parallel: Layer 1 (Marker production rollout) is also `status: ready` after architectural decision to make Marker the single production parser, gated on the hosting decision below.
2. **Gate 2 unblock** — Silver tapes produce zero fills for politics/sports. Crypto bucket positive (7/10) but blocked on new markets. WAIT_FOR_CRYPTO policy active. Escalation deadline for benchmark_v2 was 2026-04-12 — needs decision on next steps.
3. **Track 1A Crypto Pair Bot** — BLOCKED on no active BTC/ETH/SOL 5m/15m markets on Polymarket. Check periodically with `crypto-pair-watch --one-shot`.

## Open Decisions Needed

- **Academic pipeline hosting** — where does the academic ingest pipeline run in production? Operator confirmed GPU available on dev machine; recommendation is Docker with GPU passthrough on dev machine, but operator must answer the open questions in [[Decision - Academic Pipeline Hosting]] before [[Work-Packet - Marker Structural Parser Integration]] can ship.
- **Benchmark_v2 strategy** — the 2026-04-12 escalation deadline has passed. What's the path forward for Gate 2?
- **Polymarket account setup** (KYC, wallet, USDC funding) — Phase 0 item still open.

## RIS Scientific RAG Status (as of 2026-04-29)

| Layer | Packet | Status |
|---|---|---|
| L0 | [[Work-Packet - Academic Pipeline PDF Download Fix]] | ✅ Shipped 2026-04-27. pdfplumber wired in. Real arXiv ingests confirmed. |
| L1 | [[Work-Packet - Marker Structural Parser Integration]] | `status: ready` — promoted to production rollout 2026-04-29. Marker becomes single production parser; pdfplumber retired. Gated on [[Decision - Academic Pipeline Hosting]]. |
| L2 | [[Work-Packet - PaperQA2 RAG Control Flow]] | Stub. Activation gated on L5 baseline + L1 production. |
| L3 | [[Work-Packet - Pre-fetch SVM Topic Filter]] | Stub. Activation gated on L5 off-topic-rate measurement OR review queue accumulation. |
| L4 | [[Work-Packet - Multi-source Academic Harvesters]] | Stub. Activation gated on L1 + L3. Updated 2026-04-29 to add backfill-vs-monitoring distinction. |
| L5 | [[Work-Packet - Scientific RAG Evaluation Benchmark]] | `status: ready` — refined from stub 2026-04-29. **Next active packet for the architect.** |

Reference materials:
- [[11-Scientific-RAG-Target-Architecture]] — four-layer target design
- [[Decision - Scientific RAG Architecture Adoption]] — adopt/skip/defer choices
- [[11-Scientific-RAG-Pipeline-Survey]] — full GLM-5 survey of 18 candidate projects

## Recent Session Context

- **2026-04-29**: Vault reconciliation pass and L5 promotion. Scientific RAG architecture review with operator. Decided: Marker becomes single production parser (no fallback), pdfplumber retires. Updated L1, L2, L3, L4 packets with reference materials and architectural changes. Created [[Decision - Academic Pipeline Hosting]] as prerequisite for L1. Promoted L5 from stub to ready with full nine-metric breakdown and corpus selection rule.
- **2026-04-27**: L0 shipped. PDF download fix landed in production with full Docker validation.
- **2026-04-22**: Reorganized Obsidian vault into two top-level folders. Added AGENT.md entry point and this Current-Focus.md file.
- **2026-04-21**: Workflow Harness Refresh session.

## Key Blockers

| Blocker | Affects | Status |
|---------|---------|--------|
| Academic pipeline hosting decision | L1 Marker production rollout | Operator must answer [[Decision - Academic Pipeline Hosting]] open questions |
| L5 corpus accumulation | L5 ship date | Layer 0 needs ~2-4 weeks of production runtime to accumulate the 30-50-paper corpus |
| No active crypto 5m/15m markets | Track 1A | Monitoring |
| Gate 2 failed (7/50 = 14%) | Track 1B live deployment | Needs decision on benchmark_v2 |
| Silver tape zero-fill issue | Gate 2 sweep validity | Tied to crypto market availability |

---

*Last updated by Claude Project — 2026-04-29*

---

## Staleness Check

> If the "updated" date in frontmatter is more than 7 days old, this file needs a refresh.

### Recently Changed Notes (auto-generated)

```dataview
LIST
FROM "Claude Desktop"
WHERE file.mtime >= date(today) - dur(7 days)
SORT file.mtime DESC
LIMIT 5
```
