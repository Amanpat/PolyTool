# L3 v1 SVM Label Expansion — Queue Growth Pass

**Date:** 2026-05-06
**Track:** RIS / L3 v1 SVM Topic Filter
**Objective:** Expand the prefetch review queue toward the >=150-label enforce gate. Discover and queue candidates for manual labeling; no labels created or modified.

---

## Baseline (before any runs)

```
git status: 15 modified, 24 untracked (from prior L3 v1 SVM integration sessions)
```

**Label counts (python -m polytool research-prefetch-review counts --json):**
```json
{
  "total_queued": 62,
  "pending_unlabeled": 1,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

**labels.jsonl SHA256 (baseline):** `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

---

## Discovery Passes

All passes used `python -m polytool research-prefetch-discover --decision-filter all`. No PDFs downloaded, no Marker invoked, no ingestion.

### Pass 1 — Allow-like: Prediction Markets / Information Aggregation

```
--search "prediction market information aggregation price discovery"
--max-results 30 --decision-filter all
```

| Metric | Value |
|---|---|
| Discovered | 30 |
| Queued (new) | 21 |
| Skipped duplicate | 9 |
| Filter decisions | allow=15, review=15, reject=0 |
| Queue after | 83 total, 22 pending |

### Pass 2 — Allow-like: Limit Order Book / Market Microstructure

```
--search "limit order book market microstructure algorithmic trading backtesting"
--max-results 30 --decision-filter all
```

| Metric | Value |
|---|---|
| Discovered | 30 |
| Queued (new) | 25 |
| Skipped duplicate | 5 |
| Filter decisions | allow=24, review=6, reject=0 |
| Queue after | 108 total, 47 pending |

### Pass 3 — Reject-like: Unrelated Sports Administration AI

```
--search "sports facility management machine learning classification athlete performance"
--max-results 30 --decision-filter all
```

| Metric | Value |
|---|---|
| Discovered | 30 |
| Queued (new) | 28 |
| Skipped duplicate | 2 |
| Filter decisions | allow=0, review=30, reject=0 |
| Queue after | 136 total, 75 pending |

**Note:** Lexical filter scores sports papers as "review" (not "reject") — they landed in the middle band. Still useful as reject-label candidates; operator judgment at labeling time determines ground truth.

### Pass 4 — Reject-like: Unrelated Medical AI / Computer Vision

```
--search "medical imaging deep learning object detection radiology classification survey"
--max-results 30 --decision-filter all
```

| Metric | Value |
|---|---|
| Discovered | 30 |
| Queued (new) | 23 |
| Skipped duplicate | 7 |
| Filter decisions | allow=0, review=15, reject=15 |
| Queue after | 159 total, 98 pending |

---

## Final State

**Label counts (after all passes):**
```json
{
  "total_queued": 159,
  "pending_unlabeled": 98,
  "labeled_total": 61,
  "labeled_allow": 30,
  "labeled_reject": 31
}
```

**labels.jsonl SHA256 (post-run):** `3940D2FFB1F9F62C2BF65B5A01C33CE3F9BDF7623532916B68F1C5276E6000A2`

SHA256 matches baseline — labels.jsonl unmodified. ✓

---

## Queue Growth Summary

| Metric | Before | After | Delta |
|---|---|---|---|
| Total queued | 62 | 159 | +97 |
| Pending unlabeled | 1 | 98 | +97 |
| Labeled allow | 30 | 30 | 0 |
| Labeled reject | 31 | 31 | 0 |
| Labeled total | 61 | 61 | 0 |

97 new candidates available for manual labeling.

---

## Labeling Workload Remaining to Reach 150

The enforce gate requires **>=150 labels** total plus Director approval.

| Milestone | Labels needed | Gap |
|---|---|---|
| Current | 61 | — |
| Enforce gate | 150 | **89 more labels needed** |

With 98 pending candidates in queue, the pool is sufficient to reach 150 (need 89 labels from 98 candidates = 91% labeling rate acceptable, or operator can discard some).

Recommended labeling split to balance class distribution:
- Target: ~75 allow + 75 reject = 150
- Need: 45 more allow (from queue allow-like candidates), 44 more reject (from queue reject-like candidates)
- Current queue has strong allow-side candidates (passes 1+2) and reject-side candidates (passes 3+4)

---

## arXiv / API Notes

No rate limits encountered across all 4 passes. All calls completed within 15s timeout.

---

## Code Changes

None. No implementation files modified. Queue artifact extended only.

---

## Open Items

- Operator labeling session needed: 89 labels required to reach enforce gate
- After labeling, confirm class balance (ideally >=75 each class)
- Director approval required before enforce mode can be enabled
- Model selection decision still open: bge-large-en-v1.5 vs SPECTER2 options (separate packet)
