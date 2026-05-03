# RIS L3.1 Prefetch Review Queue + Label Store — Close-out

**Date:** 2026-05-02
**Type:** Docs-only close-out (no code changes in this session)
**Packet:** L3.1 Prefetch Review Queue + Label Store

---

## Mode State at Close-out

| Mode | Status | Notes |
|------|--------|-------|
| `off` | ✅ Default — safe by design | Filter not called |
| `dry-run` | ✅ Safe to use | Scores and logs; always ingests |
| `enforce` | ⚠️ Experimental | REJECT skipped; REVIEW ingested with audit flag; corresponds to Scenario A (20.0%), not <10% |
| `hold-review` | ✅ Safe for operator use | REVIEW candidates queued and held out; hold-out invariant preserved even on queue write failure |

**Default is `off`.** `hold-review` must be explicitly activated. Do not claim SVM is implemented.

---

## What Shipped (L3.1)

All code shipped in commit `ac3aebc`. Codex PASS WITH FIXES issues resolved in the same session.

| Capability | Path |
|-----------|------|
| Review queue (JSONL, idempotent) | `packages/research/relevance_filter/queue_store.py` — `ReviewQueueStore` |
| Label store (JSONL, append-only) | `packages/research/relevance_filter/queue_store.py` — `LabelStore` |
| hold-review mode in URL path | `tools/cli/research_acquire.py` — returns `queued_for_review` + `queue_error` |
| hold-review mode in search path | `tools/cli/research_acquire.py` — same semantics as URL path |
| Queue management CLI | `tools/cli/research_prefetch_review.py` — `list`, `label`, `counts` |
| Health stats | `tools/cli/research_health.py` — `_prefetch_review_stats()` |

### Artifact paths (all gitignored)

| Artifact | Path |
|----------|------|
| Hold-review queue | `artifacts/research/prefetch_review_queue/review_queue.jsonl` |
| Label store | `artifacts/research/svm_filter_labels/labels.jsonl` |
| Filter audit | `artifacts/research/acquisition_reviews/filter_decisions.jsonl` |

---

## Codex PASS WITH FIXES — All Issues Resolved

| Finding | Severity | Fix |
|---------|----------|-----|
| Queue write failure emitted `queued_for_review: true` | M1 | `_write_to_review_queue()` now returns `(bool, err)`; both call sites set `queued_for_review: queue_ok` and include `queue_error` on failure |
| Malformed JSONL silently dropped | L2 | `_read_jsonl()` prints `WARNING: malformed JSONL in <path> at line <N>` to stderr |
| Feature doc omitted hold-review, artifact paths, health counters | L1 | Feature doc updated: Filter Modes table, Artifact Paths section, Health Counters section, Files Shipped extended, stale Deferred Items removed |
| Search-mode hold-review had no offline coverage | L3 | `TestSearchModeHoldReview` added: monkeypatched `search_by_topic`, stubbed `KnowledgeStore`, spied `ingest_external` (asserts never called) |

**Test count after fixes: 160 passed, 0 failed.**

---

## Docs Updated in This Session

| File | Change |
|------|--------|
| `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` | Status line + Codex review line updated to reflect L3.1 complete |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 note updated; L3.1 row added to Recently Completed; Architect note updated with hold-review semantics, label store path, SVM trigger |
| `docs/INDEX.md` | L3 feature row updated to include hold-review and `research-prefetch-review`; 4 new dev log rows added |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L3 table row updated; new session context bullet added |

---

## Next Recommended Step

**Label accumulation.** Use `--prefetch-filter-mode hold-review` in live acquisition sessions
to populate the review queue. Review queued items with `research-prefetch-review list`, then
label each as allow/reject with `research-prefetch-review label <id> allow|reject`.

Track progress with:
```bash
python -m polytool research-prefetch-review counts
```

SVM training (L3 v1) is triggered when both:
- `allowed_label_count >= 30`
- `rejected_label_count >= 30`

at `artifacts/research/svm_filter_labels/labels.jsonl`.

Until then, L3 v0 lexical filter is the production path. No new implementation needed.

---

## Open Items (non-blocking)

| Item | Status |
|------|--------|
| `research-health` label_count counter | Deferred — useful once labels accumulate |
| Enforce fail-closed on scoring/config errors | Deferred — low risk pre-production |
| Per-record labeled status in queue | Deferred — cross-join of queue vs. labels; not needed until volume justifies |
| Queue idempotency O(n) per enqueue | Acceptable at current queue sizes |
