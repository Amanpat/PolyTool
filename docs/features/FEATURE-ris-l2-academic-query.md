---
status: complete
completed: 2026-05-09
track: Research Intelligence System
layer: L2
---

# Feature: RIS L2 Academic Query — Marker-only RAG Control Flow

**Completed:** 2026-05-09
**Track:** Research Intelligence System — L2 Academic Retrieval
**Dev log:** `docs/dev_logs/2026-05-09_ris-academic-pipeline-completion-sprint.md`

---

## What This Feature Delivers

L2 of the RIS academic pipeline: a `research-query` CLI that queries the
KnowledgeStore academic corpus using multi-angle query planning (adapted from
PaperQA2's paper-level search pattern). Only Marker-parsed papers appear in
results — enforced at ingest time by `IngestPipeline.ingest_external`'s
academic gate (`body_source=marker AND body_length >= 5000`).

---

## New Files

| File | Purpose |
|------|---------|
| `packages/research/synthesis/academic_query.py` | Core L2 library: multi-angle KS query, paper-level grouping, citation extraction |
| `tools/cli/research_query.py` | `research-query` CLI entrypoint |
| `tests/test_research_query.py` | 34 tests covering all control flow branches |

## Modified Files

| File | Change |
|------|--------|
| `polytool/__main__.py` | `research-query` wired to `research_query_main`; help text added |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | `research-query` operator section added |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 activated then closed |

---

## Algorithm (PaperQA2-inspired, Apache-2.0)

1. **Multi-angle query planning** — `plan_queries()` generates up to N template-based angles from the question (deterministic; LLM optional).
2. **KS query per angle** — `query_knowledge_store_for_rrf()` with `source_family="academic"` on each angle; case-insensitive substring match.
3. **Claim-level deduplication** — `_merge_claims()` keeps best `effective_score` per claim_id across all angles.
4. **Paper-level grouping** — `_group_by_paper()` groups by `doc_id`; papers ranked by max claim score.
5. **Citation enrichment** — `get_source_document()` fetches title, source_url, arxiv_id, body_source per paper.
6. **Graceful fallback** — if no academic docs in KS, returns `had_fallback=True` with actionable warning.

---

## Operator Path

```bash
# Query the academic corpus
python -m polytool research-query --question "market microstructure"

# More results with step-back context
python -m polytool research-query \
  --question "sports betting inefficiencies" \
  --k 10 --step-back

# Narrow to 1 query angle (primary only)
python -m polytool research-query \
  --question "avellaneda stoikov model" \
  --max-angles 1
```

**Output JSON fields:**

| Field | Description |
|-------|-------------|
| `citations[].title` | Paper title from KS source_documents |
| `citations[].arxiv_id` | arXiv ID from canonical_ids metadata |
| `citations[].source_url` | Canonical URL |
| `citations[].best_snippet` | Highest-scoring claim text for this paper |
| `citations[].paper_score` | Effective score of best claim |
| `citations[].body_source` | Parser used (`"marker"` = canonical quality) |
| `citations[].claim_count` | Claims from this paper matched by any query angle |
| `marker_only_count` | Papers with `body_source=marker` in the result set |
| `had_fallback` | `true` when KS has no academic docs |
| `query_angles` | All query strings executed |

---

## Scope

### What L2 Is

- Multi-angle KnowledgeStore query with paper-level aggregation
- Marker-only result filter (via source_family gate at ingest)
- Structured citation output with arxiv_id, source_url, body_source
- Graceful fallback when corpus is empty

### What L2 Is Not (scope guards from work packet)

- Does NOT query ChromaDB vector index for academic docs (body_source not in Chroma chunk metadata; future L2.1)
- Does NOT change the corpus ingestion path
- Does NOT implement full Recursive Contextual Summarization (RCS) with per-chunk LLM calls
- Does NOT implement page-level citations (requires body text in ChromaDB with page markers)
- LLM synthesis is not yet wired (structured citations only; future iteration)

---

## Dependency Matrix — Academic Pipeline

| Layer | Status |
|-------|--------|
| L0: PDF Download Fix | ✅ SHIPPED 2026-04-27 |
| L1: Marker Queue + IPC warm-worker | ✅ CLOSED 2026-05-08 |
| L1: Marker Production Readiness Rollout | ✅ COMPLETE 2026-05-09 |
| **L2: PaperQA2 RAG Control Flow** | **✅ COMPLETE 2026-05-09 (this feature)** |
| L3: Pre-fetch SVM Topic Filter | ✅ CLOSED 2026-05-07 |
| L4: Multi-source Academic Harvesters | Stub — NOT in this sprint (see blockers) |
| L5: Scientific RAG Evaluation Benchmark | ✅ SHIPPED 2026-05-02 |

---

## L4 Blockers (explicit non-scope)

L4 Multi-source Academic Harvesters requires:
- 5 new fetcher classes (SemanticScholar, SSRN, NBER, OpenReview, CrossrefUnpaywall)
- Session/cookie handling for SSRN and NBER
- New dependency: `openreview-py`
- Rate-limit + back-off implementations per source
- Deduplication across sources by DOI/arxiv_id
- Backfill mode + monitoring mode per fetcher
- CLI commands per source
- Network-dependent integration tests

**Assessment: 3–5 days of focused implementation. Too large for this sprint.
Next packet trigger: Director explicitly opens L4 workpacket.**

---

## Tests

| Test class | Tests | Focus |
|------------|-------|-------|
| `TestQueryAcademicCorpus` | 13 | Core query control flow, fallback, dedup, ranking |
| `TestResearchQueryCLI` | 6 | CLI argument validation, JSON output, help |
| `TestAcademicQueryHelpers` | 15 | Private helpers (extract_arxiv_id, merge_claims, etc.) |
| **Total** | **34** | All pass |

---

## Performance Notes

- KS query uses SQLite (no GPU, no model loading) — sub-second on dev machine
- Multi-angle overhead: N × SQLite query (negligible vs. Marker parse time)
- No embedding model required for academic query (KS substring matching)
