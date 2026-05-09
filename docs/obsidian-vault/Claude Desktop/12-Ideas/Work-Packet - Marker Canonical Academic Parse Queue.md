---
tags: [work-packet, ris, ingestion, academic, parser, async-queue]
date: 2026-05-05
status: implemented-v0
priority: high
phase: 2
target-layer: 1
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Academic Pipeline Hosting]]"
prerequisites:
  - "[[Work-Packet - Marker Single-Paper Validation Control Surface]] — VALIDATED 2026-05-05"
  - "Operator decision on Marker production strategy — RESOLVED 2026-05-05: Option A (async parse queue)"
supersedes: "Option A in [[Work-Packet - Marker Structural Parser Integration]]'s DANGER callout"
unblocks:
  - "[[Work-Packet - Marker Structural Parser Integration]] — L1 warm-worker blocker resolved 2026-05-08; next L1 rollout/readiness step requires separate workpacket/Director decision"
  - "[[Work-Packet - PaperQA2 RAG Control Flow]] — L2 gated on Marker-parsed corpus (v0 queue satisfies code-side gate; live corpus needs warm-worker)"
---

# Work Packet — Marker Canonical Academic Parse Queue

> [!SUCCESS] Operator Decision Recorded: Option A — Async Parse Queue (2026-05-05)
> Control surface validation confirmed Marker works on GPU but is too slow for synchronous
> default production (`parse_seconds=85.95s` on a 15-page prose paper; ≤10s gate fails by ~8.6×).
> Cold-start model load (~80s) dominates per-paper budget in one-shot `docker compose run --rm` mode.
>
> **Operator decision: async parse queue is the implementation path.**
>
> - pdfplumber is **legacy/debug only** (`RIS_PDF_PARSER=pdfplumber` is a debug override, not production)
> - Final academic embeddings must be **Marker-only** for corpus consistency
> - New papers are discovered and enqueued immediately; Marker parse happens asynchronously
> - A warm GPU worker loads models once and processes the queue — no cold-load per paper
> - RAG-ready status requires `body_source=marker`; pdfplumber-parsed papers are not RAG-eligible

