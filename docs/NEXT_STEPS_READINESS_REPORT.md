# Next Steps Readiness Report

Date: 2026-01-28
Scope: repo-grounded audit (no network calls)

## 1. Current System Map

- **Entry points**: CLI (`tools/cli/scan.py`, `polyttool/__main__.py`) orchestrates API calls for resolve, ingest, detectors, optional positions/activity, snapshot/books, PnL, arb. The API is the central coordinator (`services/api/main.py`).
- **Data sources**:
  - Gamma API for user resolution and market metadata (`packages/polymarket/gamma.py`, `/api/resolve`, `/api/ingest/markets`).
  - Data API for trades, activity, positions (`packages/polymarket/data_api.py`, `/api/ingest/trades`, `/api/ingest/activity`, `/api/ingest/positions`).
  - CLOB API for orderbooks and fee rates (`packages/polymarket/clob.py`, `/api/snapshot/books`, `/api/compute/pnl`, `/api/compute/arb_feasibility`).
- **Storage**: ClickHouse tables and views in `infra/clickhouse/initdb/*.sql` (users, trades, activity, positions, market_tokens, markets, markets_enriched view, orderbook snapshots, PnL/arb buckets, detector results, bucket features, users_grafana_dropdown).
- **Compute**:
  - Features (`packages/polymarket/features.py`) -> `user_bucket_features`.
  - Detectors (`packages/polymarket/detectors.py`) -> `detector_results`.
  - PnL (`packages/polymarket/pnl.py`) -> `user_pnl_bucket`.
  - Arb feasibility (`packages/polymarket/arb.py`) -> `arb_feasibility_bucket`.
- **Visualization**: Grafana dashboards in `infra/grafana/dashboards/*.json` documented in `docs/DASHBOARDS.md` and `docs/QUALITY_CONFIDENCE.md`.

## 2. Data Sources & Coverage (Trades / Activity / Positions / Markets / Orderbooks)

- **Trades**
  - Source: Data API `/trades` via `DataApiClient.fetch_all_trades`.
  - Storage: `polyttool.user_trades` (ReplacingMergeTree on `ingested_at`, key `(proxy_wallet, trade_uid)`; `trade_uid` derived from API id or hash). See `infra/clickhouse/initdb/02_tables.sql`, `packages/polymarket/data_api.py`.
  - Coverage risks: dashboards often query raw `user_trades` without `argMax` or `FINAL`, so duplicates can inflate totals until merges complete (e.g., User Overview "Total Volume" and User Trades panels). See `infra/grafana/dashboards/polyttool_user_overview.json`, `polyttool_user_trades.json`.

- **Activity**
  - Source: Data API `/activity` (optional, CLI flag). Stored in `polyttool.user_activity` with ReplacingMergeTree; dashboards correctly dedupe via `argMax` in CTEs. See `infra/clickhouse/initdb/05_packet4_tables.sql` and User Trades dashboard queries.
  - Coverage risks: optional ingestion; some dashboards silently empty without activity data.

- **Positions**
  - Source: Data API `/positions`, stored as point-in-time snapshots in `polyttool.user_positions_snapshots` (ReplacingMergeTree). See `infra/clickhouse/initdb/05_packet4_tables.sql`, `/api/ingest/positions` in `services/api/main.py`.
  - Coverage risks: snapshots are not scheduled by default; staleness is common unless users run the endpoint regularly. PnL uses latest snapshot per bucket when available, else FIFO from trades (`packages/polymarket/pnl.py`).

- **Markets / Metadata**
  - Source: Gamma `/markets` via `/api/ingest/markets` (active markets only by default), plus ad-hoc backfill by condition_id (`packages/polymarket/backfill.py`).
  - Storage: `polyttool.market_tokens`, `polyttool.markets`, and `markets_enriched` view. See `infra/clickhouse/initdb/03_packet3_tables.sql` and `05_packet4_tables.sql`.
  - Coverage risks: mapping coverage depends on running market ingestion; unmapped trades inflate "UNMAPPED/Unknown" categories and reduce detector quality.

