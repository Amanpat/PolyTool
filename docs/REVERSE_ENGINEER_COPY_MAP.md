# Reverse Engineer Copy Map (Polybot -> PolyTool)

This document maps the exact polybot components that implement reverse-engineering capabilities.
It identifies what to copy, what to redesign, and how data flows end-to-end.

Constraints:
- Public data only.
- Clean-room reimplementation (MIT license; do not copy large code blocks).

## A) Target user ingestion

Purpose:
- Resolve a target identity and ingest public trades/positions.
- Enrich with market metadata, order book context, and (optionally) on-chain receipts.

Key files/folders:
- `ingestor-service/src/main/java/com/polybot/ingestor/ingest/PolymarketUserIngestor.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/polymarket/PolymarketDataApiClient.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/polymarket/PolymarketProfileResolver.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/ingest/PolymarketMarketContextIngestor.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/polymarket/PolymarketGammaApiClient.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/polymarket/PolymarketClobApiClient.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/ingest/PolymarketUpDownMarketWsIngestor.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/ingest/PolygonTxReceiptIngestor.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/config/IngestorProperties.java`
- `ingestor-service/src/main/java/com/polybot/ingestor/config/IngestorHttpConfiguration.java`
- `polybot-core/src/main/java/com/polybot/hft/polymarket/ws/ClobMarketWebSocketClient.java`
- `polybot-core/src/main/java/com/polybot/hft/events/HftEventPublisher.java`

What it does (data flow):
- Identity resolution:
  - `PolymarketUserIngestor` accepts `username` or `proxyAddress`.
  - `PolymarketProfileResolver` scrapes `https://polymarket.com/@<user>?tab=activity` and parses `__NEXT_DATA__`
    for `proxyAddress`, `primaryAddress`, and `baseAddress`.
- Trades and positions:
  - `PolymarketDataApiClient` calls `GET /trades` and `GET /positions` (Data API) with `user`, `limit`, `offset`.
  - `PolymarketUserIngestor` dedupes via `transactionHash + asset + side` (fallback: `proxyAddress + timestamp + asset + side`)
    and publishes events `polymarket.user.trade` and `polymarket.user.positions.snapshot`.
- Market context (on-trade enrichment):
  - `PolymarketMarketContextIngestor` fetches Gamma `GET /events?slug=...` and CLOB `GET /book?token_id=...`,
    then publishes `polymarket.gamma.market` and `polymarket.clob.tob`.
  - It also fetches market trades via Data API `GET /trades?market=<slug>`.
- WS top-of-book:
  - `PolymarketUpDownMarketWsIngestor` builds BTC/ETH Up/Down slugs and subscribes token IDs
    on the CLOB market websocket, emitting `market_ws.tob`.
- On-chain receipts:
  - `PolygonTxReceiptIngestor` pulls Polygon receipts for trade `transactionHash` (public JSON-RPC),
    publishing `polygon.tx.receipt`.

ASCII data flow:

  [username or proxy]                         [Gamma /events]    [CLOB /book]
          |                                         |                 |
          v                                         v                 v
  PolymarketUserIngestor ----> Data API /trades, /positions ----> MarketContextIngestor
          |                          |                              |
          |                          v                              v
          |                   polymarket.user.trade          polymarket.clob.tob
          |                   polymarket.user.positions      polymarket.gamma.market
          |                          |
          v                          v
     HftEventPublisher (Kafka) -> analytics_events (ClickHouse)
          |
          v
  analytics-service + research scripts

Replicate vs redesign:
- Replicate:
  - Paging/dedup logic (limit/offset + event key formation in `PolymarketUserIngestor`).
  - Optional market context enrichment (Gamma + CLOB).
  - Trade-triggered TOB capture and market WS TOB (as separate data sources).
- Redesign:
  - Identity resolution must be public-only: replace HTML scraping in
    `PolymarketProfileResolver` with Gamma `public-search` and `public-profile`.
  - Replace Kafka with direct writes to a local DB for MVP (fewer moving parts).
  - Keep ingestion decoupled from analytics queries to allow multiple tools later.

