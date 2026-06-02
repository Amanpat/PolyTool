---
title: Fix Marker Ipc Live Validation Blockers
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_fix-marker-ipc-live-validation-blockers.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker Docker IPC Warm-Worker Live-Validation Blockers

**Date:** 2026-05-07
**Type:** Bug fix / docs correction
**Track:** RIS — L1 Marker IPC Warm-Worker (Feature 3 prerequisite)
**Codex review:** Skip — no execution, SVM, or trading files changed.

---

## Objective

Repair the four blockers identified during the 2026-05-07 live Docker/GPU validation
of the MarkerIPCWorker, without re-running live validation. The validation verdict
(**FAIL**) and L1 blocked status are unchanged.

---

## Blockers Fixed

### 1. Stale L1-unblocked docs

**Problem:** Five locations in docs described L1 as currently unblocked based on the
2026-05-03 hosting decision. After the 2026-05-07 live validation failure, those claims
are stale — the hosting decision resolved one blocker but live validation introduced a
new one (IPC warm-worker validation gate not yet passed).

**Files changed:**

| File | Change |
|------|--------|
| `docs/INDEX.md` | Updated row for `2026-05-03_academic-pipeline-hosting-decision.md` — replaced "L1 Marker production rollout unblocked" with "hosting blocker resolved; L1 remains blocked pending Marker Docker IPC warm-worker validation (>=3 warm papers, <=10s/paper for papers 2+)" |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Open Decisions entry: replaced "L1 Marker production rollout is now unblocked" with "Hosting blocker resolved; L1 remains blocked by Marker Docker IPC warm-worker validation" |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Session context entry (2026-05-03): struck through old claim and added `*(stale — housing blocker resolved but L1 re-blocked …)*` note |
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md` | Status line: replaced "L1 Marker production rollout is unblocked" with "Hosting blocker resolved. L1 Marker production rollout remains blocked by Marker Docker IPC warm-worker validation" |
| `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` | Added stale note in Summary and `## Is L1 unblocked?` section — original claims labeled as historical, forward pointer to 2026-05-07 validation dev log |

**Why:** Current-positive unblocked claims in docs mislead future sessions. Historical
references are preserved but clearly labeled as stale.

---

### 2. Dockerfile.ris rebuild gap

**Problem:** `docker compose --profile ris-gpu build ris-scheduler-gpu` failed with
`error: package directory './packages/research/relevance_filter' does not exist` because
`pyproject.toml` declares `packages.research.relevance_filter` but the builder stage stub
creation step did not include a `mkdir -p` for that directory. This prevented clean image
rebuilds; the live validation session had to use `docker cp` as a workaround.

**File changed:** `Dockerfile.ris`

