---
tags: [research]
date: 2026-04-09
status: active
---
# Wallet Discovery Pipeline — Implementation Roadmap
**Version:** 1.0 · **Date:** 2026-04-09
**Parent:** PolyTool Master Roadmap v5.1
**Companion Notes:** [[01-Wallet-Discovery-Pipeline]], [[02-Metrics-Engine-MVF]], [[03-Insider-Detection]], [[04-Loop-B-Live-Monitoring]], [[05-LLM-Chunking-Strategy]]

---

## What We're Building

A continuous wallet discovery and analysis system that:
1. Finds profitable wallets on Polymarket automatically
2. Monitors known-profitable wallets in real-time
3. Detects anomalous trading patterns platform-wide
4. Generates strategy hypotheses using LLM analysis of quantitative fingerprints
5. Stores all findings in the RAG knowledge base for downstream use

This system feeds the existing RIS knowledge base and hypothesis registry. It does NOT include SimTrader validation or live trading — those are separate phases that consume this system's output.

---

## Architecture Summary

### Four Independent Loops

| Loop | Purpose | Trigger | Data Source | Cost |
|------|---------|---------|-------------|------|
| A — Discovery | Find new profitable wallets | 24h schedule | Polymarket Data API leaderboard | Free |
| B — Watchlist | Monitor known wallets live | Continuous | Alchemy WebSocket (filtered by address) | ~1.2M CU/mo |
| C — Deep Analysis | Full scan + MVF + LLM | Triggered by A, B, or D | Existing scan pipeline + new metrics | Free (Gemini Flash) |
| D — Anomaly Detection | Detect suspicious patterns platform-wide | Continuous | CLOB WebSocket (all markets) | Free |

**Total monthly cost: ~1.38M CU/month Alchemy (4.6% of 30M free tier) + $0 everything else**

### Two Data Feeds

| Feed | What | Wallet Addresses? | Cost | Used By |
|------|------|-------------------|------|---------|
| CLOB WebSocket | All trades, all markets | No | Free | Loop D |
| Alchemy WebSocket | Filtered OrderFilled events | Yes (maker/taker) | ~40 CU/event | Loop B |

When Loop D detects an anomaly, it queries Alchemy REST (`eth_getLogs`, 60 CU/call) to identify which wallets were involved.

### Data Stores

| Store | What Goes Here | Written By |
|-------|----------------|------------|
| ClickHouse | Watchlist, leaderboard snapshots, scan results, trade events, insider scores | All loops |
| RAG (polytool_brain) | Strategy hypotheses, MVF profiles, LLM analysis reports | Loop C |
| DuckDB | Historical analysis queries (read-only) | N/A (read only) |

---

## Build Order

```
Phase 0: Prerequisites (verify data, set up accounts)
    │
    ▼
Phase 1: Metrics Engine Extension (MVF + exemplar selector)
    │
    ├──▶ Phase 2: Loop A (leaderboard discovery)     ──┐
    │                                                    │
    ├──▶ Phase 3: Loop D (CLOB anomaly detection)     ──┤
    │                                                    │
    └──▶ Phase 5: Insider Detection (Phase 1 heuristic) │
                                                         │
Phase 4: Loop B (Alchemy wallet monitoring)  ◀───────────┘
    │                                         (needs watchlist populated)
    ▼
Phase 6: Loop C (deep analysis + LLM hypotheses)
    │                  (needs metrics engine + exemplar selector)
    ▼
Phase 7: n8n Integration (workflow visualization)
    │
    ▼
Future: SimTrader integration, external strategy discovery, autoresearch
```

Phases 2, 3, and 5 can run in parallel after Phase 1. Phase 4 needs at least one of them populating the watchlist. Phase 6 needs Phases 1 and 4. Phase 7 can start anytime but is most useful after Phases 2-6 are working.

---

## Phase 0 — Prerequisites
**Effort:** 1-2 days
**Dependencies:** None
**Can be a Claude Code work packet:** Yes

### 0.1 Verify maker/taker data in ClickHouse

Check whether `polymarket_trades` table includes maker/taker wallet address columns. The scan pipeline ingests trades from the polymarket-apis REST endpoint — verify whether that endpoint returns maker/taker fields.