- **Orderbooks / Liquidity**
  - Source: CLOB `/book` via `/api/snapshot/books` and live pricing for PnL/arb. Stored in `polyttool.token_orderbook_snapshots` with status flags (`ok`, `empty`, `one_sided`, `no_orderbook`, `error`). See `infra/clickhouse/initdb/08_orderbook_snapshots.sql` and `packages/polymarket/orderbook_snapshots.py`.
  - Snapshot selection: positions -> recent trades -> active market filter -> optional historical fallback. Backfills missing market tokens before active filter. Stops early when `BOOK_SNAPSHOT_MIN_OK_TARGET` reached and skips recent `no_orderbook` tokens for 24h (default). See `/api/snapshot/books` in `services/api/main.py` and `docs/packet_5_2_1_4_tradeability.md`.
  - Coverage risks: early stop + TTL skips can bias "no_orderbook rate" downward; snapshots are not scheduled by default; freshness is not surfaced as a first-class metric in dashboards.

## 3. Profitability Realism Audit (PnL, MTM, Fees, Slippage, Confidence)

**What exists**
- Realized PnL uses FIFO matching of buys/sells per token (`packages/polymarket/pnl.py`), aligned with docs and README.
- MTM uses best bid for long positions and best ask for shorts. If recent snapshots exist in ClickHouse (default max age 3600s), they are used; otherwise live CLOB best bid/ask is fetched. Pricing source and snapshot ratio are recorded (`pricing_source`, `pricing_snapshot_ratio`, `pricing_confidence`). See `packages/polymarket/pnl.py`, `services/api/main.py`, `docs/QUALITY_CONFIDENCE.md`.
- Fees for arb feasibility are fetched per token from CLOB `/fee-rate` (`packages/polymarket/clob.py`) and applied via the documented quadratic fee curve (`packages/polymarket/fees.py`, README). PnL does not use fees.

**Key realism gaps**
- **MTM is priced at compute time for all historical buckets**. `compute_user_pnl_buckets` applies a single as-of pricing snapshot to every bucket, so historic MTM curves are anchored to current prices, not prices at bucket time. This can materially mislead trend interpretation and reverse-engineering of timing. (`services/api/main.py` passes `as_of=datetime.utcnow()`; `packages/polymarket/pnl.py` uses that for snapshot lookups and live pricing.)
- **No usable book gate for MTM**. MTM does not check spread or depth thresholds; if a book exists it is used. Slippage is not incorporated in MTM.
- **Fees/slippage not part of PnL**. Fees are only modeled in arb feasibility; PnL does not apply fees or slippage at all.

**Confidence layer (partial)**
- Pricing confidence is computed from snapshot ratio + missing tokens and stored in `user_pnl_bucket` (`pricing_confidence`, `pricing_snapshot_ratio`). It is displayed in User Overview but **not used to filter PnL charts**. (`docs/QUALITY_CONFIDENCE.md`, `infra/grafana/dashboards/polyttool_user_overview.json`.)

**Assessment**
- Realized PnL is directionally useful (assuming trade ingestion completeness) but FIFO is approximate.
- MTM is **not realistic enough for historical performance attribution** or reverse-engineering trade timing. It is acceptable for coarse "current exposure" estimation **only when confidence is HIGH**.

## 4. Liquidity Snapshot Audit (no_orderbook, active filtering, token selection, freshness)

**What exists**
- Snapshot pipeline with explicit status breakdown (`ok`, `empty`, `one_sided`, `no_orderbook`, `error`). See `packages/polymarket/orderbook_snapshots.py` and `infra/clickhouse/initdb/08_orderbook_snapshots.sql`.
- Active-market filtering and backfill for missing metadata in `/api/snapshot/books` (positions -> recent trades -> active filter; optional historical fallback). See `services/api/main.py`.
- Liquidity confidence fields in `arb_feasibility_bucket` (high/medium/low, depth_100_ok, depth_500_ok). See `infra/clickhouse/initdb/09_quality_confidence.sql`, `packages/polymarket/arb.py`.
- Caching and rate control: PnL and arb use in-memory caches with TTLs (defaults 30s) for orderbooks/fee rates; snapshotter skips recent no_orderbook tokens and stops after `MIN_OK_TARGET`. There is no global rate limiter or retry/backoff in PnL/arb (429/5xx are counted in snapshotter only). See `services/api/main.py`, `packages/polymarket/arb.py`, `packages/polymarket/pnl.py`.

