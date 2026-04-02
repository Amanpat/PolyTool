# FEATURE: RIS v2 Query Spine — KnowledgeStore as Third Hybrid Retrieval Source

**Status:** Implemented (2026-04-02)
**Plan:** quick-260402-ivb

## What Shipped

The KnowledgeStore (RIS v1 data foundation) is now wired into the canonical
`rag-query --hybrid` retrieval path as a third RRF source alongside Chroma
vector search and FTS5 lexical search.

Previously, KnowledgeStore claims existed as a sidecar disconnected from the
real query path. This closes the "Chroma wiring" gap deferred in
`FEATURE-ris-v1-data-foundation.md`.

## Architecture

```
                         ┌─────────────────────────────┐
                         │     rag-query --hybrid       │
                         │     --knowledge-store PATH   │
                         └──────────────┬──────────────┘
                                        │
               ┌────────────────────────┼────────────────────────┐
               ▼                        ▼                         ▼
   ┌──────────────────┐    ┌──────────────────────┐   ┌────────────────────┐
   │  Chroma Vector   │    │   SQLite FTS5         │   │  KnowledgeStore    │
   │  (top_k_vector)  │    │   Lexical             │   │  Claims            │
   │                  │    │   (top_k_lexical)     │   │  (top_k_knowledge) │
   └────────┬─────────┘    └──────────┬────────────┘   └─────────┬──────────┘
            │                         │                           │
            └─────────────────────────┼───────────────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  reciprocal_rank_    │
                           │  fusion_multi()      │
                           │  (3-way RRF, k=60)   │
                           └──────────┬───────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  Optional reranker   │
                           │  (cross-encoder)     │
                           └──────────┬───────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  Ranked result list  │
                           │  (top k results)     │
                           └─────────────────────┘
```

## Files Changed

| File | Change |
|------|--------|
| `packages/polymarket/rag/lexical.py` | Added `reciprocal_rank_fusion_multi()` for N-way RRF |
| `packages/polymarket/rag/query.py` | Added `knowledge_store_path`, `source_family`, `min_freshness`, `top_k_knowledge` params |
| `packages/research/ingestion/retriever.py` | Added `query_knowledge_store_for_rrf()` |
| `tools/cli/rag_query.py` | Added `--knowledge-store`, `--source-family`, `--min-freshness`, `--evidence-mode`, `--top-k-knowledge` flags |
| `tests/test_ris_query_spine.py` | 25 new offline tests |

## CLI Usage

### Basic hybrid query with KnowledgeStore
```bash
python -m polytool rag-query \
  --question "market microstructure edge" \
  --hybrid \
  --knowledge-store default
```

### With source_family filter
```bash
python -m polytool rag-query \
  --question "wallet behavior patterns" \
  --hybrid \
  --knowledge-store default \
  --source-family wallet_analysis
```

### With evidence-mode (shows provenance + contradiction annotations)
```bash
python -m polytool rag-query \
  --question "gabagool22 trading strategy" \
  --hybrid \
  --knowledge-store default \
  --evidence-mode
```

### Full options
```bash
python -m polytool rag-query \
  --question "market maker profitability" \
  --hybrid \
  --knowledge-store kb/rag/knowledge/knowledge.sqlite3 \
  --source-family book_foundational \
  --min-freshness 0.5 \
  --evidence-mode \
  --top-k-knowledge 25 \
  --k 10
```

## How Contradiction Downranking Works

KnowledgeStore applies a `0.5x` penalty multiplier to `effective_score` for
claims that are the target of at least one `CONTRADICTS` relation. This means:

- A claim with confidence=0.80 and freshness=1.0 normally has `effective_score = 0.80`
- If that claim is contradicted, `effective_score = 0.80 * 0.5 = 0.40`
- Lower `effective_score` → lower `score` in RRF-compatible output → lower RRF rank

In `--evidence-mode` output, contradicted claims have `is_contradicted: true`
and `contradiction_summary` listing the contradicting claim texts.

## How Freshness Affects Ranking

Freshness is computed via exponential decay based on source family half-lives
(config: `config/freshness_decay.json`):

```
modifier = max(floor, 2^(-age_months / half_life))
```

Key half-lives:
- `news`: 3 months
- `wallet_analysis`: 6 months
- `blog`, `reddit`, `twitter`, `youtube`: 6-9 months
- `academic_empirical`, `preprint`, `github`: 12-18 months
- `book_foundational`, `academic_foundational`: null (timeless, no decay)

Claims with `freshness_modifier < 0.5` → `staleness_note = "STALE"` in metadata.
Claims with `freshness_modifier < 0.7` → `staleness_note = "AGING"`.

In RRF, lower `effective_score = freshness * confidence * contradiction_penalty`
means lower rank in fused results.

## How Provenance Is Surfaced

In `--evidence-mode`, KS-sourced results have these fields promoted to
top-level keys (they also exist in `metadata`):

- `provenance_docs`: list of source document dicts `{title, source_url, source_family}`
- `contradiction_summary`: list of contradicting claim texts
- `staleness_note`: `"STALE"`, `"AGING"`, or `""`
- `lifecycle`: `"active"`, `"archived"`, `"superseded"`
- `is_contradicted`: bool

The provenance chain is: `KS result → claim_evidence → source_documents`.

## What Is NOT Included

- **Semantic search over claims**: KS retrieval uses keyword filter only
  (`text_query` is a case-insensitive substring match, not embedding-based).
  This is intentional — KS claims are structured, not free text, and semantic
  matching over structured claims adds complexity without proportional value.
- **Automatic claim extraction**: No LLM-based extraction from ingested docs.
  Claims are added manually or via the seeder CLI.
- **Qdrant migration**: Still using SQLite-backed KnowledgeStore.
  Qdrant was deferred and remains so.

## Tests

- File: `tests/test_ris_query_spine.py`
- Count: 25 offline tests
- Coverage: output shape, filtering, contradiction ranking, staleness annotation,
  provenance population, three-way RRF fusion, backward compatibility,
  `reciprocal_rank_fusion_multi` correctness

## Deferred

- Semantic/embedding-based matching over claims (future enhancement)
- Automatic claim extraction from ingested documents (Phase 3+)
