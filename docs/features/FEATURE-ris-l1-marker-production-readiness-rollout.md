---
status: complete
completed: 2026-05-09
track: Research Intelligence System
layer: L1
---

# Feature: RIS L1 Marker Production Readiness Rollout

**Completed:** 2026-05-09
**Track:** Research Intelligence System — L1 Academic Ingestion
**Runbook:** `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

---

## What This Feature Delivers

This is the L1 production readiness milestone: the point at which the academic
ingestion pipeline has a repeatable, documented, tested operator path from paper
discovery through Marker parse through RAG-ready output. It does not add new code —
it confirms and documents that the infrastructure shipped across prior work packets
(Queue v0, IPC warm-worker v1, scaffold) is now production-usable by an operator.

---

## Definition of Done — L1 Readiness

| Criterion | Status | Evidence |
|-----------|--------|----------|
| One documented path from arXiv ID to Marker-parsed output | ✅ | `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` |
| Marker-only accepted docs (`body_source=marker`) | ✅ | `IngestPipeline.ingest_external()` academic gate |
| No pdfplumber production fallback | ✅ | Marker-mode rejects on failure — no downgrade |
| Queue states understandable and recoverable | ✅ | State machine + recovery in runbook |
| Bad/short parses rejected or retryable, not silently RAG-ready | ✅ | `MIN_MARKER_BODY_LENGTH=5000`; retries up to MAX_ATTEMPTS=3 |
| Output location and inspection commands documented | ✅ | Runbook: artifacts/research/marker_parse_queue/ |
| Smoke test / live evidence without fresh Docker parse required | ✅ | Feature 3 validation: 3 papers, body_source=marker, ipc_warm_worker_used=true |
| Stale "L1 gated" text in CLI removed | ✅ | research_marker_queue.py updated 2026-05-09 |
| Tests pass for all touched areas | ✅ | 158 passed, 1 skipped (platform-correct Linux skip) |

---

## Dependency Matrix — Academic Pipeline Work Packets

| Work Packet | Status | Notes |
|------------|--------|-------|
| L0: Academic Pipeline PDF Download Fix | ✅ SHIPPED 2026-04-27 | pdfplumber wired; real arXiv ingests confirmed |
| L1: Marker Structural Parser Integration | ✅ UNBLOCKED 2026-05-08 | Queue v0 + IPC warm-worker v1 complete |
| L1: Marker Single-Paper Validation Control Surface | ✅ SHIPPED 2026-05-05 | `run-academic-url`; body_source=marker, body_length=56923, parse_seconds=85.95s |
| L1: Marker Canonical Academic Parse Queue v0 | ✅ SHIPPED 2026-05-05 | File-backed queue, CLI, is_marker_ready(), Marker-only gate, 43 tests |
| L1: Marker Docker IPC Warm-Worker v1 | ✅ CLOSED 2026-05-08 (Feature 3) | Revised functional gate PASS; timings 45.55s/69.73s/48.31s; delta 0.13s/0.22s |
| **L1: Marker Production Readiness Rollout** | **✅ COMPLETE 2026-05-09** | **This feature** |
| L2: PaperQA2 RAG Control Flow | ✅ COMPLETE 2026-05-09 | `research-query` CLI; Marker-ready query-time guard; feature doc `FEATURE-ris-l2-academic-query.md` |
| L3: Pre-fetch SVM Topic Filter | ✅ CLOSED 2026-05-07 | Default-off; dry-run/hold-review ready; enforce deferred |
| L4: Multi-source Academic Harvesters | COMPLETE 2026-05-09 | 4 metadata-only harvesters; SSRN/NBER deferred |
| L5: Scientific RAG Evaluation Benchmark | ✅ SHIPPED 2026-05-02 | Baseline locked: corpus=23, P@5=1.0 |

---

## L1 Operator Path (Summary)

Full details in `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`.

```bash
# 1. Enqueue one or more arXiv papers
python -m polytool research-marker-queue enqueue --url 2604.24366

# 2. Check queue status
python -m polytool research-marker-queue counts

# 3. Process with IPC warm-worker (inside Docker/GPU container)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process --max-items 5

