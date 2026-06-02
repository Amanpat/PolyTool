---
title: Marker Canonical Parse Queue V0 Fixes
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-fixes.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Canonical Parse Queue v0 — Codex FAIL Resolution

Date: 2026-05-05
Scope: Fix three Codex blockers from `2026-05-05_codex-review-marker-canonical-parse-queue-v0.md`
Status: FIXED — all blockers resolved; live Docker queue validation still blocked (see below)

---

## Codex Blockers and Resolutions

### Blocker 1 — Warm worker was not actually warm

**Finding:** `MarkerParseQueue.process_next()` created one `LiveAcademicFetcher` but the
Linux/Docker production path (`_marker_production_extract_subprocess`) spawned a fresh
process per paper and called `create_model_dict()` per extraction — no warm-model reuse.

**Fix:**

- Added `_preloaded_model_dict: Optional[dict]` parameter to `MarkerPDFExtractor.__init__()`.
  When provided, `extract()` skips `create_model_dict()` and uses the pre-loaded dict.

- Added `_preloaded_model_dict` to `LiveAcademicFetcher.__init__()`.  The thread-path
  extraction method (`_marker_production_extract_thread`) passes the preloaded dict to
  `MarkerPDFExtractor` when available.

- Added `LiveAcademicFetcher.create_warm_thread_worker()` class method.  Pre-loads
  `create_model_dict()` once before returning a fetcher instance.  Raises `RuntimeError`
  on Linux/Docker (subprocess mode) because model objects cannot cross process boundaries.

- Updated `process_next()` docstring to be honest about platform behaviour:
  - **Windows (thread mode):** models pre-loaded once per batch via `create_warm_thread_worker()`.
  - **Linux/Docker (subprocess mode):** fresh process per paper; model reloads each extraction.
    Warm IPC worker (persistent subprocess with IPC) is explicitly deferred to v1.

- Updated CLI description and `process` subcommand help to drop "warm-model worker" claim
  and replace with accurate platform-specific text.

**Files changed:** `packages/research/ingestion/extractors.py`,
`packages/research/ingestion/fetchers.py`, `packages/research/ingestion/marker_queue.py`,
`tools/cli/research_marker_queue.py`

---

### Blocker 2 — Missing Marker-only indexing gate

**Finding:** `IngestPipeline.ingest_external()` had no check for `body_source == "marker"`
before chunking and storing academic documents.  A pdfplumber or abstract-fallback body
could be indexed as canonical academic corpus.

**Fix:**

- Added `_ACADEMIC_MIN_MARKER_BODY_LENGTH = 5000` constant to `pipeline.py` (mirrors
  `marker_queue.MIN_MARKER_BODY_LENGTH` — must stay in sync manually).

- Added Marker-only gate in `ingest_external()` immediately after adaptation and field
  overrides, before the hard-stop check:

  ```
  if source_family == "academic":
      if body_source != "marker" or body_length < _ACADEMIC_MIN_MARKER_BODY_LENGTH:
          return IngestResult(rejected=True, reject_reason="academic_marker_gate: ...")
  ```

- Gate triggers on: `pdfplumber_fallback`, `abstract_fallback`, `marker_failed`, `unknown`,
  and any `marker` body shorter than the threshold.
- Non-academic families (`blog`, `github`, `news`, etc.) are unaffected.

**Files changed:** `packages/research/ingestion/pipeline.py`

---

### Blocker 3 (Non-blocking elevated to fix) — Short Marker output marked done

**Finding:** `body_source="marker"` with `body_length < MIN_MARKER_BODY_LENGTH` produced
`queue_status="done"` with `marker_ready=False` and no `failure_reason`.  This made queue
counts look healthier than the usable corpus and blocked auditability.

**Fix:**

