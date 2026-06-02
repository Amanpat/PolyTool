---
title: "Historical Import"
type: concept
status: superseded
superseded_by: repo-docs/specs/spec-0018-bulk-historical-import-foundation-v0.md
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: stale
tags: [module, status/done, historical-import]
---

# Historical Import

Source: audit Section 1.1 — `packages/polymarket/historical_import/` (4 files).

Handles bulk historical trade import from polymarket-apis and pmxt archive data.

---

## Module Inventory

| Module | Purpose | Status |
|--------|---------|--------|
| `clickhouse_writer.py` | Write historical trades to ClickHouse | WORKING |
| `downloader.py` | Download historical data from polymarket-apis | WORKING |
| `parser.py` | Parse raw historical trade records | WORKING |
| `pipeline.py` | Full import pipeline orchestration | WORKING |

---

## Data Sources

- **pmxt archive** — compressed historical trade data
- **polymarket-apis** — REST API for historical market and trade records
- **Jon-Becker dataset** — 72.1M trades, Bronze tier, accessed via DuckDB Parquet

---

## Cross-References

- [[legacy/PolyTool/02-Modules/Core-Library]] — `historical_import/` is a subpackage under `packages/polymarket/`
- [[legacy/PolyTool/01-Architecture/Database-Rules]] — imports write to ClickHouse; historical queries use DuckDB
- [[legacy/PolyTool/01-Architecture/Tape-Tiers]] — Bronze tapes sourced from Jon-Becker dataset

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
