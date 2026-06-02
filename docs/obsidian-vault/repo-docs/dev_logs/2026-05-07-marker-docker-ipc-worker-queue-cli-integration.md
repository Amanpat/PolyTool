---
title: Marker Docker Ipc Worker Queue Cli Integration
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Docker IPC Warm-Worker v1 — Queue/CLI Integration

Date: 2026-05-07
Type: implementation
Scope: MarkerIPCWorker created; queue and CLI wired for Linux/Docker warm-worker processing

---

## Summary

Implements the IPC warm-worker integration as specified in the context map
(`2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md`) and work packet.
No live Marker parsing was performed. Only the harness, queue wiring, and test
coverage were built. L1 production rollout remains blocked until live Docker
validation passes (gates 1–7).

---

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `packages/research/ingestion/marker_ipc_worker.py` | **Created (new)** | IPC warm-worker module: `_marker_ipc_worker_main` (module-level spawn-safe entry), `MarkerIPCWorker` class with `start`, `parse`, `extract`, `restart`, `shutdown`, `is_alive`. Linter enhanced with `_process_factory`/`_queue_factory` injectable params for offline testing. |
| `packages/research/ingestion/fetchers.py` | Added `_marker_ipc_worker` param to `LiveAcademicFetcher.__init__()`. Added `_marker_ipc_worker_extract()` method. Fixed `_marker_production_extract()` to route IPC path regardless of `_marker_use_process` flag (critical for cross-platform tests). Modified `_marker_production_extract_subprocess()` to delegate to IPC when worker is set. |
| `packages/research/ingestion/marker_queue.py` | Added `_ipc_worker_cls`, `_http_fn`, `_pdf_http_fn` params to `process_next()`. Restructured Linux/Docker branch to create `MarkerIPCWorker` and pass to fetcher. Wrapped processing loop in try/finally for clean IPC worker shutdown. Windows branch unchanged. |
| `tools/cli/research_marker_queue.py` | Added `warm-process` subcommand: processes pending items via IPC warm worker, prints per-paper parse_seconds, reports IPC usage status, prints L1 gating message. Routed in `main()`. |
| `tests/test_ris_marker_ipc_worker.py` | **Created (new)** | 35 offline tests. Linter added `_ThreadProcess`/`_thread_process_factory` for fully offline subprocess simulation. Tests cover model-loaded-once, warm reuse, extraction error, startup failure, shutdown idempotency, restart, timeout. |
| `tests/test_ris_marker_queue.py` | Added `TestProcessNextIPCWorker` (6 tests) and `TestCLIWarmProcess` (5 tests). Tests verify IPC worker lifecycle, shutdown-on-exception, Windows non-IPC behavior, L1 gate message. |

---

## Architecture

```
process_next() [Linux/Docker path]
    ├── creates MarkerIPCWorker (_ipc_worker_cls or real)
    ├── calls _ipc_worker.start()
    ├── creates LiveAcademicFetcher(_marker_ipc_worker=_ipc_worker)
    ├── [loop] for each pending item:
    │       fetcher.fetch(url)
    │         → _parse_pdf()
    │         → _marker_production_extract()
    │         → _marker_production_extract_subprocess()   ← IPC path
    │         → _marker_ipc_worker_extract()
    │         → _ipc_worker.extract(tmp_path, timeout)   ← send/receive
    └── finally: _ipc_worker.shutdown()

Windows path: unchanged (thread mode, create_warm_thread_worker)
Linux/Docker: one MarkerIPCWorker per process_next() call
```

Key design decisions:
- `_MARKER_DISABLED` is NOT set on IPC timeout; worker restarts instead
- `_marker_production_extract()` checks `_marker_ipc_worker` before `_marker_use_process`  
  to ensure IPC path works in cross-platform tests (Windows default `_marker_use_process=False`)
- IPC worker shutdown wrapped in try/finally — guaranteed even on exception
- Fresh queues allocated per `start()` — stale results from timeout never leak

---

