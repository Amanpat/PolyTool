---
tags: [work-packet, ris, ingestion, academic, parser, ipc, docker, linux, warm-worker]
date: 2026-05-07
status: closed
priority: high
phase: 2
target-layer: 1
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
prerequisites:
  - "[[Work-Packet - Marker Canonical Academic Parse Queue]] — v0 SHIPPED 2026-05-05 (queue, CLI, indexing gate, 43 tests; Codex re-review PASS)"
  - "[[Decision - Academic Pipeline Hosting]] — RESOLVED 2026-05-02: Docker+GPU on dev machine; RTX 2070 Super; CUDA 13.2"
supersedes: "v0 thread-based warm worker (Windows local only; not suitable for Linux/Docker production)"
unblocks:
  - "[[Work-Packet - Marker Structural Parser Integration]] — L1 production rollout gated on this packet passing all acceptance gates"
  - "[[Work-Packet - PaperQA2 RAG Control Flow]] — L2 explicitly blocked until warm-worker acceptance gates pass"
---

# Work Packet — Marker Docker IPC Warm-Worker v1

> [!INFO] Status: CLOSED — Feature 3 complete (2026-05-08)
> All revised functional gates PASS. Completion protocol executed 2026-05-08.
> Feature doc: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`.
> **Live validation 2026-05-08 (Linux/Docker IPC)**: daemon=False fix confirmed; 3 papers completed in one warm session; `body_source=marker` all 3; `ipc_warm_worker_used=true` all 3; no daemonic error; clean shutdown (done=3, failed=0). Timings: 45.55s / 69.73s / 48.31s. Papers 2–3 delta: 0.13s / 0.22s.
> **Director gate revision 2026-05-08**: Original ≤10s/paper timing gate rejected/superseded as unrealistic for full academic PDFs on RTX 2070 Super. Revised functional gate (see Director Gate Revision section below) — all criteria PASS.
> **L1 Marker production rollout is UNBLOCKED** — resume at next explicit Director workpacket.
> **L2 PaperQA2 RAG Control Flow remains STUB** — gated on L1 production rollout completion. Do NOT activate.
>
> **End-to-end validation 2026-05-09 (Windows/local warm-thread path)**: Full pipeline
> (enqueue→warm-process→index-done→research-query) passed with 3 arXiv papers.
> `ipc_warm_worker_used=false` — this used the thread warm-worker (Windows dev path),
> not the Linux/Docker IPC worker. Academic pipeline is operator-tested v1.
> Docker/GPU IPC 3-paper batch re-run remains an optional performance/infra follow-up.

---

## Context

Queue v0 (shipped 2026-05-05) delivers file-backed parse queue, CLI surface (`enqueue`, `list`, `process`, `counts`), `is_marker_ready()` gate, Marker-only `IngestPipeline` gate, short-body rejection, and 43 offline tests. Codex re-review PASS.

v0 also shipped `create_warm_thread_worker()` — but this is Windows thread mode only. It pre-loads the Marker model dict once in a thread; it is NOT a process-boundary IPC worker and is NOT suitable for Linux/Docker production.

On Linux/Docker, each `docker compose run --rm` invocation cold-loads Marker models from disk (~136–270s cold-start), which fails the ≤10s/paper gate for papers 2+ by 13–27×. Cold-start time dominates per-paper latency; the ~5–10s/paper estimate from the architecture survey assumed a warm-model benchmark not replicated in the `docker compose run --rm` path.

**v1 fix:** a persistent subprocess stays alive inside the `ris-scheduler-gpu` Docker container, holding Marker models in GPU VRAM. An IPC channel (Unix domain socket or named pipe) dispatches parse requests from the queue consumer to the persistent worker. Models load once at startup; papers 2+ parse from warm VRAM with cold-load overhead eliminated (delta ≤5s for papers 2+; per-paper inference time ~45–70s is a hardware constant on the RTX 2070 Super — see Director Gate Revision section).

### Platform behavior (preserved from v0 honest docs)

| Platform | Warm mode | Production? |
|----------|-----------|-------------|
| Windows local dev | Thread mode (`create_warm_thread_worker()`) — pre-loads model dict once in thread | Dev/debug only |
| Linux/Docker | v0: subprocess per paper (cold-load each time) → ❌ fails ≤10s gate | NOT production |
| Linux/Docker | **v1: IPC warm worker (persistent subprocess, models in VRAM)** → ✅ target | **Production target** |

v1 does NOT change Windows behavior. Thread mode remains available on Windows for local dev. Linux/Docker IPC is the only new addition.

---

## Goal

Deliver a persistent IPC warm-worker process for the Marker parse queue on Linux/Docker so that:

1. Marker models load once at Docker container start and stay warm in GPU VRAM
2. Multiple queued papers are processed sequentially through the warm worker; papers 2+ show delta (total_seconds − parse_seconds) ≤5s, confirming cold-load overhead is eliminated — per-paper inference time (~45–70s) is accepted at actual GPU speed (revised gate — see Director Gate Revision section)
3. A process-boundary IPC channel (socket or named pipe) isolates the warm worker from the queue consumer
4. ≥3 papers complete in one warm-worker session without a container restart
5. Queue state and result semantics from v0 remain intact — `is_marker_ready()`, CLI surface, state transitions, persistence
6. pdfplumber does not enter any production parse path — not as a fallback, not as a default
7. L2 activation is explicitly gated on this packet passing acceptance gates

---

## Acceptance Gates

| # | Gate | What must be true |
|---|------|-------------------|
| 1 | IPC worker process exists | A persistent subprocess (`warm_worker.py` or equivalent) starts inside the `ris-scheduler-gpu` container, loads Marker models once, and keeps them loaded across multiple parse requests via an IPC channel (Unix domain socket or named pipe) |
| 2 | Models stay warm across papers | ~~`parse_seconds` for papers 2+ ≤10s~~ **REVISED (Director 2026-05-08):** Papers 2+ must show `delta` (`total_seconds − parse_seconds`) ≤5s, confirming cold-load overhead is eliminated. Per-paper inference time is accepted at actual GPU speed. Evidence: paper 1 delta=26.76s (cold-load amortised); papers 2–3 delta=0.13–0.22s (warm). **PASS.** |
| 3 | ≥3 papers validated in one session | One end-to-end worker session (no container restart) successfully parses ≥3 papers. All 3 show `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback; no daemon-process error. ~~papers 2–3 `parse_seconds ≤10s`~~ **REVISED (Director 2026-05-08):** timing gate replaced by functional gate in Gate 2. Measured timings: arxiv:2604.24366=45.55s, arxiv:2109.07581=69.73s, arxiv:1910.08858=48.31s. **PASS.** |
| 4 | Queue semantics intact | All v0 state transitions (`marker_queued → marker_processing → marker_ready / marker_failed_*`), `is_marker_ready()`, CLI surface (`enqueue`, `list`, `process`, `counts`), and queue persistence survive v1 changes without regression |
| 5 | No pdfplumber fallback | When Marker parse fails on a paper, the state becomes `marker_failed_retryable` or `marker_failed_terminal` — never a pdfplumber downgrade. `failure_reason` is populated. No pdfplumber call exists in any production parse code path |
| 6 | Windows local behavior unchanged | On Windows, thread-based warm mode remains the only available mode. v1 does NOT add IPC to Windows. Docs remain honest about the platform distinction: Windows = thread (dev only), Linux/Docker = IPC (production) |
| 7 | Dev log with timing evidence | `docs/dev_logs/YYYY-MM-DD_marker-docker-ipc-warm-worker-v1.md` documents warm parse timing for papers 1, 2, 3+ with actual `parse_seconds` from a real Docker session on the RTX 2070 Super |