**Change:** Added `&& mkdir -p packages/research/relevance_filter \` to the builder stub
creation block (between `packages/research/hypotheses` and `packages/research/scheduling`),
matching the actual directory that exists in the codebase.

---

### 3. Worker restart-after-timeout gap in `fetchers.py`

**Problem:** When `MarkerIPCWorker.parse()` timed out on paper 1, it terminated the worker
subprocess (setting `_proc = None`). Subsequent `parse()` calls found `is_alive()=False`
and returned `worker_not_running` immediately without any restart attempt. This caused all
papers after the first timeout to fail instantly — defeating the purpose of the warm-worker
session and meaning max_items=3 would actually complete 0 papers after one timeout.

The design intent (per the worker's API contract) was that callers call `restart()` after a
timeout. The fetcher's `_marker_ipc_worker_extract()` was not doing this.

**File changed:** `packages/research/ingestion/fetchers.py`

**Change:** In `_marker_ipc_worker_extract()`, after detecting `"marker_timeout"` in the
failure_reason from `parse()`, added a `try/except` that calls `self._ipc_worker.restart()`.

Behavior after fix:
- Paper 1 times out: `_marker_ipc_worker_extract()` returns `marker_failed` (unchanged).
- Worker is restarted before returning; `_terminate_worker()` already ran inside `parse()`.
- Paper 2 proceeds with the restarted worker and pays a new cold load.
- If restart fails (exception), it is logged as a warning and the error dict is still returned.
- `_MARKER_DISABLED` is never set by this code path.

**Constraints respected:**
- No pdfplumber fallback added.
- `_MARKER_DISABLED` not set.
- Restart failure propagates as a warning, not an exception.

---

## Tests Added

**File:** `tests/test_ris_marker_ipc_worker.py` — new class `TestFetcherIPCWorkerRestartAfterTimeout`

6 tests covering:

| Test | What it proves |
|------|---------------|
| `test_timeout_triggers_restart` | restart() called exactly once after a marker_timeout result |
| `test_timeout_does_not_set_marker_disabled` | _MARKER_DISABLED never set by IPC path |
| `test_second_paper_succeeds_after_timeout_and_restart` | After restart, next parse() succeeds — not worker_not_running |
| `test_no_restart_on_non_timeout_error` | restart() NOT called for non-timeout errors (OOM, crash) |
| `test_restart_failure_does_not_raise` | restart() exception caught; method still returns error dict cleanly |
| `test_worker_not_running_result_does_not_trigger_restart` | worker_not_running is not a timeout — no restart |

Tests use `_MockIPCWorker` (a minimal mock with `parse()` / `restart()` call tracking)
and `_fetcher_with_mock_worker()` to exercise `_marker_ipc_worker_extract()` directly.
No real Docker, GPU, subprocess, or network required.

---

## Commands Run and Outputs

### Test run

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
```

**Result:** 125 passed, 1 skipped in 2.19s

### CLI smoke test

```
python -m polytool research-marker-queue --help
```

**Result:** CLI loads, `warm-process` subcommand present, L1 gate language intact.

### Stale grep verification

```
git grep -n "L1 Marker production rollout unblocked|production rollout unblocked|L1.*unblocked" docs
```

**Result:** Only two hits remain — both are the stale-labeled historical references in
`2026-05-03_academic-pipeline-hosting-decision.md` and `Current-Focus.md` session context.
No unqualified current-positive claims remain.

---

## Files Changed

| File | Why |
|------|-----|
| `packages/research/ingestion/fetchers.py` | Worker restart-after-timeout fix |
| `Dockerfile.ris` | Add `relevance_filter` stub dir to builder stage |
| `docs/INDEX.md` | Remove stale unblocked claim from index entry |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Remove / label stale unblocked claims |
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md` | Update status line |
| `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` | Add stale notes to historical claims |
| `tests/test_ris_marker_ipc_worker.py` | Add 6 restart-after-timeout tests |

---

## Remaining Validation Prerequisites (L1 still blocked)

Before L1 can be unblocked, the following must succeed in a live Docker/GPU run:

1. **arXiv API cooldown** — wait ≥60 min after last session's API calls before retrying.
2. **Simple text-heavy papers only** — use economics/policy papers (<20 pages, no complex
   figures/equations). The Polymarket microstructure paper (`arxiv:2604.24366`, 15 pages)
   parsed in ~6s OCR (single-paper validation 2026-05-05). The Mistral 7B (55 pages) and
   LoRA (139 chunks including appendix) papers both exceeded the 900s timeout.
3. **Dockerfile.ris rebuild** — image must be rebuilt after the `relevance_filter` fix
   before the next live validation run. No more `docker cp` workarounds.
4. **Run `warm-process --max-items 3`** — verify ≥3 papers complete in one session with
   `ipc_warm_worker_used=true` and papers 2+ showing `parse_seconds <= 10s`.

---

## L1 Production Status

**L1 production remains BLOCKED.** This session fixed infrastructure gaps and test
coverage but did NOT re-run live Docker validation. Feature 3 (Marker Docker IPC
warm-worker) is not complete. L2/PaperQA2/L4 remain stubs.

The gate requires ≥3 warm papers at ≤10s/paper in one live Docker/GPU session.
That gate has not been passed.
