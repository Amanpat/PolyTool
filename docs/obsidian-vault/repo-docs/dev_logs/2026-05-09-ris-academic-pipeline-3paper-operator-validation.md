---
title: Ris Academic Pipeline 3Paper Operator Validation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Academic Pipeline — 3-Paper Operator Validation (2026-05-09)

**Date:** 2026-05-09  
**Type:** Docs-only validation record  
**Track:** Research Intelligence System — L1/L2/L4

---

## Summary

The full academic pipeline — enqueue → warm-process → index-done → research-query — was
operator-tested end-to-end using an isolated 3-paper queue (`artifacts/research/operator_test_queue_3paper`).

This run used the **Windows/local warm-thread path** (`ipc_warm_worker_used=false`). It
is a functional validation, not a Docker/GPU performance run. The pipeline is confirmed
operator-tested v1.

---

## Commands Executed

```bash
# Enqueue 3 arXiv papers
python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_3paper enqueue --url 2604.24366
python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_3paper enqueue --url 2109.07581
python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_3paper enqueue --url 1910.08858

# Parse with warm-thread worker (Windows local path)
python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_3paper warm-process --max-items 3

# Index into KnowledgeStore + auto-extract claims
python -m polytool research-marker-queue --queue-dir artifacts/research/operator_test_queue_3paper index-done

# Query the indexed corpus
python -m polytool research-query --question "prediction markets"
python -m polytool research-query --question "sports betting markets" --k 10 --step-back
```

---

## Results

### Queue State After warm-process

| Status | Count |
|--------|-------|
| done   | 3     |
| failed | 0     |
| pending | 0    |

### Paper Results

| Paper | body_source | body_length (chars) | chunks | claims | ipc_warm_worker_used |
|-------|------------|---------------------|--------|--------|---------------------|
| arxiv:2604.24366 | marker | 56,856 | 25 | 125 | false |
| arxiv:2109.07581 | marker | 51,370 | 23 | 115 | false |
| arxiv:1910.08858 | marker | 60,814 | 31 | 133 | false |

**Totals:** 79 chunks, 373 claims across 3 papers.

All 3 papers have `body_source=marker` and `body_length >= 5000` — fully RAG-ready.

### Query Results

| Query | had_fallback | Marker citations returned |
|-------|-------------|--------------------------|
| `"prediction markets"` | false | Yes (body_source=marker confirmed) |
| `"sports betting markets" --k 10 --step-back` | false | 2 (body_source=marker confirmed) |

Both queries hit the Marker-indexed corpus without fallback. `had_fallback=false` confirms no
empty-corpus fallback path was exercised.

---

## Caveats

1. **Windows/local warm-thread path.** `ipc_warm_worker_used=false` for all 3 papers. The
   thread warm-worker pre-loads the Marker model dict once and processes papers sequentially.
   This is a dev/debug path — not the Linux/Docker IPC production path.

2. **Docker/GPU IPC performance validation is separate and optional.** The Linux/Docker IPC
   warm-worker was validated independently on 2026-05-08 with 3 papers and `ipc_warm_worker_used=true`
   (timings: 45.55s / 69.73s / 48.31s; papers 2–3 delta: 0.13s / 0.22s). It is an optional
   performance/infra follow-up, not a functional blocker for the pipeline.

3. **SSRN/NBER deferred.** Only arXiv papers were used in this run. Crossref/OpenReview
   candidates discovered by L4 harvesters may require operator resolution to an arXiv URL
   before the current Marker queue can parse them.

4. **ChromaDB academic retrieval deferred (L2.1).** `research-query` uses the KnowledgeStore
   (SQLite) path only. ChromaDB chunk metadata does not yet store `body_source`. This is a
   known deferred item (L2.1).

---

## Docs Updated in This Session

| File | Change |
|------|--------|
| `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md` | Created (this file) |
| `docs/CURRENT_STATE.md` | Added operator-tested v1 section at end |
| `docs/CURRENT_DEVELOPMENT.md` | Added validation entry to Recently Completed; updated Architect Notes |
| `docs/INDEX.md` | Added this dev log to Recent Dev Logs |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Added Known-good 3-paper validation section |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Updated academic pipeline status |
| `docs/obsidian-vault/.../Work-Packet - PaperQA2 RAG Control Flow.md` | Added operator-tested note |
| `docs/obsidian-vault/.../Work-Packet - Multi-source Academic Harvesters.md` | Added arXiv path operator-tested note |
| `docs/obsidian-vault/.../Work-Packet - Marker Docker IPC Warm-Worker v1.md` | Added Windows e2e note |
| `docs/obsidian-vault/.../Work-Packet - Marker Canonical Academic Parse Queue.md` | Added 3-paper validation note |

---

## Remaining Optional Follow-ups

| Item | Type | Blocker? |
|------|------|---------|
| Docker/GPU IPC 3-paper batch repeat (`ipc_warm_worker_used=true`) | Performance/infra validation | No — optional |
| Crossref/OpenReview non-arXiv URL resolution path | Discovery quality | No — deferred |
| ChromaDB academic retrieval path (L2.1 — `body_source` in chunk metadata) | Retrieval quality | No — deferred |
| Discovery quality tuning (relevance, SSRN/NBER, L3 coverage) | Scope expansion | No — future |
