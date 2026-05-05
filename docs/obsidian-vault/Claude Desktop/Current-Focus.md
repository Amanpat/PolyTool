---
tags: [meta, focus]
created: 2026-04-22
updated: 2026-05-05
---
# Current Focus

Living document — updated each session when priorities shift. Read this first to understand what matters right now.

---

## Active Priorities

1. **RIS Scientific RAG roadmap** — primary active workstream. **L1 Marker production rollout is BLOCKED 2026-05-05** — validation failed. One-shot benchmarks time out on math-heavy papers (1200-1800s); scheduler lacks single-paper submit path, hard-cancel, and per-paper parse metadata. L1 is deferred until [[Work-Packet - Marker Single-Paper Validation Control Surface]] ships. L5 shipped 2026-05-02; L3/L3.1 shipped 2026-05-02. L2 and L4 remain stubs. Next recommended work: **Marker Single-Paper Validation Control Surface** OR resume L3 label accumulation toward ≥30+30 SVM trigger. Do NOT start L2 yet.
2. **Gate 2 unblock** — Silver tapes produce zero fills for politics/sports. Crypto bucket positive (7/10) but blocked on new markets. WAIT_FOR_CRYPTO policy active. Escalation deadline for benchmark_v2 was 2026-04-12 — needs decision on next steps.
3. **Track 1A Crypto Pair Bot** — BLOCKED on no active BTC/ETH/SOL 5m/15m markets on Polymarket. Check periodically with `crypto-pair-watch --one-shot`.

## Open Decisions Needed

- ~~**Academic pipeline hosting**~~ — **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). L1 Marker production rollout is now unblocked.
- **Benchmark_v2 strategy** — the 2026-04-12 escalation deadline has passed. What's the path forward for Gate 2?
- **Polymarket account setup** (KYC, wallet, USDC funding) — Phase 0 item still open.

## RIS Scientific RAG Status (as of 2026-05-01)

| Layer | Packet | Status |
|---|---|---|
| L0 | [[Work-Packet - Academic Pipeline PDF Download Fix]] | ✅ Shipped 2026-04-27. pdfplumber wired in. Real arXiv ingests confirmed. |
| L1 | [[Work-Packet - Marker Structural Parser Integration]] | **BLOCKED 2026-05-05.** Code + Codex fixes done 2026-05-03. Validation failed: one-shot benchmarks time out on math-heavy papers; scheduler has no single-paper submit path, no hard cancel, no per-paper parse metadata. Gated on [[Work-Packet - Marker Single-Paper Validation Control Surface]]. |
| L2 | [[Work-Packet - PaperQA2 RAG Control Flow]] | Stub. Activation gated on L5 baseline + L1 production. |
| L3 | [[Work-Packet - Pre-fetch SVM Topic Filter]] | ✅ Shipped 2026-05-02. **L3.1 also shipped 2026-05-02** — `hold-review` mode: REVIEW candidates queued, not ingested; `ReviewQueueStore` + `LabelStore`; `research-prefetch-review` CLI; Codex PASS WITH FIXES resolved; 160 tests. Next: accumulate ≥30+30 labels for SVM trigger. Feature doc: `FEATURE-ris-prefetch-relevance-filter-v0.md`. |
| L4 | [[Work-Packet - Multi-source Academic Harvesters]] | Stub. Activation gated on L1 + L3. Updated 2026-04-29 to add backfill-vs-monitoring distinction. |
| L5 | [[Work-Packet - Scientific RAG Evaluation Benchmark]] | ✅ Shipped 2026-05-02. Baseline locked: corpus=23, off_topic_rate=30.43%, P@5=1.0, Recommendation A. |

Reference materials:
- [[11-Scientific-RAG-Target-Architecture]] — four-layer target design
- [[Decision - Scientific RAG Architecture Adoption]] — adopt/skip/defer choices
- [[11-Scientific-RAG-Pipeline-Survey]] — full GLM-5 survey of 18 candidate projects

## Recent Session Context