# 4. Inspect results
python -m polytool research-marker-queue list --status done
python -m polytool research-marker-queue list --status failed
```

---

## RAG-Readiness Gate

```
marker_ready = body_source == "marker" AND body_length >= 5000 chars
```

Enforced by:
- `is_marker_ready()` in `packages/research/ingestion/marker_queue.py`
- Academic Marker-only gate in `IngestPipeline.ingest_external()` (`packages/research/ingestion/pipeline.py`)

pdfplumber-parsed papers are **not** RAG-eligible. They remain in the raw source cache
as low-fidelity references until a separate bulk re-ingest cleanup task re-parses them.

---

## Key Invariants

- **No pdfplumber fallback in canonical path.** When Marker fails, the paper transitions
  to `marker_failed_retryable` or `marker_failed_terminal` — never downgraded to pdfplumber.
- **Queue persistence.** Queued papers survive worker restarts; the queue is backed by
  `artifacts/research/marker_parse_queue/queue.jsonl`.
- **Short-body rejection.** Even a `body_source=marker` result with `body_length < 5000`
  is not RAG-ready — treated as retryable until MAX_ATTEMPTS=3, then terminal.
- **IPC warm-worker.** On Linux/Docker, models load once at worker start; papers 2+
  pay only inference time (~45-70s hardware constant). Cold-load overhead (~27s) is
  eliminated for papers 2+.

---

## Performance Evidence (2026-05-08 Live Session)

Session: 3 full academic PDFs, one Docker/GPU container, no restart. RTX 2070 Super, CUDA 13.2.

| Paper | arxiv_id | parse_seconds | total_seconds | delta | body_source | ipc_warm_worker_used |
|-------|----------|--------------|--------------|-------|-------------|----------------------|
| 1 (Polymarket microstructure) | 2604.24366 | 45.55s | 72.31s | 26.76s (cold) | marker | true |
| 2 (COVID-19 sports betting) | 2109.07581 | 69.73s | 69.86s | 0.13s (warm) | marker | true |
| 3 (Sports betting inefficiencies) | 1910.08858 | 48.31s | 48.53s | 0.22s (warm) | marker | true |

Gate: ≥3 full PDFs, papers 2+ delta ≤5s, body_source=marker all, ipc_warm_worker_used=true all. **PASS.**

---

## What Is Explicitly Not Included

| Item | Status |
|------|--------|
| L2 PaperQA2 RAG Control Flow | Complete 2026-05-09 — `research-query` CLI with Marker-ready query-time guard |
| L4 Multi-source academic harvesters | COMPLETE 2026-05-09 — `research-harvest`; 4 metadata-only harvesters |
| Bulk re-ingest of existing pdfplumber-parsed corpus | Separate cleanup task |
| Automatic warm-worker startup on container boot | Deferred — post-v1 hardening |
| IPC crash recovery / reconnect | Deferred — post-v1 hardening |
| SVM enforce mode | Hard-blocked at rc=1 pending future Director approval |

---

## Tests

| Test file | Tests | Result |
|-----------|-------|--------|
| `tests/test_ris_marker_queue.py` | ~100 | 158 combined pass (incl. IPC worker tests) |
| `tests/test_ris_marker_ipc_worker.py` | ~58 | See above |

Combined: **158 passed, 1 skipped** (Linux-only platform skip, correct on Windows).

---

## Dev Logs

| Log | Date | Topic |
|-----|------|-------|
| [L1 Marker Production Readiness Rollout](../dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md) | 2026-05-09 | This feature: stale CLI fix, runbook, DoD pass, completion protocol |
| [Marker Docker IPC Warm-Worker v1 Closeout](../dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md) | 2026-05-08 | Feature 3 closed; all revised functional gates PASS |
| [Marker IPC Revised Gate and Result Evidence](../dev_logs/2026-05-08_marker-ipc-revised-gate-and-result-evidence.md) | 2026-05-08 | Persistence fix; revised gate documented |
| [Marker Canonical Parse Queue v0 Closeout](../dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md) | 2026-05-05 | Queue v0 shipped; IPC deferred to v1 |
| [Marker Single-Paper Validation Control Surface](../dev_logs/2026-05-05_ris-marker-single-paper-validation-control-surface.md) | 2026-05-05 | run-academic-url; body_source=marker validated |
