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
kb/ + artifacts/ -> lexical index (SQLite FTS5: kb/rag/lexical/lexical.sqlite3)
Chroma/lexical -> rag-query -> snippets for offline memos
```

RAG storage locations:
- `kb/rag/index/` - Chroma vector index
- `kb/rag/lexical/lexical.sqlite3` - SQLite FTS5 lexical index
- `kb/rag/models/` - embedding + reranker model cache
- `kb/rag/eval/reports/` - retrieval eval outputs

## Local RAG boundary
The RAG pipeline indexes by default:
- `kb/`
- `artifacts/`

Optionally, `docs/archive/` can be added when you want RAG to surface past design decisions:
```
polytool rag-index --roots "kb,artifacts,docs/archive" --rebuild
```

**External / manual LLM UIs**: if you paste retrieved snippets into a hosted model (Opus 4.5 web,
ChatGPT, etc.), upload only the memo + minimal dossier excerpts you are comfortable sharing.

## Hybrid retrieval (vector + lexical)

PolyTool supports offline hybrid retrieval: vector search (Chroma) + keyword search (SQLite FTS5),
combined with Reciprocal Rank Fusion (RRF). The lexical DB lives at:

```
kb/rag/lexical/lexical.sqlite3
```

**Fusion method**: RRF with default *k=60* (configurable via `--rrf-k`).

## RAG metadata filter schema

Each indexed chunk carries structured metadata used by Chroma `where`-filters at
query time.  This replaces the earlier path-prefix post-filtering with database-level
enforcement.

| Field | Type | Nullable | Source |
|-------|------|----------|--------|
| `doc_type` | string | no | Path pattern: `user_kb`, `dossier`, `kb`, `artifact`, `docs`, `archive` |
| `user_slug` | string | yes | Extracted from `kb/users/<slug>/` or `artifacts/dossiers/<slug>/` |
| `proxy_wallet` | string | yes | 0x-address parsed from path (if present) |
| `is_private` | bool | no | `true` for `kb/` and `artifacts/`, `false` for `docs/` |
| `created_at` | ISO-8601 | yes | Date from path pattern, else file mtime |

### Safe defaults

- **Default query scope is private-only** (`is_private = true`).  Public `docs/`
  content is never returned unless `--public-only` is explicitly passed.
- **Archive documents excluded by default** (`doc_type != "archive"`).  Pass
  `--include-archive` to include them.
- **User isolation**: passing `--user <slug>` adds `user_slug = <slug>` to the
  Chroma where-clause.  Chunks without a matching `user_slug` are excluded at
  the database level.
- Path-prefix post-filtering is retained as a **defensive backstop** only;
  correctness comes from the metadata where-clause.

### CLI flags (rag-query)

```
--user <slug>             Scope to a single user
--doc-type <value>        Filter by doc_type (repeatable / comma-separated)
--private-only            (default) Only private content
--public-only             Only public content
--date-from YYYY-MM-DD    Created on or after
--date-to   YYYY-MM-DD    Created on or before
--include-archive         Include archive documents
--hybrid                  Use vector + lexical retrieval with RRF fusion
--lexical-only            Use lexical (FTS5) retrieval only
--top-k-vector <n>         Vector candidates for hybrid fusion (default 25)
--top-k-lexical <n>        Lexical candidates for hybrid fusion (default 25)
--rrf-k <n>                RRF constant (default 60)
```

## Safety
A pre-push guard blocks committing private or secrets-like files. See `docs/RISK_POLICY.md`.