**If YES:** MVF metric #1 (Maker/Taker Ratio) is computable from existing data.
**If NO:** Two options:
- (a) Add an on-chain enrichment step that queries OrderFilled events via Subgraph/Alchemy to add maker/taker to trade records
- (b) Defer MTR to Loop B only (where we get maker/taker from live Alchemy WebSocket) and use 11-dim MVF for historical scans

Option (b) is simpler and doesn't block anything.

### 0.2 Create ClickHouse watchlist table

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    wallet_address String,
    added_by String,
    added_at DateTime DEFAULT now(),
    reason String,
    priority UInt8 DEFAULT 3,
    active UInt8 DEFAULT 1,
    last_activity Nullable(DateTime),
    metadata String DEFAULT '{}'
) ENGINE = ReplacingMergeTree()
ORDER BY wallet_address;
```

### 0.3 Create ClickHouse leaderboard_snapshots table

```sql
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    snapshot_date Date,
    category String,
    time_period String,
    rank UInt32,
    proxy_wallet String,
    username String,
    pnl Float64,
    volume Float64,
    is_new UInt8 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (snapshot_date, category, rank);
```

### 0.4 Create Alchemy account

Sign up at alchemy.com, create a Polygon PoS app, note the API key and WebSocket URL. Free tier: 30M CU/month.

### 0.5 Test CLOB WebSocket connectivity

Quick Python script: connect to `wss://ws-subscriptions-clob.polymarket.com/ws/market`, subscribe to one active market's token IDs, verify `last_trade_price` events arrive. Confirm PING/PONG behavior (send "PING" every 10s).

**Pass criteria:** All 5 sub-tasks complete. Watchlist and leaderboard tables created. Alchemy account active. CLOB WebSocket connectivity confirmed.

---

## Phase 1 — Metrics Engine Extension
**Effort:** 3-5 days
**Dependencies:** Phase 0
**Can be a Claude Code work packet:** Yes

### 1.1 Add MVF computation module

New file: `packages/polymarket/metrics/mvf.py`

Compute the 11-dimension MVF vector (12 if maker/taker available) from existing scan data:

| # | Metric | Implementation | Library |
|---|--------|---------------|---------|
| 1 | Maker/Taker Ratio | Vol_maker / Vol_total (if data available) | pandas |
| 2 | Trade Burstiness | StdDev(inter_trade_time) / Mean(inter_trade_time) | numpy |
| 3 | Lifecycle Entry % | Mean((first_trade - market_create) / (resolution - market_create)) | pandas |
| 4 | Resolution Exit % | Mean((last_trade - market_create) / (resolution - market_create)) | pandas |
| 5 | Sizing Convexity | Correlation(Trade_Size, Abs(Trade_Price - Market_Mid)) | scipy.stats |
| 6 | Category Entropy | Shannon_Entropy(market_category_distribution) | scipy.stats.entropy |
| 7 | Complement Rate | Already computed by COMPLETE_SET_ARBISH detector | existing |
| 8 | Win Rate | Already computed | existing |
| 9 | Payoff Ratio | Avg_Profit_Per_Win / Abs(Avg_Loss_Per_Loss) | numpy |
| 10 | CLV | Already computed | existing |
| 11 | Longshot Bias | ROI_below_20c - ROI_above_80c | pandas.groupby |

**Input:** Existing dossier JSON (from wallet-scan output)
**Output:** MVF vector as JSON object with all dimensions + metadata

Market creation timestamps required for metrics 3-4: fetch from Gamma API via existing `gamma.py` module.

### 1.2 Add exemplar selector

New file: `packages/polymarket/metrics/exemplar_selector.py`

Select 15-25 raw trades from the dossier for LLM context:

1. Top 10 by absolute PnL (5 winners, 5 losers)
2. Top 5 by trade size
3. 5 trades around large price moves (>5% in <30 min)
4. 3-5 trades that are statistical outliers relative to the MVF fingerprint
5. All trades in first 5% of market lifecycle (early entry signal)
6. All trades on wrong side of final resolution (if any)

Each exemplar annotated with one-line explanation: `"Unusual because: largest single trade, 8x median size, placed 2 minutes before 12% price move"`

**Input:** Dossier JSON + MVF vector
**Output:** List of annotated exemplar trade objects

### 1.3 Add insider detection Phase 1 metrics

