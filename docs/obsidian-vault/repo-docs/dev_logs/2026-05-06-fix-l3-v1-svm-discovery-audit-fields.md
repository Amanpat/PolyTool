---
title: Fix L3 V1 Svm Discovery Audit Fields
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix L3 v1 SVM Discovery Audit Fields — Codex P1

**Date:** 2026-05-06  
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter  
**Scope:** Codex P1 fix only. No acquisition changes, no enforcement mode, no label/artifact edits, no L2/L4/Marker IPC work.

---

## Summary

Fixed Codex P1 blocking finding: `research-prefetch-discover` was building queue and dry-run records from `FilterDecision` without copying scorer audit fields. SVM-discovered evidence records now include `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, and `svm_lexical_baseline_note` in both dry-run (`would_queue`) and queued JSONL records. Lexical records carry `scorer="lexical"` with empty SVM fields, making the schema consistent. Three new tests prove both SVM and lexical paths. 52/52 discovery tests pass; 95/95 scorer+filter regression tests pass.

---

## Codex P1 Addressed

**Finding (from `2026-05-06_codex-review-l3-v1-svm-default-off-integration.md`):**

> `research-prefetch-discover` does not preserve SVM audit fields in queued or dry-run records. The queue record is built from `FilterDecision` fields at `tools/cli/research_prefetch_discover.py:416`, but it omits `scorer`, `svm_model_name`, `svm_model_path`, `svm_random_state`, and `svm_lexical_baseline_note`. SVM-discovered evidence therefore cannot be reliably tied back to the scorer/model that produced it.

**Fix:** Added all five fields to the `record` dict in the scoring loop. They are always present — for lexical scorer they carry default values (`"lexical"`, `""`, `""`, `0`, `""`); for SVM scorer they carry the model identity from the metadata ledger. This makes the queue schema uniform and verifiable.

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `tools/cli/research_prefetch_discover.py` | Added `scorer` + `svm_*` fields to `record` dict | P1 fix: audit fields must be preserved in both dry-run and queued records |
| `tools/cli/research_prefetch_discover.py` | Updated `argparse` description | P3 (non-blocking): removed false "no embeddings" claim; SVM mode does embed |
| `tests/test_ris_prefetch_discovery.py` | Added 3 tests to `TestSvmScorerDiscover` | Prove P1 fix for dry-run, queued, and lexical paths |
| `docs/dev_logs/2026-05-06_fix-l3-v1-svm-discovery-audit-fields.md` | New file | This dev log |

### Unchanged files (scope respected)

- `tools/cli/research_acquire.py` — not touched
- `packages/research/relevance_filter/svm_scorer.py` — not touched
- `packages/research/relevance_filter/svm_training.py` — not touched
- All label JSONL files and model artifacts — not touched
- All L2/L4/Marker IPC code — not touched

---

## Code Change Detail

**`tools/cli/research_prefetch_discover.py` — record dict (line ~416):**

```python
# Before (missing audit fields):
record: dict = {
    ...
    "config_version": result.config_version,
    "source_family": args.source_family,
    "discovery_query": args.search,
}

# After (audit fields always present):
record: dict = {
    ...
    "config_version": result.config_version,
    # Scorer audit fields — always present; SVM keys are empty for lexical scorer
    "scorer": result.scorer,
    "svm_model_name": result.svm_model_name,
    "svm_model_path": result.svm_model_path,
    "svm_random_state": result.svm_random_state,
    "svm_lexical_baseline_note": result.svm_lexical_baseline_note,
    "source_family": args.source_family,
    "discovery_query": args.search,
}
```

The five fields are available on every `FilterDecision` as of the runtime scorer session. Lexical `RelevanceScorer` produces `scorer="lexical"` and empty `svm_*` defaults; `SvmRelevanceScorer` produces `scorer="svm"` and populated model fields from the loaded metadata ledger.

---

## Commands Run

### Targeted test suite
```
python -m pytest tests/test_ris_prefetch_discovery.py -q --tb=short
→ 52 passed in 0.74s  (49 pre-existing + 3 new)
```

### Regression suites
```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_svm_scorer.py -q --tb=short
→ 95 passed in 2.26s
```

### Help text smoke test
```
python -m polytool research-prefetch-discover --help
→ exit 0; description no longer claims "no embeddings" unconditionally
```

### Total: 147 tests, 0 failed, 0 regressions.

---

## Remaining Risks / Open Items

### Codex P2 (not fixed in this prompt — tracked)

**Finding:** SVM loading is lazy and happens at `scorer.score(candidate)` on the scoring loop, outside the scorer-initialization try block. If the model file is missing, metadata is corrupt, or a dependency (joblib/numpy) is absent at score time, the exception propagates unhandled out of the loop — no rc=1, no clear error message.

**Why deferred:** P2 is error-handling logic in the scoring loop, not audit-field data propagation. The current prompt's objective is P1 only. P2 fix belongs in the next integration pass.

**Mitigation until P2 is fixed:** `SvmRelevanceScorer._load()` raises `SvmModelLoadError` (clear domain error) or `SvmMissingDepsError` (clear dep error) — both are `RuntimeError` subclasses with descriptive messages. The exception will surface to the operator even without a clean rc=1.

### Schema stability

The five new fields are now part of the queue JSONL schema for SVM-scored records. Any consumer that reads `review_queue.jsonl` (e.g., `research-prefetch-review list`) should treat them as optional — they were absent in records written before this fix and will be present in records written after. Existing consumers only read `decision`, `title`, `source_url`, `candidate_id`, and `created_at`, so no breakage.

---

## Codex Review Summary

Review tier: Recommended (RIS filtering/discovery CLI — no live trading, risk, or execution code).  
P1 addressed: yes — queue and dry-run records now carry scorer identity.  
P2 status: not fixed in this prompt; tracked above.  
P3 (help text): fixed.
