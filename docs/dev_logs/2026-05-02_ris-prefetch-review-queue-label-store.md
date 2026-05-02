# RIS L3.1 — Prefetch Review Queue + Label Store

**Date:** 2026-05-02
**Work packet:** L3.1 Prefetch Review Queue + Label Store
**Author:** operator + Claude Code

---

## Summary

Adds the `hold-review` workflow to the L3 pre-fetch relevance filter pipeline.
`hold-review` is a new `--prefetch-filter-mode` that ingests ALLOW candidates
normally, skips REJECT candidates (same as enforce), and **holds REVIEW
candidates in a file-backed operator queue without ingesting them**.

Labeling queued items via `research-prefetch-review label` accumulates
training examples in the label store (`artifacts/research/svm_filter_labels/labels.jsonl`),
building toward the ≥30 allow + ≥30 reject threshold that triggers L3 v1 SVM training.

The default mode remains `off`. No new ML dependencies introduced.

---

## Mode Semantics

| Mode | ALLOW | REVIEW | REJECT |
|------|-------|--------|--------|
| `off` | not called | not called | not called |
| `dry-run` | ingest (log only) | ingest (log only) | ingest (log only) |
| `enforce` | ingest | ingest + audit flag | **skip** |
| `hold-review` | ingest | **queue, skip** | **skip** |

Key distinction: `enforce` corresponds to Scenario A (20.0% off-topic);
`hold-review` achieves Scenario B semantics (5.88%, target <10%) by
excluding the 3 REVIEW papers from the corpus in addition to the 3 REJECT papers.

---

## Queue / Label Schema

### Review queue record (`review_queue.jsonl`)

```json
{
  "candidate_id": "<sha256(source_url)>",
  "source_url": "https://arxiv.org/abs/...",
  "title": "...",
  "abstract": "...",
  "score": 0.65,
  "raw_score": 1.0,
  "decision": "review",
  "reason_codes": ["positive:liquidity"],
  "matched_terms": {"positive": ["liquidity"], ...},
  "allow_threshold": 0.80,
  "review_threshold": 0.35,
  "config_version": "v1.1",
  "created_at": "2026-05-02T..."
}
```

Idempotent by `candidate_id` (sha256 of source_url). Duplicate URLs are silently skipped.

### Label store record (`labels.jsonl`)

```json
{
  "candidate_id": "<sha256(source_url)>",
  "source_url": "https://arxiv.org/abs/...",
  "title": "...",
  "label": "allow|reject",
  "note": "operator free-text note",
  "labeled_at": "2026-05-02T..."
}
```

Append-only. Multiple labels for the same candidate are allowed (useful for
auditing or changing a decision). SVM training should deduplicate by taking
the latest label per candidate_id.

---

## Commands Added

### `research-prefetch-review`

```
python -m polytool research-prefetch-review list [--json] [--queue-path PATH]
python -m polytool research-prefetch-review label <CANDIDATE_ID> allow|reject [--note TEXT]
python -m polytool research-prefetch-review counts [--json]
```

- `list`: show all queue items with score, date, title, URL
- `label`: append a label to the label store; candidate_id prefix matching supported
- `counts`: show pending_review_count, label_count, allowed/rejected counts; SVM trigger gap

### `research-acquire` changes

```
--prefetch-filter-mode {off,dry-run,enforce,hold-review}
--prefetch-review-queue-dir PATH   (default: artifacts/research/prefetch_review_queue)
```

---

## Artifact Paths

| Artifact | Path |
|----------|------|
| Review queue | `artifacts/research/prefetch_review_queue/review_queue.jsonl` |
| Label store | `artifacts/research/svm_filter_labels/labels.jsonl` |
| Filter audit | `artifacts/research/acquisition_reviews/filter_decisions.jsonl` |

Both new paths are under `artifacts/**` which is already gitignored.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/relevance_filter/queue_store.py` | **Created** — `ReviewQueueStore`, `LabelStore`, `candidate_id_from_url` |
| `packages/research/relevance_filter/__init__.py` | Updated — export `ReviewQueueStore`, `LabelStore`, `candidate_id_from_url` |
| `tools/cli/research_acquire.py` | Updated — `hold-review` mode, `--prefetch-review-queue-dir`, `_write_to_review_queue` helper |
| `tools/cli/research_prefetch_review.py` | **Created** — `list`, `label`, `counts` subcommands |
| `tools/cli/research_health.py` | Updated — `_prefetch_review_stats()` appended to both JSON and table output |
| `polytool/__main__.py` | Updated — `research-prefetch-review` registered |
| `tests/test_ris_relevance_filter.py` | Updated — `TestReviewQueueStore` (8 tests), `TestLabelStore` (6 tests) |
| `tests/test_ris_research_acquire_cli.py` | Updated — `TestPrefetchFilterModes` (6 tests), `TestResearchPrefetchReviewCLI` (10 tests) |

---

## Tests Run

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_research_acquire_cli.py tests/test_ris_eval_benchmark.py -q --tb=short
```

**157 passed, 0 failed** (44 new tests added across 2 files).

Prior suite total before this packet: 113 collected across the two original test files.

---

## Remaining Limitations

1. **No per-record labeled status in queue.** The queue is append-only and does
   not track which items have been labeled. `pending_count()` returns total queued
   records, not unlabeled-only. A cross-join of queue vs. label store is needed
   for a true "awaiting label" view. Deferred until label volume justifies it.

2. **Multiple labels per candidate allowed.** LabelStore is append-only; SVM
   training code (not yet written) must deduplicate by taking latest label per
   candidate_id. This is by design (supports correction).

3. **Enforce fail-open on scoring errors still present.** This was a deferred item
   from v0 closeout. Not addressed in this packet.

4. **URL mode only tested for hold-review.** Search mode (`--search`) hold-review
   logic was updated in code but is not covered by offline tests (search mode
   requires real HTTP or more complex fixture wiring). Functional parity is
   implemented; offline test coverage deferred.

---

## SVM Training Trigger

Run `python -m polytool research-prefetch-review counts` to monitor progress:

```
SVM trigger (>=30 each) : need 30 more allow, 30 more reject
```

When both allow ≥ 30 and reject ≥ 30, the label store is ready for
L3 v1 SPECTER2 + S2FOS + SVM training. See
`docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` for the v1 path.

---

## Codex Review

Skipped for this packet. L3.1 changes are file I/O wrappers and mode-branching
only — no execution, kill-switch, or order-placement code. No mandatory Codex
review tier applies.