New file: `packages/polymarket/metrics/insider_score.py`

Two metrics computed per wallet:

**Market-adjusted win rate test:**
- For each resolved trade: compute baseline probability p0 = price at entry
- Observed win rate p̂ = wins / total
- Binomial test: `scipy.stats.binom_test(wins, total, p0)`
- Output: informedness_score = -log10(p_value)

**Pre-event trading score:**
- Define "events" as price moves >5% within 30 minutes (computed from trade data)
- For each wallet: count trades in [t_event - τ, t_event) in correct direction
- τ = 1 hour (initial, calibrate later)
- Null: Binomial(N_total, τ/T)
- Output: pre_event_score = -log10(p_value)

**Input:** Dossier JSON with trade timestamps + market resolution data
**Output:** insider_scores JSON: {informedness_score, pre_event_score, n_trades, flags[]}

### 1.4 Integrate into unified scan command

Modify `tools/cli/scan.py` (or create wrapper) so that `polytool scan <address>` runs:
1. Existing wallet-scan (data collection + detectors + PnL + CLV)
2. MVF computation (new)
3. Exemplar selection (new)
4. Insider scoring (new)
5. Output: unified dossier JSON with all components

Keep existing `--` flags for component isolation during debugging.
Add `--quick` flag that skips LLM hypothesis step (Phase 6).

**Pass criteria:** `polytool scan <address>` produces a dossier containing: existing scan data + 11-dim MVF vector + 15-25 annotated exemplars + insider scores. Runs in <60 seconds for a wallet with 500 trades.

---

## Phase 2 — Loop A: Leaderboard Discovery
**Effort:** 2-3 days
**Dependencies:** Phase 0 (ClickHouse tables), Phase 1 (scan command)
**Can be a Claude Code work packet:** Yes

### 2.1 Leaderboard fetcher module

New file: `packages/polymarket/discovery/leaderboard.py`

```python
def fetch_leaderboard(order_by="PNL", time_period="ALL", category="OVERALL", 
                      limit=50, max_pages=10) -> list[dict]:
    """Fetch from data-api.polymarket.com/v1/leaderboard with pagination."""
```

Fetches top N wallets by PNL and VOL across all categories. Stores snapshots in `leaderboard_snapshots` ClickHouse table.

### 2.2 Churn detection

Compare current snapshot to previous snapshot:
- **New wallets:** proxyWallet appears in current but not previous → flag is_new=1
- **Rising wallets:** rank improved by >50 positions → priority bump
- **DAY vs ALL comparison:** wallet in DAY top-100 but not in ALL top-500 → fast-rising, high priority

### 2.3 Scan queue manager

New file: `packages/polymarket/discovery/scan_queue.py`

Maintains a queue of wallets to scan:
- New discoveries from leaderboard → add to queue with priority based on churn detection
- Wallets from Loop D flags → add with high priority
- Manual additions → `polytool scan-queue add <address>`
- Rescan triggers → wallets last scanned >14 days ago with changed leaderboard metrics

### 2.4 Loop A orchestrator

New file: `packages/polymarket/discovery/loop_a.py`

```python
async def run_loop_a():
    """24-hour discovery cycle."""
    # 1. Fetch leaderboard (all categories, PNL + VOL)
    # 2. Store snapshot, detect churn
    # 3. Queue new/changed wallets for scanning
    # 4. Process queue: run full scan on each wallet
    # 5. Store results in ClickHouse + RAG
    # 6. Promote high-value wallets to watchlist
```

CLI: `polytool discovery run-loop-a` (one-shot) and `polytool discovery start-loop-a` (scheduled)

### 2.5 Watchlist promotion logic

After scanning, wallets meeting ANY of these criteria are added to the watchlist:
- PnL > $10,000 (lifetime)
- Win rate > baseline + 15% with N > 50 trades
- Insider score > threshold (informedness_score > 3.0)
- CLV consistently positive
- Strategy hypothesis flagged as "novel" by LLM (Phase 6)

**Pass criteria:** `polytool discovery run-loop-a` fetches leaderboard, detects new wallets, runs scans, populates watchlist. Runs end-to-end in <30 minutes for 100 new wallets.

---

