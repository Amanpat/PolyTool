---
title: Marker Docker Ipc Warm Worker V1
type: reference
status: complete
completed: 2026-05-08
track: Research Intelligence System
layer: L1
source_zone: repo
mirror_of: docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md
last_synced: '2026-05-25T22:14:18Z'
lifecycle: reviewed
generator: repo-sync
---

# Feature: Marker Docker IPC Warm-Worker v1

**Completed:** 2026-05-08
**Track:** Research Intelligence System — L1 Marker Academic Parse Queue
**Feature doc:** `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`

---

## What Shipped

### IPC Warm-Worker Process (`marker_ipc_worker.py`)

A persistent subprocess (`IpcMarkerWorker`) lives inside the `ris-scheduler-gpu` Docker
container for the duration of a parse session. Marker models load once at startup and
remain in GPU VRAM across all queued papers. An IPC channel (Unix domain socket at
`/tmp/marker_worker.sock`) dispatches parse requests from the queue consumer to the
persistent worker process.

**daemon=False fix:** The worker process is spawned with `daemon=False`. On Linux, daemon
processes cannot spawn child processes (multiprocessing restriction). The fix was required
for the IPC worker subprocess to spawn Marker's internal child processes for surya layout
detection. This unblocked the daemonic-process `RuntimeError` seen in initial validation.

### Queue Consumer Integration (`marker_queue.py`)

`MarkerParseQueue.process_next_ipc()` dispatches parse requests to the IPC worker and
collects results. The `_extra_result_fields` parameter was added to `process_next()` to
include `ipc_warm_worker_used` in `result_record` before `_append_result()` writes to
`results.jsonl` — ensuring the field is persisted to disk rather than only appearing in
the live command JSON output.

### Direct-PDF Validation Path (`fetchers.py`)

`fetch_pdf_direct()` added to the fetcher to support `--pdf-url` queue items. This
bypasses the standard arXiv URL resolution and downloads PDFs directly, enabling isolated
queue validation without depending on the normal ingestion chain.

### CLI Surface (`research_marker_queue.py`)

- `research-marker-queue warm-process` — starts the IPC warm-worker and processes queued
  papers. Accepts `--max-items N` and `--marker-timeout SECONDS`.
- `research-marker-queue enqueue --pdf-url URL` — enqueue a paper by direct PDF URL for
  isolated validation.

### Result Evidence Persistence

`ipc_warm_worker_used=true` is now persisted in `results.jsonl` for all papers processed
through the IPC warm-worker path. The field is `false` for non-IPC (subprocess-per-paper)
path entries. Verified by 4 new tests in `TestIPCResultPersistence`.

---

## Platform Behavior

| Platform | Warm mode | Production? |
|----------|-----------|-------------|
| Windows local dev | Thread mode (`create_warm_thread_worker()`) — pre-loads model dict once in thread | Dev/debug only |
| Linux/Docker (v0) | Subprocess per paper — cold model load each time (~136–270s) | NOT production |
| Linux/Docker (v1) | **IPC warm worker — models load once, stay in GPU VRAM across papers** | **Production target** |

v1 does NOT change Windows behavior. Thread mode remains available on Windows for local
dev. IPC is Linux/Docker only.

---

## Revised Functional Gate (Director-Approved 2026-05-08)

The original ≤10s/paper timing gate for papers 2+ was **rejected as unrealistic** for
full academic PDFs on the RTX 2070 Super and replaced with a functional warm-worker gate.

**Why ≤10s was rejected:** Marker runs a five-stage multi-model pipeline per paper (layout
detection, OCR error detection, bounding box detection, text recognition, table
recognition). Full academic PDFs (15–46 pages) require ~45–70s warm inference on the
RTX 2070 Super. The ≤10s target was aspirational and derived from an over-optimistic
estimate that assumed a synthetic benchmark, not real academic PDFs. No measured evidence
ever existed for ≤10s on this hardware.

**What the warm-worker actually delivers:**

- Cold-load overhead eliminated for papers 2+. Paper 1 pays the one-time model load;
  papers 2+ pay only inference + queue overhead.
- All papers parse successfully with `body_source=marker`, no pdfplumber fallback, no
  daemon error.
- Per-paper inference time (~45–70s) is a hardware constant for this paper complexity — it
  cannot be reduced by IPC warm-worker design. It is NOT a regression.

**Revised functional gate (replaces ≤10s):**

| Criterion | Threshold | Evidence |
|-----------|-----------|----------|
| ≥3 full academic PDFs in one warm session | all done | done=3, failed=0 |
| Papers 2+ delta ≤5s | cold-load not repeated | paper 2: 0.13s, paper 3: 0.22s |
| `body_source=marker` all papers | true | all 3 |
| `ipc_warm_worker_used=true` all papers | true | all 3 |
| No pdfplumber fallback | none | confirmed |
| No daemon-process error | none | confirmed |
| Clean shutdown, no orphans | exit_code=0 | confirmed |
| `ipc_warm_worker_used` persisted in `results.jsonl` | fix applied | 4 new tests pass |

