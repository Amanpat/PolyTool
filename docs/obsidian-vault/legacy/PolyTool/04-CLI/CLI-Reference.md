---
type: reference
status: done
tags: [reference, cli, status/done]
created: 2026-04-08
---

# CLI Reference

Source: audit Section 2 — `polytool/__main__.py` command routing (~60 commands).

Entry point: `python -m polytool <command>`. Commands are lazily routed via `_COMMAND_HANDLER_NAMES` dict using `importlib.import_module`.

---

## Core Research / Dossier Workflow

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `scan` | `tools.cli.scan` | Wallet behavior scan, emits trust artifacts | IMPLEMENTED |
| `wallet-scan` | `tools.cli.wallet_scan` | Deep wallet scan with full dossier | IMPLEMENTED |
| `alpha-distill` | `tools.cli.alpha_distill` | Distill alpha signals from wallet scans | IMPLEMENTED |
| `llm-bundle` | `tools.cli.llm_bundle` | Build LLM research packet bundles | IMPLEMENTED |
| `opus-bundle` | `tools.cli.opus_bundle` | Deprecated alias for `llm-bundle` | STUB (22 lines) |
| `candidate-scan` | `tools.cli.candidate_scan` | Scan for candidate wallets | IMPLEMENTED |
| `export-dossier` | `tools.cli.export_dossier` | Export wallet dossier to file | IMPLEMENTED |
| `export-clickhouse` | `tools.cli.export_clickhouse` | Export ClickHouse data to file | IMPLEMENTED |

---

## RAG Commands

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `rag-index` | `tools.cli.rag_index` | Build or rebuild RAG vector index | IMPLEMENTED |
| `rag-query` | `tools.cli.rag_query` | Hybrid RAG query (vector + lexical) | IMPLEMENTED |
| `rag-refresh` | alias for `rag-index --rebuild` | Refresh RAG index | IMPLEMENTED (alias) |

---

## Research Intelligence System (RIS)

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `research-precheck` | `tools.cli.research_precheck` | Pre-build STOP/CAUTION/GO verdict | IMPLEMENTED |
| `research-ingest` | `tools.cli.research_ingest` | Ingest text/file research into RIS | IMPLEMENTED |
| `research-acquire` | `tools.cli.research_acquire` | Acquire URL-based research | IMPLEMENTED |
| `research-report` | `tools.cli.research_report` | Generate research synthesis report | IMPLEMENTED |
| `research-health` | `tools.cli.research_health` | RIS pipeline health snapshot | IMPLEMENTED |
| `research-stats` | `tools.cli.research_stats` | RIS pipeline metrics | IMPLEMENTED |
| `research-scheduler` | `tools.cli.research_scheduler` | APScheduler management | IMPLEMENTED |
| `research-bridge` | `tools.cli.research_bridge` | Link research findings to strategies | IMPLEMENTED |

---

## Hypothesis / Experiment Registry

Hypothesis subcommands use `_FULL_ARGV_COMMANDS` — full `sys.argv` is passed through.

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `hypothesis register` | `tools.cli.hypothesis` | Register new hypothesis | IMPLEMENTED |
| `hypothesis status` | `tools.cli.hypothesis` | Show hypothesis status | IMPLEMENTED |
| `hypothesis experiment-init` | `tools.cli.hypothesis` | Initialize experiment | IMPLEMENTED |
| `hypothesis experiment-run` | `tools.cli.hypothesis` | Run experiment | IMPLEMENTED |
| `hypothesis validate` | `tools.cli.hypothesis` | Validate hypothesis results | IMPLEMENTED |
| `hypothesis diff` | `tools.cli.hypothesis` | Diff hypothesis versions | IMPLEMENTED |
| `hypothesis summary` | `tools.cli.hypothesis` | Hypothesis summary | IMPLEMENTED |

---

## Tape / Benchmark Workflow

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `fetch-price-2min` | `tools.cli.fetch_price_2min` | Fetch and store 2-min price bars | IMPLEMENTED |
| `batch-reconstruct-silver` | `tools.cli.batch_reconstruct_silver` | Batch reconstruct Silver tapes | IMPLEMENTED |
| `reconstruct-silver` | `tools.cli.reconstruct_silver` | Reconstruct single Silver tape | IMPLEMENTED |
| `benchmark-manifest` | `tools.cli.benchmark_manifest` | Manage benchmark tape manifest | IMPLEMENTED |
| `close-benchmark-v1` | `tools.cli.close_benchmark_v1` | Close benchmark v1 (finalized 2026-03-21) | IMPLEMENTED |
| `new-market-capture` | `tools.cli.new_market_capture` | Plan new-market Gold tape capture | IMPLEMENTED |
| `capture-new-market-tapes` | `tools.cli.capture_new_market_tapes` | Execute new-market tape capture | IMPLEMENTED |

---

## SimTrader Commands

All SimTrader subcommands are in `tools/cli/simtrader.py` (5419 lines — largest CLI file).

| Subcommand | Description | Status |
|------------|-------------|--------|
| `simtrader quickrun` | Quick replay run with auto market-pick | IMPLEMENTED |
| `simtrader run` | Full replay run with explicit config | IMPLEMENTED |
| `simtrader shadow` | Live shadow mode (WS stream, simulated fills) | IMPLEMENTED |
| `simtrader sweep` | Parameter sweep across tape set | IMPLEMENTED |
| `simtrader batch` | Batch replay runner | IMPLEMENTED |
| `simtrader studio` | Browser-based replay UI (WebSocket server) | IMPLEMENTED |
| `simtrader tape-record` | Live tape recorder | IMPLEMENTED |
| `simtrader probe` | Market activeness probe | IMPLEMENTED |

---

## Market Selection

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `market-scan` | `tools.cli.market_scan` | Run 7-factor market scorer | IMPLEMENTED |
| `crypto-pair-watch` | `tools.cli.crypto_pair_watch` | One-shot active crypto pair check | IMPLEMENTED |

---

## Optional / Special Load

Loaded via `try/except ImportError` — not in main command dict.

| Command | Handler Module | Description | Status |
|---------|----------------|-------------|--------|
| `mcp` | `tools.cli.mcp_server` | Start MCP server (FastMCP, optional dep) | IMPLEMENTED (optional) |
| `examine` | `tools.cli.examine` | Legacy orchestrator (820 lines) | DEAD |
| `cache-source` | `tools.cli.cache_source` | Legacy cache source (356 lines) | DEAD |

---

## Not Yet Implemented (per CLAUDE.md)

| Command | Planned Phase | Notes |
|---------|---------------|-------|
| `autoresearch import-results` | Phase 4 | Not in repo |
| `strategy-codify` | Phase 4 | Not in repo |
| FastAPI `/api/*` endpoints | Phase 3 | `services/api/main.py` exists but no CLI routing |

---

## Cross-References

- [[System-Overview]] — Layer roles
- [[SimTrader]] — SimTrader CLI detail
- [[RIS]] — Research Intelligence System CLI commands
- [[RAG]] — RAG CLI commands
- [[Gates]] — Gate scripts (not CLI-routed, run directly)