## Phase 3 — Loop D: Platform-Wide Anomaly Detection
**Effort:** 5-7 days
**Dependencies:** Phase 0 (Alchemy account, CLOB WebSocket test, watchlist table)
**Can be a Claude Code work packet:** Yes (complex — may need 2 sessions)

### 3.1 CLOB subscription manager

New file: `packages/polymarket/discovery/clob_stream.py`

Manages a WebSocket connection to the CLOB market channel:
- On startup: fetch all active markets from Gamma API, extract all token IDs
- Subscribe to all token IDs with `custom_feature_enabled: true`
- Listen for `new_market` events → auto-subscribe new token IDs
- Listen for `market_resolved` events → unsubscribe resolved token IDs
- Send PING every 9.9 seconds
- On disconnect: reconnect, re-bootstrap from Gamma API
- Backfill gap: on reconnect, query CLOB REST `GET /trades` for missed period

```python
async def run_clob_stream(on_trade: Callable, on_anomaly: Callable):
    """Persistent CLOB WebSocket consumer with dynamic subscription management."""
```

### 3.2 Rolling aggregates engine

New file: `packages/polymarket/discovery/aggregates.py`

Maintains in-memory rolling statistics per market:
- 5-minute volume (sum of trade sizes)
- 1-hour volume
- 5-minute trade count
- Rolling average trade size
- Price velocity (rate of change over 5 minutes)
- Last N trade sizes (for sudden size spike detection)

Data structure: `dict[asset_id, MarketAggregates]` updated on every `last_trade_price` event.

### 3.3 Anomaly detectors

New file: `packages/polymarket/discovery/anomaly_detectors.py`

Three parallel detectors running on the same trade stream:

**Detector 1 — Volume spike:**
Flag when 5-minute volume > 5x the trailing 1-hour average for a market. Threshold configurable. Ignores markets with <10 trades in trailing hour (too sparse for meaningful baseline).

**Detector 2 — Size anomaly:**
Flag when a single trade size > 10x the trailing median trade size for that market. Catches large "whale" trades on normally small markets.

**Detector 3 — Price velocity:**
Flag when price moves >5% within 5 minutes without a corresponding volume spike (potential informed trading before news — price moves on low volume are more suspicious than high-volume moves).

Each detector outputs: `AnomalyEvent(market_id, asset_id, detector_name, severity, timestamp, details)`

### 3.4 Wallet attribution (on anomaly trigger)

When any detector fires:
1. Query Alchemy REST `eth_getLogs` for OrderFilled events on the flagged market's contract, filtered by recent blocks (~100 blocks, covers ~5 minutes)
2. Extract unique maker/taker wallet addresses
3. Cross-reference with watchlist (already known?) and leaderboard (ranked?)
4. For unknown wallets: check wallet age (new account?), check trade count (first trades?)
5. If wallet meets flagging criteria → add to watchlist + queue for Loop C deep analysis
6. Send Discord alert: "Anomaly detected: [detector] on [market]. Wallets involved: [addresses]. New accounts: [count]."

### 3.5 Loop D orchestrator

New file: `packages/polymarket/discovery/loop_d.py`

```python
async def run_loop_d():
    """Continuous platform-wide anomaly detection."""
    # 1. Start CLOB subscription manager
    # 2. Initialize rolling aggregates
    # 3. For each trade event:
    #    a. Update aggregates
    #    b. Run all detectors
    #    c. If anomaly: trigger wallet attribution
    # 4. Run indefinitely until killed
```

CLI: `polytool discovery start-loop-d`
Docker: runs as its own service in docker-compose.yml

**Pass criteria:** Loop D connects to CLOB WebSocket, subscribes to all active markets, processes trades in real-time, detects at least one volume spike within 24 hours of running, successfully attributes wallets via Alchemy. Discord alert fires on detection.

---

## Phase 4 — Loop B: Live Wallet Monitoring
**Effort:** 3-4 days
**Dependencies:** Phase 0 (Alchemy account, watchlist table), at least one of Phase 2/3 populating watchlist
**Can be a Claude Code work packet:** Yes

### 4.1 Alchemy WebSocket client

New file: `packages/polymarket/discovery/alchemy_stream.py`

```python
async def run_alchemy_stream(watchlist: list[str], on_fill: Callable):
    """Subscribe to OrderFilled events for watched wallets via Alchemy WebSocket."""
```