**Key realism gaps**
- **Arb feasibility uses live books, not snapshots**. The function signature includes snapshot args but they are unused; liquidity confidence is derived from live CLOB `/book` at compute time. This makes historical arb analysis potentially misleading. (`packages/polymarket/arb.py`.)
- **No user-scoped liquidity dashboard**. Liquidity Snapshot dashboard is global and not user-filtered. "Orderbook Quality" in User Overview is also global, not user token-scoped. (`infra/grafana/dashboards/polyttool_liquidity_snapshots.json`, `polyttool_user_overview.json`.)
- **no_orderbook rate may be biased** because snapshotter stops early once OK targets are met and skips recent no_orderbook tokens for 24h. The observed rate is *not* a comprehensive per-user metric.
- **Freshness is not explicit**. Snapshots have `snapshot_ts` and `book_timestamp`, but dashboards do not surface "latest snapshot age" or "staleness vs max age".

**Assessment**
- Liquidity metrics are **useful for "is this token tradeable now"** but **not reliable for historical feasibility analysis**. They need per-user coverage metrics and freshness indicators to be decision-grade.

## 5. Dashboard Interpretability Audit (User Overview + others)

**Dashboard inventory (variables, core panels, and time/confidence defaults)**
- **PolyTool - User Overview** (`polyttool_user_overview.json`)
  - Variables: `proxy_wallet`, `bucket_type`.
  - Core panels: Summary stats; PnL/Exposure; Plays tables; Strategy Signals; Market Mix; Liquidity & Arb.
  - Time filter: mixed (Plays + Orderbook Quality use `$__timeFilter`; summary and market mix do not).
  - Trustworthy by default: **No** (no confidence filter on PnL/arb panels).

- **PolyTool - Strategy Detectors** (`polyttool_strategy_detectors.json`)
  - Variables: `proxy_wallet`, `bucket_type`, `detector_name`.
  - Core panels: detector scores over time, latest results, evidence JSON, bucket features.
  - Time filter: **No** (bucketed only).
  - Trustworthy by default: **N/A** (confidence not applicable).

- **PolyTool - PnL** (`polyttool_pnl.json`)
  - Variables: `proxy_wallet`, `bucket_type`.
  - Core panels: realized PnL, MTM estimate, exposure.
  - Time filter: **No** (bucketed only).
  - Trustworthy by default: **No** (no confidence filter).

- **PolyTool - Arb Feasibility** (`polyttool_arb_feasibility.json`)
  - Variables: `proxy_wallet`, `bucket_type`.
  - Core panels: total events/fees/slippage, break-even notional, results table.
  - Time filter: **No** (bucketed only).
  - Trustworthy by default: **No** (no confidence filter).

- **PolyTool - Liquidity Snapshots** (`polyttool_liquidity_snapshots.json`)
  - Variables: none.
  - Core panels: snapshot counts by status, spread/depth/slippage over time, latest snapshots, error reasons.
  - Time filter: **Yes** (all panels use `$__timeFilter`).
  - Trustworthy by default: **Not user-scoped** (global only).

- **PolyTool - User Trades** (`polyttool_user_trades.json`)
  - Variables: `proxy_wallet`, `username`.
  - Core panels: trades over time, buy/sell split, volume, activity charts, exposure snapshot.
  - Time filter: **No** (mostly lifetime).
  - Trustworthy by default: **No** (no dedupe in trade totals; activity panels do dedupe).

- **PolyTool - Infra Smoke** (`polyttool_infra_smoke.json`)
  - Variables: none.
  - Core panels: ClickHouse heartbeat and server time.
  - Time filter: **N/A**.

