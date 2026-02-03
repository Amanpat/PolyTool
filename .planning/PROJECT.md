# PolyTool

## Vision
Monorepo for Polymarket reverse-engineering tools and analysis infrastructure. Local-first, offline-capable tooling for market data analysis with RAG-powered knowledge retrieval.

## Stack
- Python (services, CLI, RAG pipeline)
- ClickHouse (analytics storage)
- Grafana (visualization)
- ChromaDB + SQLite FTS5 (vector + lexical search)
- SentenceTransformers (embeddings)

## Key Principles
- Local-first: all infrastructure runs locally via Docker Compose
- Offline-only: no external API calls for core workflows
- Privacy-scoped: user isolation enforced at query and index level
- Deterministic: SHA256-based IDs, reproducible indexes
