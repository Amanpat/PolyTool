---
phase: quick-260408-i3a
plan: "01"
subsystem: docs
tags: [audit, codebase, inventory, ground-truth]
dependency_graph:
  requires: []
  provides: [docs/CODEBASE_AUDIT.md]
  affects: []
tech_stack:
  added: []
  patterns: [read-only source inspection, grep-based discovery]
key_files:
  created:
    - docs/CODEBASE_AUDIT.md
  modified: []
decisions:
  - "Status classification: WORKING = >20 lines real logic + test refs; STUBBED = skeleton/placeholder; DEAD = not imported, no tests"
  - "No Python execution — CLI commands derived from source reading of __main__.py and tools/cli/*.py"
  - "ClickHouse tables enumerated from infra/clickhouse/initdb/ SQL files rather than live DB query"
  - "Env var values explicitly excluded per T-audit-01 threat disposition"
metrics:
  duration_minutes: 90
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
  completed_date: "2026-04-08"
---

# Phase quick-260408-i3a Plan 01: Codebase Ground-Truth Audit Summary

## One-Liner

835-line read-only inventory of all PolyTool modules, CLI commands, databases, integrations, config/env vars, test coverage, and duplication — derived entirely from source code inspection.

## What Was Built

Created `docs/CODEBASE_AUDIT.md` with 7 sections covering the full PolyTool codebase state as of 2026-04-08. All data derived from source code reading — no Python execution, no external connections, no code modifications.

### Section Coverage

1. **Module Inventory** — 35+ `packages/polymarket/` modules, 20 `crypto_pairs/` modules, 8 SimTrader subpackages (tape/broker/replay/shadow/execution/portfolio/strategies/studio), all 7 `packages/research/` subpackages, 56 `tools/cli/` files, `services/api/main.py`
2. **CLI Commands** — ~60 commands from `polytool/__main__.py` source analysis; all SimTrader subcommands from 5419-line `simtrader.py`; deprecated/dead commands flagged
3. **Database State** — 23 ClickHouse tables from `infra/clickhouse/initdb/` SQL files; 5 DuckDB usage files; ChromaDB collection `"polytool_rag"` + separate SQLite RIS KnowledgeStore (`kb/rag/knowledge/knowledge.sqlite3`)
4. **External Integrations** — 6 WebSocket clients, 7 REST API clients, GraphQL (The Graph/Gamma), on-chain JSON-RPC (Polygon CTF), py_clob_client, praw, yt_dlp, FastMCP, ChromaDB, n8n pilot
5. **Config and Environment** — 24 env var names enumerated (no values), 7 config files listed, 9 pyproject.toml optional dep groups documented
6. **Test Coverage** — 130+ test files mapped to modules, 883+ total tests; 8 significant coverage gaps identified including `services/api/main.py` (3054 lines, zero tests) and `execution/adverse_selection.py` (589 lines, zero tests)
7. **Known Duplication** — Dual fee modules (float vs Decimal), ClickHouse auth inconsistency (fail-fast vs silent fallback), 3 HTTP client approaches, 4 independent WebSocket reconnect implementations, 2 hypothesis registry implementations

## Key Findings

### Critical Issues Found

1. **ClickHouse auth CLAUDE.md violation** — `examine.py`, `export_dossier.py`, `export_clickhouse.py`, `reconstruct_silver.py` silently fall back to `"polytool_admin"` instead of fail-fast. This directly violates the CLAUDE.md ClickHouse authentication rule.

2. **pyproject.toml packaging gap** — `packages/research/evaluation`, `ingestion`, `integration`, `monitoring`, and `synthesis` are NOT in the `packages` list. Five subpackages work via `sys.path` insertion but would fail on clean install.

3. **services/api/main.py island** — 3054-line FastAPI service with zero test coverage. Per CLAUDE.md, this is a Phase 3 deliverable pre-built without tests.

4. **Dual fee implementations** — `packages/polymarket/fees.py` (float) and `packages/polymarket/simtrader/portfolio/fees.py` (Decimal) both implement the same quadratic fee formula. Risk of drift on fee model changes.

### Notable Architecture Facts

- `packages/polymarket/rag/knowledge_store.py` (555 lines) is SQLite-based, completely separate from ChromaDB — two distinct storage systems in the RAG area
- `packages/polymarket/opportunities.py` is a 22-line stub dataclass — essentially dead code
- `tools/cli/examine.py` (820 lines) and `tools/cli/cache_source.py` (356 lines) are loaded via `try/except ImportError` but not in the command dict — effectively dead
- Live crypto pair deployment is BLOCKED — no active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29
- `benchmark_v1` files in `config/` are finalized and locked (DO NOT MODIFY)

## Deviations from Plan

None — plan executed exactly as written. All 7 sections populated from source code inspection only. No code was modified. No external connections were made. No Python was executed.

## Commits

| Task | Description | Hash | Files |
|------|-------------|------|-------|
| Task 1 | Create codebase ground-truth audit | b323e3f | docs/CODEBASE_AUDIT.md |

## Known Stubs

- `packages/polymarket/opportunities.py` — 22-line stub `Opportunity` dataclass. No consumers. No tests. Flows nowhere.

## Threat Flags

None — read-only audit. No new network endpoints, auth paths, file access patterns, or schema changes introduced. Env var values were explicitly excluded per T-audit-01.

## Self-Check: PASSED

- docs/CODEBASE_AUDIT.md: FOUND (835 lines, ≥ 300 required)
- Commit b323e3f: FOUND
- All 7 H2 sections: FOUND (verified via grep at lines 10, 390, 492, 560, 618, 685, 744)
- No other repo files modified: CONFIRMED (git diff shows only docs/CODEBASE_AUDIT.md)
- No secret values in audit doc: CONFIRMED (env var names only, no values)