- Connect to Alchemy Polygon WebSocket
- Subscribe to logs: address = [CTFExchange, NegRiskCTFExchange], topic0 = OrderFilled, topic1/topic2 = watchlist addresses
- Decode OrderFilled events using eth-abi: extract maker, taker, assetId, amounts, fee
- Call `on_fill` callback with decoded trade data

### 4.2 Watchlist poller

Every 60 seconds, query ClickHouse watchlist table for changes:
- New addresses (added_at > last_check) → dynamically add to Alchemy subscription
- Deactivated addresses (active=0) → remove from subscription
- No reconnection needed — Alchemy supports adding/removing topic filters on an existing subscription

### 4.3 Trade processor

For each fill event on a watched wallet:
1. Resolve market metadata (asset_id → market slug, category, current price) via Gamma API cache
2. Store trade event in ClickHouse
3. Check for alert conditions:
   - First trade in a market we haven't seen this wallet in before → Discord yellow alert
   - Trade size > 2x this wallet's historical average → Discord yellow alert
   - Trade in a market that Loop D has also flagged → Discord red alert
4. If copy-trading enabled: evaluate copy signal (future feature, stub for now)

### 4.4 Loop B orchestrator

```python
async def run_loop_b():
    """Continuous wallet-specific monitoring."""
    # 1. Load watchlist from ClickHouse
    # 2. Start Alchemy WebSocket with current watchlist
    # 3. Start watchlist poller (60s interval)
    # 4. Process fill events via trade processor
    # 5. Run indefinitely
```

CLI: `polytool discovery start-loop-b`
Docker: runs as its own service

**Pass criteria:** Loop B connects to Alchemy, subscribes to watchlist addresses, receives OrderFilled events in <3 seconds of on-chain confirmation, stores trades in ClickHouse, fires Discord alert when watched wallet trades in a new market.

---

## Phase 5 — Insider Detection Integration
**Effort:** 2-3 days
**Dependencies:** Phase 1 (insider_score.py), Phase 3 (Loop D providing event data)
**Can be a Claude Code work packet:** Yes

### 5.1 Batch insider scoring

New CLI command: `polytool insider-scan --all-scanned`

Runs insider detection metrics (from Phase 1.3) across ALL previously scanned wallets:
- Compute informedness_score and pre_event_score for each
- Rank by combined score
- Flag wallets exceeding threshold
- Output: ranked list + ClickHouse insert into new `insider_scores` table

### 5.2 Live insider scoring integration

When Loop D attributes wallets after an anomaly:
- Run insider metrics on the attributed wallet's trade history
- If the wallet has enough trades (N ≥ 30): compute full scores
- If new account with few trades: flag as "insufficient data, monitor" and add to watchlist for future scoring

### 5.3 Insider score dashboard (Grafana)

New Grafana panels:
- Top 20 wallets by informedness_score
- Pre-event trading score distribution
- Flagged wallets timeline (when were they flagged, what triggered it)

**Pass criteria:** `polytool insider-scan --all-scanned` produces ranked output. At least one known profitable wallet has a measurably higher informedness_score than the median.

---

## Phase 6 — Loop C: Deep Analysis + LLM Hypothesis Generation
**Effort:** 3-5 days
**Dependencies:** Phase 1 (MVF + exemplars), Phase 2 or 3 or 4 (something triggering analysis)
**Can be a Claude Code work packet:** Yes

### 6.1 Enhanced LLM bundle

Extend existing `llm_research_packets.py` to accept MVF + exemplars:

**Prompt structure:**
```
[System] You are a quantitative researcher analyzing prediction market wallets.

[Context: Strategy Classification Reference]
{MVF interpretation guide — market maker, arb, directional, etc.}

[Data: MVF Vector]
{12-dim vector with labels and values}

[Data: Existing Detector Outputs]
{HOLDING_STYLE, DCA_LADDERING, COMPLETE_SET_ARBISH, etc.}

[Data: Insider Detection Scores]
{informedness_score, pre_event_score}

[Data: Annotated Exemplar Trades]
{15-25 trades with one-line annotations}

[Task]
Given the above, propose 1-3 non-obvious strategy hypotheses.
For each: name, key evidence, confidence (0-1), testable prediction.
Focus on strategies the detectors did NOT already identify.
Return as JSON array.
```