## B) Trade and position storage

Purpose:
- Persist raw events and build normalized/enriched views for analytics and research.

Key files/folders:
- `analytics-service/clickhouse/init/001_init.sql` (Kafka -> `analytics_events`)
- `analytics-service/clickhouse/init/002_canonical.sql` (`user_trades`, `clob_tob`, `market_trades`, `gamma_markets`)
- `analytics-service/clickhouse/init/003_enriched.sql` (`user_trades_dedup`, `user_trade_enriched`)
- `analytics-service/clickhouse/init/004_research.sql` (`user_trade_research`)
- `analytics-service/clickhouse/init/005_position_ledger.sql` (`user_position_ledger`, `user_position_final`,
  `user_complete_sets_by_market`)
- `analytics-service/clickhouse/init/0051_complete_sets_detected.sql` (`user_complete_sets_detected`)
- `analytics-service/clickhouse/init/006_microstructure.sql` (market activity)
- `analytics-service/clickhouse/init/008_enhanced_data_collection.sql` (flow + enriched v2)
- `analytics-service/clickhouse/init/0080_polygon_tx_receipts.sql`
- `analytics-service/clickhouse/init/0082_polygon_log_decoding.sql`
- `analytics-service/clickhouse/init/0084_user_trade_onchain_pair_v2.sql`
- `analytics-service/clickhouse/init/0090_enriched_ws.sql` (WS TOB ASOF join)
- `scripts/clickhouse/apply-init.sh`

What it does (data flow):
- `analytics_events` is the raw sink for all event JSON.
- Materialized views extract trade, TOB, market-trade, and Gamma fields into typed tables.
- Derived views compute:
  - deduped trades (`user_trades_dedup`)
  - resolved outcomes and PnL (`user_trade_enriched`)
  - research-ready features (`user_trade_research`, `user_trade_enriched_v2/v3/v4`)
  - positions from trade ledger (`user_position_ledger`, `user_position_final`)
  - complete-set stats (`user_complete_sets_by_market`, `user_complete_sets_detected`)

Replicate vs redesign:
- Replicate:
  - Raw trade storage and dedup.
  - Derived features that power detectors (seconds_to_end, edge vs mid, exec_type).
  - Complete-set aggregates and pair detection.
- Redesign:
  - Use a lighter DB (SQLite or DuckDB) for MVP; keep schemas explicit and versioned.
  - Store `positions` snapshots directly (polybot does not persist them in ClickHouse; it infers positions from trades).
  - Keep raw JSON columns to avoid re-ingesting when new features are needed.

## C) Analytics queries (dashboards and APIs)

Purpose:
- Serve precomputed analytics for dashboards and reports.

Key files/folders:
- `analytics-service/src/main/java/com/polybot/analytics/web/UserTradeAnalyticsController.java`
- `analytics-service/src/main/java/com/polybot/analytics/repo/JdbcUserTradeAnalyticsRepository.java`
- `analytics-service/src/main/java/com/polybot/analytics/web/UserPositionAnalyticsController.java`
- `analytics-service/src/main/java/com/polybot/analytics/repo/JdbcUserPositionAnalyticsRepository.java`
- `analytics-service/src/main/java/com/polybot/analytics/web/AnalyticsController.java`

What it does:
- Trade analytics: side/outcome breakdowns, timing buckets, execution quality, complete-set stats,
  realized PnL by market/series, activity by hour.
- Position analytics: open vs resolved, MTM PnL, ledger views, complete-set summaries.

Replicate vs redesign:
- Replicate:
  - Core endpoints for user overview and complete-set stats.
  - Execution quality classification (maker-like vs taker-like).
- Redesign:
  - Use API routes aligned with PolyTool (single service or modular endpoints).
  - Replace ClickHouse-specific SQL with DB-agnostic queries or a data access layer.

## D) Dashboards

Purpose:
- Visualize strategy performance, data coverage, and execution quality.

