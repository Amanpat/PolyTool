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
PaperQA2's paper-level search pattern). Only Marker/RAG-ready papers appear in
results: the ingest gate enforces `body_source=marker AND body_length >= 5000`
for new rows, and `research-query` re-checks that metadata before returning
citations so legacy pdfplumber rows cannot leak into operator answers.

---

## New Files

| File | Purpose |
|------|---------|
| `packages/research/synthesis/academic_query.py` | Core L2 library: multi-angle KS query, paper-level grouping, citation extraction |
| `tools/cli/research_query.py` | `research-query` CLI entrypoint |
| `tests/test_research_query.py` | 36 tests covering all control flow branches |

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
4. **Marker-ready filter** — source document metadata must prove `body_source=marker` and `body_length >= 5000`.
5. **Paper-level grouping** — `_group_by_paper()` groups by `doc_id`; papers ranked by max claim score.
6. **Citation enrichment** — `get_source_document()` fetches title, source_url, arxiv_id, body_source per paper.
7. **Graceful fallback** — if no Marker-ready academic docs remain, returns `had_fallback=True` with actionable warning.

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
| `marker_only_count` | Papers with `body_source=marker` in the result set; should equal returned citations |
| `had_fallback` | `true` when KS has no academic docs |
| `query_angles` | All query strings executed |

---

## Query Normalization (2026-05-09 fix)

`_normalize_question()` and `_build_sub_queries()` strip common question preambles
before retrieval so that natural-language questions work without requiring exact
substring matches in claim text.

**Preamble examples stripped:** "what are", "what is", "explain", "how does",
"describe", "tell me about", "give me an overview of".

**Behavior table:**

| Question input | Retrieval also searches |
|----------------|------------------------|
| `"prediction markets"` | `"prediction markets"` (no change — already a phrase) |
| `"what are prediction markets"` | `"prediction markets"` (preamble stripped) |
| `"explain sports betting markets"` | `"sports betting markets"` (preamble stripped) |
| `"avellaneda stoikov spread model"` | `"avellaneda stoikov model"` (no change) |

The original question string is always preserved in the JSON output `question` field.
Retrieval is conservative substring/phrase matching — **not** semantic or vector retrieval.
Unrelated questions (e.g., "what is the weather today") still return no citations if
no claim text matches.

## No-Result Cases

Two distinct situations both result in no citations returned (`had_fallback=true`):

| Case | Cause | Operator action |
|------|-------|-----------------|
| **Empty academic corpus** | KnowledgeStore has no academic source documents | Run `index-done` first to load Marker-ready papers; confirm `warm-process` produced `marker_ready=True` results |
| **Corpus exists, no matching claims** | Academic docs are indexed but no claim text matches the query (including normalized form) | Expand corpus via `research-harvest` → `warm-process` → `index-done`; or try a different topic phrase |

Both cases emit an actionable warning. The `had_fallback` flag is `true` for both.
The warning message text distinguishes them at runtime.

## Scope

### What L2 Is

- Multi-angle KnowledgeStore query with paper-level aggregation
- Marker-ready result filter (`source_family=academic` plus query-time metadata guard)
- Structured citation output with arxiv_id, source_url, body_source
- Natural-language query normalization (preamble stripping for retrieval only)
- Graceful fallback with actionable warning for both empty-corpus and no-match cases

### What L2 Is Not (scope guards from work packet)

- Does NOT query ChromaDB vector index for academic docs (body_source not in Chroma chunk metadata; future L2.1)
- Does NOT implement semantic or vector retrieval — retrieval is conservative substring/phrase matching
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
| L4: Multi-source Academic Harvesters | COMPLETE 2026-05-09 after this L2 sprint; see `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md` |
| L5: Scientific RAG Evaluation Benchmark | ✅ SHIPPED 2026-05-02 |

---

## L4 Status

L4 was not part of the original L2 sprint, but it was completed later on
2026-05-09. It ships four metadata-only harvesters (arXiv, Semantic Scholar,
Crossref, OpenReview), source registry/selection, deduplication, and the
`research-harvest` CLI. SSRN and NBER remain explicitly deferred because they
require brittle session/cookie or HTML scraping paths.

---

## Tests

| Test class | Tests | Focus |
|------------|-------|-------|
| `TestQueryAcademicCorpus` | 15 | Core query control flow, fallback, dedup, ranking, bad-doc rejection |
| `TestResearchQueryCLI` | 6 | CLI argument validation, JSON output, help |
| `TestAcademicQueryHelpers` | 15 | Private helpers (extract_arxiv_id, merge_claims, etc.) |
| Normalization tests | 18 | `_normalize_question()`, `_build_sub_queries()`, natural-language preamble stripping |
| **Total** | **54** | All pass |

---

## Performance Notes

- KS query uses SQLite (no GPU, no model loading) — sub-second on dev machine
- Multi-angle overhead: N × SQLite query (negligible vs. Marker parse time)
- No embedding model required for academic query (KS substring matching)
