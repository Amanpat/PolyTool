---
phase: quick-260401-n1w
plan: 01
subsystem: research-ingestion
tags: [ris, ingestion, pipeline, knowledge-store, cli]
dependency_graph:
  requires: [packages/polymarket/rag/knowledge_store.py, packages/research/evaluation/hard_stops.py, packages/research/evaluation/evaluator.py]
  provides: [packages/research/ingestion/extractors.py, packages/research/ingestion/pipeline.py, packages/research/ingestion/retriever.py, tools/cli/research_ingest.py]
  affects: [polytool/__main__.py]
tech_stack:
  added: []
  patterns: [pluggable-extractor-abc, pipeline-orchestration, sqlite-query-helpers]
key_files:
  created:
    - packages/research/ingestion/__init__.py
    - packages/research/ingestion/extractors.py
    - packages/research/ingestion/pipeline.py
    - packages/research/ingestion/retriever.py
    - tools/cli/research_ingest.py
    - tests/fixtures/ris_seed_corpus/sample_research.md
    - tests/fixtures/ris_seed_corpus/sample_wallet_analysis.txt
    - tests/test_ris_ingestion_integration.py
    - docs/dev_logs/2026-04-01_ris_ingestion_pipeline.md
  modified:
    - polytool/__main__.py
    - docs/features/FEATURE-ris-v1-data-foundation.md
decisions:
  - Pluggable Extractor ABC so future extractors (PDF, HTML) don't change the pipeline contract
  - Hard-stop always runs regardless of --no-eval (guards the knowledge store from garbage)
  - No automatic claim extraction deferred until LLM authority conflict is resolved
  - Retriever stays separate from Chroma (separate data planes per feature doc policy)
metrics:
  duration: ~25m
  completed: 2026-04-01
  tasks_completed: 2
  files_created: 9
  files_modified: 2
  tests_added: 12
  tests_total: 2934
---

# Phase quick-260401-n1w Plan 01: RIS Ingestion Pipeline Summary

**One-liner:** PlainTextExtractor + IngestPipeline wiring KnowledgeStore with hard-stop gating, query_knowledge_store helpers, and a `research-ingest` CLI command.

## What Was Built

End-to-end RIS ingestion pipeline connecting the shipped KnowledgeStore data foundation
to a usable local-first ingest path. A user can now ingest `.md` or `.txt` files into
the SQLite knowledge store with a single CLI command.

## Tasks

| # | Name | Commit | Status |
|---|------|--------|--------|
| 1 | Ingestion core -- extractors, pipeline, retriever, seed fixtures | 3a7878c | Done |
| 2 | CLI command + __main__ wiring + docs | fbc581a | Done |

## Key Components

### packages/research/ingestion/extractors.py
- `Extractor` ABC with `extract(source, **kwargs) -> ExtractedDocument`
- `PlainTextExtractor`: handles `.md` files (H1 title extraction), `.txt` files (stem title), and raw text strings
- `source_type` -> `source_family` mapping via `SOURCE_FAMILIES`
- SHA-256 content hash stored in metadata

### packages/research/ingestion/pipeline.py
- `IngestPipeline(store, extractor=None, evaluator=None)` -- evaluator=None skips eval gate
- Orchestrates: extract -> hard-stop -> optional eval gate -> KnowledgeStore.add_source_document
- Returns `IngestResult(doc_id, chunk_count, gate_decision, rejected, reject_reason)`
- Hard-stop always runs; `--no-eval` only skips the DocumentEvaluator step

### packages/research/ingestion/retriever.py
- `query_knowledge_store(store, source_family=None, min_freshness=None, top_k=20)`: filters claims from KnowledgeStore.query_claims() by source_family and/or freshness
- `format_provenance(claim, source_docs)`: human-readable claim + source attribution string
- Completely separate from Chroma/FTS5 retrieval

### tools/cli/research_ingest.py
- `main(argv) -> int` -- follows research_eval.py pattern exactly
- `--file` / `--text` (mutually exclusive), `--title`, `--source-type`, `--author`, `--db`, `--no-eval`, `--provider`, `--json`
- Returns 0 on success (including rejected docs), 1 on argument error, 2 on unexpected exception
- Closes KnowledgeStore in finally block

## Verification Results

```
# 12 new tests
python -m pytest tests/test_ris_ingestion_integration.py -v
# 12 passed in 0.95s

# Full regression
python -m pytest tests/ -x -q
# 2934 passed, 0 failed, 25 warnings

# CLI smoke tests
python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_research.md --no-eval --json
# {"doc_id": "c54880ed78a0...", "chunk_count": 1, "rejected": false, "gate": "skipped"}

python -m polytool research-ingest --file tests/fixtures/ris_seed_corpus/sample_wallet_analysis.txt --no-eval
# Ingested: sample_wallet_analysis | doc_id=24e0eac7458e... | chunks=1 | gate=skipped

python -m polytool --help | grep research-ingest
# research-ingest       Ingest a document into the RIS knowledge store
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. The ingestion pipeline stores `source_documents` only (no auto-claim extraction). This is intentional per the plan's design -- automatic claim extraction is deferred pending the LLM authority conflict resolution. The data plane is complete and functional for manual claim creation.

## Self-Check: PASSED

Files created:
- packages/research/ingestion/__init__.py -- FOUND
- packages/research/ingestion/extractors.py -- FOUND
- packages/research/ingestion/pipeline.py -- FOUND
- packages/research/ingestion/retriever.py -- FOUND
- tools/cli/research_ingest.py -- FOUND
- tests/fixtures/ris_seed_corpus/sample_research.md -- FOUND
- tests/fixtures/ris_seed_corpus/sample_wallet_analysis.txt -- FOUND
- tests/test_ris_ingestion_integration.py -- FOUND

Commits:
- 3a7878c -- FOUND (Task 1)
- fbc581a -- FOUND (Task 2)
