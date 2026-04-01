# Dev Log: RIS v1 Ingestion Pipeline

**Date:** 2026-04-01
**Task ID:** quick-260401-n1w
**Branch:** feat/ws-clob-feed
**Author:** Claude Code

## Objective

Bridge the gap between the shipped KnowledgeStore data foundation (quick-055) and a
usable local-first ingest/query path. Implement the end-to-end ingestion pipeline:
pluggable extractor -> hard-stop -> optional eval gate -> KnowledgeStore persistence,
plus a `research-ingest` CLI command and integration tests.

## Files Changed

| File | Change Type | Purpose |
|------|-------------|---------|
| `packages/research/ingestion/__init__.py` | New | Package init; re-exports key types |
| `packages/research/ingestion/extractors.py` | New | Extractor ABC + PlainTextExtractor |
| `packages/research/ingestion/pipeline.py` | New | IngestPipeline orchestration |
| `packages/research/ingestion/retriever.py` | New | query_knowledge_store + format_provenance |
| `tools/cli/research_ingest.py` | New | `research-ingest` CLI entrypoint |
| `polytool/__main__.py` | Modified | Wire `research-ingest` into CLI router |
| `tests/fixtures/ris_seed_corpus/sample_research.md` | New | Seed fixture: microstructure analysis |
| `tests/fixtures/ris_seed_corpus/sample_wallet_analysis.txt` | New | Seed fixture: wallet pattern study |
| `tests/test_ris_ingestion_integration.py` | New | 12 offline integration tests |
| `docs/features/FEATURE-ris-v1-data-foundation.md` | Modified | Added ingestion pipeline section |

## Commands Run / Results

```
python -m pytest tests/test_ris_ingestion_integration.py -v --tb=short
# 12 passed in 0.95s

python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_research.md --no-eval --json
# {"doc_id": "c54880ed78a0...", "chunk_count": 1, "rejected": false, "reject_reason": null, "gate": "skipped"}

python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_wallet_analysis.txt --no-eval
# Ingested: sample_wallet_analysis | doc_id=24e0eac7458e... | chunks=1 | gate=skipped

python -m polytool research-ingest --text "..." --title "Test Doc" --no-eval --json
# {"doc_id": "2441887e66a9...", "chunk_count": 1, "rejected": false, ...}

python -m pytest tests/ -x -q --tb=short
# 2934 passed, 0 failed, 25 warnings
```

## Decisions Made

### Pluggable extractor ABC
`PlainTextExtractor` implements `Extractor` for .md/.txt/raw-text. The ABC makes it
easy to add future extractors (e.g., `PDFExtractor`, `HTMLExtractor`) without changing
the pipeline contract.

### IngestPipeline orchestration
The pipeline holds no state between calls: each `ingest()` call is fully independent.
This keeps the unit test surface clean and avoids session-level coupling.

### Retriever separate from Chroma
`packages/research/ingestion/retriever.py` queries the SQLite `derived_claims` table
directly via `KnowledgeStore.query_claims()`. It does not touch the Chroma vector store.
This is intentional: the knowledge store is a separate data plane from the RAG index.
Chroma integration is deferred per the feature doc's "Deliberate Simplifications" section.

### No automatic claim extraction
The pipeline stores source documents but does not create `derived_claims` entries
automatically. LLM-assisted claim extraction remains deferred (authority conflict between
Roadmap v5.1 and PLAN_OF_RECORD still unresolved). Claims must be added manually or
via a future dedicated plan.

### source_family derivation
PlainTextExtractor maps `source_type` -> `source_family` via `SOURCE_FAMILIES` from
`packages.research.evaluation.types`. Unknown source_types fall back to the source_type
string itself, matching the freshness module's behavior for unknown families.

### Hard-stop is always checked
`check_hard_stops()` runs regardless of `--no-eval`. This protects the knowledge store
from empty/garbage documents even when the LLM eval gate is skipped.

## Open Questions / Follow-Up

1. **Claim extraction**: When is the authority conflict between Roadmap v5.1 and
   PLAN_OF_RECORD resolved? That unblocks automatic claim extraction on ingest.
2. **Chroma wiring**: A follow-up plan should wire `KnowledgeStore` claims into
   the hybrid retrieval pipeline as a third retrieval source.
3. **Chunk storage**: Currently chunks are counted but not stored as embeddings.
   Chroma integration would store each chunk as a vector for semantic retrieval.

## Codex Review

**Tier:** Skip (no execution/OMS/risk code touched; CLI formatting + pipeline orchestration only)
