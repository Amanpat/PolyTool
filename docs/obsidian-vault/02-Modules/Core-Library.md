---
type: module
status: done
tags: [module, status/done, core]
lines: 10000+
test-coverage: high
created: 2026-04-08
---

# Core Library

Source: audit Section 1.1 "Top-Level Modules" table — `packages/polymarket/`.

30+ top-level modules. All business logic lives here. CLI commands wrap the core for developer speed — never the reverse.

---

## Top-Level Module Inventory

| Module | Lines | Purpose | Status | Key Exports |
|--------|-------|---------|--------|-------------|
| `arb.py` | 601 | Complete-set arbitrage detection | WORKING | `ArbOpportunity`, `find_arb_opportunities` |
| `backfill.py` | 580 | Historical trade backfill from polymarket-apis | WORKING | `BackfillConfig`, `TradeBackfiller` |
| `benchmark_gap_fill_planner.py` | 693 | Plans gap-fill operations for Silver tapes | WORKING | `GapFillPlan`, `GapFillPlanner` |
| `benchmark_manifest_contract.py` | 373 | Canonical data contract for benchmark tape manifests | WORKING | `TapeManifest`, `TapeEntry` |
| `clob.py` | 263 | CLOB API client wrapper | WORKING | `ClobClient`, `get_orderbook` |
| `clv.py` | 1698 | Closing Line Value computation — largest module | WORKING | `CLVResult`, `compute_clv` |
| `data_api.py` | 641 | Polymarket data API client | WORKING | `DataApiClient`, `get_markets` |
| `detectors.py` | 728 | Wallet behavior detectors (holding, DCA, arb-ish) | WORKING | `HoldingDetector`, `DCADetector` |
| `duckdb_helper.py` | 258 | DuckDB connection management and Parquet queries | WORKING | `DuckDBHelper`, `query_parquet` |
| `features.py` | 228 | Feature extraction from wallet/market data | WORKING | `FeatureExtractor` |
| `fees.py` | 113 | Fee calculation (float-based quadratic curve) | WORKING | `calculate_fee`, `FeeModel` |
| `gamma.py` | 1089 | Gamma API client — market metadata, resolution | WORKING | `GammaClient`, `get_market` |
| `http_client.py` | 245 | Shared HTTP session with retry/backoff | WORKING | `PolyHttpClient` |
| `llm_research_packets.py` | 1795 | LLM prompt bundling and research packet generation | WORKING | `ResearchPacket`, `build_llm_bundle` |
| `new_market_capture_planner.py` | 371 | Planner for new-market Gold tape capture | WORKING | `NewMarketCapturePlan` |
| `normalization.py` | 33 | Data normalization (price, volume) | WORKING | `normalize_price` |
| `on_chain_ctf.py` | ~180 | On-chain CTF contract resolution (raw JSON-RPC) | WORKING | `OnChainCTFProvider` |
| `opportunities.py` | 22 | **STUBBED** — opportunity dataclass only | STUBBED | `Opportunity` (unused) |
| `orderbook_snapshots.py` | 532 | L2 orderbook snapshot management | WORKING | `OrderbookSnapshot`, `write_snapshot` |
| `pnl.py` | 528 | PnL computation with fee model | WORKING | `PnLResult`, `compute_pnl` |
| `price_2min_fetcher.py` | 322 | 2-minute price bar fetcher | WORKING | `Price2MinFetcher` |
| `resolution.py` | 446 | 4-stage resolution cascade | WORKING | `CachedResolutionProvider` |
| `silver_reconstructor.py` | 877 | Silver tape reconstruction | WORKING | `SilverReconstructor` |
| `slippage.py` | 247 | Slippage modeling for fill simulation | WORKING | `SlippageModel` |
| `subgraph.py` | ~150 | GraphQL client for The Graph | WORKING | `SubgraphProvider` |
| `token_resolution.py` | 57 | Token-to-market slug resolution | WORKING | `TokenResolver` |

### Highlighted by Size

- `llm_research_packets.py` (1795 lines) — largest module, LLM prompt engineering
- `clv.py` (1698 lines) — CLV computation engine
- `gamma.py` (1089 lines) — Gamma API client with full event decomposition

### Special Notes

- `opportunities.py` (22 lines) is a **STUB** — the `Opportunity` dataclass is defined but unused. Overlaps conceptually with `arb.py` (`ArbOpportunity`) and `crypto_pairs/opportunity_scan.py`. See [[Issue-Dead-Opportunities-Stub]].
- `fees.py` uses float-based quadratic curve. A separate Decimal-precision version exists in `simtrader/portfolio/fees.py`. See [[Issue-Dual-Fee-Modules]].

### Two Storage Backends in rag/

ChromaDB (vector RAG) and SQLite FTS5 (lexical RIS knowledge store) coexist in `packages/polymarket/rag/`. See [[RAG]].

---

## Subpackage Summary

| Subpackage | Files | Purpose |
|------------|-------|---------|
| `crypto_pairs/` | 20 | Crypto pair bot (Track 1A) |
| `historical_import/` | 4 | Bulk historical trade import |
| `hypotheses/` | 2 | JSON-backed hypothesis registry |
| `market_selection/` | 3+ | 7-factor composite market scorer |
| `notifications/` | 2 | Discord webhook alerting |
| `rag/` | 13 | ChromaDB + SQLite FTS5 RAG |
| `simtrader/` | 40+ | Full simulation engine |

---

## Cross-References

- [[System-Overview]] — Layer roles and package structure
- [[Database-Rules]] — ClickHouse/DuckDB one-sentence rule
- [[RAG]] — rag/ subpackage detail
- [[Issue-Dual-Fee-Modules]] — Fee module duplication
- [[Issue-Dead-Opportunities-Stub]] — Unused stub
