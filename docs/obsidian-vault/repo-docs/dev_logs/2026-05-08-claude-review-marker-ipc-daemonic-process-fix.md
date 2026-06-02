---
title: Claude Review Marker Ipc Daemonic Process Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_claude-review-marker-ipc-daemonic-process-fix.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Claude Review — Marker IPC Daemonic Process Fix

Date: 2026-05-08
Type: read-only code review
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1 (daemon=False fix)
Verdict: **PASS**

---

## Summary

The daemon=False fix is correct, complete, and safe. All 9 verification items pass.
Codex review may proceed. Docker rebuild is required before live validation.

---

## Files Reviewed

- `packages/research/ingestion/marker_ipc_worker.py` (untracked — new file from fix session)
- `packages/research/ingestion/fetchers.py` (modified — pre-existing session changes)
- `packages/research/ingestion/marker_queue.py` (modified — pre-existing session changes)
- `tests/test_ris_marker_ipc_worker.py` (untracked — new file from fix session)
- `tests/test_ris_marker_queue.py` (modified — prior session base + daemon-safety tests appended)
- `docs/dev_logs/2026-05-08_fix-marker-ipc-daemonic-process-error.md`
- `docs/CURRENT_DEVELOPMENT.md` (read-only, not touched by fix)

---

## Commands Run and Outputs

### Tests

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
```

```
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
collected 155 items

tests\test_ris_marker_ipc_worker.py ....................................
........
tests\test_ris_marker_queue.py ...........................................
...................s..................................................

154 passed, 1 skipped in 2.90s
```

1 skipped = platform-conditional test skipping on Windows (expected).

### CLI help

```
python -m polytool research-marker-queue warm-process --help
```
→ Exit 0. `--max-items` and `--marker-timeout` present. No regressions.

### Git diff stat (HEAD)

```
Dockerfile.ris                      |   1 +   (pre-existing: mkdir relevance_filter)
docs/INDEX.md                       |   2 +-  (pre-existing)
packages/research/ingestion/fetchers.py      | 137 +++++  (pre-existing IPC integration)
packages/research/ingestion/marker_queue.py  | 112 +++-   (pre-existing queue v0)
tests/test_ris_marker_queue.py               | 663 +++    (prior base + 3 new daemon tests)
tools/cli/research_marker_queue.py           | 133 ++++-  (pre-existing)
```

Note: `marker_ipc_worker.py` and `test_ris_marker_ipc_worker.py` are **untracked** (new files
from the fix session, not yet committed). They do not appear in `git diff HEAD` but are visible
in `git status` as `??`.

---

## Verification Findings

### 1. IPC worker process and restart path are non-daemonic ✅

`marker_ipc_worker.py` lines 239 and 287–296:

```python
def _make_process(self, target, args, daemon=False):   # default changed
    ...

