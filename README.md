# PolyTool

PolyTool is a local-first toolbox for analyzing Polymarket users. You run scans against a target handle, and PolyTool writes trust artifacts and reports to local disk for repeatable, offline review. The code and docs are public; private analysis outputs stay under gitignored `artifacts/` and `kb/`.

## What PolyTool Is

PolyTool combines a local API, ClickHouse, and CLI commands to turn a user handle into structured research artifacts. It can ingest positions/trades, compute PnL and CLV, enrich resolution data, generate hypothesis candidates, and aggregate cross-user hypotheses. The primary entrypoint is:

```bash
python -m polytool <command> [options]
```

## Quickstart

### 1. Prerequisites

- Python 3.10+
- Docker Desktop (or Docker Engine + Compose)
- `git`

### 2. Install

```bash
git clone <your-repo-url>
cd PolyTool
python -m venv .venv
. .venv/Scripts/Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

### 3. Start local services

```bash
docker compose up -d
docker compose ps
```

Expected local endpoints:

- API docs: `http://localhost:8000/docs`
- ClickHouse HTTP: `http://localhost:8123`
- Grafana: `http://localhost:3000`

### 4. Configure API base URL (optional but recommended on Windows)

Set `.env` in repo root:

```env
API_BASE_URL=http://127.0.0.1:8000
```

You can also pass `--api-base-url` directly to commands.

### 5. Target a user

1. Find the Polymarket handle (for example `@DrPufferfish`).
2. Run a scan with no stage flags:

```bash
python -m polytool scan --user "@DrPufferfish"
```

3. Open the latest run root:

```text
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/
```

4. Open these first:
- `coverage_reconciliation_report.md` (or `.json`)
- `segment_analysis.json`
- `hypothesis_candidates.json`
- `audit_coverage_report.md`

## One-Command Full Scan (Default)

If you pass no stage flags, `scan` runs the full research pipeline by default.

```bash
python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000"
```

Default full scan emits a run manifest plus trust artifacts, including coverage reports, segment analysis, hypothesis candidates, CLV preflight, CLV warm-cache summary, and audit coverage.

## Common Recipes

### Fast/lite scan

```bash
python -m polytool scan --user "@DrPufferfish" --lite
```

`--lite` runs a minimal pipeline: positions + pnl + resolution enrichment + CLV compute.

### Debug export diagnostics

```bash
python -m polytool scan --user "@DrPufferfish" --full --debug-export
```

`--debug-export` prints export/hydration diagnostics to help debug sparse coverage.

### Aggregate-only batch from existing run roots

```bash
python -m polytool batch-run \
  --aggregate-only \
  --run-roots artifacts/research/batch_runs/2026-02-20/<batch_id>/
```

## Command Reference

### `scan`

```bash
python -m polytool scan --user "@handle" [options]
```

Defaulting rules:
- No stage flags: full pipeline auto-enabled.
- Any stage flag present: only explicitly selected stages are used (no auto-enable).
- `--full`: force full pipeline even if stage flags are present.
- `--lite`: force minimal fast pipeline.

Convenience flags:
- `--full`
- `--lite`

Stage flags:
- `--ingest-markets`: ingest active market metadata.
- `--ingest-activity`: ingest user activity.
- `--ingest-positions`: ingest positions snapshot.
- `--compute-pnl`: compute PnL.
- `--compute-opportunities`: compute opportunity candidates.
- `--snapshot-books`: snapshot orderbook metrics.
- `--enrich-resolutions`: enrich resolution data.
- `--warm-clv-cache`: warm CLV snapshot cache.
- `--compute-clv`: compute per-position CLV fields.

Other common flags:
- `--debug-export`
- `--audit-sample N`
- `--audit-seed INT`
- `--resolution-max-candidates N`
- `--resolution-batch-size N`
- `--resolution-max-concurrency N`
- `--clv-offline`
- `--clv-window-minutes MINUTES`
- `--config polytool.yaml`
- `--api-base-url URL`

### `batch-run`

```bash
python -m polytool batch-run --users users.txt [options]
```

Purpose: run scans for multiple users and build deterministic leaderboard artifacts.

Common flags:
- `--users PATH`
- `--workers N`
- `--continue-on-error` / `--no-continue-on-error`
- `--aggregate-only --run-roots PATH`
- Scan pass-through flags: `--api-base-url`, `--full`, `--lite`, `--ingest-positions`, `--compute-pnl`, `--enrich-resolutions`, `--debug-export`, `--warm-clv-cache`, `--compute-clv`

### `audit-coverage`

```bash
python -m polytool audit-coverage --user "@handle" [options]
```

