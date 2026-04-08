---
type: architecture
tags: [architecture, database, status/done]
created: 2026-04-08
---

# Database Rules

Source: audit Section 3 + CLAUDE.md database rules.

---

## The One-Sentence Rule

**ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads. They do not replace each other.**

Both are imported in the same Python files. Both serve distinct, non-overlapping roles. Never use ClickHouse for Parquet reads. Never use DuckDB for live streaming writes.

---

## ClickHouse Authentication Rule

All CLI entrypoints that touch ClickHouse MUST read credentials from the `CLICKHOUSE_PASSWORD` environment variable with fail-fast behavior:

```python
ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
if not ch_password:
    sys.exit(1)
```

- **Never** use a hardcoded fallback like `"polytool_admin"`
- **Never** silently default to empty string
- Admin user: `CLICKHOUSE_USER` from `.env` (default name `polytool_admin`)
- Grafana read-only user: `grafana_ro` / `grafana_readonly_local` (SELECT only)

Files using the **correct** fail-fast pattern: `fetch_price_2min.py`, `close_benchmark_v1.py`, `batch_reconstruct_silver.py`

Files using the **incorrect** silent fallback (CLAUDE.md violation): `examine.py`, `export_dossier.py`, `export_clickhouse.py`, `reconstruct_silver.py`

See [[Issue-CH-Auth-Violations]] for details.

---

## ClickHouse Connection

- Host: `localhost:8123`
- User: from `CLICKHOUSE_USER` environment variable
- Password: from `CLICKHOUSE_PASSWORD` environment variable (fail-fast required)

---

## All 23 ClickHouse Tables

Source: audit Section 3.1 — all tables identified from `infra/clickhouse/initdb/` SQL initialization files.

| Table | SQL File | Purpose |
|-------|----------|---------|
| `polymarket_trades` | `01_init.sql` | Raw trade events from polymarket-apis |
| `price_changes` | `01_init.sql` | L2 price change events (WS stream) |
| `orderbook_snapshots` | `01_init.sql` | L2 orderbook snapshots |
| `wallet_scans` | `02_wallet_scans.sql` | Wallet scan results and trust artifacts |
| `alpha_signals` | `03_alpha_signals.sql` | Distilled alpha signals per wallet |
| `market_resolutions` | `04_market_resolutions.sql` | Market resolution results (cached) |
| `pnl_snapshots` | `05_pnl_snapshots.sql` | PnL computation snapshots |
| `research_items` | `06_research_items.sql` | RIS research items (ingested content) |
| `research_evaluations` | `07_research_evaluations.sql` | LLM evaluation results for research items |
| `replay_runs` | `08_replay_runs.sql` | SimTrader replay run manifests |
| `sweep_results` | `09_sweep_results.sql` | SimTrader sweep scenario results |
| `benchmark_tapes` | `10_benchmark_tapes.sql` | Benchmark tape manifest entries |
| `gate_results` | `11_gate_results.sql` | Gate pass/fail results |
| `shadow_sessions` | `12_shadow_sessions.sql` | Shadow mode session records |
| `price_2min` | `13_price_2min.sql` | 2-minute price bars (Gold acquisition) |
| `market_scores` | `14_market_scores.sql` | Market selection scorer output |
| `crypto_pair_events` | `26_crypto_pair_events.sql` | Crypto pair trade events (live/paper) |
| `crypto_pair_sessions` | `26_crypto_pair_events.sql` | Crypto pair session records |
| `hypothesis_registry` | `15_hypothesis_registry.sql` (estimated) | Hypothesis registry (or SQLite-backed) |
| `clv_results` | found via grep | CLV computation results |
| `dossier_bundles` | found via grep | Wallet dossier bundle records |
| `tape_coverage` | found via grep | Tape coverage tracking |
| `arb_opportunities` | found via grep | Detected arbitrage opportunities |

---

## DuckDB Usage

DuckDB is used exclusively for historical Parquet reads. Zero-config — no server process. Reads Parquet files directly from disk without any ingestion step.

| File | Usage |
|------|-------|
| `packages/polymarket/duckdb_helper.py` | Core helper — connection management, Parquet queries |
| `packages/polymarket/backfill.py` | Reads historical Parquet archives |
| `packages/polymarket/silver_reconstructor.py` | Queries Silver Parquet data |
| `tools/cli/export_clickhouse.py` | DuckDB-backed export path |
| `tools/gates/corpus_audit.py` | Reads corpus Parquet files for audit |

DuckDB databases are ephemeral / in-memory or file-based; no persistent schema files under `infra/`.

---

## ChromaDB (RAG Vector Store)

- Default collection: `"polytool_rag"` (defined in `packages/polymarket/rag/defaults.py`)
- Persist directory: `kb/rag/chroma/` (inferred from defaults)
- Embedding model: SentenceTransformers (via `packages/polymarket/rag/embedder.py`)
- Used by: `packages/polymarket/rag/index.py` (build), `packages/polymarket/rag/query.py` (query)

---

## RIS KnowledgeStore (SQLite — separate from ChromaDB)

- File: `kb/rag/knowledge/knowledge.sqlite3`
- Code: `packages/polymarket/rag/knowledge_store.py` (555 lines)
- Purpose: stores external research items, claims, calibration data
- NOT ChromaDB — fully separate storage system

---

## Cross-References

- [[System-Overview]] — Layer roles and package structure
- [[Issue-CH-Auth-Violations]] — ClickHouse auth violation details
- [[Data-Stack]] — Five free data layers including DuckDB/ClickHouse role
- [[RAG]] — ChromaDB and KnowledgeStore usage
