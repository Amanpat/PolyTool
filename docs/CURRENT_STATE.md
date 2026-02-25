# Current State / What We Built

This repo is a local-first toolchain for Polymarket analysis: data ingestion,
ClickHouse analytics, Grafana dashboards, private evidence exports, and a local
RAG workflow that never calls external LLM APIs.

## What exists today

- A local CLI (`polytool`) that drives ingestion and exports.
- A data pipeline that writes to ClickHouse and visualizes in Grafana.
- Private dossier exports with resolution outcomes and PnL enrichment.
- Local RAG indexing + retrieval over private content (`kb/` + `artifacts/`).
- Evidence bundle generation with standardized prompt templates.
- LLM report retention with automatic LLM_notes for RAG surfacing.
- MCP server integration for Claude Desktop.

## SimTrader (replay-first + shadow mode)

SimTrader is a realism-first simulated trader for Polymarket CLOB markets. It records the Market Channel WS into deterministic tapes and supports both offline replay and live simulated "shadow" runs.

What exists today:
- One-shot runner: `simtrader quickrun` (auto market pick/validate → record → run or sweep)
- Scenario sweeps (`--sweep quick` / `quick_small`) and batch leaderboard (`simtrader batch`)
- Shadow mode: `simtrader shadow` (live WS → strategy → BrokerSim fills; optional tape recording)
- Activeness probe: `--activeness-probe-seconds` / `--require-active` on `quickrun` measures live WS update rate before committing to a market
- Artifact management: `simtrader clean` (safe dry-run deletion of artifact folders) and `simtrader diff` (side-by-side comparison of two run directories, writes `diff_summary.json`)
- Local UI: `simtrader report` generates self-contained `report.html` for run/sweep/batch/shadow artifacts; `simtrader browse --open` opens newest results
- Explainability: `strategy_debug.rejection_counts`, sweep/batch aggregates, and audited JSONL artifacts

Start here:
- `docs/README_SIMTRADER.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`

---

## Pipeline (text)

```
scan -> canonical workflow entrypoint:
  -> ClickHouse + Grafana refresh
  -> trust artifacts in artifacts/dossiers/.../coverage_reconciliation_report.* + run_manifest.json

Individual steps:
  export-dossier -> artifacts/dossiers/.../memo.md + dossier.json + manifest.json
  llm-bundle -> kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md + prompt.txt
  export-clickhouse -> kb/users/<slug>/exports/<YYYY-MM-DD>/
  rag-index -> kb/rag/*
  rag-query -> evidence snippets
  llm-save -> kb/users/<slug>/llm_reports/ + kb/users/<slug>/notes/LLM_notes/
  cache-source -> kb/sources/
  examine -> legacy orchestrator wrapper (non-canonical)
  mcp -> Claude Desktop integration
```

## CLI commands (plain language)

- `scan`: run a one-shot ingestion via the local API to pull user data into
  ClickHouse (with optional activity, positions, and PnL flags), and emit trust
  artifacts (`coverage_reconciliation_report.*`, `run_manifest.json`) per run.
- `examine`: legacy orchestrator (scan -> dossier -> bundle -> prompt) kept for
  compatibility and golden-case operations.
- `export-dossier`: build a private, point-in-time evidence package for one user
  (memo + JSON + manifest) under `artifacts/`. Now includes resolution outcomes
  and position lifecycle data.
- `export-clickhouse`: export recent ClickHouse datasets for one user into the
  private KB under `kb/users/<slug>/exports/<YYYY-MM-DD>/`.
- `rag-index`: build or rebuild the local RAG index over `kb/` + `artifacts/`.
  Outputs live in `kb/rag/`.
- `rag-query`: retrieve relevant evidence snippets from the local index with
  optional scoping by user, doc type, or date.
- `rag-eval`: run retrieval quality checks and write reports to
  `kb/rag/eval/reports/<timestamp>/`.
- `llm-bundle`: assemble a short evidence bundle from dossier data and curated
  RAG excerpts into `bundle.md` for offline reporting.
- `llm-save`: store LLM report runs (report + manifest) into `llm_reports/` AND
  write a summary note to `notes/LLM_notes/` for RAG surfacing.
- `cache-source`: cache trusted web sources for RAG indexing (allowlist enforced).
- `mcp`: start the MCP server for Claude Desktop integration.

## User identity routing

User identity is resolved canonically via `polytool/user_context.py`:

- **Handle-first (strict)**: `--user "@DrPufferfish"` always routes to `drpufferfish/` folders
- **Strict mapping**: in `--user` mode, wallet must resolve; no fallback to `unknown/` or wallet-prefix slugs
- **Wallet-to-slug mapping**: When wallet is known with a handle, the mapping is
  persisted to `kb/users/<slug>/profile.json`
- **Wallet mode**: wallet-first flows can use `--wallet`; when no mapping exists, fallback is `wallet_<first8>`
- **Consistent paths**: All CLI commands and MCP tools use the same resolver

This ensures outputs like dossiers, bundles, and reports always land in the same
user folder for handle-first workflows.

## Resolution outcomes

Each position now includes a resolution_outcome field:
- `WIN` / `LOSS`: Held to resolution
- `PROFIT_EXIT` / `LOSS_EXIT`: Exited before resolution
- `PENDING`: Market not yet resolved
- `UNKNOWN_RESOLUTION`: Resolution data unavailable

## Common pitfalls

- **User scoping**: quote `--user "@name"` (PowerShell) and keep user vs wallet
  inputs consistent across commands.
- **Private-only defaults**: `rag-query` searches private content by default;
  public docs are excluded unless `--public-only` is set.
- **Model downloads/caching**: the first vector or rerank run downloads models
  into `kb/rag/models/`.
- **FTS5 availability**: lexical or hybrid search requires SQLite with FTS5; if
  missing, use vector-only retrieval.
- **Index freshness**: after adding dossiers or LLM reports, rerun `rag-index`
  so the new files are searchable.
- **CLI rename**: Use `polytool` (not `polyttool`). The old name still works
  but prints a deprecation warning.

## Developer Notes

- **Canonical commands**: Always use `python -m polytool <command>` in docs,
  scripts, and runbooks. The `polytool` console script also works.
- **Manual workflow is default**: The manual examination workflow
  (scan -> export/bundle -> paste -> llm-save) is the primary path. See
  `docs/RUNBOOK_MANUAL_EXAMINE.md`.
- **MCP is optional**: The MCP server (`python -m polytool mcp`) provides
  Claude Desktop integration but is not required for the core workflow.
  It is tracked separately in the roadmap.
- **polyttool shim removal**: The `polyttool` backward-compatibility shim
  will be removed after version 0.2.0. See
  [ADR-0001](adr/ADR-0001-cli-and-module-rename.md).
