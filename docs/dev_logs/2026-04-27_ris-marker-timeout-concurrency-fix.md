# 2026-04-27 — RIS Marker Timeout Concurrency Fix (Prompt D)

## Confirmed Bug

The Prompt C semaphore did NOT prevent zombie thread accumulation on timeout.

### Execution trace (before fix)

```
caller acquires _MARKER_WORK_SEMAPHORE
caller spawns ThreadPoolExecutor thread (Marker worker)
  _fut.result(timeout=N) fires _cf.TimeoutError
  → caught by except Exception as exc
  → sets marker_fail_reason = "marker_timeout: ..."
outer finally: _MARKER_WORK_SEMAPHORE.release()   ← semaphore freed HERE
  ↑ while Marker worker THREAD IS STILL RUNNING
↓
second request arrives:
  _MARKER_WORK_SEMAPHORE.acquire(blocking=False) → SUCCEEDS (semaphore free)
  spawns second Marker worker thread
  → TWO zombie threads now running simultaneously ✗
```

The semaphore blocked *concurrent in-flight* attempts, but since it was released
in the outer `finally` (triggered by the caller returning), it was freed while
the underlying thread was still alive.

---

## Fix: Two-Layer Guard

### Layer 1 (unchanged) — `_MARKER_WORK_SEMAPHORE`
Blocks new Marker attempts while a conversion is *actively starting* (i.e.,
before the ThreadPoolExecutor has been created and submitted). Has the same
race described above on timeout.

### Layer 2 (new) — `_MARKER_DISABLED = threading.Event()`
Set to signalled the moment `_cf.TimeoutError` fires, **before** the semaphore
is released. All subsequent Marker requests check this flag first:

```python
if _MARKER_DISABLED.is_set():
    return self._pdfplumber_extract(
        tmp_path,
        fallback_reason="marker_disabled: previous timeout, Marker disabled for this process",
    )
```

With this ordering:

```
_cf.TimeoutError fires
→ _MARKER_DISABLED.set()      ← flag set FIRST
→ outer finally releases _MARKER_WORK_SEMAPHORE
second request checks _MARKER_DISABLED.is_set() → True → immediate pdfplumber
# No new Marker thread is ever created ✓
```

### Lifecycle

- `_MARKER_DISABLED` is `threading.Event()` — thread-safe, no GIL tricks needed.
- Set on first timeout, never auto-cleared for the process lifetime.
- Cleared explicitly by calling `_MARKER_DISABLED.clear()` — used in tests via
  the `reset_marker_state` autouse fixture.
- Result: **at most one zombie thread** can exist per process lifetime.

---

## Files Changed

| File | Change |
|---|---|
| `packages/research/ingestion/fetchers.py` | Added `_MARKER_DISABLED = threading.Event()`; updated comment block; added disabled-flag check at top of `_try_marker_or_fallback`; `_MARKER_DISABLED.set()` called in `_cf.TimeoutError` handler before semaphore release |
| `tests/test_ris_academic_pdf.py` | Added `reset_marker_state` autouse fixture to `TestMarkerFetcherIntegration`; updated timeout test to assert `_MARKER_DISABLED.is_set()`; added `test_marker_second_call_after_timeout_skips_new_thread` |

---

## New Test: `test_marker_second_call_after_timeout_skips_new_thread`

Uses `_CountingSlowMarker` that increments a counter each time `extract()` is
called (then sleeps 1s). Timeout is 50ms.

- Call 1: Marker starts, times out at 50ms, `_MARKER_DISABLED` set, pdfplumber_fallback returned
- Call 2: `_MARKER_DISABLED.is_set()` → immediate pdfplumber_fallback, no new thread
- Assertion: `worker_start_count["n"] == 1` (only one Marker worker ever started)

---

## Commands Run

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_academic_ingest_v1.py tests/test_ris_research_acquire_cli.py -v --tb=short
```
**73 passed, 0 failed** (was 72 — 1 new test added).

```
python -m pytest tests/ -x -q --tb=short
```
**2397 passed, 1 failed** — pre-existing `test_ris_claim_extraction` failure unchanged.

---

## Remaining Limitation

The one timed-out Marker worker thread **cannot be killed** on Windows (no
SIGKILL for threads). It runs to completion in the background (5–10+ min on
CPU). `_MARKER_DISABLED` ensures no further threads are spawned after that.
True cancellation requires a process boundary (subprocess/multiprocessing) and
is deferred to a future hardening pass if Marker ever becomes a production
parser on GPU.
