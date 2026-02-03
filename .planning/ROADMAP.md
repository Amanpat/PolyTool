# PolyTool Roadmap

## Milestone: v1.0 — Core RAG Pipeline

### Phase 1: Foundation (COMPLETE)
- ClickHouse + Grafana infrastructure
- Scanner and export pipelines

### Phase 2: RAG Core (COMPLETE)
- Chunker, embedder, metadata derivation
- Chroma vector index + query pipeline
- Deterministic IDs, idempotent indexing

### Phase 3: Hybrid Retrieval (COMPLETE)
- SQLite FTS5 lexical index
- Reciprocal Rank Fusion
- Lexical-only mode

### Phase 4: Index Management & Eval (COMPLETE)
- Reconcile mode for stale chunk cleanup
- Offline eval harness with recall@k, MRR@k, scope violations
- JSONL test suite format

### Phase 5: Reranking (PLANNED)
- Optional cross-encoder reranking after hybrid fusion
- Model caching under kb/rag/models/
- Integration with eval harness
