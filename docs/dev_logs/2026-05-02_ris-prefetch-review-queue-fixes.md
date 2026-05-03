# RIS L3.1 Prefetch Review Queue — Codex PASS WITH FIXES Resolution

**Date:** 2026-05-02
**Codex review commit:** `ac3aebc` (L3.1 prefetch review queue + label store + hold-review mode)
**Codex verdict:** PASS WITH FIXES → fixed in this session

---

## Issues Fixed

### M1: Queue write failure produced misleading `queued_for_review: true`

**Before:** `_write_to_review_queue()` returned `None`. On exception, it swallowed the error
and printed only a warning to stderr. Both URL mode and search mode unconditionally emitted
`"queued_for_review": true` regardless of whether the write succeeded.

**After:** `_write_to_review_queue()` returns `(bool, Optional[str])`:
- `(True, None)` on successful write (including idempotent already-queued)
- `(False, error_message)` if the write raised

Both call sites (URL mode and search mode) now:
- Set `"queued_for_review": queue_ok` (false when write failed)
- Include `"queue_error": <message>` in JSON output when `queue_ok=False`
- Print `WARNING: hold-review queue write failed: ...` to stderr on failure
- Still return 0 and do NOT ingest — the hold-out invariant is preserved even on write failure

**Files changed:** `tools/cli/research_acquire.py`

### L2: Malformed JSONL silently dropped in `_read_jsonl()`

**Before:** `except json.JSONDecodeError: pass` — bad lines vanished without any signal.

**After:** Bad lines print `WARNING: malformed JSONL in <path> at line <N>: <error>` to stderr.
Valid records are still returned; the store remains usable. This is fail-loud behavior
appropriate for an append-only audit store.

**Files changed:** `packages/research/relevance_filter/queue_store.py`

### L1: Feature doc omitted hold-review mode, queue/label paths, health counters

**Before:** `FEATURE-ris-prefetch-relevance-filter-v0.md` Filter Modes section listed only
`{off, dry-run, enforce}`. Queue/label artifact paths were absent. "Deferred Items" still
listed `Label store file` and `research-health label_count counter` as deferred despite
both being shipped in L3.1.

**After:**
- Filter Modes section replaced with a 4-row table including `hold-review` with behavior description
- Added `hold-review` queue failure semantics (queued_for_review=false + queue_error, hold-out preserved)
- Added `research-prefetch-review` CLI reference
- Added `Artifact Paths` table (filter audit, hold-review queue, label store)
- Added queue record JSON schema example
- Added `Health Counters` table (pending_review_count, label_count, allowed/rejected)
- Removed `Label store file` and `research-health label_count counter` from Deferred Items (both shipped)
- Added `queue_store.py` and `research_prefetch_review.py` to Files Shipped table

**Files changed:** `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md`

### L3: Search-mode hold-review had no offline test coverage

**Before:** `TestPrefetchFilterModes` only covered URL mode. The search mode hold-review
code path (`_run_search_mode`, lines 673–701) was untested.

**After:** `TestSearchModeHoldReview.test_search_mode_hold_review_queues_review_does_not_ingest`
— fully offline via monkeypatching:
- `LiveAcademicFetcher.search_by_topic` returns 2 papers (REVIEW + REJECT)
- `KnowledgeStore` stubbed to avoid DB I/O
- `IngestPipeline.ingest_external` spied on — asserts it is never called
- Verifies REVIEW paper in queue, REJECT paper skipped, queue file has exactly 1 record

**Files changed:** `tests/test_ris_research_acquire_cli.py`

---

## New Tests Added

| Test | File | What it covers |
|------|------|----------------|
| `TestReviewQueueStore::test_malformed_jsonl_warns` | `test_ris_relevance_filter.py` | Bad JSONL line → valid records returned + WARNING to stderr |
| `TestPrefetchFilterModes::test_hold_review_queue_write_failure_reports_error` | `test_ris_research_acquire_cli.py` | enqueue raises → `queued_for_review=false` + `queue_error` in output, rc=0, no ingest |
| `TestSearchModeHoldReview::test_search_mode_hold_review_queues_review_does_not_ingest` | `test_ris_research_acquire_cli.py` | Search mode hold-review: REVIEW queued, REJECT skipped, ingest_external never called |

---

## Tests Run

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_eval_benchmark.py -v --tb=short
```

**160 passed, 0 failed** (was 157 before this session — 3 new tests added)

---

## Remaining Limitations

- `research-health` `label_count` counter is still deferred (useful once labels accumulate)
- Enforce mode still fails open on scoring/config errors (low risk pre-production)
- Queue idempotency check is O(n) per enqueue call (acceptable at current queue sizes)

---

## Codex Review Summary

Tier: PASS WITH FIXES — M1 + L1 + L2 + L3 fixed in this session. No HIGH/CRITICAL issues
were found. All issues addressed. 160/160 tests pass.