**L2 gate:** L2 PaperQA2 RAG Control Flow remains stub. Does NOT activate until L1 production rollout completes.

---

### Director Gate Revision (2026-05-08)

**Decision:** Original ≤10s/paper timing gate for papers 2+ is rejected as unrealistic and replaced with a functional warm-worker gate.

**Why ≤10s was rejected:**

Marker runs a multi-model pipeline per paper: layout detection, OCR error detection, bounding box detection, text recognition, and table recognition. Even with models warm in GPU VRAM, this pipeline requires ~45–70s per paper for full academic PDFs (15–46 pages) on the RTX 2070 Super. The ≤10s target was aspirational and derived from an over-optimistic estimate that assumed a synthetic benchmark, not real academic PDFs. No measured evidence ever existed for ≤10s on this hardware with this paper set.

**What the warm-worker actually delivers:**

- **Cold-load overhead eliminated for papers 2+.** Paper 1 delta = 26.76s (one-time model load). Papers 2–3 delta = 0.13–0.22s (queue bookkeeping + PDF download only). Models stay warm in GPU VRAM across the session.
- **All papers parse successfully** with `body_source=marker`, no pdfplumber fallback, no daemon-process error.
- **Per-paper inference time** (~45–70s) is a hardware constant for this paper complexity — it cannot be reduced by IPC warm-worker design. It is NOT regression.

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
| `ipc_warm_worker_used` persisted in `results.jsonl` | fix applied 2026-05-08 | 4 new tests pass |