> [!SUCCESS] Implementation Status: v0 Shipped — Docker IPC Warm-Worker v1 Closed 2026-05-08
> Codex re-review PASS. Queue v0 is complete. IPC warm-worker v1 closed 2026-05-08 under revised functional gate. L1 warm-worker blocker resolved; next L1 production/readiness step requires separate workpacket/Director decision.
>
> **v0 Shipped (offline-only; no Docker validation required):**
> - File-backed parse queue (`queue.jsonl` + `results.jsonl`), surviving worker restarts
> - CLI surface: `enqueue`, `list`, `process`, `counts`
> - `is_marker_ready(body_source, body_length)` — canonical RAG-readiness rule
> - Short Marker body rejection: retryable until `MAX_ATTEMPTS=3`, then `failed`; `failure_reason` populated
> - Marker-only academic indexing gate in `IngestPipeline.ingest_external()` — rejects pdfplumber/abstract/marker_failed
> - Honest platform docs: Windows thread mode = warm (pre-loads model dict once); Linux/Docker subprocess = cold per paper
> - `create_warm_thread_worker()` on `LiveAcademicFetcher` for Windows warm-batch sessions
> - 43 offline tests; Codex re-review PASS
>
> **v1 Recently Completed Feature 3 (Docker IPC warm-worker — closed 2026-05-08):**
> - Persistent subprocess on Linux/Docker with IPC (sockets/pipes) — keeps models loaded across papers
> - Multi-paper warm throughput validation: ≥3 papers; papers 2+ delta (total_seconds − parse_seconds) ≤5s; `ipc_warm_worker_used=true`
> - Original `parse_seconds ≤10s` timing gate **rejected as unrealistic (Director 2026-05-08)**; revised functional gate PASS — see `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
> - L1 warm-worker blocker resolved; next L1 rollout/readiness step requires separate workpacket/Director decision
> - Acceptance gates 2 and 3 from this packet are governed by the revised gate (see Feature 3 closeout)
>
> **Close-out log:** `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md`

## Goal

Deliver a persistent async parse queue so that:

1. Paper discovery is decoupled from Marker parse time (enqueue immediately, parse later)
2. A long-running GPU worker processes the queue with warm models (original ≤10s/paper timing target; **revised gate 2026-05-08:** papers 2+ delta ≤5s, cold-load overhead eliminated — see Feature 3)
3. Only Marker-parsed papers (`body_source=marker`) reach the academic RAG embedding step
4. pdfplumber is not used in the canonical academic corpus production path
5. The queue survives worker restarts and tracks per-paper parse state

## Non-Goals

- Synchronous Marker as the default inline ingest parser (proven not viable at cold-start speed)
- pdfplumber as a production fallback for any canonical corpus paper
- Layer 2 changes (PaperQA2 RAG Control Flow — gated on this packet shipping)
- Gate 2, benchmark, or trading code — not touched
- LLM-enriched Marker extraction — deferred to Layer 2
- Bulk re-ingest of existing pdfplumber-parsed corpus — separate cleanup task

---

## Paper State Model

Each academic paper in the RIS ingestion pipeline moves through the following states:

| State | Meaning |
|-------|---------|
| `discovered` | arXiv ID and metadata stored; no body text yet |
| `marker_queued` | Enqueued for Marker parse; not yet picked up by worker |
| `marker_processing` | Marker worker actively parsing this paper |
| `marker_ready` | Parse succeeded; `body_source=marker`; eligible for ChromaDB indexing |
| `marker_failed_retryable` | Parse failed; transient error (timeout, container restart); eligible for re-queue |
| `marker_failed_terminal` | Parse failed permanently; image-only PDF, corrupt file, or max retries exceeded |
| `rag_ready` | Marker-parsed body indexed in ChromaDB; active in retrieval |

**Key invariant: `rag_ready` requires `body_source=marker`.**
Papers in `discovered`, `marker_queued`, or `marker_failed_*` states are not indexed in ChromaDB.

---

## Acceptance Gates

1. **Queue accepts candidates.** A paper can be enqueued via `research-acquire --url <arxiv-id>` (or scheduler academic_ingest job) without triggering an inline Marker parse. Metadata (title, abstract, authors, arxiv_id) is written before parse starts. Paper state transitions to `marker_queued`.

2. **Worker processes ≥3 papers in one warm session.** A single long-running `MarkerWorker` inside the `ris-scheduler-gpu` container loads models once, then consumes the queue sequentially. ≥3 papers complete in one session.

3. **No per-paper cold-load after first paper.** Papers 2–N in the same worker session show `parse_seconds` consistent with warm-model throughput. ~~≤10s/paper for a typical 10–20 page prose paper on RTX 2070 Super~~ — **timing gate rejected as unrealistic (Director 2026-05-08).** Revised gate: papers 2+ delta (total_seconds − parse_seconds) ≤5s (cold-load overhead eliminated); per-paper inference ~45–70s is a hardware constant on RTX 2070 Super. Paper 1 cold-load overhead (delta ~27s) is expected and acceptable. Evidence: paper 2 delta=0.13s, paper 3 delta=0.22s. See Feature 3 closeout for full timing record.

4. **Output includes canonical fields.** For each processed paper the queue record contains:
   `body_source` (`"marker"` or `"marker_failed_*"`), `body_length`, `parse_seconds`, `failure_reason` (null on success), and `has_structured_metadata` flag.

5. **Embedding path enforces Marker-only.** The ChromaDB indexing step (academic embedding pipeline) refuses papers with `body_source` other than `"marker"` by default. Attempts to index a pdfplumber-parsed paper log a warning and skip the paper rather than silently ingesting low-fidelity chunks.

6. **No pdfplumber fallback in canonical path.** When Marker fails on a paper, the paper transitions to `marker_failed_retryable` or `marker_failed_terminal` — never downgraded to pdfplumber output. `failure_reason` is populated. The rejection is logged to the acquisition review JSONL.

7. **Queue persistence.** Queued papers survive a worker restart — the queue is backed by a persistent store (SQLite or file-backed JSONL under `artifacts/research/`). Re-starting the worker resumes from the same queue without re-discovering papers.

8. **Existing tests still pass.** `pytest tests/ -x -q --tb=short` reports the same pass count as pre-implementation. No regressions in non-queue tests.

9. **Dev log written.** `docs/dev_logs/YYYY-MM-DD_marker-canonical-parse-queue-impl.md` documents warm-model timing evidence (parse_seconds for papers 1, 2, 3+) and any rejected papers found during worker validation.

---

## Architecture Sketch

```
research-acquire --url <id>  OR  scheduler academic_ingest job
         ↓
   [DiscoveryPipeline]
   - Fetches arXiv metadata (title, abstract, authors)
   - Writes to RawSourceCache (metadata only; body_text="")
   - Enqueues paper_id → ParseQueue
   - paper_state = "marker_queued"
         ↓
   [ParseQueue]  (persistent; SQLite or JSONL in artifacts/research/parse_queue/)
         ↑
   [MarkerWorker]  (long-running; inside ris-scheduler-gpu container)
   - Loads Marker/surya models once at startup
   - Polls queue for "marker_queued" entries
   - Updates paper_state → "marker_processing"
   - Calls MarkerPDFExtractor.extract() for each paper
   - On success: writes body_text, body_source="marker", parse_seconds → RawSourceCache
               updates paper_state → "marker_ready"
   - On failure: writes failure_reason → RawSourceCache
               updates paper_state → "marker_failed_retryable" (or terminal after max retries)
         ↓
   [EmbeddingPipeline]
   - Accepts only body_source="marker" papers
   - Chunks body_text via existing chunker
   - Indexes into ChromaDB → paper_state = "rag_ready"
