---
title: Fix Marker Docker Ipc Worker Integration
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker Docker IPC Warm-Worker Integration

**Date:** 2026-05-07
**Status:** Complete — tests pass, CLI updated, L1 production still gated

---

## Codex Blockers Reproduced

Codex FAIL reported that the checked-out repo contained no actual IPC warm-worker
integration:

- `fetchers.py` had no `_ipc_worker` param — `LiveAcademicFetcher` could not
  route parse requests to a `MarkerIPCWorker`.
- `marker_queue.py` `process_next()` comment read "warm IPC worker is deferred
  to v1" and spawned a fresh subprocess per paper on Linux/Docker.
- CLI `research-marker-queue --help` showed no `warm-process` subcommand.
- `test_ris_marker_queue.py` had no tests for IPC path, single-worker reuse, or
  `ipc_warm_worker_used` in results.

Both `test_ris_marker_ipc_worker.py` (35 tests) and `test_ris_marker_queue.py`
(68 tests) passed at baseline — the core worker worked but was unconnected.

---

## Files Changed and Why

### `packages/research/ingestion/fetchers.py`
- Added `_ipc_worker=None` parameter to `LiveAcademicFetcher.__init__`.
- Added `_marker_ipc_worker_extract(tmp_path)` method: delegates to
  `self._ipc_worker.parse()`, returns `(body_text, meta_dict)`. Does NOT set
  `_MARKER_DISABLED`. Does NOT fall back to pdfplumber on any error path.
  Returns structured `marker_failed` meta on error or short-body rejection.
- In `_parse_pdf()`: added early-exit check before all other paths — if
  `_ipc_worker is not None`, dispatch to `_marker_ipc_worker_extract` and
  bypass the semaphore/disabled-flag logic entirely.

### `packages/research/ingestion/marker_queue.py`
- Added `process_next_ipc(max_items, marker_timeout, _ipc_worker, _fetcher)`
  method.
- On Linux/Docker (`_MARKER_DEFAULT_USE_PROCESS=True`): creates one
  `MarkerIPCWorker`, calls `start()`, creates `LiveAcademicFetcher(_ipc_worker=worker)`,
  delegates to `process_next(_fetcher=fetcher)`, calls `worker.shutdown()` in
  `finally`. One cold load amortized across the full batch.
- On Windows (thread mode): falls back to `create_warm_thread_worker()` (same
  as `process_next`). `_ipc_worker` is not created; `ipc_warm_worker_used=False`.
- `_fetcher` injection bypasses worker lifecycle entirely (test path).
- Each result dict gets `ipc_warm_worker_used: bool` added.

### `tools/cli/research_marker_queue.py`
- Added `_cmd_warm_process(args)` handler: calls `process_next_ipc`, prints
  per-paper `parse_seconds`, `ipc_warm_worker_used`, processed count, and L1
  gate reminder. Supports `--json` output.
- Added `warm-process` subparser with `--max-items`, `--marker-timeout`, `--json`.
- Added `warm-process` dispatch in `main()`.

### `tests/test_ris_marker_queue.py`
- `_MockIPCWorker`: offline stand-in with `parse_call_count` tracker.
- `TestIPCFetcherExtract` (6 tests): proves `_marker_ipc_worker_extract` routes
  through injected worker, propagates `parse_seconds`, returns `marker_failed`
  on error, does NOT set `_MARKER_DISABLED`, does NOT produce pdfplumber body_source.
- `_IPCTrackingFetcher`: wraps a single mock worker, increments `parse_call_count`
  per `fetch()` call.
- `TestProcessNextIPC` (7 tests): multiple queue items via one worker (call count
  verified), `ipc_warm_worker_used` in results, IPC failure → retryable → terminal
  after MAX_ATTEMPTS, no pdfplumber fallback, empty queue → [], Windows thread path
  unchanged.
- `TestCLIWarmProcess` (4 tests): `warm-process` in top-level help, subcommand
  help exits 0, empty queue returns cleanly, JSON output includes `ipc_warm_worker_used`.

---

## Commands Run and Outputs

```
python -m polytool research-marker-queue --help
# → warm-process present in subcommand list

python -m polytool research-marker-queue warm-process --help
# → --max-items, --marker-timeout, --json flags shown

python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
# → 119 passed, 1 skipped

git diff --stat
# → 4 files changed, 488 insertions(+)
#   packages/research/ingestion/fetchers.py
#   packages/research/ingestion/marker_queue.py
#   tests/test_ris_marker_queue.py
#   tools/cli/research_marker_queue.py
```

---

## CLI Command Added

```
python -m polytool research-marker-queue warm-process --max-items 5 --marker-timeout 900
python -m polytool research-marker-queue warm-process --max-items 5 --json
```

Output includes per-paper `parse_seconds`, `ipc_warm_worker_used`, and the L1
gate reminder on every run.

---

## L1 Production Gate Status

**L1 production remains BLOCKED.** This work wire up the integration code path
and proves it offline via mock workers. The gate requires:

1. Live Docker/GPU run with real Marker models loaded.
2. At least one paper completing warm parse within ≤10s (papers 2+).
3. Structured result roundtrip verified against a real PDF in the queue.

No live Marker jobs were run in this session. Do not promote to production until
live Docker validation passes.

---

## Remaining Risks

- `create_warm_thread_worker()` on Windows still raises `RuntimeError` if called
  on Linux/Docker — that guard is intentional and unchanged.
- `process_next_ipc` with no `_fetcher` on Linux/Docker will actually try to
  spawn a `MarkerIPCWorker` subprocess, which requires Marker + GPU. Any CI that
  runs `process_next_ipc` without injection will need a guard or will fail at
  `worker.start()` if Marker is not installed. Existing CI only calls
  `process_next` via `_fetcher` injection — unaffected.
- The `_MARKER_DISABLED` flag is intentionally bypassed by the IPC path. If a
  previous cold-subprocess timeout set the flag, a subsequent `process_next_ipc`
  call is unaffected. This is the correct behavior per the IPC worker contract.