**`ipc_warm_worker_used` persistence fix (2026-05-08):**

Codex review found that `ipc_warm_worker_used=true` appeared in live command JSON but was absent from `results.jsonl`. Root cause: `process_next_ipc()` tagged the flag onto in-memory result dicts after `_append_result()` had already written to disk. Fix: added `_extra_result_fields` parameter to `process_next()` so the field is included in `result_record` before persistence. 4 new tests in `TestIPCResultPersistence` verify this.

**Feature 3 status:** All revised functional gates PASS. Feature 3 is CLOSED (2026-05-08). Codex closeout verification complete. L1 production rollout is UNBLOCKED. L2 remains gated on L1 production rollout completion.

---

## Non-Goals

- **No L2 work.** `Work-Packet - PaperQA2 RAG Control Flow` remains stub. L2 activation gates on warm-worker passing.
- **No L4 work.** Multi-source academic harvesters remain stub and are not touched.
- **No pdfplumber recovery path.** pdfplumber is legacy/debug only. No fallback added.
- **No Windows IPC.** Thread mode is correct for Windows local dev. IPC is Linux/Docker only.
- **No ChromaDB or embedding changes.** The Marker-only `IngestPipeline` gate from v0 is unchanged.
- **No SVM or L3 changes.** SVM enforce remains blocked at rc=1 pending future Director approval.
- **No trading code, Gate 2, or benchmark changes.** Entirely RIS scope.
- **No bulk re-ingest.** Existing pdfplumber-parsed papers in ChromaDB are not re-parsed by this packet.
- **No automatic warm-worker startup.** v1 scope: manual trigger only (`research-scheduler run-warm-worker`). Auto-start on container boot is deferred.

---

## Deferred Items

| Item | Reason | Resume trigger |
|------|--------|----------------|
| Automatic warm-worker startup on `ris-scheduler-gpu` container boot | v1 scope: manual trigger only. Auto-start adds container lifecycle complexity. | Post-validation, once first successful end-to-end warm session is confirmed |
| IPC channel crash recovery / reconnect | If the warm worker dies, v1 policy is: queue consumer restarts the worker (simple restart). Reconnect logic deferred. | Post-v1 hardening pass |
| Bulk re-ingest of pdfplumber-parsed corpus | Separate cleanup task — not this packet. v0/v1 both specify new papers only. | After warm-worker is stable and processing a queue |
| LLM-enriched Marker extraction (`marker_llm_boost`) | Layer 2 work; out of scope here | After L2 activation |

---

## Architecture Sketch

```
[ris-scheduler-gpu Docker container]
        |
        ├── [MarkerWorker / queue consumer]
        |         polls parse_queue for marker_queued entries
        |         updates paper_state → marker_processing
        |         |
        |         | IPC request: (arxiv_id, pdf_path)
        |         | Unix domain socket / named pipe
        |         ↓
        └── [IpcMarkerWorker subprocess]  ← persistent, one per container lifetime
                  |
                  | loads Marker + surya models ONCE at startup (~136–270s)
                  | holds model dict in GPU VRAM across all papers
                  |
                  for each request:
                    calls MarkerPDFExtractor.extract(pdf_path)
                    returns body_text, parse_seconds, failure_reason
                          ↓
                  queue consumer writes result → results.jsonl
                  paper_state = marker_ready  (body_source=marker)
                            OR marker_failed_retryable / terminal
```

