# Dev Log: RIS Phase 2 Query Spine Wiring

**Date:** 2026-04-02
**Plan:** quick-260402-ivb
**Author:** agent (claude-sonnet-4-6)

## Objective

Wire the seeded RIS corpus (KnowledgeStore) into the canonical `rag-query --hybrid`
retrieval path as a third RRF source. KnowledgeStore claims previously existed as a
sidecar disconnected from real retrieval — this plan closes that gap.

## Files Changed

| File | What Changed | Why |
|------|-------------|-----|
| `packages/polymarket/rag/lexical.py` | Added `reciprocal_rank_fusion_multi()` | Need N-way RRF to merge 3 sources (vector + lexical + KS) |
| `packages/polymarket/rag/query.py` | Added `knowledge_store_path`, `source_family`, `min_freshness`, `top_k_knowledge` params to `query_index()` | KS integration point in hybrid path |
| `packages/research/ingestion/retriever.py` | Added `query_knowledge_store_for_rrf()` | RRF-compatible adapter for KS claims |
| `tools/cli/rag_query.py` | Added `--knowledge-store`, `--source-family`, `--min-freshness`, `--evidence-mode`, `--top-k-knowledge` flags | CLI exposure of new hybrid+KS path |
| `tests/test_ris_query_spine.py` | New: 25 offline tests | TDD coverage for all new functionality |
| `docs/features/FEATURE-ris-v2-query-spine.md` | New: feature doc | Architecture, CLI examples, provenance/contradiction docs |
| `docs/CURRENT_STATE.md` | Updated RIS section | Record shipped truth |

## Key Decisions

### 1. Three-way RRF over a separate sidecar

**Decision:** Merge KS claims into the existing RRF pipeline via
`reciprocal_rank_fusion_multi()` rather than returning them as a separate
section in the output payload.

**Rationale:** A unified ranked list is more useful to callers (rerankers,
consumers of the output) than separate sections requiring manual merging.
The RRF formulation is also naturally extensible — adding a fourth source
later requires no interface change.

### 2. Keyword filter over semantic search for claims

**Decision:** `query_knowledge_store_for_rrf(text_query=...)` uses a
case-insensitive substring match (`query_lower in claim_text.lower()`),
NOT embedding-based semantic search.

**Rationale:** KS claims are concise, structured statements (10-50 words).
Running a full embedding model over them adds latency and complexity.
Keyword matching is sufficient for the current use case (filtering obvious
non-matches). Semantic matching over claims is deferred.

### 3. Evidence-mode as opt-in, not always-on

**Decision:** Provenance/contradiction fields are promoted to top-level keys
only when `--evidence-mode` is set. By default, KS results appear as normal
snippets with rich metadata available in the `metadata` dict.

**Rationale:** The default output format should be uniform for all result
sources. Evidence-mode is a "zoom in" operation for operators who want full
provenance visibility. Not all consumers need it.

## Commands Run

### TDD cycle
```bash
# RED phase: tests fail as expected (25 failures)
python -m pytest tests/test_ris_query_spine.py -v --tb=short

# GREEN phase: implement code, rerun
python -m pytest tests/test_ris_query_spine.py -v --tb=short
# Result: 25 passed in 0.44s
```

### Full regression
```bash
python -m pytest tests/ -x -q --tb=short
# Result: 3037 passed, 0 failed, 25 warnings in 101.98s
# (was 3012 before this plan; +25 new tests)
```

### CLI smoke tests
```bash
python -m polytool --help
# rag-query listed, no import errors

python -m polytool rag-query --help
# --knowledge-store, --source-family, --min-freshness, --evidence-mode, --top-k-knowledge all present
```

## Codex Review

Tier: Recommended. No adversarial-required files touched (no execution/,
kill_switch.py, risk_manager.py, rate_limiter.py, or CLOB order placement).
This is pure query/retrieval code — no live execution paths changed.
Codex review skipped for this session (retrieval-only change, no capital risk).

## Notes / Limitations

- This closes the "Chroma wiring" gap from `FEATURE-ris-v1-data-foundation.md`
  (previously deferred under "Chroma wiring deferred").
- No semantic matching on claims (keyword only). This is a known limitation.
- No automatic claim extraction from documents. Claims are added manually or via seeder.
- The `DEFAULT_KNOWLEDGE_DB_PATH` is `kb/rag/knowledge/knowledge.sqlite3`. If this
  file does not exist, `query_index()` with `knowledge_store_path=default` will
  raise a sqlite3 error. Operators must run the seeder before using `--knowledge-store default`.
- text_query in query_index is passed as the `question` parameter. This means ALL
  questions sent to hybrid+KS mode also filter KS claims by substring. If the question
  has no matching claims, KS returns empty and the two-source fusion degrades to normal
  two-way RRF. This is the correct behavior.