### 6.2 LLM model routing

Use existing RIS LLM policy:
1. Gemini Flash (primary — free, 1M context, 1500 req/day)
2. DeepSeek V3 (escalation for borderline cases)
3. Ollama local (fallback)

### 6.3 Hypothesis storage

LLM output → parsed → stored in:
- RAG `user_data` partition (for retrieval by future analysis)
- Hypothesis registry (existing, for tracking status)
- ClickHouse (for Grafana dashboard visibility)
- Discord notification: "New hypothesis for wallet 0x7163: [name]. Confidence: 0.82. Evidence: [summary]."

### 6.4 Loop C orchestrator

```python
async def run_loop_c(trigger_queue: asyncio.Queue):
    """Triggered deep analysis worker."""
    while True:
        event = await trigger_queue.get()
        # 1. Run full scan (if not recently scanned)
        # 2. Compute MVF
        # 3. Select exemplars
        # 4. Compute insider scores
        # 5. Build LLM prompt
        # 6. Call LLM
        # 7. Parse and store hypotheses
        # 8. Notify via Discord
```

Trigger sources:
- Loop A: new wallet discovered
- Loop B: watched wallet unusual activity
- Loop D: anomaly detection flagged wallet
- Manual: `polytool discovery analyze <address>`

**Pass criteria:** End-to-end pipeline from trigger → scan → MVF → exemplars → LLM → hypothesis stored in RAG + Discord notification. LLM produces parseable JSON hypotheses for at least 80% of wallets with 50+ trades.

---

## Phase 7 — n8n Workflow Integration
**Effort:** 3-5 days
**Dependencies:** Phases 2-6 working as CLI commands, n8n operational
**Can be a Claude Code work packet:** Partially (n8n workflows need manual setup)

### 7.1 n8n project folder

Create "Wallet Discovery System" project in n8n, separate from the RIS project.

### 7.2 Workflow designs

| Workflow | Type | Trigger | What It Does |
|----------|------|---------|-------------|
| Loop A: Leaderboard Discovery | Scheduled | Every 24h at 02:00 | Runs `polytool discovery run-loop-a` |
| Loop A: Rescan Stale Wallets | Scheduled | Every 7 days | Runs rescan on wallets >14 days stale |
| Loop C: Deep Analysis | Webhook | POST /webhook/analyze | Receives wallet address, runs full analysis |
| Health Monitor | Scheduled | Every 30 min | Checks Loop B/D process status, alerts on failure |
| Manual Scan | Webhook | POST /webhook/scan | One-shot scan of a specific address |

Note: Loops B and D are long-running Python processes (WebSocket consumers), NOT n8n workflows. n8n monitors them via health checks and triggers Loop C when they detect something.

### 7.3 Grafana dashboard updates

New dashboard: "Wallet Discovery"
Panels:
- Watchlist table (active wallets, priority, last activity)
- Leaderboard churn (new entrants over time)
- Scan queue depth and processing rate
- Anomaly detection event log (Loop D)
- Insider score distribution
- Recent hypotheses generated

Fix existing: Target user dropdown in existing dashboards (query ClickHouse `wallet_scans` table for distinct usernames).

**Pass criteria:** n8n shows all workflows in "Wallet Discovery System" folder. Loop A runs on schedule. Health monitor alerts on Loop B/D process failure. Grafana dashboard shows live data.

---

## Future Phases (Not In This Roadmap)

### SimTrader Closed-Loop Testing (after this roadmap is complete)
- Hypotheses from Loop C → codified as SimTrader strategy classes
- Automated L1/L2/L3 validation against benchmark tape set
- Results feed back to RAG
- Strategy generation from RAG content (autoresearch)

### External Strategy Discovery (parallel, lower priority)
- Extend RIS scraper with strategy extraction prompts
- GitHub repo scanning for prediction market bot patterns
- Academic paper ingestion for new quantitative methods
- Discord notification when a novel strategy is discovered externally

### Copy-Trading System (after Loop B is proven)
- Loop B detects watched wallet trade → evaluate copy signal
- Risk checks: position size limits, market liquidity check, correlation with existing positions
- Execution: place order via py-clob-client with configurable delay
- Requires separate risk framework and human approval gate