**Platform branch (in `MarkerWorker`):**
- Linux/Docker: spawn `IpcMarkerWorker`; connect via IPC; dispatch requests
- Windows: use existing `create_warm_thread_worker()` thread mode (unchanged)

---

## Files Expected to Change

| File | Change | Review level |
|------|--------|-------------|
| `packages/research/ingestion/warm_worker.py` (new) | `IpcMarkerWorker`: load models once, IPC server loop, parse dispatch, state callbacks | Mandatory |
| `packages/research/ingestion/worker.py` | `MarkerWorker` queue consumer: platform branch — Linux=IPC dispatch, Windows=thread mode; update state transitions to use IPC result | Mandatory |
| `tools/cli/research_scheduler.py` | Add `run-warm-worker` (or `run-marker-worker`) subcommand: starts IPC worker, blocks until shutdown signal | Mandatory |
| `tests/test_ris_warm_worker.py` (new) | IPC worker startup (mocked IPC), parse dispatch, multi-paper warm session test, state transition callbacks, platform branch isolation | Mandatory |
| `docs/dev_logs/YYYY-MM-DD_marker-docker-ipc-warm-worker-v1.md` | Warm parse timing evidence from Docker session: papers 1, 2, 3+ with `parse_seconds` | Mandatory |
| `docs/features/ris-marker-docker-ipc-warm-worker-v1.md` (new) | Feature doc on ship | Mandatory |

---

## Open Questions for Architect

1. **IPC transport.** Unix domain socket vs named pipe. Unix socket preferred on Linux — faster, kernel-buffered, no network stack. Confirm path: `/tmp/marker_worker.sock` inside container (ephemeral, matches container lifetime).

2. **Request/response format.** JSON over IPC socket (simple) vs msgpack (compact). JSON preferred for debuggability — parse payloads are not large (pdf_path string + metadata dict).

3. **Worker trigger in v1.** Manual only: operator runs `research-scheduler run-warm-worker` (or `run-marker-worker`). Queue consumer connects to the socket — if socket is not present, falls back to per-paper subprocess (cold, with a warning logged). This makes v1 backward-compatible without requiring the warm worker.

4. **Test strategy.** IPC socket tests must be offline — do NOT load real Marker models in CI. Use a mock IPC server that returns a canned `body_text` + `parse_seconds`. Real Marker timing evidence comes from a Docker session recorded in the dev log.

5. **Existing `MarkerPDFExtractor`.** The IPC warm worker calls this internally after models are loaded. The IPC boundary sits between the queue consumer and the warm worker — `MarkerPDFExtractor` is unchanged.

---

## Reference Materials

1. `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md` — v0 shipped; IPC deferred scope documented
2. `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md` — cold-start evidence: paper 1 = 85.95s; RTX 2070 Super; papers 2+ expected ≤10s warm
3. `docs/features/ris-marker-structural-parser-scaffold.md` — `MarkerPDFExtractor`, `_MARKER_DISABLED` guard, concurrency design, process-boundary cancel
4. `packages/research/ingestion/queue.py` — v0 parse queue state machine; IPC worker must preserve all semantics
5. `packages/research/ingestion/extractors.py` — `MarkerPDFExtractor` with process-boundary cancel; IPC worker calls this
6. [[Work-Packet - Marker Canonical Academic Parse Queue]] — v0 spec; acceptance gates 2 and 3 of that packet are the warm-throughput gates this packet satisfies
7. `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md` — why synchronous default failed; Option A rationale

---

## Cross-References

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Work-Packet - Marker Structural Parser Integration]] — L1 production rollout; BLOCKED pending this packet
- [[Work-Packet - PaperQA2 RAG Control Flow]] — L2; explicitly blocked until warm-worker acceptance gates pass
- [[Work-Packet - Marker Canonical Academic Parse Queue]] — v0 that this packet extends (IPC warm-worker is the v1 deferred item)
- [[Work-Packet - Marker Single-Paper Validation Control Surface]] — VALIDATED; cold-start timing evidence
- [[Decision - Academic Pipeline Hosting]] — Docker GPU passthrough confirmed; RTX 2070 Super; CUDA 13.2
