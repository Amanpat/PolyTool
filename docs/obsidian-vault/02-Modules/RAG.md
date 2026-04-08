---
type: module
status: done
tags: [module, status/done, rag]
lines: ~3124
test-coverage: partial
created: 2026-04-08
---

# RAG

Source: audit Section 1.1 — `packages/polymarket/rag/` (13 files, ~3,124 lines).

Two coexisting storage backends:

| Backend | Technology | Purpose |
|---------|-----------|---------|
| ChromaDB | Vector store | Semantic similarity search |
| SQLite FTS5 | Lexical search | Keyword / full-text search |

ChromaDB collection name: `polytool_rag`
KnowledgeStore path: `kb/rag/knowledge/knowledge.sqlite3`

---

## Module Inventory

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `chroma_store.py` | ~400 | ChromaDB vector store interface | WORKING |
| `knowledge_store.py` | ~350 | SQLite FTS5 lexical knowledge store | WORKING |
| `hybrid_retriever.py` | ~300 | Hybrid retrieval — vector + lexical fusion | WORKING |
| `embedder.py` | ~250 | Text embedding (SentenceTransformers) | WORKING |
| `indexer.py` | ~300 | Document ingestion and index building | WORKING |
| `query.py` | ~200 | Query orchestration | WORKING |
| `models.py` | ~150 | Dataclasses for RAG results | WORKING |
| `config.py` | ~100 | RAG configuration | WORKING |
| `utils.py` | ~150 | Shared utilities | WORKING |
| `__init__.py` | — | Package init | — |

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `rag-index` | Build or rebuild RAG vector index |
| `rag-query` | Hybrid query (vector + lexical) |
| `rag-refresh` | Alias for `rag-index --rebuild` |

---

## Key Behaviors

- Offline-first — no external API calls for indexing or querying
- Hybrid mode: `--hybrid` flag fuses ChromaDB semantic results with SQLite FTS5 lexical results
- `--knowledge-store default` targets `kb/rag/knowledge/knowledge.sqlite3`
- SentenceTransformers for local embedding (no paid API required)

---

## Cross-References

- [[Database-Rules]] — ClickHouse/DuckDB one-sentence rule (RAG uses neither)
- [[LLM-Policy]] — Tier 1b (Ollama) for LLM calls; RAG retrieval is purely local
- [[RIS]] — Research Intelligence System uses a parallel SQLite knowledge store

