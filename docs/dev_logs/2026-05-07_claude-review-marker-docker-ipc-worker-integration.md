# Read-Only Sanity Review: Marker Docker IPC Warm-Worker Integration

**Date:** 2026-05-07  
**Reviewer:** Claude (read-only pass)  
**Status:** PASS — Codex review may proceed

---

## Files Reviewed

- `packages/research/ingestion/fetchers.py` (modified)
- `packages/research/ingestion/marker_queue.py` (modified)
- `tools/cli/research_marker_queue.py` (modified)
- `tests/test_ris_marker_queue.py` (modified)
- `packages/research/ingestion/marker_ipc_worker.py` (new, untracked)
- `tests/test_ris_marker_ipc_worker.py` (new, untracked)
- `docs/dev_logs/2026-05-07_fix-marker-docker-ipc-worker-integration.md`

---

## Commands Run and Outputs

### 1. CLI help

```
python -m polytool research-marker-queue --help
```

Output confirms `warm-process` is present in the subcommand list:

```
{enqueue,list,process,warm-process,counts}
    warm-process  Process next N pending items using MarkerIPCWorker
                  (warm IPC, Linux/Docker). On Windows, falls back to
                  warm thread worker. NOTE: L1 production gated — live
                  Docker/GPU validation required.
```

**CHECK 1 PASS:** `warm-process` is exposed in `--help`.

### 2. Tests

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q
```

```
119 passed, 1 skipped
```

The 1 skip is the pre-existing Linux-platform skip in `TestWarmWorkerBehavior`
(`test_warm_thread_worker_raises_on_subprocess_platform` — correctly skipped on
Windows because the guard only fires on Linux/Docker). No new failures.

**CHECK 3/4/5/6 PASS (test coverage):** 17 new IPC tests pass; Windows path
test passes; no regressions in the original 102-test baseline.

### 3. Git diff scope

```
git diff --stat / --name-status
```

```
M  packages/research/ingestion/fetchers.py      (+40)
M  packages/research/ingestion/marker_queue.py  (+98)
M  tests/test_ris_marker_queue.py               (+236)
M  tools/cli/research_marker_queue.py           (+114)

?? packages/research/ingestion/marker_ipc_worker.py   (new, untracked)
?? tests/test_ris_marker_ipc_worker.py                (new, untracked)
```

No unrelated files touched. SVM, trading, L2/L4, config, infra, artifacts,
Dockerfile, docker-compose — all clean.

**CHECK 8 PASS:** Scope is exactly the four expected files plus the two
pre-existing untracked new files from the prior work packet.

---

## Findings Per Check

### CHECK 1 — `warm-process` in CLI help
**PASS.** `{enqueue,list,process,warm-process,counts}` confirmed in live
`--help` output. Subparser has `--max-items`, `--marker-timeout`, `--json`.

### CHECK 2 — `MarkerIPCWorker` imported/used by queue/fetcher
**PASS.** `marker_queue.py` line 386: `from packages.research.ingestion.marker_ipc_worker import MarkerIPCWorker` inside `process_next_ipc` (lazy import, Linux/Docker path only). `fetchers.py` stores the injected worker at `self._ipc_worker` and calls `self._ipc_worker.parse()` in `_marker_ipc_worker_extract`.

### CHECK 3 — Queue reuses one worker across multiple items
**PASS.** `TestProcessNextIPC.test_multiple_items_share_one_worker_instance`
uses `_IPCTrackingFetcher` wrapping a single `_MockIPCWorker` instance and
asserts `parse_call_count == 2` for 2 enqueued papers. `process_next_ipc` creates
one worker, constructs one `LiveAcademicFetcher(_ipc_worker=worker)`, and calls
`process_next` with that fetcher — the worker is shared across the full batch
by construction.

### CHECK 4 — Windows thread mode unchanged
**PASS.** `process_next` is untouched. `process_next_ipc` falls back to
`create_warm_thread_worker()` on Windows (`_MARKER_DEFAULT_USE_PROCESS=False`).
`test_windows_thread_path_unchanged` passes. The `TestWarmWorkerBehavior` class
(pre-existing) continues to verify thread vs. subprocess selection.

### CHECK 5 — IPC failure does not set `_MARKER_DISABLED`
**PASS.** Verified two ways:
1. Source inspection: `_marker_ipc_worker_extract` (lines 291–318) contains
   zero calls to `_MARKER_DISABLED.set()`. The only references to
   `_MARKER_DISABLED` in the method body are in the docstring comment
   ("Does NOT set _MARKER_DISABLED.").
2. Test: `TestIPCFetcherExtract.test_error_does_not_set_marker_disabled` calls
   `_marker_ipc_worker_extract` with an error-returning mock worker, then
   asserts `not _MARKER_DISABLED.is_set()` — passes.

### CHECK 6 — No pdfplumber fallback introduced
**PASS.** Verified two ways:
1. `_parse_pdf` dispatch chain: IPC path (`if self._ipc_worker is not None:
   return self._marker_ipc_worker_extract(tmp_path)`) is placed **before** all
   `pdfplumber` dispatches (lines 274–278). Once `_ipc_worker` is set, execution
   never reaches `_pdfplumber_extract` or `_try_marker_or_fallback`.
2. `_marker_ipc_worker_extract` body: only returns `("", {"body_source":
   "marker_failed", ...})` on error — no `_pdfplumber_extract` call anywhere
   in the method.
3. Test: `TestIPCFetcherExtract.test_no_pdfplumber_fallback_on_error` asserts
   `body_source not in ("pdfplumber_fallback", "pdfplumber", "pdf")` — passes.

### CHECK 7 — L1 production documented/gated as blocked
**PASS.** Gate language confirmed in three places:
- `marker_queue.py` docstring (line 345): "NOTE: L1 production is NOT unblocked.
  Live validation required before production deployment of this path."
- `research_marker_queue.py` (lines 191, 231): "NOTE: L1 production remains
  gated until live Docker/GPU validation passes." — printed to stdout on every
  non-JSON `warm-process` invocation.
- `research_marker_queue.py` subparser help (line 366): "NOTE: L1 production
  gated — live Docker/GPU validation required." — visible in `--help`.

### CHECK 8 — No unrelated files touched
**PASS.** `git diff --name-status` shows exactly the four expected files
modified. `git status --short` on `packages tools tests polytool config infra
docker-compose.yml Dockerfile.ris artifacts` shows only those four modified
plus the two pre-existing untracked new files (`marker_ipc_worker.py`,
`test_ris_marker_ipc_worker.py`).

---

## Minor Observations (non-blocking)

1. **Em-dash encoding in CLI help**: The `—` in `"NOTE: L1 production gated —
   live Docker/GPU validation required."` renders as a replacement character
   on the Windows cp1252 terminal. Cosmetic only; pre-existing platform issue,
   not introduced by this work.