```

---

## Files Expected to Change

| File | Change | Review level |
|------|--------|-------------|
| `packages/research/ingestion/queue.py` (new) | `ParseQueue`: enqueue, dequeue, update_state, list_pending, list_by_state | Mandatory |
| `packages/research/ingestion/worker.py` (new) | `MarkerWorker`: warm-load loop, queue consumer, state machine, retry policy | Mandatory |
| `packages/research/ingestion/fetchers.py` | `LiveAcademicFetcher`: enqueue mode — enqueue paper and return without inline Marker parse when queue is active | Mandatory |
| `packages/research/ingestion/pipeline.py` | Embedding step: add `body_source=marker` enforcement gate; log warning and skip non-marker papers | Mandatory |
| `tools/cli/research_scheduler.py` | Add `run-marker-worker` subcommand to start the warm worker process | Mandatory |
| `tests/test_ris_parse_queue.py` (new) | Queue state transitions, worker enqueue/dequeue, Marker-only gate, queue persistence, failure handling | Mandatory |
| `docs/dev_logs/YYYY-MM-DD_marker-canonical-parse-queue-impl.md` | New dev log with warm-model timing evidence | Mandatory |
| `docs/features/ris-marker-canonical-parse-queue.md` | New feature doc on ship | Mandatory |

---

## Open Questions for Architect

1. **Queue storage format.** SQLite (reuse pattern from `LabelStore`) vs file-backed JSONL (reuse pattern from `ReviewQueueStore`). SQLite preferred for atomic state transitions and `list_by_state` queries. Confirm with existing `packages/research/` patterns before deciding.

2. **Worker trigger (v0 scope).** For v0: manual trigger only (`research-scheduler run-marker-worker`). Automatic worker startup on `ris-scheduler-gpu` service start is deferred to v1. This keeps v0 scope tight.

3. **Re-queue policy.** `marker_failed_retryable` default retry count: 3. After 3 failures the paper transitions to `marker_failed_terminal`. Configurable via `--max-retries` flag.

4. **Existing pdfplumber-parsed papers in ChromaDB.** Papers already indexed with `body_source=pdf` remain until a separate cleanup pass re-parses them through the queue. This packet does not retroactively clear the existing corpus.

5. **Interaction with `research-acquire` and scheduler split.** Currently `research_acquire.main()` calls `LiveAcademicFetcher` synchronously. In queue mode it should enqueue and return immediately. May require a `--parse-mode queue` flag on `research-acquire` and a corresponding `--parse-mode` scheduler job config. Verify against the existing `exclude_job_ids` scheduler split before designing.

---

## Reference Materials

1. `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md` — performance evidence; warm-model assumption validated (paper 1 = 85.95s cold; ~~papers 2+ expected ≤10s warm~~ — **timing gate rejected as unrealistic 2026-05-08; measured warm times: 69.73s paper 2, 48.31s paper 3 — see Feature 3**)
2. `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md` — why synchronous default failed; Option A rationale
3. `docs/features/ris-marker-structural-parser-scaffold.md` — existing `MarkerPDFExtractor`, `_MARKER_DISABLED` guard, concurrency design, process-boundary cancel
4. `packages/research/ingestion/extractors.py` — current `MarkerPDFExtractor` with process-boundary cancel
5. `packages/research/ingestion/queue.py` (search: `ReviewQueueStore`) — SQLite queue pattern in L3
6. [[Work-Packet - Marker Single-Paper Validation Control Surface]] — `run-academic-url`; warm-vs-cold timing evidence

---

## Cross-References

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Work-Packet - Marker Structural Parser Integration]] — L1 production rollout; blocked pending this packet
- [[Work-Packet - PaperQA2 RAG Control Flow]] — L2; gated on this packet shipping
- [[Decision - Academic Pipeline Hosting]] — Docker GPU passthrough confirmed; RTX 2070 Super
- [[Work-Packet - Marker Single-Paper Validation Control Surface]] — VALIDATED; control surface tooling
- `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md`
- `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md`