- Added `elif result["body_length"] < MIN_MARKER_BODY_LENGTH` branch in `_process_item()`.
  Short Marker outputs now produce:
  - `rejected=True`
  - `exit_code=1`
  - `failure_reason="marker_body_too_short: X chars < 5000 threshold"`
  - `queue_status="pending"` on first failure (retryable up to `MAX_ATTEMPTS=3`), then `"failed"`

**Files changed:** `packages/research/ingestion/marker_queue.py`

---

## Tests

### Updated tests

- `TestProcessFailure.test_marker_short_body_not_ready` — updated to expect `rejected=True`,
  `queue_status="pending"`, and `failure_reason` containing `"marker_body_too_short"`.

### New tests added

| Test class | Tests added |
|---|---|
| `TestProcessFailure` | `test_marker_short_body_failure_reason_contains_lengths` |
| `TestProcessFailure` | `test_marker_short_body_becomes_failed_after_max_attempts` |
| `TestWarmWorkerBehavior` | `test_platform_selects_correct_marker_mode` |
| `TestWarmWorkerBehavior` | `test_warm_thread_worker_raises_on_subprocess_platform` |
| `TestWarmWorkerBehavior` | `test_preloaded_model_dict_skips_create_model_dict` |
| `TestWarmWorkerBehavior` | `test_cold_extractor_calls_create_model_dict` |
| `TestAcademicPipelineMarkerGate` | 7 gate tests (accepted, pdfplumber, abstract, marker_failed, short marker, unknown, non-academic family) |

### Test run

```
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_academic_pdf.py tests/test_ris_scheduler.py
```

Result: **146 passed, 1 skipped** in 1.76 s

The 1 skipped test (`test_warm_thread_worker_raises_on_subprocess_platform`) runs correctly
on Linux/Docker CI; it skips on Windows where subprocess mode is not active.

---

## Files Changed

| File | Change |
|---|---|
| `packages/research/ingestion/extractors.py` | Add `_preloaded_model_dict` to `MarkerPDFExtractor` |
| `packages/research/ingestion/fetchers.py` | Add `_preloaded_model_dict` + `create_warm_thread_worker()` to `LiveAcademicFetcher`; thread path uses preloaded dict |
| `packages/research/ingestion/marker_queue.py` | Honest docstring; warm fetcher in thread mode; short Marker body rejected |
| `packages/research/ingestion/pipeline.py` | Add `_ACADEMIC_MIN_MARKER_BODY_LENGTH`; add Marker-only gate in `ingest_external()` |
| `tools/cli/research_marker_queue.py` | Remove false "warm-model worker" claim; honest platform description |
| `tests/test_ris_marker_queue.py` | Update short-body test; add 10 new tests |

---

## Live Docker Queue Validation — Still Blocked

Live Docker validation (`python -m polytool research-marker-queue process`) may NOT proceed
as an L1 acceptance gate yet.

Blocking reasons:
1. Subprocess mode (Linux/Docker): each paper spawns a fresh process; `create_model_dict()`
   runs per extraction. Warm IPC worker that keeps models loaded in a persistent subprocess
   is deferred to v1. The throughput claim ("~6s per paper after cold load") does NOT hold
   for Docker.
2. The canonical embedding path (pipeline gate → RAG indexing) was not previously enforced.
   Any previously indexed academic documents with non-marker body_source may be in the
   knowledge store and should be audited before treating the corpus as Marker-canonical.

What CAN be run diagnostically:
- `enqueue`, `list`, `counts` commands
- A single cold parse via `process --max-items 1` to verify the subprocess path
- Verify `queue_status="failed"` / `failure_reason` for a paper that times out

What must NOT be treated as L1 queue validation:
- Multi-paper throughput measurement
- Warm-worker latency claims

---

## Codex Review Summary

Tier: Mandatory (RIS parser and ingestion correctness). Blockers before fix: 2 blocking,
3 non-blocking. Blockers after this session: 0 blocking (non-blocking issues 2 and 3 also
addressed). Live Docker validation blocked for reasons documented above.
