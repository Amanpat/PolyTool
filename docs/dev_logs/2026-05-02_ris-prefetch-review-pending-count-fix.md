# RIS L3.1 Prefetch Review Queue — Pending Count Fix

**Date:** 2026-05-02
**Type:** Bug fix / UX improvement
**Scope:** queue_store, research-prefetch-review CLI, research-health

---

## Problem Found in Live Operator Test

After labeling all 3 queued items as `allow`, `research-prefetch-review counts` still
reported `3 item(s) pending` because `pending_count()` counted total queued records
rather than unlabeled-only records. This was confusing and would make it impossible
to track labeling progress at scale.

Expected state after labeling 3/3 items:
- `pending_unlabeled = 0`
- `total_queued = 3`
- `labeled_allow = 3`

Actual before fix: `"Prefetch review queue: 3 item(s) pending"` — indistinguishable
from the pre-labeling state.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/relevance_filter/queue_store.py` | Added `ReviewQueueStore.queue_stats(label_store)` — cross-join of queue vs label store |
| `tools/cli/research_prefetch_review.py` | Updated `counts` output; updated `list` to filter unlabeled by default; added `--all` and `--label-path` to `list` parser |
| `tools/cli/research_health.py` | Updated `_prefetch_review_stats()` and `_output_table()` to use new fields |
| `tests/test_ris_relevance_filter.py` | Added `TestQueueLabelJoin`, `TestListCommand`, `TestCountsCommand` test classes (18 new tests) |

---

## New Count / List Semantics

### `queue_stats(label_store)` — new method on `ReviewQueueStore`

Cross-joins queue records against label store by `candidate_id`:

| Key | Meaning |
|-----|---------|
| `total_queued` | All records in queue (labeled or not) |
| `pending_unlabeled` | Queue records with no label in label store |
| `labeled_total` | Queue records that have at least one label |
| `labeled_allow` | Label records with `label='allow'` for queued items |
| `labeled_reject` | Label records with `label='reject'` for queued items |

`pending_count()` is unchanged (still returns total). `queue_stats()` is the new
single-call API for joined counts.

### `research-prefetch-review counts` output

```
Prefetch review queue : 3 total queued  |  0 pending unlabeled
Labels (in queue)     : 3 labeled  |  3 allow  |  0 reject
SVM trigger (>=30 each) : need 27 more allow, 30 more reject
```

JSON output includes both new keys (`total_queued`, `pending_unlabeled`, `labeled_*`)
and legacy keys (`pending_review_count`, `label_count`, `allowed_label_count`,
`rejected_label_count`) for backward compat.

### `research-prefetch-review list` behavior

- **Default**: shows only unlabeled pending items. When all items are labeled, prints:
  `"No pending unlabeled items. (N total queued, all labeled. Use --all to see labeled items.)"`
- **`--all`**: shows all queue items (labeled + unlabeled) with `[label=allow/reject]`
  or `[pending]` tag per item.
- `--label-path` now accepted on the `list` subcommand (needed for the join).

### `research-health` L3 Prefetch Filter section

```
L3 Prefetch Filter
  total_queued          : 3
  pending_unlabeled     : 0
  labeled_total         : 3
  labeled_allow         : 3
  labeled_reject        : 0
```

---

## Tests Run

```
pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py -x -q
85 passed, 0 failed
```

Full regression suite: `2397 passed, 1 failed (pre-existing test_ris_claim_extraction), 19 warnings`.
The pre-existing failure is unrelated to this change.

---

## Remaining Limitations

| Item | Status |
|------|--------|
| `queue_stats()` is O(n) per call (reads both files each time) | Acceptable at current queue sizes |
| Multiple labels for same item: `labeled_allow/reject` counts label records, not distinct IDs | Not a concern given append-once usage pattern |
| Label store entries for non-queue candidate_ids are silently ignored in cross-join | By design — only queue items matter for pending count |
