# Codex Review: RIS L3.1 Prefetch Review Queue + Label Store

Date: 2026-05-02
Reviewer: Codex (automated — Claude Code)
Verdict: **PASS WITH FIXES**

---

## Commands Run

| Command | Exit Code |
|---------|-----------|
| `python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_eval_benchmark.py -v --tb=short` | 0 |
| `python -m polytool research-acquire --help` | 0 |
| `python -m polytool --help \| grep -i "review\|queue\|label"` | 0 |

---

## Test Results

**157 passed, 0 failed, 0 skipped** (1.63 s)

Breakdown:
- `test_ris_relevance_filter.py`: 41 tests (scorer, config loader, queue store, label store)
- `test_ris_research_acquire_cli.py`: 71 tests (dry-run, full-flow, prefetch filter modes URL path, review CLI)
- `test_ris_eval_benchmark.py`: 45 tests (eval benchmark, simulate-prefetch-filter)

---

## Check Results

### 1. Default mode off

**PASS**

`argparse` default for `--prefetch-filter-mode` is `"off"` (`research_acquire.py:245`).
`_score_candidate_for_filter()` guards on `getattr(args, "prefetch_filter_mode", "off") == "off"` and returns `None` immediately (`research_acquire.py:54`).
When `filter_decision is None` the entire filter block is skipped (`research_acquire.py:359`).
No scoring, no audit write, no queue write can occur unless the caller explicitly passes `--prefetch-filter-mode`.

### 2. dry-run semantics

**PASS**

In `dry-run` mode (`research_acquire.py:362-368`):
- `_write_filter_audit()` is called (audit JSONL is written; this is intentional and documented).
- A log line is emitted to stderr.
- There is **no `return` statement** after the logging block.
- Execution falls through to the normal dry-run exit (`research_acquire.py:409`) and then to the ingest path if `--dry-run` is not also set.

Confirmed by test `TestPrefetchFilterModes::test_dry_run_mode_logs_but_ingests` (passes rc=0, no queue file created).

Note: the `--prefetch-filter-mode dry-run` flag is independent of the `--dry-run` flag. When used together (as in the test), the standard `--dry-run` exit fires at step 4 and no ingest occurs. When used alone, the filter logs and ingest proceeds normally. This is correct behavior per spec.

### 3. enforce semantics

**PASS**

Enforce mode behavior (`research_acquire.py:369-383`):
- `REJECT`: hits `elif ... and filter_decision.decision == "reject"` → returns 0 immediately, **no ingest**.
- `REVIEW`: no matching branch (the `elif` on line 384 is `hold-review` only). Execution falls through to the ingest path. **REVIEW candidates are ingested with audit flag** (`enforced=True` in the audit record).
- `ALLOW`: no branch matches. Falls through to ingest normally.

This matches the stated spec: "enforce: skip REJECT; ingest REVIEW with audit flag."

The search mode (`_run_search_mode`) implements the same logic consistently at lines 651-671.

### 4. hold-review semantics (CRITICAL)

**PASS — with caveat (see MEDIUM finding below)**

Hold-review mode in URL path (`research_acquire.py:369-406`):

- `ALLOW`: no branch matches → falls through to ingest. Correct.
- `REJECT`: hits `elif (enforce, hold-review) and decision == reject` → returns 0, skipped. Correct.
- `REVIEW`: hits `elif hold-review and decision == review` (`research_acquire.py:384`) → writes to queue → **returns 0 before ingest**. The `return 0` on line 406 confirms the paper is **never handed to `pipeline.ingest_external()`**.