Key files/folders:
- `research/paper_trading_dashboard.py` (CLI dashboard)
- `research/generate_showcase_viz.py` (matplotlib image for README)
- `monitoring/grafana/dashboards/polybot-trading-overview.json` (Grafana overview)

Replicate vs redesign:
- Replicate:
  - Key widgets: PnL, trade volume, execution quality, inventory imbalance.
- Redesign:
  - Build a web dashboard (PolyTool `apps/web`) with user-focused analytics.
  - Keep Grafana optional (monitoring stack is not required for MVP).

## E) Strategy inference (reverse engineering)

Purpose:
- Extract behavioral signatures (complete-set, timing, sizing, execution style).

Key files/folders:
- `research/snapshot.py` (ClickHouse -> Parquet snapshots)
- `research/snapshot_report.py` (offline report; pairing delays, edge)
- `research/run_analysis.py` (complete-set detection + PnL gap)
- `research/final_strategy_findings.py` and `research/deep_analysis.py` (full narrative)
- `research/clickhouse_writer.py` + `analytics-service/clickhouse/init/007_research_labels.sql`
- `docs/STRATEGY_RESEARCH_GUIDE.md`
- `docs/EXAMPLE_STRATEGY_SPEC.md`

What it does (data flow):
  user_trade_enriched -> snapshots -> Python analysis -> labels (optional) -> analytics views

Replicate vs redesign:
- Replicate:
  - Pairing heuristics (complete-set edge and timing).
  - Execution edge decomposition (price vs mid).
  - Market mix and timing buckets.
- Redesign:
  - Build generic detectors (not target-specific).
  - Make all detector evidence machine-readable.
  - Avoid any reliance on private web scraping or non-public endpoints.

## What we can learn from this repo (detailed report)

1) Public data sources are sufficient for a full reverse-engineering loop:
   - Trades and positions come from Data API `/trades` and `/positions`.
   - Market metadata and token mapping come from Gamma `/events`.
   - Order book context comes from CLOB `/book` and WS `market_ws.tob`.

2) Event-driven ingestion is robust for analytics:
   - `analytics_events` is the raw event sink.
   - ClickHouse materialized views (`user_trades`, `clob_tob`, `market_trades`, `gamma_markets`)
     make downstream queries fast and stable.
   - Dedup uses an event key based on `transactionHash + asset + side`.

3) Complete-set behavior is measurable from fills alone:
   - `user_complete_sets_by_market` aggregates Up/Down or Yes/No exposure.
   - `user_complete_sets_detected` pairs trades within a time window.
   - `research/snapshot_report.py` and `research/run_analysis.py` quantify pairing delays
     and edge.

4) Execution edge dominates PnL in the example research:
   - `user_trade_enriched` computes `price_minus_mid` and `exec_type`.
   - `research/final_strategy_findings.py` decomposes PnL into directional vs execution edge.

5) High-fidelity inference needs fresh TOB and both outcomes:
   - `market_ws.tob` plus ASOF joins (`user_trade_enriched_v3/v4`) reduce lag.
   - `PolymarketMarketContextIngestor` snapshots both outcomes when token lists are known.

6) On-chain receipts add routing context (optional, still public):
   - `polygon_tx_receipts` + decoded logs (`polygon_exchange_orders_matched`)
     let you distinguish mint-style fills and paired legs.
   - `docs/STRATEGY_RESEARCH_GUIDE.md` notes relayer addresses in `tx.from`.

7) Research tooling is designed for repeatable offline analysis:
   - `research/snapshot.py` creates versioned Parquet snapshots.
   - `research/clickhouse_writer.py` writes labels back to ClickHouse.
   - `research/replication_score.py` compares distribution-level behavior.

8) Key limitations are explicitly documented:
   - TOB staleness and missing opposite-leg context are known blockers.
   - Fills alone cannot show unfilled orders or cancels.

## Clean-room implementation notes

- The MIT license allows reuse, but PolyTool should reimplement logic cleanly.
- Keep attribution notes in docs (not in code) for conceptual inspiration.
- Avoid copying large code blocks; implement equivalent logic from specs.
