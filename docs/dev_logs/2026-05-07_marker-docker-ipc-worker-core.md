# Marker Docker IPC Warm-Worker Core — Dev Log

**Date:** 2026-05-07
**Scope:** Terminal A — IPC warm-worker core (new file + tests only)
**Status:** COMPLETE — tests pass, no regressions

---

## Context

Queue v0 shipped 2026-05-05. On Linux/Docker, each `docker compose run --rm`
spawns a fresh subprocess that cold-loads Marker models (~80-270s per paper),
failing the ≤10s/paper gate for papers 2+. This session implements the IPC
warm-worker core that Claude 2 will wire into the queue consumer and CLI.

---

## Files Changed

### `packages/research/ingestion/marker_ipc_worker.py` (existed; rewritten)

The file existed with a partial implementation (basic `start()`, `extract()`,
`restart()`, `shutdown()`). It was missing:

- `parse()` method — the primary public API that returns structured error dicts
  instead of raising `queue.Empty` on timeout
- Injectable `_process_factory` / `_queue_factory` for offline testing
- Injectable grace timeouts for fast test teardown
- `start()` idempotency guard (RuntimeError if already running)
- `_terminate_worker()` internal helper with SIGTERM → SIGKILL pattern
- `_SENTINEL` module-level constant for the poison pill
- Startup error signalling (worker puts startup_error in result queue if model
  load fails, so parent gets an error dict rather than hanging to timeout)

**Public API created:**

| Symbol | Type | Purpose |
|--------|------|---------|
| `_SENTINEL` | `None` | Poison pill value sent to request_queue to exit worker |
| `_marker_ipc_worker_main(request_queue, result_queue, _extractor_cls=None)` | Module-level function | Spawn-safe worker entry point; loads models once, serves requests |
| `MarkerIPCWorker` | Class | Parent-side warm-worker manager |
| `MarkerIPCWorker.start()` | Method | Spawn subprocess, allocate fresh queues |
| `MarkerIPCWorker.parse(pdf_path, timeout=900.0)` | Method | Send request, return structured result dict (never raises) |
| `MarkerIPCWorker.extract(tmp_path, timeout)` | Method | Raw IPC call, raises `queue.Empty` on timeout (lower-level) |
| `MarkerIPCWorker.is_alive()` | Method | True if subprocess is running |
| `MarkerIPCWorker.restart()` | Method | Terminate + respawn (one new cold load) |
| `MarkerIPCWorker.shutdown()` | Method | Idempotent clean shutdown (poison pill → join → force-kill) |

**`parse()` return dict:**
```python
{
    "status": "ok" | "error",
    "body": str,                   # Markdown text; empty on error
    "meta": dict,                  # body_source, page_count, parse_seconds, ...
    "parse_seconds": float,
    "failure_reason": str | None,  # None on success
}
```

**`_marker_ipc_worker_main` result_queue payloads:**
- `{"status": "startup_error", "error": str, "parse_seconds": 0.0}` — model load failed; emitted once, worker exits
- `{"status": "ok", "body": str, "meta": dict, "parse_seconds": float}` — successful parse
- `{"status": "error", "error": str, "parse_seconds": float}` — per-paper exception

**Key design decisions:**
- `_MARKER_DISABLED` is NOT set on timeout — IPC timeout handled locally without poisoning parent-process Marker state
- No pdfplumber fallback anywhere — error dicts are returned instead
- Metadata filtered to picklable primitive types (`str, int, float, bool, None`) to stay queue-safe
- `parse_seconds` added to `meta` dict for Claude 2 integration compatibility with `_build_marker_result`
- `_process_factory` / `_queue_factory` injectable so tests use `threading.Thread` + stdlib `queue.Queue` (no spawn, no pickling)
- Grace timeout params (`_terminate_grace_seconds`, `_kill_grace_seconds`, `_shutdown_join_timeout`) injectable for fast test teardown

### `tests/test_ris_marker_ipc_worker.py` (existed as stub; fully replaced)

The file existed with 8 basic tests covering `_marker_ipc_worker_main` only.
Replaced with 33 tests covering both the function and the full `MarkerIPCWorker` class.

**Test structure:**

| Class | Tests | What it covers |
|-------|-------|----------------|
| `TestMarkerIPCWorkerInterface` | 4 | Method presence, pre-start state, extract raises, parse returns error dict |
| `TestMarkerIPCWorkerMain` | 8 | Direct function tests: single request, 3-paper warm reuse (call_log count=1), poison pill, extract error, startup error + exit, error-then-success, meta filtering, 5 sequential papers |
| `TestMarkerIPCWorkerLifecycle` | 8 | start/alive/RuntimeError-on-double-start, shutdown idempotency, not-alive-after-shutdown, restart-when-not-running, restart-replaces-process |
| `TestMarkerIPCWorkerParse` | 11 | Single paper ok, required keys, body_source=marker, 3-paper warm reuse proof (call_log=1), not-started error, error propagation, per-paper error doesn't kill worker, timeout→error+not-alive, restart after timeout, no pdfplumber fallback |
| `TestMarkerIPCWorkerExtractRaw` | 3 | RuntimeError before start, raw result dict, queue.Empty on timeout |

