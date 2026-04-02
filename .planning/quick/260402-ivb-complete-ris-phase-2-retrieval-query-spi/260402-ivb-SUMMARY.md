---
phase: quick
plan: 260402-ivb
subsystem: ris-query-spine
tags: [ris, rag, hybrid-retrieval, rrf, knowledge-store, evidence-mode]
dependency_graph:
  requires: [quick-055-ris-v1-data-foundation, quick-260401-nzz-corpus-seeding, quick-260401-o1q-operator-loop]
  provides: [ks-hybrid-retrieval, three-way-rrf, evidence-mode-output]
  affects: [rag-query-cli, hybrid-retrieval-path, query-index-api]
tech_stack:
  added: [reciprocal_rank_fusion_multi, query_knowledge_store_for_rrf]
  patterns: [three-way-rrf-fusion, keyword-filter-over-structured-claims, opt-in-evidence-mode]
key_files:
  created:
    - tests/test_ris_query_spine.py
    - docs/features/FEATURE-ris-v2-query-spine.md
    - docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md
  modified:
    - packages/polymarket/rag/lexical.py
    - packages/research/ingestion/retriever.py
    - packages/polymarket/rag/query.py
    - tools/cli/rag_query.py
    - docs/CURRENT_STATE.md
decisions:
  - Three-way RRF via reciprocal_rank_fusion_multi() over a sidecar approach — unified ranked list more useful to callers
  - Keyword substring filter over semantic search for KS claims — structured claims are short; embedding overhead unjustified
  - Evidence-mode as opt-in flag — default output format stays uniform across all retrieval sources
metrics:
  duration_minutes: 6
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 5
  tests_added: 25
  tests_total_after: 3037
  completed_date: "2026-04-02"
---

# Phase quick Plan 260402-ivb: RIS Phase 2 Query Spine Wiring Summary

**One-liner:** Three-way RRF hybrid retrieval with KnowledgeStore as third source, freshness/contradiction ranking, and opt-in evidence-mode provenance output.

## What Was Built

The KnowledgeStore (RIS v1 data foundation) is now wired into the canonical `rag-query --hybrid`
retrieval path as a third RRF source alongside Chroma vector search and FTS5 lexical search.
This closes the "Chroma wiring" gap that was deferred in `FEATURE-ris-v1-data-foundation.md`.

Previously, KnowledgeStore claims existed as a sidecar disconnected from the real query path.
Now they participate in the unified RRF ranking pipeline alongside vector and lexical results.

## Tasks Completed

### Task 1: TDD — Core Retrieval Functionality (commit: 5f07dc9)

**Files created/modified:**
- `packages/polymarket/rag/lexical.py` — added `reciprocal_rank_fusion_multi()` for N-way RRF
- `packages/research/ingestion/retriever.py` — added `query_knowledge_store_for_rrf()`
- `packages/polymarket/rag/query.py` — added `knowledge_store_path`, `source_family`, `min_freshness`, `top_k_knowledge` params + three-way fusion path
- `tests/test_ris_query_spine.py` — 25 offline tests (TDD RED then GREEN)

**TDD cycle:**
- RED: 25 failures on first run
- GREEN: 25 passed after implementation
- Full regression: 3037 passed, 0 failed (was 3012; +25 new)

### Task 2: CLI/Docs Wiring (commit: e6af757)

**Files created/modified:**
- `tools/cli/rag_query.py` — 5 new flags + evidence-mode post-processing
- `docs/features/FEATURE-ris-v2-query-spine.md` — feature doc with architecture diagram
- `docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md` — dev log
- `docs/CURRENT_STATE.md` — RIS Phase 2 query spine section added

## Architecture

```
                         +-----------------------------+
                         |     rag-query --hybrid      |
                         |     --knowledge-store PATH  |
                         +-------------+---------------+
                                       |
              +------------------------+------------------------+
              v                        v                         v
  +------------------+    +----------------------+   +--------------------+
  |  Chroma Vector   |    |   SQLite FTS5         |   |  KnowledgeStore    |
  |  (top_k_vector)  |    |   Lexical             |   |  Claims            |
  |                  |    |   (top_k_lexical)     |   |  (top_k_knowledge) |
  +--------+---------+    +----------+------------+   +---------+----------+
           |                         |                           |
           +-------------------------+-----------+---------------+
                                                 |
                                      +----------v----------+
                                      |  reciprocal_rank_   |
                                      |  fusion_multi()     |
                                      |  (3-way RRF, k=60)  |
                                      +----------+----------+
                                                 |
                                      +----------v----------+
                                      |  Optional reranker  |
                                      +----------+----------+
                                                 |
                                      +----------v----------+
                                      |  Ranked result list |
                                      +---------------------+
```

