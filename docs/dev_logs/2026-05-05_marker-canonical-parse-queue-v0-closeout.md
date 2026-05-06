# Marker Canonical Parse Queue v0 — Close-out

Date: 2026-05-05
Scope: Docs-only close-out after Codex re-review PASS.
Status: COMPLETE — v0 shipped; Docker IPC warm-worker deferred to v1.

---

## Summary

Codex re-review returned PASS on 2026-05-05. All prior FAIL blockers are resolved:
warm-worker claim corrected to be honest about platform behavior, Marker-only indexing
gate added to `IngestPipeline`, short Marker output now becomes auditable failure/retry
(not a `queue_status="done"` record). Live Docker warm-worker validation may NOT proceed
as an L1 acceptance gate — deferred to v1.

Codex review chain:
1. Initial review: FAIL — 3 blockers
   (`docs/dev_logs/2026-05-05_codex-review-marker-canonical-parse-queue-v0.md`)
2. Fixes applied: all 3 blockers resolved
   (`docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-fixes.md`)
3. Re-review: **PASS** — all 7 review points passed
   (`docs/dev_logs/2026-05-05_codex-rereview-marker-canonical-parse-queue-v0.md`)

---

## v0 Shipped Scope

All offline-only. No Docker, no live Marker, no GPU validation required for v0.

| Deliverable | File | Status |
|---|---|---|
| File-backed parse queue (`queue.jsonl`, `results.jsonl`) | `packages/research/ingestion/marker_queue.py` | Shipped |
| `MarkerParseQueue.process_next()` with `is_marker_ready()` gate | `packages/research/ingestion/marker_queue.py` | Shipped |
| CLI surface: `enqueue`, `list`, `process`, `counts` | `tools/cli/research_marker_queue.py` | Shipped |
| Short Marker body rejection (retryable; `failure_reason` populated) | `packages/research/ingestion/marker_queue.py` | Shipped |
| Marker-only academic indexing gate (`IngestPipeline.ingest_external`) | `packages/research/ingestion/pipeline.py` | Shipped |
| pdfplumber/abstract/marker_failed blocked from canonical embeddings | `packages/research/ingestion/pipeline.py` | Shipped |
| Honest platform docs: thread=warm (Windows); subprocess=cold (Linux/Docker) | `tools/cli/research_marker_queue.py`, `marker_queue.py` | Shipped |
| `create_warm_thread_worker()` class method on `LiveAcademicFetcher` | `packages/research/ingestion/fetchers.py` | Shipped |
| `_preloaded_model_dict` support in `MarkerPDFExtractor` | `packages/research/ingestion/extractors.py` | Shipped |
| 43 offline tests (all pass) | `tests/test_ris_marker_queue.py` | Shipped |
| RAG-ready rule: `is_marker_ready(body_source, body_length)` canonical | `packages/research/ingestion/marker_queue.py` | Shipped |

Test run: 146 passed, 1 skipped (the skipped test is Linux-only, valid on CI).

---

## v1 Deferred Scope

| Deliverable | Reason |
|---|---|
| Docker/Linux IPC warm worker (persistent subprocess, models loaded once per session) | Subprocess mode spawns a fresh process per paper on Linux/Docker; model objects cannot cross process boundaries; a separate IPC layer (e.g., sockets) is required to keep models loaded across papers |
| Multi-paper warm throughput validation (≥3 papers, ≤10s/paper for papers 2+) | Depends on IPC warm worker |
| L1 production Marker throughput validation via Docker | Depends on IPC warm worker |
| Automatic worker startup on `ris-scheduler-gpu` service start | v1 deliverable — requires stable warm-worker design first |

---

## Acceptance Gate Final Status

