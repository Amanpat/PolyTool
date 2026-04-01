# Dev Log: RIS v1 Data Foundation

**Date:** 2026-04-01
**Task:** quick-055 / 260401-m8q
**Branch:** feat/ws-clob-feed

## Objective

Implement the RIS v1 data foundation: a lightweight SQLite-backed persistence
layer for source documents, derived claims, claim evidence, and claim relations,
with query-time freshness decay and retrieval helpers for the `external_knowledge`
RAG partition.

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `packages/polymarket/rag/knowledge_store.py` | Created | Core persistence layer |
| `packages/polymarket/rag/freshness.py` | Created | Freshness decay computation |
| `config/freshness_decay.json` | Created | Source-family half-life config |
| `tests/test_knowledge_store.py` | Created | 38 offline tests |
| `docs/features/FEATURE-ris-v1-data-foundation.md` | Created | Feature documentation |
| `docs/CURRENT_STATE.md` | Appended | RIS v1 section + authority conflict note |

## Commands Run + Output

**Task 1 verification (knowledge store tests):**
```
python -m pytest tests/test_knowledge_store.py -v --tb=short
38 passed in 0.43s
```

**Task 1 TDD fix cycle:**
- RED: 0 tests collected (modules missing) -- correct failure
- GREEN (first attempt): 35 passed, 3 failed
  - `sqlite_sequence` internal table: `_list_tables()` needed to filter sqlite_ prefix tables
  - `test_recent_news_high_modifier`: 30-day-old news was borderline 0.796 for > 0.8 threshold; adjusted test to use 14-day window
  - `test_provenance_returns_source_docs_for_claim`: two docs had same deterministic ID (same source_url + content_hash); test fixture needed distinct URLs/hashes
- GREEN (final): 38 passed, 0 failed

**Full regression suite:**
```
python -m pytest tests/ -x -q --tb=short
2825 passed, 25 warnings in 99.55s
```
(Warnings are pre-existing `datetime.utcnow()` deprecation warnings, not caused by this task.)

**Module import smoke test:**
```
python -c "from packages.polymarket.rag.knowledge_store import KnowledgeStore; ks = KnowledgeStore(':memory:'); print('OK')"
OK

python -c "from packages.polymarket.rag.freshness import load_freshness_config; c = load_freshness_config(); print(len(c['source_families']), 'families')"
11 families
```

**CLI smoke test:**
```
python -m polytool --help
[passes cleanly]
```

## Decisions Made

### SQLite over ORM

The existing codebase (`lexical.py`) already uses stdlib `sqlite3` directly.
Following that pattern avoids a new dependency and keeps the codebase consistent.
SQLite is sufficient for the current use cases (offline analysis, seeding
Jon-Becker findings, Phase 2 research scraper foundation).

### No Chroma wiring yet

The knowledge store is a data-plane addition. Wiring it into the Chroma/FTS5
hybrid retrieval pipeline is a separate concern deferred to a future plan. Adding
it now would expand the scope beyond the plan objective and risk breaking the
existing RAG pipeline.

### Claim shape choices

- Required fields kept minimal: `claim_text`, `claim_type`, `confidence`,
  `trust_tier`, `validation_status`, `lifecycle`, `actor`, `created_at`, `updated_at`
- Optional fields allow extensibility without schema migrations: `scope`, `tags`,
  `notes`, `superseded_by`, `source_document_id`
- `lifecycle` values: `active` (default), `archived`, `superseded` -- these map
  directly to the filtering semantics in `query_claims()`

### Freshness computation

- `functools.lru_cache` on the resolved config file path avoids repeated disk reads
- Exponential decay: `2^(-age_months / half_life)` is the standard half-life formula
- Floor=0.3 prevents zero-valued modifiers for very old content (some value is better
  than complete silence)
- `None` published_at returns 1.0 (unknown age = no penalty, not maximum penalty)

### Contradiction penalty

- Applied as a 0.5x multiplier to `freshness_modifier` when any CONTRADICTS
  relation targets the claim
- Result: `effective_score = freshness_modifier * confidence * contradiction_penalty`
- Contradicted claims sort lower but are not hidden (use `include_archived=True`
  to retrieve them alongside archived claims if needed)

### _llm_provider = None

The `KnowledgeStore._llm_provider` attribute is an integration point for future
LLM-assisted claim extraction. Defaulting to None prevents any accidental cloud
API calls while still providing a clear extension point.

## Authority Conflict (Unresolved)

**Roadmap v5.1, Section "LLM Policy":**
> Tier 1: Free cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash) -- allowed per v5.1
> for hypothesis generation and scraper evaluation.

**PLAN_OF_RECORD, Section 0 "Roadmap Authority and Open Deltas":**
> Current toolchain policy remains no external LLM API calls.

Code includes `_llm_provider` abstraction but defaults to `None`. Resolution
requires an explicit operator decision. See
`docs/features/FEATURE-ris-v1-data-foundation.md` for the full conflict writeup.

## Open Questions

1. **Authority conflict resolution:** When will the operator decide whether to
   enable Tier 1 free cloud API calls for claim extraction? The code is ready;
   only policy is blocking.

2. **Jon-Becker seed timing:** When should the Jon-Becker wallet analysis findings
   be seeded into the knowledge store? This is described as a Phase 1 roadmap item
   in v5.1 but has no scheduled task yet.

3. **Chroma integration approach:** Should claim text be indexed in Chroma for
   semantic retrieval? The current data plane stores raw text but doesn't embed it.
   A future plan should define the embedding strategy.

## Codex Review

Tier: Skip (docs, config, new standalone library module with no execution/trading
path dependency). No adversarial review required per CLAUDE.md Codex policy.
