---
phase: quick
plan: 260402-ogq
subsystem: ris
tags: [claim-extraction, evidence-linking, heuristic, tdd, knowledge-store]
dependency_graph:
  requires: [quick-260402-ogu, quick-260402-m6p, quick-260402-m6t]
  provides: [derived_claims, claim_evidence, claim_relations, research-extract-claims CLI]
  affects: [RIS data plane, IngestPipeline, KnowledgeStore]
tech_stack:
  added: []
  patterns: [TDD, INSERT-OR-IGNORE deduplication, deterministic SHA-256 IDs, heuristic NLP]
key_files:
  created:
    - packages/research/ingestion/claim_extractor.py
    - tests/test_ris_claim_extraction.py
    - tools/cli/research_extract_claims.py
    - docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md
  modified:
    - packages/research/ingestion/__init__.py
    - packages/research/ingestion/pipeline.py
    - polytool/__main__.py
    - docs/features/FEATURE-ris-v1-data-foundation.md
    - docs/CURRENT_STATE.md
decisions:
  - Deterministic created_at via SHA-256 of doc_id+sentence+chunk_id+extractor_id ensures idempotent claim IDs
  - Empirical regex requires 3+ digit numbers to avoid 2-digit normative context (e.g., "20 bps") being misclassified
  - Evidence deduplication via pre-insert SELECT (add_evidence has no INSERT OR IGNORE)
  - post_ingest_extract is opt-in and non-fatal; extraction failure never causes ingest failure
  - No LLM calls; authority conflict between Roadmap v5.1 and PLAN_OF_RECORD remains unresolved
metrics:
  duration: ~45 minutes (split across two sessions)
  completed: 2026-04-02
  tasks_completed: 2
  files_changed: 8
  tests_added: 56
  tests_total: 3262
---

# Phase quick Plan 260402-ogq: RIS Phase 4 Claim Extraction Summary

**One-liner:** Heuristic sentence-level claim extraction from ingested docs into `derived_claims` + `claim_evidence` + typed `SUPPORTS/CONTRADICTS` relations, fully idempotent via deterministic SHA-256 claim IDs.

## What Was Built

### Task 1: HeuristicClaimExtractor (TDD)

56 tests written RED-first in `tests/test_ris_claim_extraction.py`, then implementation written to pass them.

**Core module:** `packages/research/ingestion/claim_extractor.py`

```
source_document (already ingested in KnowledgeStore)
  -> _get_document_body()         [file:// path or metadata_json body key]
  -> chunk_text(body)             [400-word chunks, 80-word overlap]
  -> _extract_assertive_sentences(chunk)
      - strips ## heading tokens merged inline by chunk_text
      - strips table fragments, code fences, blockquotes
      - filters: len < 30, all-caps, code-looking
      - up to 5 sentences per chunk
  -> _classify_claim_type()       -> empirical | normative | structural
  -> _confidence_for_tier()       -> 0.85 | 0.70 | 0.55
  -> store.add_claim(det_created_at=...)  [INSERT OR IGNORE, idempotent]
  -> store.add_evidence()         [guarded by pre-insert SELECT]
  -> build_intra_doc_relations()  [pairwise; SUPPORTS or CONTRADICTS]
```

**Public API:**
- `extract_claims_from_document(store, doc_id) -> list[str]`
- `build_intra_doc_relations(store, claim_ids) -> int`
- `extract_and_link(store, doc_id) -> dict`
- `HeuristicClaimExtractor` (class wrapper)

### Task 2: CLI Command and Integration Wiring

**`tools/cli/research_extract_claims.py`:**
```bash
python -m polytool research-extract-claims --doc-id <DOC_ID>
python -m polytool research-extract-claims --all
python -m polytool research-extract-claims --all --dry-run
python -m polytool research-extract-claims --all --json
python -m polytool research-extract-claims --all --db-path <PATH>
```

**`IngestPipeline.ingest()` extended:**
```python
result = pipeline.ingest("paper.md", post_ingest_extract=True)
# Claims extracted automatically after source_document stored (non-fatal if fails)
```

**`packages/research/ingestion/__init__.py`:** exports `HeuristicClaimExtractor`,
`extract_claims_from_document`, `build_intra_doc_relations`, `extract_and_link`, `CLAIM_EXTRACTOR_ID`.

## Test Results

```
3262 passed, 0 failed, 25 warnings
```

25 warnings are pre-existing `datetime.utcnow()` deprecation warnings unrelated to this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Normative claim misclassified as empirical for 2-digit numbers**
- **Found during:** Task 1 — `test_normative_recommend` failure
- **Issue:** `_EMPIRICAL_RE = re.compile(r"\d+%|\d+\.\d+|\b\d{2,}\b")` matched "20" in
  "We recommend a minimum spread of 20 bps", returning `empirical` instead of `normative`
- **Fix:** Changed to `\b\d{3,}\b` — requires 3+ digit standalone numbers
- **Files modified:** `packages/research/ingestion/claim_extractor.py`
- **Commit:** `92f9b15`

**2. [Rule 1 - Bug] Non-idempotent claim IDs — different IDs on second extraction run**
- **Found during:** Task 1 — `test_idempotent_extraction` failure
- **Issue:** `store.add_claim()` without explicit `created_at` calls `_utcnow_iso()` at
  insertion time. Since claim IDs are `SHA-256("claim" + text + actor + created_at)`, every
  run produces different IDs, so INSERT OR IGNORE never fires and evidence rows duplicate.
- **Fix:** Added `_deterministic_created_at(doc_id, sentence, chunk_id)` that hashes
  content fields to produce a stable pseudo-timestamp (`2000-01-01T00:00:00.{offset}+00:00`).
  Also added pre-insert SELECT guard for evidence rows.
- **Files modified:** `packages/research/ingestion/claim_extractor.py`
- **Commit:** `92f9b15`

## Commits

| Task | Description | Hash |
|------|-------------|------|
| 1 (RED) | 56 failing tests for claim extraction | `f2ef790` |
| 1 (GREEN) | HeuristicClaimExtractor implementation | `92f9b15` |
| 2 | CLI, pipeline wiring, docs, dev log | `418267a` |

## Known Stubs

None. Claim extraction pipeline is fully functional end-to-end. The `KnowledgeStore._llm_provider`
attribute remains None as designed — LLM extraction is a future enhancement pending operator
resolution of the Roadmap v5.1 / PLAN_OF_RECORD authority conflict.

## Self-Check: PASSED
