---
type: module
status: done
tags: [module, status/done, historical-import]
lines: ~1200
test-coverage: partial
created: 2026-04-08
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

- [[Core-Library]] — `historical_import/` is a subpackage under `packages/polymarket/`
- [[Database-Rules]] — imports write to ClickHouse; historical queries use DuckDB
- [[Tape-Tiers]] — Bronze tapes sourced from Jon-Becker dataset

