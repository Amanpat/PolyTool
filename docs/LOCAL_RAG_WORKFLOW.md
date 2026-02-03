# Local RAG Workflow

This workflow is fully local/offline. It never uses external LLM APIs.

## RAG vs export-dossier (what each does)
- **export-dossier** creates a single-user evidence package (JSON + memo + manifest)
  from a scan. It is a point-in-time dossier meant for human review and downstream
  memo writing.
- **Local RAG** builds a searchable index over your private corpus (`kb/` +
  `artifacts/`). It does not summarize content by itself; it retrieves snippets
  you can stitch into a memo or feed into an offline model.

## Install (local only)
```
pip install -r requirements-rag.txt
```

Windows note: for CUDA builds of `torch`, follow the official PyTorch install selector. CPU-only works fine.

## Directory layout (private + gitignored)
- `kb/rag/index/` - Chroma vector index
- `kb/rag/lexical/lexical.sqlite3` - SQLite FTS5 lexical index
- `kb/rag/models/` - cached embedding + reranker models
- `kb/rag/eval/reports/<timestamp>/` - `rag-eval` outputs (`report.json`, `summary.md`)
- `artifacts/dossiers/...` - dossier exports from `export-dossier`
- `kb/users/<slug>/exports/<YYYY-MM-DD>/` - ClickHouse export datasets

## End-to-end workflow (scan -> Grafana -> dossier -> RAG -> Opus bundle -> eval)

1) Run scan (ingest data into ClickHouse)
```
python -m polyttool scan
```

2) View results in Grafana
- Open http://localhost:3000
- Dashboards: **PolyTool - User Trades**, **Strategy Detectors**, **PnL**

3) Export dossier (private artifacts)
```
python -m polyttool export-dossier --user "@Pimping"
```

4) Export ClickHouse datasets (private KB, optional but recommended for RAG)
```
python -m polyttool export-clickhouse --user "@Pimping"
```

5) Build the local RAG index (kb + artifacts only)
```
python -m polyttool rag-index --roots "kb,artifacts" --rebuild
```

Optional - include archived docs (useful when you want RAG to surface past design decisions):
```
python -m polyttool rag-index --roots "kb,artifacts,docs/archive" --rebuild
```

6) Query the local RAG index (hybrid + rerank recommended)
```
python -m polyttool rag-query --question "Summarize recent strategy shifts" --hybrid --rerank --k 8
```

Limit to a specific user:
```
python -m polyttool rag-query --user "@Pimping" --question "Most recent evidence" --hybrid --rerank --k 8
```

7) Build an Opus 4.5 evidence bundle
See `docs/OPUS_BUNDLE_WORKFLOW.md` for the exact files + prompt template.

8) Optional - evaluate retrieval quality
```
python -m polyttool rag-eval --suite docs/eval/sample_queries.jsonl
```
Reports are written to `kb/rag/eval/reports/<timestamp>/`.

## Scoping and filters (rag-query)

The default scope is **private-only** (`kb/` + `artifacts/`). Public docs are excluded
unless you explicitly pass `--public-only`.

Common scoping flags:
- `--user <slug>`: isolate results to one user (e.g. `"@Pimping"`).
- `--doc-type <value>`: filter by document type (repeatable or comma-separated). Values:
  `user_kb`, `dossier`, `kb`, `artifact`, `docs`, `archive`.
- `--date-from YYYY-MM-DD` / `--date-to YYYY-MM-DD`: filter by created date.
- `--include-archive`: include `docs/archive` content (excluded by default).

Examples:
```
# Only your private KB notes (not dossiers)
python -m polyttool rag-query --question "open questions" --doc-type kb --k 6

# Only a user's KB notes
python -m polyttool rag-query --question "latest reasoning" --doc-type user_kb --user "@Pimping" --k 6

# Time-bounded query
python -m polyttool rag-query --question "January decisions" --date-from 2026-01-01 --date-to 2026-01-31 --k 8
```

## rag-query flags (quick reference)
- `--question` (required): the query string.
- `--k`: number of results to return.
- `--user`, `--doc-type`, `--private-only`, `--public-only`, `--date-from`, `--date-to`, `--include-archive`.
- `--hybrid`, `--lexical-only`, `--top-k-vector`, `--top-k-lexical`, `--rrf-k`.
- `--rerank`, `--rerank-top-n`, `--rerank-model`.
- `--model`, `--device`, `--persist-dir`, `--collection`.

## Retrieval modes (vector / lexical / hybrid / rerank)
- **Vector (default)**: embedding search over the Chroma index.
- **Lexical-only** (`--lexical-only`): SQLite FTS5 keyword search. Fast, no embedding model needed.
- **Hybrid** (`--hybrid`): vector + lexical fused with RRF. Tune with `--top-k-vector`,
  `--top-k-lexical`, and `--rrf-k`.
- **Rerank** (`--rerank`): cross-encoder rescoring of the top fused results.
  Requires `--hybrid`. Configure with `--rerank-top-n` and `--rerank-model`.

Model files are cached under `kb/rag/models/` (gitignored). First run downloads the model;
subsequent runs load from cache.

## Common pitfalls
- **PowerShell quoting**: always quote `@user` values.
  Example: `--user "@Pimping"` or `--user '@Pimping'`.
- **FTS5 missing**: if you see `no such module: fts5`, your SQLite build lacks FTS5.
  Reinstall Python/SQLite with FTS5 enabled, or run vector-only retrieval (skip
  `--lexical-only` and `--hybrid`).
- **First-run model downloads**: the first vector/hybrid/rerank run downloads models
  into `kb/rag/models/`. If you are fully offline, pre-download the models or use
  `--lexical-only` temporarily.
- **Rerank requires hybrid**: `--rerank` only works with `--hybrid`.

## RAG eval outputs (what they mean)
`rag-eval` is a retrieval quality harness. It does not produce summaries.
It reports whether required files appear in the top-k results and whether any
out-of-scope files leak into the results.

Outputs:
- `report.json`: machine-readable metrics per case/mode (recall@k, MRR@k, latency,
  scope violations).
- `summary.md`: human-readable aggregates + per-case metrics. No snippets or content.

## Dev Brain (private dev context under kb/)
Store private engineering context under `kb/` so it is indexed alongside dossier data.
See `docs/KNOWLEDGE_BASE_CONVENTIONS.md` for the canonical KB layout and the required
Agent Run Log format (one log per agent run).

After adding files, rebuild or reconcile the index:
```
python -m polyttool rag-index --roots "kb,artifacts" --rebuild
```

Example queries:
```
# Search general dev notes
python -m polyttool rag-query --question "release checklist" --doc-type kb --k 8

# Search a specific user's notes
python -m polyttool rag-query --question "risk posture" --doc-type user_kb --user "@Pimping" --k 8
```