Hold-review mode in search path (`_run_search_mode`, lines 673-701`):

- `REVIEW`: hits `elif hold-review and decision == review` → writes to queue → `continue` (line 701) bypasses `pipeline.ingest_external()`. Correct.

**REVIEW candidates are truly held out in both URL mode and search mode.**

Caveat: `_write_to_review_queue()` catches all exceptions and only prints a warning (`research_acquire.py:101-102`). If the queue write silently fails, the code still returns 0 and emits `"queued_for_review": true` in JSON output (`research_acquire.py:392-400`). The candidate is NOT ingested (safe), but it is also not in the queue (data loss). This is the primary non-blocking issue.

### 5. Queue idempotency

**PASS**

`ReviewQueueStore.enqueue()` (`queue_store.py:79-108`):
1. Reads all existing records.
2. Extracts the set of existing `candidate_id` values.
3. If `candidate_id` (sha256 of source_url) is already present, returns `False` without writing.
4. Only appends if the ID is genuinely new.

The `candidate_id_from_url()` function uses `hashlib.sha256(source_url.encode("utf-8")).hexdigest()` — stable, deterministic, 64-character hex.

Confirmed by three tests:
- `test_enqueue_idempotent_same_url` — same URL queued twice: only 1 record
- `test_enqueue_idempotent_explicit_candidate_id` — explicit candidate_id collision: only 1 record
- `test_hold_review_idempotent_duplicate_url` — CLI-level: same URL run twice, only 1 queue record

One performance note (LOW severity): idempotency check reads the entire queue file on every `enqueue()` call. For the expected queue sizes (tens to low hundreds of entries), this is acceptable. At scale (thousands of entries) it becomes O(n) per insert. Not a current concern.

### 6. Label store format

**PASS**

`LabelStore.append_label()` (`queue_store.py:136-185`):
- Opens the file in append mode (`"a"`).
- Writes one JSON line per call followed by `\n`.
- Record schema: `candidate_id`, `source_url`, `title`, `label` (`"allow"` or `"reject"`), `note`, `labeled_at` (ISO-8601 UTC).
- `label` is validated to `{"allow", "reject"}` with a `ValueError` on invalid input.
- `labeled_at` uses `datetime.now(tz=timezone.utc).isoformat()` — correct UTC-aware timestamp.
- `_utcnow_iso()` is not using deprecated `datetime.utcnow()` — compliant with the repo's known warning backlog.

Confirmed by tests `test_append_label_allow`, `test_append_label_reject`, `test_append_label_invalid_raises`, `test_counts_accumulate`.

### 7. No heavy ML deps

**PASS**

`packages/research/relevance_filter/scorer.py` imports:
```
__future__, json, math, dataclasses, pathlib, typing
```

`packages/research/relevance_filter/queue_store.py` imports:
```
__future__, hashlib, json, datetime, pathlib, typing
```

`packages/research/relevance_filter/__init__.py` imports only from sibling modules.

No `transformers`, `sentence_transformers`, `sklearn`, `specter`, `torch`, `numpy`, or other heavy ML dependencies anywhere in the relevance_filter package.

The dev log and feature doc explicitly state SVM/SPECTER2 are deferred to L3 v1 training pass.

### 8. No scope creep

**PASS**

No imports from or references to:
- `execution/` modules
- `kill_switch`
- `risk_manager`
- `pair_engine`
- `reference_feed`
- PaperQA2 / Marker
- n8n
- `py_clob_client` or EIP-712 signing

The new files (`queue_store.py`, `research_prefetch_review.py`) are purely file I/O and argparse wrappers with stdlib-only dependencies. The changes to `research_acquire.py` add mode-branching and helper functions, all scoped to the filter decision flow.

### 9. Artifacts gitignored

**PASS**

`.gitignore` contains:
```
/artifacts/
/artifacts/**
```

Both new artifact paths are covered:
- `artifacts/research/prefetch_review_queue/review_queue.jsonl`
- `artifacts/research/svm_filter_labels/labels.jsonl`
- `artifacts/research/acquisition_reviews/filter_decisions.jsonl` (existing audit path)

The dev log (`2026-05-02_ris-prefetch-review-queue-label-store.md`) explicitly notes: "Both new paths are under `artifacts/**` which is already gitignored."

---

## Findings by Severity

### CRITICAL

None.

`hold-review` correctly holds REVIEW candidates out of ingestion in both URL mode (`return 0` at line 406) and search mode (`continue` at line 701). The filter semantics are sound and the critical invariant — REVIEW candidates are never passed to `pipeline.ingest_external()` — is preserved.

### HIGH

None.

### MEDIUM

**M1: Queue write failure produces misleading `queued_for_review: true` output**

File: `tools/cli/research_acquire.py`

Location A (URL mode, lines 101-102, 392-400):
```python
# queue_store.py call site
except Exception as exc:
    print(f"WARNING: failed to write review queue record: {exc}", ...)
# ... then unconditionally:
print(json.dumps({"queued_for_review": True, "skipped": True, ...}))
return 0
```

Location B (search mode, lines 682-698): same pattern.

Impact: If `_write_to_review_queue()` raises an exception (unwritable directory, permissions error, disk full), the candidate is NOT ingested (correct — safe), but the JSON output reports `queued_for_review: true` when the candidate was not actually written to the queue. The operator cannot tell from output whether the queue write succeeded.

Fix options (operator to decide):
1. Return the write status from `_write_to_review_queue()` (currently returns `None`). On failure, emit `"queued_for_review": false, "queue_error": "<message>"` and consider returning exit code 2.
2. Raise from `_write_to_review_queue()` and let the caller handle it, similar to how fetch errors are handled.

This is non-blocking for safety (the candidate is still held out of ingest) but weakens auditability.

### LOW / SUGGESTIONS

**L1: Feature doc `FEATURE-ris-prefetch-relevance-filter-v0.md` is stale**

File: `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md`

Lines 32-39: Filter Modes section still documents only `{off,dry-run,enforce}`. `hold-review` mode, the queue path, and the label store are absent from the feature doc.

Lines 181-185: Deferred Items still says "Label store file — deferred" and "research-health label_count counter — deferred." Both are now shipped.

The L3.1 dev log documents the full picture correctly; the feature doc needs to be updated to include hold-review semantics, the new `research-prefetch-review` CLI, queue/label artifact paths, and current health counter state.

**L2: JSONL read errors are silently dropped in `_read_jsonl()`**

File: `packages/research/relevance_filter/queue_store.py:47-50`

```python
except json.JSONDecodeError:
    pass
```

Malformed lines are dropped from counts, duplicate checks, and all_records() returns. A corrupted queue JSONL line would silently vanish. For an audit-grade store this is weak. Consider logging or counting parse errors. Low priority before the queue contains real data.

**L3: Search-mode hold-review has no offline test coverage**

File: `tests/test_ris_research_acquire_cli.py`

`TestPrefetchFilterModes` covers URL mode only. The search mode (`_run_search_mode`) hold-review code path (lines 673-701) is implemented correctly (same branching pattern as URL mode) but is not exercised by any test. Adding a monkeypatched `search_by_topic` test with mixed ALLOW/REVIEW/REJECT candidates would close this gap.

**L4: Queue idempotency does O(n) full read per enqueue call**

File: `packages/research/relevance_filter/queue_store.py:96`

`existing_ids = {r.get("candidate_id") for r in _read_jsonl(self._path)}`

At current expected queue sizes (tens of entries) this is fine. Not a concern for the current work packet, but worth noting if the queue grows to thousands of entries over time.

---

## Hold-Review Safety Assessment

**YES** — hold-review is safe for operator dry use.

The critical invariant is confirmed: a `REVIEW`-decision candidate reaches `return 0` or `continue` **before** any call to `pipeline.ingest_external()` in both the URL path and the search path. There is no code path where a hold-review REVIEW candidate can accidentally fall through to ingest.

The remaining risk (M1) is not accidental ingestion — it is silent queue loss when the file write fails. The candidate is not ingested in that scenario; it simply does not appear in the queue for operator review.

Safe to enable `--prefetch-filter-mode hold-review` for manual acquisition sessions. Do NOT enable it as a default.

---

## Fixes Required

**Before treating as production-grade auditability:**

1. **(M1)** Make `_write_to_review_queue()` return a bool (True=written, False=failed). On failure, emit `"queued_for_review": false` and `"queue_error": "<message>"` in JSON output. Consider returning exit code 2 on queue write failure so the operator is notified.

2. **(L1)** Update `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` to add `hold-review` to the Filter Modes section, add the queue/label paths, and remove the now-shipped "deferred" items.

**Recommended but non-blocking:**

3. **(L3)** Add one offline test for search-mode hold-review (monkeypatch `search_by_topic` to return 3 papers with different filter decisions).

4. **(L2)** Surface JSONL parse errors in `_read_jsonl()` via a warning print or a `read_errors` counter returned to callers.
