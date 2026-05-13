# Fix: research-query fallback/warning semantics

**Date:** 2026-05-09  
**Scope:** `packages/research/synthesis/academic_query.py`, `tests/test_research_query.py`

## Root cause

`query_academic_corpus()` uses verbatim case-insensitive substring matching
(`query_knowledge_store_for_rrf`). When the query text does not appear as a
substring in any indexed claim, `all_raw` and `merged` both come back empty.
The fallback branch at `if not merged:` has only one warning path:

> "No academic documents found in the KnowledgeStore."

This is accurate when the corpus is truly empty (Case A), but misleading when
Marker-ready academic documents are indexed and the query simply had no
matching claims (Case B). The user sees "no documents" when documents exist.

## Files changed

- `packages/research/synthesis/academic_query.py`
  - Added `_has_academic_documents(ks)` — lightweight single-row SQL probe
    (`SELECT 1 FROM source_documents WHERE source_family='academic' LIMIT 1`).
  - Inside the main `try` block, when `all_raw` is empty after all query
    angles are exhausted, calls `_has_academic_documents(ks)` before the KS
    is closed.
  - `if not merged:` branch now emits one of two warnings depending on the
    probe result (Case A vs Case B).
- `tests/test_research_query.py`
  - Added `test_case_a_empty_ks_returns_no_docs_warning` — empty KS, verifies
    "No academic documents found" wording.
  - Added `test_case_b_populated_ks_unrelated_query_returns_no_relevant_warning`
    — KS has one Marker-ready doc, query does not match any claim, verifies
    "Academic documents exist" wording and that "No academic documents found"
    is absent.

## Warning text

**Case A (empty corpus):**
> "No academic documents found in the KnowledgeStore. To add papers: python -m polytool research-marker-queue enqueue --url ARXIV_ID"

**Case B (docs exist, query unmatched):**
> "Academic documents exist in the KnowledgeStore, but no relevant claims matched this question. Try a more specific question or add more related papers: python -m polytool research-marker-queue enqueue --url ARXIV_ID"

`had_fallback` remains `True` in both cases — no citations were returned.

## Tests run

```
tests/test_research_query.py                  38 passed
tests/test_ris_marker_queue.py               ~182 passed, 1 skipped
tests/test_ris_claim_extraction.py            ~21 passed
```

Total: 203 passed, 1 skipped — no regressions.

## Before / after

**Before (Case B):**
```json
{
  "citations": [],
  "had_fallback": true,
  "warning": "No academic documents found in the KnowledgeStore. ..."
}
```

**After (Case B):**
```json
{
  "citations": [],
  "had_fallback": true,
  "warning": "Academic documents exist in the KnowledgeStore, but no relevant claims matched this question. ..."
}
```

## Caveats

- `_has_academic_documents` accesses `ks._conn` (private attribute) to avoid
  adding a public method to `KnowledgeStore`. The probe runs only when
  `all_raw` is empty, so it adds negligible overhead on normal (matching)
  queries.
- Claim-level substring matching is unchanged. A query that partially matches
  claims will still return results; this fix only affects the zero-hit path.
- ChromaDB vector path is not yet wired (L2.1 deferred). Semantic-similarity
  hits that would surface relevant papers are out of scope here.

## Codex review

Tier: Skip (docs/tests/warning-text change; no execution, risk, or strategy
logic touched).