---

## Live Validation Evidence (2026-05-08)

Session: 3 full academic PDFs in one Docker/GPU warm-worker session on the RTX 2070 Super
(CUDA 13.2). No container restart. No pdfplumber fallback. Clean shutdown (done=3, failed=0).

| Paper | arxiv_id | parse_seconds | total_seconds | delta | body_source | ipc_warm_worker_used |
|-------|----------|--------------|--------------|-------|-------------|----------------------|
| 1 (Polymarket microstructure) | 2604.24366 | 45.55s | 72.31s | **26.76s (cold-load)** | marker | true |
| 2 (COVID-19 sports betting) | 2109.07581 | 69.73s | 69.86s | **0.13s (warm)** | marker | true |
| 3 (Sports betting inefficiencies) | 1910.08858 | 48.31s | 48.53s | **0.22s (warm)** | marker | true |

Papers 2–3 delta ≈ 0.13–0.22s confirms cold-load overhead is eliminated. Models stay warm
in GPU VRAM across the session.

Artifacts (gitignored, read-only evidence):
- `artifacts/research/marker_ipc_validation/daemon_fix_direct_pdf_live_20260508_115111.log`
- `artifacts/research/marker_validation_queue_direct/queue.jsonl`
- `artifacts/research/marker_validation_queue_direct/results.jsonl`

---

## What This Feature Improves (and What It Does Not)

**Improves:** Process/model warm lifecycle on Linux/Docker. Models load once; papers 2+
pay only inference cost, not cold-start overhead. Eliminates 26s+ per-paper cold-start
tax on all papers after the first.

**Does NOT improve:** Marker per-page inference speed. Per-paper latency (~45–70s) is
determined by Marker's multi-model pipeline and the RTX 2070 Super's GPU throughput —
this is a hardware/software constant, not a bug or regression.

**Does NOT affect:** SVM enforce, L2 PaperQA2, L4 harvesters, trading code, Gate 2,
benchmark, or any non-RIS component.

---

## Safety and Scope Limits

- pdfplumber is legacy/debug only. No pdfplumber path exists in any production parse code.
- L2 PaperQA2 RAG Control Flow and L4 Multi-source Academic Harvesters were
  completed later on 2026-05-09.
- No automatic warm-worker startup on container boot. v1 scope: manual trigger only
  (`research-marker-queue warm-process`). Auto-start deferred to a future hardening pass.
- No bulk re-ingest of existing pdfplumber-parsed ChromaDB entries. Separate cleanup task.
- No SVM, Gate 2, benchmark, or trading changes.

---

## Tests

- `tests/test_ris_marker_ipc_worker.py` — IPC worker startup (mocked IPC), parse
  dispatch, multi-paper warm session, state transition callbacks, platform branch
  isolation.
- `tests/test_ris_marker_queue.py` — extended with `TestIPCResultPersistence` (4 new
  tests): `ipc_warm_worker_used` persisted when IPC worker provided; `false` when not;
  backward-compatible non-IPC path unchanged; multi-paper all have flag persisted.

Combined: 158 passed, 1 skipped (Linux-only platform skip correct on Windows).

---

## Remaining Work / Follow-On Items

| Item | Status | Resume trigger |
|------|--------|----------------|
| L1 Marker Production Rollout — scheduling + full queue pipeline | Complete 2026-05-09 | See `FEATURE-ris-l1-marker-production-readiness-rollout.md` |
| Automatic warm-worker startup on `ris-scheduler-gpu` boot | Deferred | Post-v1 hardening pass, once a full queue session is stable |
| IPC channel crash recovery / reconnect | Deferred | Post-v1 hardening pass |
| Bulk re-ingest of pdfplumber-parsed corpus | Deferred | After warm-worker is stable processing a full queue |
| L2 PaperQA2 RAG Control Flow | Complete 2026-05-09 | See `FEATURE-ris-l2-academic-query.md` |
| L4 Multi-source Academic Harvesters | Complete 2026-05-09 | See `FEATURE-ris-l4-multisource-academic-harvesters.md` |

---

## Dev Logs

| Log | Date | Topic |
|-----|------|-------|
| [Marker IPC — Revised Gate and Result Evidence](../dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md) | 2026-05-08 | Persistence fix, Director gate revision, revised gate recorded |
| [Marker IPC Daemon-Fix Direct-PDF Live Validation](../dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md) | 2026-05-08 | Live Docker/GPU session: 3 papers, warm-worker validated |
| [Codex Verify: Marker IPC Warm-Worker v1 Live Validation](../dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md) | 2026-05-07 | Codex PASS — live validation confirmed all revised functional gates |
| [Marker Docker IPC Warm-Worker v1 Closeout](../dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md) | 2026-05-08 | Completion protocol checklist, files changed, validation evidence summary |
