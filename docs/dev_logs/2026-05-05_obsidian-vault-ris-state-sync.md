# Obsidian Vault + Repo Docs — RIS State Sync

**Date:** 2026-05-05
**Track:** Research Intelligence System (docs-only)
**Status:** Complete

---

## Objective

Sync the Obsidian vault and repo docs to the current RIS Scientific RAG state so that
`Current-Focus.md`, work packets, decision docs, and index entries accurately reflect
completed work and the next packet without requiring chat history to reconstruct context.

---

## Files Audited

| File | Result |
|------|--------|
| `docs/CURRENT_DEVELOPMENT.md` | Accurate. Feature 3 freed, L3.2 + Marker queue v0 in Recently Completed, IPC warm-worker in Paused/Deferred, Architect Notes current through 2026-05-05. |
| `docs/INDEX.md` | 3 L3.2 dev logs missing; L3 feature doc description did not mention L3.2. Fixed. |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | One stale heading ("as of 2026-05-01" → "as of 2026-05-05"). Fixed. Otherwise accurate. |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md` | Accurate. Status: completed. Label counts 30/31/1 correct. Warm-worker deferred reminder present. |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` | Accurate. Status: stub (not falsely marked implemented). Trigger condition MET documented. |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md` | Accurate. Status: implemented-v0. Queue v0 shipped; Docker IPC warm-worker deferred to v1; L1 blocked documented. |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` | Accurate. Status: blocked. Blocked-reason references async parse queue packet. |

---

## Files Changed

| File | Change |
|------|--------|
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Fixed stale heading: "RIS Scientific RAG Status (as of 2026-05-01)" → "(as of 2026-05-05)" |
| `docs/INDEX.md` | Added 3 missing L3.2 dev log entries (impl, Codex review PASS, Codex SVM trigger verify PASS) |
| `docs/INDEX.md` | Updated L3 feature doc description to note L3.2 completion + SVM trigger MET (30/31/1) |
| `docs/INDEX.md` | Added this sync dev log entry |

---

## Stale Items Corrected

1. `Current-Focus.md` section heading "as of 2026-05-01" → "as of 2026-05-05"
2. `INDEX.md` L3 feature doc description: was L3/L3.1 only; now includes L3.2 + SVM trigger status
3. `INDEX.md` missing dev logs: `l3-2-prefetch-label-discovery-impl.md`, `codex-review-l3-2-prefetch-label-discovery.md`, `codex-verify-l3-2-svm-trigger.md`

---

## Final Current-State Summary (as of 2026-05-05)

| Layer | Status |
|-------|--------|
| L0 Academic PDF ingest | ✅ Shipped 2026-04-27 — pdfplumber wired; real arXiv ingests confirmed |
| L1 Marker production rollout | **BLOCKED** — queue v0 shipped; Docker IPC warm-worker (v1) deferred; L1 stays blocked until ≥3 warm papers at ≤10s/paper |
| L2 PaperQA2 RAG Control Flow | Stub — gated on L5 + L1 production |
| L3 Pre-fetch Relevance Filter | ✅ v0 shipped 2026-05-02 (lexical scorer, 4 modes, Scenario B 5.88%) |
| L3.1 Review Queue + Label Store | ✅ Shipped 2026-05-02 (hold-review, ReviewQueueStore, LabelStore, research-prefetch-review CLI) |
| L3.2 Prefetch Label Discovery | ✅ Shipped 2026-05-05 (research-prefetch-discover, 36 tests). **SVM trigger MET: 30 allow / 31 reject / 1 pending unlabeled** |
| L3 v1 SVM Topic Filter | Stub — ready to activate; trigger MET; Director must open packet |
| L4 Multi-source Harvesters | Stub — gated on L1 + L3 |
| L5 Scientific RAG Eval Benchmark | ✅ Shipped 2026-05-02 — baseline locked (corpus=23, P@5=1.0, off_topic_rate=30.43%, Recommendation A) |

**Active count:** 2 (Feature 1: Track 2 Paper Soak; Feature 2: RIS Phase 2A). Feature 3 slot FREE.

**Deferred (NOT canceled):** Marker Docker/Linux IPC warm-worker (Queue v1, Option A). Must be
revisited after L3/SVM stream completes or before L2 production launch, whichever comes first.

---

## Next Recommended Packet

**L3 v1 SVM Topic Filter Readiness + Training**

- Trigger: ≥30 allow + ≥30 reject labels — MET (30 allow / 31 reject as of 2026-05-05)
- Scope: SPECTER2 + S2FOS embeddings + SVM classifier trained on `artifacts/research/svm_filter_labels/labels.jsonl`
- Replaces lexical `RelevanceScorer` with a learned model that generalizes beyond keyword overlap
- Evaluate precision/recall vs. lexical v1.1 baseline (Scenario B 5.88% off-topic rate)
- Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` (status: stub, ready to activate)
- Director must explicitly open this packet before implementation begins

---

## Remaining Docs Debt (not fixed in this session)

- `CURRENT_DEVELOPMENT.md` Feature 2 "Last updated: 2026-04-23" is 12 days old (beyond 7-day staleness rule). Content is still accurate (implementation done, e2e validation pending). Update when Feature 2 advances.
- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — feature doc was not updated at L3.2 closeout to document `research-prefetch-discover` CLI. Low priority since INDEX description now covers L3.2 completion.
- 4 completion-doc items from 2026-04-14/15 remain backlogged (see CURRENT_DEVELOPMENT.md Completion-Doc Debt section).

---

## Verification

- `git diff --check` — 0 whitespace errors (LF/CRLF warnings in obsidian-vault `.ajson` files only; non-blocking; pre-existing)
- No runtime code touched
- No tests touched
- No artifacts/ touched
- All referenced dev log paths verified to exist in `docs/dev_logs/`
- All referenced work packet paths verified to exist in `docs/obsidian-vault/Claude Desktop/12-Ideas/`