## New CLI Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--knowledge-store PATH` | str | None | KS SQLite path; `default` resolves to `kb/rag/knowledge/knowledge.sqlite3` |
| `--source-family NAME` | str | None | Filter KS claims by source family |
| `--min-freshness FLOAT` | float | None | Exclude KS claims below freshness threshold |
| `--evidence-mode` | flag | False | Promote provenance/contradiction fields to top-level output |
| `--top-k-knowledge N` | int | 25 | KS candidate count for RRF |

## Canonical Query Path

```bash
python -m polytool rag-query \
  --question "market microstructure edge" \
  --hybrid \
  --knowledge-store default \
  --evidence-mode
```

## Decisions Made

**1. Three-way RRF over a separate sidecar**
Used `reciprocal_rank_fusion_multi()` to merge KS claims into the existing RRF pipeline
rather than returning them as a separate section. Unified ranked list is more useful to
callers (rerankers, consumers); extensible to 4+ sources without interface change.

**2. Keyword substring filter over semantic search for claims**
`query_knowledge_store_for_rrf()` uses case-insensitive substring match, not embedding-based
semantic search. KS claims are concise structured statements (10-50 words); keyword matching
is sufficient and avoids embedding overhead/latency. Semantic matching deferred.

**3. Evidence-mode as opt-in, not always-on**
Provenance/contradiction fields promoted to top-level only when `--evidence-mode` is set.
Default output format is uniform across all result sources. Evidence-mode is a "zoom in"
operation for operators who need full provenance visibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `test_filter_by_min_freshness` test using timeless source family**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test fixture used `source_family="book_foundational"` for the "stale" document,
  but `book_foundational` has `null` half-life (timeless, no decay). Freshness always = 1.0,
  so the min_freshness filter never excluded it.
- **Fix:** Changed fixture to use `source_family="news"` (3-month half-life). A 2020 document
  with `news` family correctly decays below 0.5.
- **Files modified:** `tests/test_ris_query_spine.py`
- **Commit:** 5f07dc9

**2. [Rule 1 - Bug] Fixed `test_three_way_fusion_merges_ks_results` substring mismatch**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test query was `"gabagool22 trading"` but claim text was `"gabagool22 trades BTC/ETH pairs."`.
  `"trading"` is not a substring of `"trades"`, so KS returned empty results and the fusion
  degraded to two-source rather than three-source.
- **Fix:** Changed test question to `"gabagool22 trades"` to match the actual claim text.
- **Files modified:** `tests/test_ris_query_spine.py`
- **Commit:** 5f07dc9

## Known Stubs

None. All new functionality is fully wired. KS results flow through RRF into the ranked output
list when `--knowledge-store` is provided.

**Limitation:** If `kb/rag/knowledge/knowledge.sqlite3` does not exist, `--knowledge-store default`
will raise a sqlite3 error. Operators must seed the KnowledgeStore before using this flag.
This is expected behavior, not a stub.

## Test Coverage

- File: `tests/test_ris_query_spine.py`
- Count: 25 offline tests
- Classes:
  - `TestReciprocalRankFusionMulti` (5 tests): correctness of N-way RRF, empty lists, single list
  - `TestQueryKnowledgeStoreForRRF` (15 tests): output shape, text filter, source_family filter,
    min_freshness filter, contradiction ranking, staleness annotation, provenance population
  - `TestQueryIndexKnowledgeStore` (5 tests): backward compat (no KS), three-way fusion, guard
    against non-hybrid + KS, empty KS degrades gracefully
- All use `KnowledgeStore(":memory:")` — no disk, no network

## Self-Check: PASSED

All key files found on disk. All task commits verified in git log.

| Item | Status |
|------|--------|
| tests/test_ris_query_spine.py | FOUND |
| packages/polymarket/rag/lexical.py | FOUND |
| packages/research/ingestion/retriever.py | FOUND |
| packages/polymarket/rag/query.py | FOUND |
| tools/cli/rag_query.py | FOUND |
| docs/features/FEATURE-ris-v2-query-spine.md | FOUND |
| docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md | FOUND |
| docs/CURRENT_STATE.md | FOUND |
| Commit 5f07dc9 (Task 1) | FOUND |
| Commit e6af757 (Task 2) | FOUND |
