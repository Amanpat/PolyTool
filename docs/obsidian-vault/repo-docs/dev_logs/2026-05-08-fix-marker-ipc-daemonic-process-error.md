---
title: Fix Marker Ipc Daemonic Process Error
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker IPC Warm-Worker Daemonic Process Error

Date: 2026-05-08
Type: bug fix
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1

---

## Root Cause Analysis

**Error:** `daemonic processes are not allowed to have children`

**Where it fired:** Paper 2's extraction in a warm-process session (paper 1 succeeded; paper 2 failed at `parse_seconds=0.0`, `total_seconds=0.24s` — before any Marker inference began).

**Cause:** `MarkerIPCWorker.start()` in `packages/research/ingestion/marker_ipc_worker.py` created the worker subprocess with `daemon=True`:

```python
proc = self._make_process(
    target=_marker_ipc_worker_main,
    args=(req_q, res_q, self._extractor_cls),
    daemon=True,   # ← BUG
)
```

Python's multiprocessing rule: **daemon processes cannot spawn child processes.** Marker's ONNX/torch pipeline spawns internal worker processes during PDF extraction. This constraint fires when any code inside the daemon subprocess calls `multiprocessing.Process(...).start()`.

**Why paper 1 succeeded:** The initial cold-load pass (`create_model_dict()`) happened to follow a code path that did not require spawning child processes. Paper 2's extraction request triggered a different internal code path (e.g., ONNX Runtime data workers, torch DataLoader worker re-initialization) that did require child process spawning — failing immediately on the daemon boundary.

**Why `_make_process` also had `daemon=True` as default:** Defensive coding pattern (worker dies with parent on crash). But this is unnecessary: the worker lifecycle is already managed explicitly via `shutdown()` → poison pill → join → `_terminate_worker()` → SIGTERM/SIGKILL. Changing to `daemon=False` is safe.

---

## Files Changed and Why

### `packages/research/ingestion/marker_ipc_worker.py`

1. `_make_process` default: `daemon=True` → `daemon=False`
2. `start()` call: `daemon=True` → `daemon=False`
3. Added explanatory comment in `start()` documenting the reason

The worker lifecycle is explicitly managed — `daemon=False` does not risk orphan processes in Docker (container exit kills all children) or in normal use (shutdown/terminate handle cleanup).

### `tests/test_ris_marker_ipc_worker.py`

1. Updated `_thread_process_factory` to always create daemon threads (accept but ignore the `daemon` argument). Reason: timeout tests leave threads running with a 60-second sleep. If the thread is non-daemon, pytest cannot exit until the sleep completes. Threads are always daemon for test isolation; the `daemon` flag is accepted only to match the real factory signature.

2. Added `TestMarkerIPCWorkerDaemonSafety` class (5 tests):
   - `test_start_passes_daemon_false_to_factory` — captures and asserts `daemon=False`
   - `test_restart_passes_daemon_false_to_factory` — same for restart path
   - `test_multi_parse_paper1_ok_paper2_ok` — core live-failure scenario reproduced and passing
   - `test_daemonic_error_from_extractor_surfaced_as_structured_error` — daemonic `AssertionError` from Marker internals becomes structured error dict, worker stays alive
   - `test_worker_survives_daemonic_error_and_next_paper_succeeds` — paper 2 succeeds after paper 1 raises daemonic error

### `tests/test_ris_marker_queue.py`

Added `TestProcessNextIPCDaemonSafety` class (3 tests):
- `test_two_paper_session_both_done` — two papers in one `process_next_ipc` call, both `marker_ready=True`
- `test_daemonic_error_from_marker_internals_is_retryable` — the exact `failure_reason` from the live log results in `queue_status=pending` (retryable, not terminal)
- `test_direct_pdf_path_two_papers_both_done` — two `pdf_url` items, both routed via `fetch_pdf_direct`, both done

---

## Commands Run and Outputs

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
```

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
collected 155 items

tests\test_ris_marker_ipc_worker.py ....................................
........
tests\test_ris_marker_queue.py ...........................................
...................s..................................................

======================= 154 passed, 1 skipped in 2.98s ========================
```

154 passed, 1 skipped (platform-specific test skips on Windows — expected).

```
python -m polytool research-marker-queue warm-process --help   → exit 0, --max-items and --marker-timeout present
python -m polytool research-marker-queue enqueue --help        → exit 0, --pdf-url present
```

---

## No Live Validation Run

No live Docker validation was run. No Docker rebuild or prune. No Docker containers were started. No queue artifacts were mutated. This is a code-only fix session.

---

## Whether Docker Rebuild + Live Validation May Proceed

Yes, after operator review of this fix. Pre-conditions:
1. Docker image rebuild required (stale baked packages; use current bind-mount workaround or rebuild with `Dockerfile.ris`)
2. Reset or re-prepare the direct-PDF validation queue (paper 2 and 3 are still in `pending` state from the previous run — `force` re-enqueue or create a new queue dir)
3. Run one new live validation with `warm-process --max-items 3`
4. Acceptance gates: ≥ 3 papers done, papers 2+ `parse_seconds ≤ 10s`, `body_source=marker`, `ipc_warm_worker_used=true`

---

## Remaining Risks

1. **ONNX Runtime or torch DataLoader spawn depth.** `daemon=False` removes the Python-level daemon restriction. If Marker's internal children try to spawn grandchildren from their own daemon context, a nested daemonic error could still occur. This is unlikely (Marker's workers typically do not recurse further), but cannot be proven without a live run.

2. **Orphan process on parent crash.** With `daemon=False`, if the Python process crashes hard (SIGKILL, OOM) without running shutdown, the worker subprocess persists until its current task completes. In Docker, container exit kills all descendants. On bare Linux, the orphan would run briefly and then exit (no more requests arrive). Acceptable risk.

3. **Model warm state across papers.** The live evidence shows paper 1 took 51.62s (cold load + inference). Paper 2 should be ≤ 10s if models stay warm. This is the critical gate that requires a live run to confirm.

4. **L1 remains blocked.** This fix unblocks the code path but does not constitute live validation. L1 Marker production rollout requires a successful ≥ 3-paper live validation run.

---

## Codex Review Summary

Tier: recommended (strategy/ingestion). Not a mandatory file (execution/kill-switch path not involved). No live validation or Docker operations performed in this session.
