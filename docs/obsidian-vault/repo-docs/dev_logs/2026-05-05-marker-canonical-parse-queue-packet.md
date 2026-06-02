---
title: Marker Canonical Parse Queue Packet
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_marker-canonical-parse-queue-packet.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Canonical Academic Parse Queue — Packet Creation

Date: 2026-05-05
Scope: Activate operator decision, create async parse queue work packet, update governing docs.
Status: COMPLETE (docs-only — no code changes)

---

## Operator Decision Recorded

Following control surface validation (`parse_seconds=85.95s` >> ≤10s/paper gate),
the operator has chosen **Option A: async parse queue** as the path to Marker-only
canonical academic embeddings.

Key decisions:

- **pdfplumber is legacy/debug only.** `RIS_PDF_PARSER=pdfplumber` remains as a debug
  override but is not used in any production academic corpus path.
- **Final academic embeddings must be Marker-only.** Papers with `body_source` other than
  `"marker"` are not RAG-indexed in the canonical corpus.
- **Synchronous Marker per-paper inline ingest is not the path.** Cold-start model load
  (~80s) makes one-shot invocation unviable. The warm-worker approach is the solution.
- **A warm GPU worker is the canonical parse path.** Models load once at worker start;
  subsequent papers on RTX 2070 Super are expected at ≤10s/paper (warm VRAM).

---

## What Was Created

### New Work Packet

**`docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`**

Status: `ready`. Key contents:

**State model:**

| State | Meaning |
|-------|---------|
| `discovered` | Metadata only; no body |
| `marker_queued` | Enqueued; not yet picked up |
| `marker_processing` | Worker actively parsing |
| `marker_ready` | `body_source=marker`; RAG-eligible |
| `marker_failed_retryable` | Transient failure; eligible for re-queue (default max: 3 retries) |
| `marker_failed_terminal` | Permanent failure; image-only PDF, corrupt, or max retries exceeded |
| `rag_ready` | Indexed in ChromaDB; active in retrieval |

**Acceptance gates (9 total):**

1. Queue accepts candidates (no inline parse; metadata stored first)
2. Worker processes ≥3 papers in one warm session
3. Papers 2+ show `parse_seconds ≤10s` (warm VRAM; no model reload)
4. Output includes `body_source`, `body_length`, `parse_seconds`, `failure_reason`, structured_metadata flag
5. Embedding path refuses non-marker bodies by default
6. No pdfplumber fallback — Marker failure → `marker_failed_*`, not pdfplumber downgrade
7. Queue persists across worker restarts (SQLite or file-backed)
8. Existing tests still pass (no regressions)
9. Dev log written with warm-model timing evidence

**Architecture:** discovery → enqueue → ParseQueue → MarkerWorker (warm) → RawSourceCache → EmbeddingPipeline (marker-only gate) → ChromaDB

---

## Status Changes Made

| Document | Change |
|----------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md` | **CREATED** — new work packet; status: ready |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` | `blocked-reason` updated with operator decision; DANGER callout updated to show Option A chosen and new packet link |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L1 table updated; "Operator decision needed" → "Option A chosen, Feature 3 assigned"; Key Blockers updated; session context added |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 added (Marker Canonical Academic Parse Queue); L1 Paused/Deferred row updated with Option A decision; architect note updated |
| `docs/INDEX.md` | New dev log row; features entry for scaffold updated to reflect operator decision |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Status updated; operator decision noted; pdfplumber-as-legacy clarified; new packet cross-referenced |

---

## What Was NOT Changed

Per scope constraints:
- No parser runtime code changed
- No Docker configuration changed
- No scheduler implementation changed
- No L2/PaperQA2 work touched
- No L3/SVM/label store changed
- No L4 harvester work touched
- No trading or n8n code touched

---

## L1 Production Status

L1 Marker production rollout remains **BLOCKED** pending async queue implementation.
The operator decision removes the "awaiting decision" blocker but replaces it with
"queue not yet implemented."

Resume criteria for L1:
- [[Work-Packet - Marker Canonical Academic Parse Queue]] ships
- Warm worker processes ≥3 papers with `parse_seconds ≤10s` for papers 2+
- Embedding pipeline Marker-only gate confirmed end-to-end

L2 remains blocked. Do NOT start L2 until L1 queue ships.

---

## Next Implementation Handoff

The next coding session should implement:

1. `packages/research/ingestion/queue.py` — `ParseQueue` (SQLite-backed preferred; check `LabelStore` pattern)
2. `packages/research/ingestion/worker.py` — `MarkerWorker` (warm-load loop; process-boundary cancel from `extractors.py`)
3. `packages/research/ingestion/fetchers.py` — enqueue mode in `LiveAcademicFetcher`
4. `packages/research/ingestion/pipeline.py` — `body_source=marker` enforcement gate
5. `tools/cli/research_scheduler.py` — `run-marker-worker` subcommand
6. `tests/test_ris_parse_queue.py` — ≥6 tests

Key reference: `packages/research/ingestion/extractors.py` (current `MarkerPDFExtractor` + process-boundary cancel),
`packages/research/scheduling/scheduler.py` (`run-academic-url` pattern to follow for `run-marker-worker`).

---

## Codex Review

Tier: Skip — docs-only session; no code changes made.
