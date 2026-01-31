# Architecture

PolyTool keeps the public documentation and code clean while routing all user/private data into
local-only storage.

## Components
- `services/api/`: FastAPI service that ingests and computes analytics.
- `infra/clickhouse/`: ClickHouse schemas + migrations.
- `packages/polymarket/`: Shared clients + analytics logic.
- `tools/cli/`: Local CLI utilities (scan, dossier export, clickhouse export, RAG).
- `docs/`: Public truth source + ADRs.
- `kb/` + `artifacts/`: Private local data (gitignored).

## Data flow (local-only)
```
Polymarket APIs -> API ingest -> ClickHouse
                              -> dossier export -> artifacts/
                              -> clickhouse export -> kb/
kb/ + artifacts/ -> local embeddings -> Chroma index (kb/rag/index)
Chroma index -> rag-query -> snippets for offline memos
```

## Local RAG boundary
The RAG pipeline indexes **only**:
- `kb/`
- `artifacts/`

No other folders (including `docs/`) are indexed. This keeps public docs clean and private data
contained.

## Safety
A pre-push guard blocks committing private or secrets-like files. See `docs/RISK_POLICY.md`.