**User Overview: how a non-expert should read it (based on `docs/DASHBOARDS.md` and panel queries)**
1) **Summary row** (Total Trades/Volume/Markets/Active Days/Mapping Coverage) = lifetime scale and metadata completeness. Not time-filtered.
2) **PnL & Exposure row** = realized vs MTM trend + exposure (bucketed). Use only if Pricing Confidence is HIGH.
3) **Plays row** = recent trades (time-filtered) + top markets/outcomes/categories for the time window.
4) **Strategy Signals row** = detector labels/scores for current bucket.
5) **Market Mix row** = overall category concentration.
6) **Liquidity & Arb row** = global orderbook quality + user-level arb costs and liquidity confidence.

**Dashboard consistency issues**
- **Time picker inconsistency**: Many panels ignore Grafana time filter (User Overview summary stats, Market Mix, PnL/Detector dashboards). Plays row *does* respect it, which is confusing when totals do not move with the time range. (`polyttool_user_overview.json`, `polyttool_pnl.json`, `polyttool_strategy_detectors.json`.)
- **Global vs user-scoped liquidity**: "Orderbook Quality" is global. Users may assume it reflects their tokens. (`polyttool_user_overview.json`.)
- **Confidence not enforced**: PnL/arb charts are not filtered by confidence; confidence is shown only as a stat. This weakens "trustworthy by default."
- **Dedup risk in totals**: Some panels query ReplacingMergeTree tables without `argMax`/`FINAL` (e.g., Total Volume in User Overview, most of User Trades dashboard). Potential double counting is not explained.

**3-6 concrete changes to make it self-explanatory**
1) Add a **"How to read this dashboard" markdown panel** at top of User Overview, with bullets for each row and a "Trust only if Pricing Confidence = HIGH" note.
2) Add a **Data Quality row** on User Overview: mapping coverage, snapshot coverage %, latest snapshot age, no_orderbook rate for *user tokens*.
3) Add a **Confidence filter variable** (All/HIGH/MED) for PnL + Arb panels and default it to HIGH.
4) Make **time filtering consistent**: either apply `$__timeFilter` to all rows or clearly label "lifetime" vs "time-filtered".
5) Rename "Orderbook Quality" to "Global Orderbook Quality (All Tokens)" or replace it with a user-scoped version based on tokens in the user's trades/positions.
6) Add "As of" timestamps to PnL/Arb sections ("Pricing as of <timestamp>") to signal live pricing usage.

## 6. Detector Coverage & Roadmap (current + next 3-6 detectors)

**Current detectors (implemented)**
- HOLDING_STYLE (FIFO hold time) - `packages/polymarket/detectors.py`
- DCA_LADDERING (size consistency) - `packages/polymarket/detectors.py`
- MARKET_SELECTION_BIAS (HHI on category volume) - `packages/polymarket/detectors.py`
- COMPLETE_SET_ARBISH (buy both outcomes within 24h) - `packages/polymarket/detectors.py`

**Limitations**
- Depend on `market_tokens` coverage; unmapped tokens degrade category and arb logic.
- FIFO matching ignores transfers/redemptions and can misstate holding times.
- COMPLETE_SET_ARBISH does not validate that price sums < 1 at trade time.

**Next detectors (after data quality upgrades)**
1) **Maker/Taker proxy**
   - Inputs: trade prices + orderbook snapshots near trade timestamps (best bid/ask).
   - Compute: classify trade as maker-like if BUY <= best_bid+eps or SELL >= best_ask-eps.
   - Failure modes: stale books, missing snapshots; false maker classification in thin books.

2) **Bursty trading windows**
   - Inputs: high-resolution trade timestamps.
   - Compute: detect clusters with inter-trade gaps below a threshold; score burst intensity.
   - Failure modes: time zone or bucket aggregation hides bursts; missing trades.

3) **Event-time clustering**
   - Inputs: market end dates (`markets_enriched.end_date_iso`) + trades.
   - Compute: volume concentration within X hours of event end or resolution windows.
   - Failure modes: missing end dates; event time shifts; markets without clear end.

4) **Improved arb variant (edge-aware)**
   - Inputs: orderbook snapshots at trade time for both outcomes; market token mapping.
   - Compute: edge = 1 - (ask_yes + ask_no) or bid equivalents; classify only when edge > costs.
   - Failure modes: no historical snapshots, missing outcome mapping.