**Key testing techniques:**
- `_ThreadProcess` wrapper: mimics `multiprocessing.Process` API using `threading.Thread`; `terminate()`/`kill()` are no-ops; daemon=True so threads die on test exit
- `_make_mock_extractor(...)`: returns `(MockClass, call_log)` where `call_log` is a shared list that grows by 1 per `create_model_dict()` call — proves warm reuse without real Marker
- `_make_worker(...)`: factory with thread-based process injection and configurable grace timeouts (default 0.1s for fast teardown)

---

## Commands Run + Results

```
python -m pytest tests/test_ris_marker_ipc_worker.py -q --tb=short
  33 passed in 1.17s

python -m pytest tests/test_ris_marker_queue.py -q --tb=short
  81 passed, 1 skipped in 1.41s   (unchanged from before; no regressions)

python -m polytool --help
  OK — CLI loads cleanly

python -m pytest tests/ -x -q --tb=short (full suite)
  1 failed, 2403 passed, 3 deselected, 24 warnings in 90.24s
  FAILED: test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields
  → PRE-EXISTING: confirmed by running after git stash; failure exists on main HEAD
    without my changes.
```

---

## Decisions Made

1. **`parse()` vs `extract()`**: Added `parse()` as the primary public API (returns error dicts, handles timeout internally). Kept `extract()` as a raw IPC call for lower-level use. Claude 2 integration should use `parse()`.

2. **Startup error signalling**: Worker emits `{"status": "startup_error", ...}` to result_queue before exiting on model load failure. This ensures the first `parse()` call gets a clear error dict rather than hanging for the full timeout.

3. **No `is_alive()` bypass in `parse()`**: Checking `is_alive()` first is correct for the normal case. Startup errors are tested at the `_marker_ipc_worker_main` level (not through `parse()`), avoiding the race condition where the worker thread exits between `start()` and `parse()`.

4. **Thread-based test injection**: `_process_factory=_thread_process_factory` + `_queue_factory=queue.Queue` is the correct offline test pattern. It allows injecting unpicklable mock extractor classes because no spawn/pickle boundary exists in thread mode.

5. **Grace timeout params**: `_terminate_grace_seconds=0.1` and `_kill_grace_seconds=0.1` in tests keep timeout tests fast (≤0.3s total) without affecting production defaults (5s+2s).

6. **`meta["parse_seconds"]` included**: Added `parse_seconds` to the meta dict inside the worker so it's available via `_build_marker_result(body, meta)` when Claude 2 builds the fetcher integration.

---

## Open Questions for Claude 2 Integration

1. **Queue consumer wiring** (`marker_queue.py`): In `process_next()`, the Linux/Docker branch should create `MarkerIPCWorker()`, call `start()`, wrap the processing loop in try/finally with `worker.shutdown()`. Accept `_ipc_worker_cls` injection for offline tests.

2. **Fetcher wiring** (`fetchers.py`): Add `_marker_ipc_worker: Optional[MarkerIPCWorker] = None` to `LiveAcademicFetcher.__init__()`. In `_marker_production_extract_subprocess()`, check `self._marker_ipc_worker is not None` and delegate to it; build the result dict via `_build_marker_result(body, meta)`.

3. **Timeout on worker error**: After `parse()` returns `status="error"` with `marker_timeout` in `failure_reason`, the worker is dead (`is_alive()=False`). The queue consumer should call `worker.restart()` or `worker.shutdown()` and mark the paper retryable.

4. **`_MARKER_DISABLED` interaction**: Do NOT set `_MARKER_DISABLED` in the IPC path. The existing subprocess path sets it on timeout; the IPC path must NOT. Confirm that the integration branch (`if self._marker_ipc_worker is not None:`) is reached before the code that calls `_MARKER_DISABLED.set()`.

5. **CLI subcommand** (`research_marker_queue.py`): `warm-process` subcommand to create IPC worker, process batch, print per-paper `parse_seconds`. This is the primary validation command for acceptance gate 3.

6. **Docker validation**: Once Claude 2 wires the integration, run:
   ```
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     python -m polytool research-marker-queue warm-process --max-items 3
   ```
   Verify: paper 1 `parse_seconds` ~80-270s (cold), papers 2-3 `parse_seconds` ≤10s (warm).

---

## Codex Review

Tier: Recommended (strategy/SimTrader analog — new IPC module with process lifecycle).
Files changed: `packages/research/ingestion/marker_ipc_worker.py`, `tests/test_ris_marker_ipc_worker.py`.
Issues found: N/A (not yet reviewed).
Issues addressed: N/A.