- **2026-05-05**: L1 Marker production rollout reconciliation. Validation failed — blocked. Two papers timed out: `2604.21675` (6 pages, ML) at 1200.5s (box 114 alone = 273s); `2510.15205` (25 pages, math-heavy) at 1800.2s. Root cause: cold model load 136-270s + math-dense box spikes up to 273s/box; page count is not predictive of processing time. Scheduler validation not safe: no single-paper submit path, hardcoded topic searches, thread-based (not process-boundary) timeout, Marker disabled for entire process on first timeout, scheduler success metadata too coarse. Work packet updated to BLOCKED. New packet created: [[Work-Packet - Marker Single-Paper Validation Control Surface]]. CURRENT_DEVELOPMENT Feature 3 moved to Blocked/Deferred. Dev log: `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md`.
- **2026-05-03**: L1 Marker validation session. Codex FAIL (3 blockers) resolved: (1) `AcademicAdapter` now blocks `marker_failed` from becoming abstract — `body=""` explicit rejection; (2) `start_research_scheduler(exclude_job_ids=...)` + `--exclude-jobs academic_ingest` on CPU service implements scheduler split; (3) docker-compose.yml cache mount corrected to `/home/polytool/.cache/datalab`. 7 new tests (76 targeted pass, 2403 full suite pass). GPU validation PENDING — Docker Desktop not running in session. Run: `docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi` then `research-parser-benchmark --urls 2510.15205,2309.01454,2206.14965 --parsers marker` to close L1.
- **2026-05-03**: Academic pipeline hosting decision accepted. Docker GPU passthrough verified (RTX 2070 Super, CUDA 13.2, `docker run --gpus all` succeeds). Q1→B (Docker+GPU dev machine), Q2→confirmed, Q3→moot, Q4→academic on dev / others on partner, Q5→volume-mount host cache. L1 Marker production rollout unblocked. Next packet: [[Work-Packet - Marker Structural Parser Integration]]. Dev log: `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`.
- **2026-05-02**: L3.1 close-out. Codex PASS WITH FIXES resolved: M1 (queue write failure now visible via `queued_for_review=false` + `queue_error`), L2 (malformed JSONL warns to stderr), L1 (feature doc updated with hold-review, artifact paths, health counters), L3 (search-mode hold-review offline test added). 160/160 tests pass. Feature doc, CURRENT_DEVELOPMENT, INDEX, and Current-Focus synced. Next: use `--prefetch-filter-mode hold-review` in live acquisition sessions to accumulate labels; run `research-prefetch-review counts` to track progress toward ≥30+30 SVM trigger. Dev logs: `2026-05-02_ris-prefetch-review-queue-label-store.md`, `2026-05-02_codex-review-ris-prefetch-review-queue.md`, `2026-05-02_ris-prefetch-review-queue-fixes.md`, `2026-05-02_ris-prefetch-review-queue-closeout.md`.
- **2026-05-02**: L3 v0 close-out. Codex re-review PASS WITH FIXES. All original FAIL blockers resolved. DB-backed Scenario B=5.88%, QA REJECT=0. Title-only 6.25% overclaim corrected. Filter modes corrected: default `off`, not dry-run; flag `--prefetch-filter-mode enforce`, not `--enforce-relevance-filter`. Feature doc created. CURRENT_DEVELOPMENT Feature 3 freed. Dry-run safe; enforce experimental (Scenario A=20.0%, not <10%). Dev log: `docs/dev_logs/2026-05-02_ris-prefetch-filter-v0-closeout.md`.
- **2026-05-01**: L3 packet activation pass. L5 baseline locked 2026-05-02 (off_topic_rate=30.43%, Rule A fired). L3 promoted from stub → active. Work packet refined: v0 scope = deterministic cold-start metadata filter; v1 scope = SPECTER2/S2FOS/SVM after ≥30+30 labels. Acceptance gates set with concrete numbers. Training data plan documented (labels.jsonl path, YELLOW queue accumulation, model ledger for v1). CURRENT_DEVELOPMENT Feature 3 slot filled with L3. Dev log: `docs/dev_logs/2026-05-01_ris-prefetch-filter-packet-activation.md`.
- **2026-04-29**: Vault reconciliation pass and L5 promotion. Scientific RAG architecture review with operator. Decided: Marker becomes single production parser (no fallback), pdfplumber retires. Updated L1, L2, L3, L4 packets with reference materials and architectural changes. Created [[Decision - Academic Pipeline Hosting]] as prerequisite for L1. Promoted L5 from stub to ready with full nine-metric breakdown and corpus selection rule.
- **2026-04-27**: L0 shipped. PDF download fix landed in production with full Docker validation.
- **2026-04-22**: Reorganized Obsidian vault into two top-level folders. Added AGENT.md entry point and this Current-Focus.md file.
- **2026-04-21**: Workflow Harness Refresh session.

## Key Blockers

| Blocker | Affects | Status |
|---------|---------|--------|
| ~~Academic pipeline hosting decision~~ | ~~L1 Marker production rollout~~ | **RESOLVED 2026-05-02** — Docker GPU passthrough verified; decision accepted |
| L1 Marker validation control surface | L1 Marker production rollout | **NEW 2026-05-05** — Scheduler lacks single-paper submit path, hard cancel, and per-paper parse metadata. See [[Work-Packet - Marker Single-Paper Validation Control Surface]] |
| L5 corpus accumulation | L5 ship date | ✅ Resolved — baseline locked 2026-05-02 with 23-paper corpus |
| No active crypto 5m/15m markets | Track 1A | Monitoring |
| Gate 2 failed (7/50 = 14%) | Track 1B live deployment | Needs decision on benchmark_v2 |
| Silver tape zero-fill issue | Gate 2 sweep validity | Tied to crypto market availability |

---

*Last updated by Claude Code — 2026-05-05*

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