## Commands Run and Results

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
```

Result: **114 passed, 1 skipped** (pre-existing skip in marker_queue suite). 0 failures.

Test breakdown:
- `test_ris_marker_ipc_worker.py`: 35 tests — all pass
- `test_ris_marker_queue.py`: 79 tests total — 78 pass, 1 pre-existing skip

```
python -m polytool research-marker-queue --help
```

Output confirms `warm-process` subcommand is exposed with correct description including
L1 gating language.

Full regression (prior to pre-existing `test_ris_claim_extraction.py` failure):
2403 passed, 1 failed (`test_ris_claim_extraction.py` — pre-existing, unrelated to this work).
0 new failures introduced.

---

## CLI Behavior (warm-process)

```
python -m polytool research-marker-queue warm-process --max-items N --marker-timeout 900
```

Output format:
- Header: mode (IPC warm worker / thread warm mode), item count, timeout
- Per paper: `[PASS/FAIL] candidate_id`, `body_source`, `body_length`, `parse_seconds`, `queue_status`
- Summary: processed count, IPC warm-worker used: True/False
- L1 gating note: explains live Docker validation required before production

`--json` mode: adds `ipc_warm_worker_used` field to output.

Platform behavior:
- Linux/Docker (`_MARKER_DEFAULT_USE_PROCESS=True`): IPC warm worker is used
- Windows (`_MARKER_DEFAULT_USE_PROCESS=False`): thread warm mode, prints honest platform note

---

## Queue/CLI Semantics Preserved (v0 unchanged)

All v0 semantics intact:
- `is_marker_ready()` gate: `body_source == "marker"` AND `body_length >= 5000`
- State machine: `pending → processing → done / pending (retry) / failed`
- `results.jsonl` append-only with `processed_at`, `attempt`, `queue_status`
- No pdfplumber fallback in any production parse path
- `_MARKER_DISABLED` not set by IPC path

---

## Remaining Live Validation Steps

Gates 1–7 from the work packet remain unvalidated. This session only built the harness.
Live validation requires running inside `ris-scheduler-gpu` container on the RTX 2070 Super:

1. Start container: `docker compose --profile ris-gpu up -d ris-scheduler-gpu`
2. Enqueue 3+ papers: `python -m polytool research-marker-queue enqueue --url <arxiv_id>`
3. Run warm-process: `python -m polytool research-marker-queue warm-process --max-items 3`
4. Inspect `artifacts/research/marker_parse_queue/results.jsonl` for `parse_seconds`
5. Verify: paper 1 ~80-270s (cold), papers 2+ ≤10s (warm)

Gates that remain blocked on live validation:
- Gate 3: ≥3 papers with `body_source=marker` in one session
- Gate 4: papers 2+ at ≤10s/paper on RTX 2070 Super
- Gate 7: dev log with actual timing evidence from real Docker session

---

## Risks / Open Questions

1. **`_MARKER_DEFAULT_USE_PROCESS` patch in tests**: Patching the module-level var works
   because `process_next()` imports it fresh each call. The fetcher's `_marker_use_process`
   default is captured at class definition time — fixed by routing IPC via `_marker_ipc_worker`
   check in `_marker_production_extract()` before the platform gate.

2. **Windows test for `test_ipc_timeout_marks_paper_retryable`**: The timeout path in
   `_marker_ipc_worker_extract()` catches `queue.Empty` from the FakeIPCWorker and
   returns `marker_failed`. Queue item retry logic runs from `_process_item` rejection.
   On first failure (attempts=1 < MAX_ATTEMPTS=3), item stays `pending`.

3. **Startup error race**: Worker may put `startup_error` before the first real request.
   `_marker_ipc_worker_extract()` handles `status == "startup_error"` the same as `"error"`.

4. **No automatic warm-worker startup on container boot**: Still deferred per work packet
   non-goals. v1 scope: manual trigger only via `warm-process` CLI.

---

## Codex Review Summary

Tier: Recommended — strategy files and queue consumer touched.
Issues found: none blocking. Linter (auto-applied) enhanced `MarkerIPCWorker` with
injectable `_process_factory`/`_queue_factory`/`_mp_context` for cleaner offline tests,
and updated `test_ris_marker_ipc_worker.py` with `_ThreadProcess` wrapper to achieve
full offline subprocess simulation. No correctness issues found.
Issues addressed: none beyond linter enhancements.

## L1 Rollout Status

**L1 production rollout remains BLOCKED.** Acceptance gates 3, 4, 7 require live Docker
validation. This session delivered gates 1 (IPC worker exists), 5 (queue semantics intact),
6 (no pdfplumber fallback), and most of gate 2 (harness for warm reuse — live timing TBD).