---

## Work Packet Boundaries

For Claude Code / Codex agent execution, each phase maps to work packets:

| Work Packet | Phase | Files Created/Modified | Estimated Tokens |
|-------------|-------|-----------------------|-----------------|
| WP-0: Prerequisites | 0 | SQL migrations, test scripts | Small |
| WP-1A: MVF Module | 1.1 | `metrics/mvf.py`, tests | Medium |
| WP-1B: Exemplar Selector | 1.2 | `metrics/exemplar_selector.py`, tests | Medium |
| WP-1C: Insider Scorer | 1.3 | `metrics/insider_score.py`, tests | Medium |
| WP-1D: Scan Integration | 1.4 | `tools/cli/scan.py` modifications | Small |
| WP-2: Loop A | 2 | `discovery/leaderboard.py`, `scan_queue.py`, `loop_a.py`, tests | Medium-Large |
| WP-3A: CLOB Stream | 3.1-3.2 | `discovery/clob_stream.py`, `aggregates.py`, tests | Large |
| WP-3B: Anomaly Detectors | 3.3-3.5 | `discovery/anomaly_detectors.py`, `loop_d.py`, tests | Large |
| WP-4: Loop B | 4 | `discovery/alchemy_stream.py`, `loop_b.py`, tests | Medium-Large |
| WP-5: Insider Integration | 5 | CLI command, Grafana panels | Small |
| WP-6: Loop C + LLM | 6 | `discovery/loop_c.py`, prompt templates, tests | Medium-Large |
| WP-7: n8n + Grafana | 7 | n8n workflow JSONs, Grafana dashboard JSON | Medium |

Each work packet includes: scope guard, don't-do list, pass/fail criteria, mandatory dev log.

---

## Dependencies on External Systems

| System | Status | Blocking? |
|--------|--------|-----------|
| ClickHouse | Running | No |
| Grafana | Running | No |
| n8n | Setup in progress (parallel chat) | Blocks Phase 7 only |
| RIS | Built, not fully operational via n8n | Not blocking |
| Alchemy account | Not yet created | Blocks Phases 3, 4 |
| Discord webhooks | Existing | No |
| Gamma API | Existing integration | No |
| Polymarket CLOB WebSocket | Available, needs connectivity test | Blocks Phase 3 |

---

## Risk Factors

1. **CLOB WebSocket subscription limit unknown.** No documented max subscriptions per connection. If Polymarket has an undocumented limit below the number of active markets (~2000+ token IDs), Loop D may need multiple connections. Mitigation: test with increasing subscription counts during Phase 0.

2. **Maker/taker data availability.** If not in existing ClickHouse data AND on-chain enrichment is too expensive, MTR metric drops from MVF. Impact: low — the other 11 dimensions are highly discriminating. MTR is still available for Loop B watched wallets.

3. **LLM hypothesis quality.** The hybrid approach (metrics + exemplars) is research-backed but untested on our specific data. Phase 6 should include a manual review of first 20 hypotheses to calibrate prompt quality before autonomous operation.

4. **CLOB WebSocket stability.** Long-running WebSocket connections may drop. Reconnection + Gamma API re-bootstrap handles this, but there will be data gaps during reconnection. Mitigation: REST backfill on reconnect, accept small gaps as tolerable.

5. **Alchemy free tier changes.** Currently 30M CU/month. If Alchemy reduces this, Loop B costs could become meaningful. Mitigation: Infura and QuickNode are drop-in alternatives with similar free tiers.

---

## Cross-References

- [[01-Wallet-Discovery-Pipeline]] — Architecture detail
- [[02-Metrics-Engine-MVF]] — Full MVF specification
- [[03-Insider-Detection]] — Detection methods and phasing
- [[04-Loop-B-Live-Monitoring]] — Two-feed architecture detail
- [[05-LLM-Chunking-Strategy]] — Hybrid approach rationale
- [[Decision - Two-Feed Architecture]]
- [[Decision - Loop A Leaderboard API]]
- [[Decision - Loop D Managed CLOB Subscription]]
- [[Decision - Watchlist ClickHouse Storage]]
- Master Roadmap Phase 2 (Discovery Engine) in `POLYTOOL_MASTER_ROADMAP_v5_1.md`