# daemon=False is required: daemon processes cannot spawn child processes,
# and Marker's ONNX/torch pipeline spawns internal worker processes during
# extraction. With daemon=True, paper 2+ fail immediately with
# "daemonic processes are not allowed to have children".
proc = self._make_process(
    target=_marker_ipc_worker_main,
    args=(req_q, res_q, self._extractor_cls),
    daemon=False,                                       # explicit, with comment
)
```

`restart()` calls `self.start()` unconditionally (line 418), which routes through
`_make_process(..., daemon=False)`. Both the initial start and the restart path produce
non-daemon processes. The explanatory comment is present and accurate.

### 2. Tests cover repeated parse behavior and daemon safety ✅

`TestMarkerIPCWorkerDaemonSafety` (5 tests in `test_ris_marker_ipc_worker.py`):
- `test_start_passes_daemon_false_to_factory` — captures the exact `daemon` value forwarded to the factory and asserts `False`. This is an independent verification: uses a custom `_capturing_factory` rather than `_thread_process_factory`, so the assertion is not circular.
- `test_restart_passes_daemon_false_to_factory` — same capture for the restart path (2 factory calls, both `daemon=False`).
- `test_multi_parse_paper1_ok_paper2_ok` — the core live-failure scenario: paper 1 then paper 2 both succeed on the same warm worker. The test includes an error message hint: "If failure_reason contains 'daemonic', daemon=False fix was not applied."
- `test_daemonic_error_from_extractor_surfaced_as_structured_error` — injects `AssertionError("daemonic processes are not allowed to have children")` from the extractor; confirms it becomes a structured `{"status": "error"}` dict and the worker stays alive.
- `test_worker_survives_daemonic_error_and_next_paper_succeeds` — transient daemonic error on paper 1; paper 2 succeeds on the same worker.

`TestProcessNextIPCDaemonSafety` (3 tests in `test_ris_marker_queue.py`):
- `test_two_paper_session_both_done` — two enqueued papers processed via `process_next_ipc`, both `marker_ready=True`, counts `done=2`.
- `test_daemonic_error_from_marker_internals_is_retryable` — exact failure reason from the live log (`"daemonic processes are not allowed to have children"`) results in `queue_status=pending` (retryable, not terminal). Confirms queue v0 retry semantics are intact for this error.
- `test_direct_pdf_path_two_papers_both_done` — two `pdf_url` items, both routed via `fetch_pdf_direct`, both done.

### 3. Timeout and restart behavior intact ✅

`parse()` still catches `queue.Empty` and calls `_terminate_worker()` (lines 346–361). The SIGTERM → grace → SIGKILL escalation in `_terminate_worker()` is unchanged. `restart()` still terminates the current worker before respawning via `start()`. All 12 pre-existing timeout/restart tests pass without modification.

One related change in tests: `_thread_process_factory` now accepts `daemon=False` (matching the real factory signature) but always creates daemon threads internally. This is by design — timeout tests leave threads running for 60 seconds; non-daemon threads would prevent pytest from exiting. The comment explains this. The independent `_capturing_factory` tests verify the value passed without relying on the thread factory.

### 4. Direct-PDF bypass still exists and avoids arXiv metadata ✅

`fetchers.py` line 672: `fetch_pdf_direct()` still present.
`_parse_pdf()` at line 277 still routes to `_marker_ipc_worker_extract()` when `_ipc_worker` is set.
`_marker_ipc_worker_extract()` at line 291 still delegates to `self._ipc_worker.parse()`.
`fetch_pdf_direct()` sets `is_url` and calls `self._pdf_http_fn` without touching `self._http_fn`
(the arXiv metadata client). `TestFetchPdfDirect` tests (8 cases) confirm the Atom API is
never called for `fetch_pdf_direct` invocations.

### 5. No `_MARKER_DISABLED` set in IPC failures ✅

`marker_ipc_worker.py` module docstring (line 30): "Does NOT set _MARKER_DISABLED."
`parse()` docstring (line 314): "Does NOT set _MARKER_DISABLED."
Class docstring (line 163): "_MARKER_DISABLED is NOT set."

`fetchers.py` line 180: "Does NOT touch _MARKER_DISABLED."
`fetchers.py` line 275: "Bypasses _MARKER_DISABLED and semaphore."
`fetchers.py` line 294: "Does NOT set _MARKER_DISABLED."

The only `_MARKER_DISABLED.set()` calls are in `_marker_production_extract_thread()` (thread path)
and `_marker_production_extract_subprocess()` (cold subprocess path). The IPC path does not pass
through either of those methods. `test_timeout_does_not_set_marker_disabled` and
`test_error_does_not_set_marker_disabled` both assert the flag remains clear after IPC errors.

### 6. No pdfplumber fallback added ✅

`marker_ipc_worker.py`: no `pdfplumber` import, no pdfplumber reference anywhere.
Module docstring (line 30): "Does NOT fall back to pdfplumber."
Class docstring (line 170): "No pdfplumber fallback in any code path."
`_marker_ipc_worker_extract()` in `fetchers.py` line 295: "Does NOT fall back to pdfplumber."
`test_no_pdfplumber_fallback_on_error` (in both test files) asserts `body_source` is never
`"pdfplumber_fallback"` or `"pdfplumber"`.

### 7. Queue v0 semantics intact ✅

`marker_queue.py` was not modified by the fix session. The pending→processing→done/failed flow,
`MAX_ATTEMPTS=3`, `is_marker_ready()` gate, `MIN_MARKER_BODY_LENGTH=5000` — all unchanged.
The new `test_daemonic_error_from_marker_internals_is_retryable` test directly confirms queue
semantics are correct for the exact error string from the live validation failure.

### 8. No closeout or L1-unblocked docs changed ✅

`CURRENT_DEVELOPMENT.md` is NOT in `git status` as modified — unchanged by the fix session.
It still reads (line 115): "Blocked on Docker IPC warm-worker (v1)."
And (line 139, paraphrased): "L1 Marker Production Rollout remains PAUSED — blocked on Docker
IPC warm-worker v1."
`docs/INDEX.md` shows as modified in `git status M` but this is a pre-existing change from
earlier sessions (the fix session only wrote to `docs/dev_logs/`).
`docs/features/ris-marker-structural-parser-scaffold.md` not in `git status` at all — untouched.
No Feature 3 closeout document exists. L1 remains explicitly blocked.

### 9. Docker image is stale relative to code changes ✅

`marker_ipc_worker.py` is an **untracked** new file — it has never been committed and therefore
was never baked into the Docker image. The previous live run confirmed the image still uses a
stale installed `packages` that predates the `be8b4f2` Marker queue v0 commit; the direct-PDF
run required a bind-mount workaround to inject current code.

The `Dockerfile.ris` modification in `git status` (pre-existing: adds
`mkdir -p packages/research/relevance_filter`) is unrelated to this fix.

**The Docker image must be rebuilt before live validation.**

---

## One Risk Flag

The `_marker_ipc_worker_main` loop catches all exceptions via `except Exception as exc`
(line 130) and returns a structured error dict. `AssertionError` is a subclass of `Exception`,
so the live-validation daemonic error (`AssertionError: daemonic processes are not allowed...`)
was correctly caught and returned as `{"status": "error", "error": "..."}`. With `daemon=False`,
this error should no longer arise from the process topology. If Marker's internal children
themselves are daemon processes that try to spawn grandchildren, the error could recur at a
deeper nesting level. This cannot be ruled out without a live run.

---

## Whether Codex Review May Proceed

**Yes.** The fix is structurally correct and all tests pass. No mandatory-review files
(execution/, kill_switch.py, risk_manager.py, rate_limiter.py) were touched. The changed
files fall in the `packages/research/ingestion/` strategy tier: Codex review is recommended,
not mandatory, per the project's Codex review policy. A Codex review may proceed with
`--background` flag without blocking the next step.

---

## Whether Docker Rebuild Is Required Before Live Validation

**Yes, unconditionally.** The fix lives in `marker_ipc_worker.py` which is:
1. An untracked file (not committed, not in any Docker layer).
2. Not in `packages/research/ingestion/` inside the baked image (confirmed by the live
   validation log: the image's installed packages predate even the Marker queue v0 commit).

The bind-mount workaround from the previous run (`-v .../packages/research:/usr/local/lib/...`)
would continue to work as an alternative to a full rebuild, since it replaces the baked stale
install. However, the clean path is a proper Docker rebuild to avoid relying on the overlay.

**Pre-conditions for next live validation:**
1. Docker rebuild OR verify bind-mount workaround covers `marker_ipc_worker.py`.
2. Reset `artifacts/research/marker_validation_queue_direct/` — paper 2 (`arxiv:2109.07581`,
   2 attempts) and paper 3 (`arxiv:1910.08858`, 0 attempts) remain in `pending` state. Either
   force-reset with `--force` or create a new queue dir with 3 fresh entries.
3. Run: `warm-process --max-items 3 --json`
4. Acceptance gates: ≥3 done, papers 2+ `parse_seconds ≤ 10s`, `body_source=marker`,
   `ipc_warm_worker_used=true`, no pdfplumber fallback.

---

## Remaining Blockers

- L1 remains blocked on live validation.
- Docker rebuild or bind-mount verification required before next validation run.
- Potential residual risk: Marker's internal children spawning grandchildren (unlikely, unverifiable offline).
- No code, tests, queues, Docker, or governance docs were modified by this review session.