2. **`ipc_warm_worker_used=False` when `_fetcher` injected**: When
   `process_next_ipc` is called with `_fetcher` injection (test path) and no
   `_ipc_worker` injection, the flag is correctly `False` because no real IPC
   worker was created. The key is always present in results — the contract is
   satisfied.

3. **`_MARKER_DISABLED` not cleared between test methods**: The
   `test_error_does_not_set_marker_disabled` test calls `_MARKER_DISABLED.clear()`
   at the start — good defensive practice. Other `TestIPCFetcherExtract` tests
   that test the error path do not clear it, but since `_marker_ipc_worker_extract`
   never sets the flag, this is safe and correct.

4. **`process_next` docstring not updated**: The existing `process_next` method
   still says "warm IPC worker is deferred to v1" in its docstring. This is now
   technically stale (v1 is implemented via `process_next_ipc`), but it is
   accurate in the narrow sense that `process_next` itself still spawns per-paper.
   Not a bug — callers who want warm IPC should use `process_next_ipc`. A
   docstring touch-up would be clean-up work for a future session.

---

## PASS / FAIL Verdict

**PASS**

All eight verification checks pass. The integration exists in the checked-out
files, is tested offline, and correctly preserves all required invariants
(`_MARKER_DISABLED` untouched, no pdfplumber fallback, Windows thread path
unchanged, one worker per batch).

---

## Remaining Blockers Before L1 Unblock

1. **Live Docker/GPU validation** — run `warm-process` against a real Marker
   install with ≥2 papers and confirm:
   - Paper 1 cold-load time logged (expected 80–270 s on RTX 2070 Super)
   - Papers 2+ warm parse time ≤10 s
   - `ipc_warm_worker_used: true` in `--json` output
   - No orphan subprocesses after `warm-process` exits
2. **L1 gate language update** — after live validation passes, update
   `process_next` docstring to remove "deferred to v1" note.

---

## Codex Review Readiness

**Codex review may proceed.** The integration is real, tested, and scoped
correctly. Suggested Codex review scope:
- `packages/research/ingestion/fetchers.py` — IPC dispatch routing, no
  `_MARKER_DISABLED` set, no fallback
- `packages/research/ingestion/marker_queue.py` — worker lifecycle management,
  `finally` shutdown, `ipc_warm_worker_used` flag
- `tools/cli/research_marker_queue.py` — `warm-process` subcommand output,
  L1 gate reminder
- `tests/test_ris_marker_queue.py` — new IPC test classes