| Gate | Status |
|---|---|
| 1. Queue accepts candidates | Shipped in v0 |
| 2. Worker processes ≥3 papers in one warm session | Deferred to v1 (requires Docker IPC) |
| 3. No per-paper cold-load after first paper (≤10s/paper for papers 2+) | Deferred to v1 (requires Docker IPC) |
| 4. Output includes canonical fields (body_source, body_length, parse_seconds, failure_reason) | Shipped in v0 |
| 5. Embedding path enforces Marker-only | Shipped in v0 (pipeline gate) |
| 6. No pdfplumber fallback in canonical path | Shipped in v0 |
| 7. Queue persistence (file-backed JSONL; survives worker restart) | Shipped in v0 |
| 8. Existing tests still pass | Shipped — 146 passed, 1 skipped |
| 9. Dev log written | Shipped — `2026-05-05_marker-canonical-parse-queue-v0.md` |

---

## Codex Verdict

| Review | Outcome |
|---|---|
| First review | FAIL — 3 blockers: warm-worker overclaim, missing Marker-only indexing gate, short Marker body marked done |
| Re-review after fixes | **PASS** — all 7 review points passed |

Issues addressed in re-review:
1. Warm-worker not actually warm — RESOLVED: honest platform docs; `create_warm_thread_worker()` for Windows thread mode; subprocess=cold on Linux/Docker documented; IPC v1 deferred explicitly
2. Missing Marker-only indexing gate — RESOLVED: `IngestPipeline.ingest_external()` now rejects academic bodies unless `body_source=="marker"` and `body_length>=5000`
3. pdfplumber/abstract_fallback/marker_failed reaching canonical embeddings — RESOLVED: gate rejects all non-marker sources before chunking/storage
4. Short Marker output marked done — RESOLVED: `rejected=True`, `exit_code=1`, `failure_reason="marker_body_too_short: ..."`, retries as `pending` until `MAX_ATTEMPTS`, then `failed`
5. Queue state/failure_reason explicit — PASS WITH CAVEAT: retryable failure = `queue_status="pending"` plus `failure_reason` in `results.jsonl`
6. No L2/SVM/L4/n8n/trading scope creep — PASS
7. Tests offline and pass — PASS: 146 passed, 1 skipped

---

## Next Recommended Options

### Option A — Docker IPC Warm-Worker v1 Packet

Implement a persistent IPC warm worker for Linux/Docker (long-lived subprocess with
socket/pipe dispatch). Validates ≥3 papers in one warm session. Unblocks the L1
Marker production throughput claim. This is the full production path for the queue.

Estimated effort: 1–2 sessions. IPC design is the hard part; `MarkerParseQueue`
infrastructure already exists.

### Option B — Windows Thread-Mode Warm Validation First

The Windows thread mode already achieves warm-model behavior via
`create_warm_thread_worker()`. Run:

```powershell
python -m polytool research-marker-queue process --max-items 10
```

on the Windows dev machine with GPU. Paper 1 cold (~80s), papers 2+ warm (expected
≤10s each). Validates the throughput claim on Windows before investing in Docker IPC.

### Option C — Proceed to L2 Planning While v1 Is Deferred

Queue v0 infrastructure is sufficient to support L2 (PaperQA2 RAG Control Flow) design
on the code side. The activation gate was "queue ships" — the queue shipped (v0). Operator
may choose to unlock L2 planning while IPC warm-worker is deferred. Note: live corpus
accumulation will be slow without warm-worker; L2 evaluation will need more Marker-parsed
papers.

---

## Docs Updated This Session

| Doc | Change |
|---|---|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md` | Status updated to `implemented-v0`; v0/v1 split added |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Queue v0 shown as complete; L1 blocked on IPC warm-worker; Key Blockers and RIS status table updated |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 moved to Recently Completed; Docker IPC warm-worker v1 added to Paused/Deferred; Notes for Architect updated |
| `docs/INDEX.md` | Closeout log, Codex re-review, fixes log, and first review log added |

---

## Codex Review

Tier: Skip — docs-only session. No runtime code, tests, Docker, or trading logic touched.