5) **Market regime specialization**
   - Inputs: `markets_enriched.is_crypto`, `interval_minutes`, tags.
   - Compute: detector scores stratified by regime (e.g., intraday crypto vs sports).
   - Failure modes: metadata sparsity; misclassified regimes.

## 7. Critical Gaps & Fast Experiments (cheap tests to reduce uncertainty)

**Critical gaps**
- Missing or stale market metadata (mapping coverage < 80% makes detectors unreliable).
- Orderbook snapshot coverage and freshness are not tracked per user.
- MTM and arb costs use current books, not historical.
- Dashboard time filters are inconsistent; some totals may be inflated by dedupe lag.

**Fast experiments (no network calls; local only)**
1) **Mapping coverage audit**
   - Query: % of trades with market_tokens join per user (already in User Overview "Mapping Coverage"). Validate with a direct ClickHouse query if needed.
2) **Snapshot freshness check**
   - Query: `max(snapshot_ts)` and age vs `ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS` for a user's tokens.
3) **no_orderbook rate for user tokens**
   - Query: status distribution for token_ids in a user's recent trades/positions, not global snapshots.
4) **Dedup risk check**
   - Compare `count()` vs `countDistinct(trade_uid)` for `user_trades` per user to quantify duplication impact.
5) **MTM sensitivity**
   - Run compute_pnl twice (after snapshot/books) and compare `pricing_snapshot_ratio` changes. This indicates how much MTM depends on live pricing.

## 8. Proposed Packet 6 (Spec + Acceptance Criteria + Stop Conditions)

**Goal**: Data Quality + Explainability, minimal scope, local-first.

**Packet 6A - Data Quality Metrics (ClickHouse + API)**
- Add a **user_data_quality view** that computes, per proxy_wallet:
  - mapping_coverage_pct
  - latest_snapshot_age_minutes
  - snapshot_ok_rate (for user tokens)
  - no_orderbook_rate (for user tokens)
  - pricing_snapshot_ratio + pricing_confidence (latest bucket)
- Add a **small API endpoint** or reuse existing endpoints to expose this view for Grafana.

**Packet 6B - Dashboard Explainability + Defaults**
- Add a **"How to read this" markdown panel** to User Overview.
- Add a **Data Quality row** using the new view.
- Add a **Confidence filter variable** (All/HIGH/MED) for PnL + Arb panels; default it to HIGH.
- Make time filter usage consistent or label panels as "lifetime".

**Packet 6C - Minimal workflow nudges**
- In `tools/cli/scan.py`, optionally default to `--snapshot-books` and `--ingest-markets` *only when* data quality is missing (guarded by a flag). Document this in README.

**Acceptance criteria**
- User Overview shows a Data Quality row with all metrics populated for a user with >= 100 trades.
- Pricing Confidence defaults to HIGH-only panels; users can toggle to include MED/LOW.
- "Orderbook Quality" on User Overview is user-scoped or explicitly labeled global.
- Time picker behavior is consistent (documented and/or enforced).

**Stop conditions**
- If mapping coverage remains <80% after market ingestion/backfill for a representative user, stop detector expansion and fix mapping ingestion.
- If snapshot_ok_rate <40% or latest_snapshot_age > 2 hours for a representative user after snapshot/books, stop and focus on liquidity snapshot coverage.
- If dedupe inflation >5% (count vs countDistinct), stop and fix dashboard queries to use argMax/FINAL.

## 9. Required User Inputs (screenshots / example users / commands)

Please provide the minimum set below so I can validate UX and interpretability:

1) **User Overview (top half)**: includes time picker, summary row, PnL row, Pricing Confidence + Snapshot Pricing %.
2) **User Overview (plays row)**: shows Latest Trades table + top markets/outcomes/categories.
3) **User Overview (bottom half)**: Strategy Signals + Liquidity & Arb row (Orderbook Quality, Arb Confidence).

Optional (only if easy):
- One example **high-activity user** and **low-activity user** handle/address to validate mapping coverage and snapshot behavior.
