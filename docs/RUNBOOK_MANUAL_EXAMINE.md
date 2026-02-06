# Runbook: Manual Examination Workflow

This is the single authoritative runbook for examining a Polymarket user using the
manual (non-MCP) workflow. Every command uses `python -m polytool`.

## Prerequisites

- Python 3.10+ with PolyTool installed (`pip install -e ".[rag,dev]"`)
- Docker Compose running (`docker compose up -d --build`)
- `.env` file configured (copy from `.env.example`)
- Target user handle or wallet address

## End-to-End Workflow

### Step 1: Scan (ingest data into ClickHouse)

```powershell
python -m polytool scan --user "@example"
```

With optional enrichments:

```powershell
python -m polytool scan --user "@example" --ingest-activity --ingest-positions --compute-pnl
```

**Output**: Data lands in ClickHouse tables.

### Step 2: View results in Grafana

Open http://localhost:3000 (login: admin / admin).

Dashboards:
- **PolyTool - User Trades**: Trade history, activity, positions
- **PolyTool - Strategy Detectors**: Detector scores and labels
- **PolyTool - PnL**: Realized PnL, MTM PnL, exposure over time

### Step 3: Run the examine orchestrator

The `examine` command automates steps 3a-3c below into a single invocation:

```powershell
python -m polytool examine --user "@example" --days 30
```

Dry-run first to verify identity resolution and output paths:

```powershell
python -m polytool examine --user "@example" --days 30 --dry-run
```

For the golden case set:

```powershell
python -m polytool examine --all-golden
```

**Outputs** (per user):
- Dossier: `artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/`
  - `memo.md`, `dossier.json`, `manifest.json`
- Bundle + Prompt: `kb/users/<slug>/llm_bundles/<date>/<run_id>/`
  - `bundle.md`, `prompt.txt`, `examine_manifest.json`

### Step 3a: Export dossier (standalone)

If you need the dossier step alone:

```powershell
python -m polytool export-dossier --user "@example" --days 30
```

### Step 3b: Export ClickHouse datasets (optional, recommended for RAG)

```powershell
python -m polytool export-clickhouse --user "@example"
```

**Output**: `kb/users/<slug>/exports/<date>/`

### Step 3c: Build LLM evidence bundle (standalone)

```powershell
python -m polytool llm-bundle --user "@example"
```

**Output**: `kb/users/<slug>/llm_bundles/<date>/<run_id>/bundle.md`

### Step 4: Paste into LLM

1. Open `prompt.txt` and copy it into your LLM UI.
2. Open `bundle.md` and paste it after the prompt.
3. The LLM should produce `hypothesis.md` and `hypothesis.json`.

### Step 5: Save the LLM report

```powershell
python -m polytool llm-save --user "@example" --model "local-llm" --report-path "path/to/hypothesis.md" --prompt-path "path/to/prompt.txt"
```

**Output**: `kb/users/<slug>/llm_reports/<date>/<model>_<run_id>/`

An LLM_note summary is also written to `kb/users/<slug>/notes/LLM_notes/`.

### Step 6: Build / rebuild the RAG index

```powershell
python -m polytool rag-index --roots "kb,artifacts" --rebuild
```

### Step 7: Query the RAG index

```powershell
python -m polytool rag-query --question "Summarize recent strategy shifts" --hybrid --rerank --k 8
```

Scoped to a single user:

```powershell
python -m polytool rag-query --user "@example" --question "Most recent evidence" --hybrid --rerank --k 8
```

### Step 8: Evaluate retrieval quality (optional)

```powershell
python -m polytool rag-eval --suite docs/eval/sample_queries.jsonl
```

Reports go to `kb/rag/eval/reports/<timestamp>/`.

## Where Files Go (Path Templates)

All private outputs use these canonical path templates. Replace `<slug>` with
the user slug (e.g., `drpufferfish`), `<wallet>` with the proxy wallet address,
`<date>` with `YYYY-MM-DD`, and `<run_id>` with the 8-char unique ID.

```
artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/
  ├── memo.md              # Human-readable research memo
  ├── dossier.json         # Structured evidence (trades, positions, outcomes)
  └── manifest.json        # Export metadata (timestamp, stats, paths)

kb/users/<slug>/llm_bundles/<date>/<run_id>/
  ├── bundle.md            # Evidence bundle for LLM paste
  ├── prompt.txt           # Standardized prompt template
  ├── examine_manifest.json # Examination run metadata
  └── bundle_manifest.json # Bundle assembly metadata

kb/users/<slug>/llm_reports/<date>/<model>_<run_id>/
  ├── report.md            # Full LLM report (or hypothesis.md)
  ├── hypothesis.md        # Structured hypothesis report
  ├── hypothesis.json      # Machine-readable hypotheses (schema v1)
  └── inputs_manifest.json # What inputs were used

kb/users/<slug>/notes/LLM_notes/
  └── <model>_<run_id>.md  # Auto-generated summary note

kb/users/<slug>/exports/<date>/
  └── *.csv / *.json       # ClickHouse export datasets

kb/users/<slug>/profile.json  # Wallet-to-slug mapping (auto-created)

kb/sources/
  ├── <safe_filename>.md        # Cached web source content
  └── <safe_filename>.meta.json # Source metadata (URL, hash, TTL)

kb/rag/
  ├── index/               # Chroma vector index
  ├── lexical/lexical.sqlite3  # FTS5 lexical index
  ├── models/              # Cached embedding + reranker models
  └── eval/reports/<timestamp>/ # rag-eval outputs
```

All `kb/` and `artifacts/` paths are **private and gitignored**.

---

## Troubleshooting

### Common path issues

- **Wrong output folder**: User identity routes on the handle. Always use
  `--user "@Name"` (with quotes) for consistent slug derivation. Wallet-only
  flows fall back to `wallet_<first8>` slugs.
- **PowerShell quoting**: Quote `@` values: `--user "@example"` or `--user '@example'`.

### Indexing problems

- **"no such module: fts5"**: Your SQLite build lacks FTS5. Reinstall Python/SQLite
  with FTS5 enabled, or skip `--hybrid` and use vector-only retrieval.
- **Stale index**: After adding dossiers, bundles, or LLM reports, always re-run
  `python -m polytool rag-index --roots "kb,artifacts" --rebuild`.
- **First-run model downloads**: The first vector/hybrid/rerank run downloads models
  into `kb/rag/models/`. Be patient or pre-download models for offline use.

### Missing notes or reports

- **llm-save did not create LLM_note**: Check that `--report-path` points to an
  existing file. The note is derived from the report content.
- **rag-query returns nothing**: Verify the index exists (`kb/rag/index/` should
  contain files). Rebuild if empty.

### ClickHouse / API issues

- **No data after scan**: Verify the API is running (`docker compose ps`). Check
  that `.env` has the correct `TARGET_USER` or pass `--user` explicitly.
- **Missing market names**: Run market metadata ingestion:
  `python -m polytool scan --ingest-markets` or call the API directly.

### MCP not relevant here

This runbook covers the manual workflow. MCP is a separate, optional integration
path. See `python -m polytool mcp --help` if needed.