Offline audit from scan artifacts. Key flags: `--sample N`, `--seed SEED`, `--run-id`, `--format {md,json}`.

### `export-dossier`

```bash
python -m polytool export-dossier --user "@handle" [options]
```

Export an LLM research packet dossier. Key flags: `--days`, `--max-trades`, `--artifacts-dir`.

### `export-clickhouse`

```bash
python -m polytool export-clickhouse --user "@handle" [options]
```

Export user datasets from ClickHouse. Key flags: `--out`, `--trades-limit`, `--orderbook-limit`, `--arb-limit`, `--no-arb`.

### `examine`

```bash
python -m polytool examine --user "@handle" [options]
```

Orchestrates examination workflow. Key flags: `--days`, `--max-trades`, `--skip-scan`, `--no-enrich-resolutions`, resolution knobs, `--dry-run`.

### `llm-bundle`

```bash
python -m polytool llm-bundle --user "@handle" [options]
python -m polytool llm-bundle --user "@handle" --run-root artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id> [options]
```

Build evidence bundle from the latest run root under `artifacts/dossiers/users/<normalized_user>/` plus optional RAG excerpts.
Manifest lookup prefers `run_manifest.json` and falls back to legacy `manifest.json`.
Use `--run-root` to bypass automatic latest-run lookup.
Key flags: `--run-root`, `--dossier-path`, `--questions-file`, `--no-devlog`.

### `llm-save`

```bash
python -m polytool llm-save --user "@handle" --model "<model>" [options]
```

Save LLM output to private KB. Key flags: `--run-id`, `--date`, `--report-path`, `--prompt-path`, `--input`, `--rag-query-path`, `--tags`, `--no-devlog`.

### `rag-index`

```bash
python -m polytool rag-index [options]
```

Build/rebuild local RAG index. Key flags: `--roots`, `--rebuild`, `--reconcile`, `--chunk-size`, `--overlap`, `--model`, `--device`.

### `rag-query`

```bash
python -m polytool rag-query --question "..." [options]
```

Query local RAG index. Key flags: `--user`, `--doc-type`, `--private-only/--public-only`, `--hybrid`, `--lexical-only`, `--rerank`.

### `rag-eval`

```bash
python -m polytool rag-eval --suite docs/eval/sample_queries.jsonl [options]
```

Offline retrieval evaluation harness.

### `cache-source`

```bash
python -m polytool cache-source --url "https://..." [options]
```

Fetch/cache trusted web sources for indexing. Key flags: `--ttl-days`, `--force`, `--output-dir`, `--config`, `--skip-robots`.

### `agent-run`

```bash
python -m polytool agent-run --agent codex --packet P5 --slug run-name [options]
```

Write one-file-per-run agent logs to `kb/devlog/`.

### `mcp`

```bash
python -m polytool mcp [--log-level INFO]
```

Start MCP server for local integration.

### Deprecated alias

- `python -m polytool opus-bundle ...` is deprecated and routes to `llm-bundle`.

## Outputs And Trust Artifacts

Run root:

```text
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/
```

| Artifact | Meaning |
|---|---|
| `run_manifest.json` | Provenance: command, argv, config snapshot, output paths |
| `dossier.json` | Exported user dossier payload |
| `coverage_reconciliation_report.json` | Machine-readable trust/coverage report |
| `coverage_reconciliation_report.md` | Human-readable trust/coverage summary |
| `segment_analysis.json` | Segment metrics and breakdowns |
| `hypothesis_candidates.json` | Ranked hypothesis candidate segments |
| `audit_coverage_report.md` | Offline trust sanity report |
| `clv_preflight.json` | CLV preflight checks and missingness reasons |
| `clv_warm_cache_summary.json` | CLV cache warm summary |
| `notional_weight_debug.json` | Notional-weight normalization diagnostics |
| `resolution_parity_debug.json` | Resolution consistency diagnostics |

## Troubleshooting

### `localhost` vs `127.0.0.1` on Windows

If `localhost` resolves to IPv6 and connections fail, use:

```bash
python -m polytool scan --user "@handle" --api-base-url "http://127.0.0.1:8000"
```

### Missing outputs or sparse coverage

1. Re-run with `--debug-export`.
2. Confirm handle -> wallet resolution in `http://localhost:8000/docs` (`/api/resolve`).
3. Check latest run root has `dossier.json` and `run_manifest.json`.
4. Re-run with `--full` to force all major stages.

### CLV gaps

- `clv_preflight.json` explains why CLV is missing.
- Use `--warm-clv-cache` to prefetch snapshot data.
- If network access is restricted, use `--clv-offline` and expect lower coverage.

---

For CLI-level details, run `python -m polytool <command> --help`.
