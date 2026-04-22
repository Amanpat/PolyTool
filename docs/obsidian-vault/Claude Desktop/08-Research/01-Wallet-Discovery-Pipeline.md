# Wallet Discovery Pipeline — Four-Loop Architecture
**Status:** Design phase — researched, not yet specced for implementation
**Last updated:** 2026-04-08

## Overview

Four independent loops with different timing, data sources, and responsibilities. They share data stores (ClickHouse, RAG, DuckDB) but don't depend on each other operationally.

## Loop A — Discovery (Slow, Thorough)
**Question:** "Who are the profitable wallets we don't know about yet?"
**Trigger:** Scheduled — 24h leaderboard scan + 7-14d rescan of known wallets
**Data source:** Polymarket leaderboard API, on-chain trade history
**Output:** New wallets added to scan queue, updated profiles for known wallets
**Rescan logic:** Compare new profile to stored profile. If significantly changed (new categories, different sizing, changed win rate) → trigger Loop C for fresh LLM analysis. If unchanged → update stats only.
**Leaderboard churn detection:** Wallets appearing on leaderboard for first time or jumping significantly in ranking get priority for immediate deep analysis.

## Loop B — Watchlist Live Monitoring (Real-time)
**Question:** "What are our known-profitable wallets doing RIGHT NOW?"
**Trigger:** Continuous — WebSocket subscription to on-chain events
**Data source:** Alchemy Polygon WebSocket `eth_subscribe("logs")` filtered by wallet addresses
**Architecture:**
- Subscribe to OrderFilled events from both CTFExchange contracts
- Filter by topic1 (maker) and topic2 (taker) for 20-50 watched addresses
- Latency: <1-3 seconds from block production
- Maker/taker classification available from indexed event fields
**Output:** Real-time Discord alerts, copy-trade signals if confidence high
**Key finding:** Cannot monitor other wallets' CLOB orders before on-chain fill. Polymarket User Channel WebSocket only works with your own API key. Earliest signal for OTHER wallets is always on-chain OrderFilled logs.
**Provider recommendation:** Alchemy primary (30M CU/mo free, persistent WebSocket, 5 webhooks). Goldsky Turbo pipeline as robust backup.

## Loop C — Deep Analysis (Triggered)
**Question:** "Run full analysis on this wallet NOW"
**Trigger:** Events from Loop A (new wallet) OR Loop B (unusual activity)
**Pipeline:**
1. Full data collection (existing wallet-scan)
2. 12-dim MVF computation (metrics engine)
3. Exemplar selection (top PnL, top size, anomalous trades)
4. LLM hypothesis generation (metrics + exemplars → Gemini Flash / DeepSeek V3)
5. Store results in RAG + ClickHouse
**Output:** Strategy hypotheses with evidence + testable predictions → Discord notification

## Loop D — Anomaly Detection (Independent, Platform-wide)
**Question:** "Is anyone on the entire platform showing statistically impossible trading patterns?"
**Trigger:** Scheduled scan of all recent activity + event-driven on large price moves
**Not watching specific wallets** — watching for anomalous PATTERNS across all activity
**Detection methods (phased):**
- Phase 1: Binomial win-rate test + pre-event trading score
- Phase 2: Wallet-level VPIN + Kyle lambda + event study tests
- Phase 3: Network analysis (funding graph clustering, behavioral fingerprinting)
- Phase 4: Real-time integration with Loop B
**Output:** Flagged wallets → promoted to Loop B watchlist + Discord alert

## Data Flow Between Loops
- Loop A discovers wallet → adds to Loop B watchlist (if profitable enough)
- Loop B detects unusual activity → triggers Loop C deep analysis
- Loop D flags anomalous wallet → promotes to Loop B watchlist + triggers Loop C
- All loops write results to RAG (polytool_brain) and ClickHouse
- Loop C results feed back into Loop A's rescan priority queue

## Open Questions
- [ ] Loop A: What leaderboard API endpoint? Is there a public Polymarket leaderboard API or do we need to build from on-chain data?
- [ ] Loop B: Alchemy free tier — will 30M CU/mo handle 50 wallets continuously? Need to estimate CU consumption per log subscription.
- [ ] Loop D: What constitutes a "large price move" trigger? >5% in <30 min? Need to calibrate.
- [ ] Cross-loop: How does Loop D's scheduled scan work without an external event feed? Do we use price moves as proxy events initially?

## Open Research Needed (2026-04-08)

### 1. Polymarket Leaderboard API
**Status:** NEEDS RESEARCH
**Context:** Aman currently copy-pastes usernames from web UI. Need to know:
- Is there a public leaderboard API endpoint?
- What data does it return (wallet addresses, usernames, PnL, volume)?
- Rate limits?
- Alternative: build our own leaderboard from on-chain OrderFilled event aggregation

### 2. Polymarket OrderFilled Event Volume
**Status:** NEEDS RESEARCH
**Context:** Loop D needs ALL platform events (not filtered by wallet). Need to estimate:
- How many OrderFilled events per day on Polymarket?
- Can Alchemy free tier (30M CU/mo) handle subscribing to ALL events?
- If too high volume, what sampling/filtering strategy?

### 3. Loop D Architecture Refinement
**Status:** DESIGN IN PROGRESS
**Key insight from discussion:** Loop D should be EVENT-CENTRIC not WALLET-CENTRIC.
- Watch all OrderFilled events platform-wide
- Run anomaly detectors on the stream (not pre-scanning wallets)
- Detectors run in parallel on same event stream:
  - New account + large profitable trade
  - Cluster of wallets hitting same market simultaneously  
  - Pre-event trading correlation
- Each detector independently flags wallets → promotes to Loop C / Loop B
- Solves the "scan wallet, deny it, miss their trade later" problem

### 4. Grafana Dashboard Cleanup
**Status:** TODO (separate task, not blocking pipeline design)
**Context:** Dashboards built early in development, contain ambiguous charts. Need:
- Clear labels on every chart explaining what it shows
- Target user dropdown fix (shows no users despite saved scans)
- Metrics that can be understood at a glance

### 5. n8n Template Research
**Status:** TODO (parallel exploration, not blocking)
**Context:** Thousands of n8n templates exist with advanced workflow patterns. Browse for:
- Patterns applicable to data pipeline orchestration
- Webhook-based alerting workflows
- Multi-step processing with error handling


## RESOLVED 2026-04-09: Loop A Leaderboard API

**Endpoint found:** `GET https://data-api.polymarket.com/v1/leaderboard`
- Public, no auth, returns proxyWallet (0x address) + PnL + volume
- Supports category filtering (POLITICS, SPORTS, CRYPTO, etc.)
- Time periods: DAY, WEEK, MONTH, ALL
- Pagination: limit=50, offset up to 1000 → can fetch top 500
- Rate limit: 1000 req/10s

**Loop A implementation plan:**
1. Every 24h: fetch top 500 by PNL (ALL time) + top 500 by VOL (ALL time) per category
2. Compare with previous scan: flag NEW wallets (leaderboard churn detection)
3. New wallets → priority queue for Loop C deep analysis
4. Known wallets → check if last full scan was >14 days ago → rescan if stale
5. Store leaderboard snapshots in ClickHouse for trend analysis

**Leaderboard churn detection:**
- Fetch DAY leaderboard separately → wallets appearing here but NOT in ALL-time list are new/rising
- These get highest priority for immediate Loop C analysis

## RESOLVED 2026-04-09: Loop D Architecture (Event-Centric, Two-Feed)

**Problem solved:** ALL OrderFilled events via Alchemy = 120M CU/month (4x over free tier). Not feasible.

**Solution:** Use Polymarket CLOB WebSocket feed (free, faster) for platform-wide monitoring:
1. Subscribe to ALL market trades via `wss://ws-subscriptions-clob.polymarket.com/ws/market`
2. Process locally: detect volume spikes, price anomalies, unusual patterns
3. When anomaly detected: query Alchemy REST for wallet addresses involved (targeted, cheap)
4. Run insider detection heuristics on identified wallets
5. Flag → promote to Loop B watchlist + trigger Loop C

**CLOB feed limitation:** No wallet addresses. Only asset_id, price, size, side, timestamp.
**Workaround:** CLOB detects WHAT is anomalous (which market, when). Alchemy tells us WHO did it (wallet addresses). Two-step process keeps costs near zero.

## Remaining Open Questions
- [ ] CLOB WebSocket market channel: can we subscribe to ALL markets at once or do we need per-asset subscriptions? Need to test.
- [ ] What is the message volume on the CLOB WebSocket? Can a single Python process handle 150k-300k messages/day?
- [ ] For Loop D wallet attribution: Alchemy `eth_getLogs` REST call cost in CUs? Need to estimate for on-demand queries.


## RESOLVED 2026-04-09: Loop D CLOB Subscription Model

**No wildcard mode.** Loop D must manage subscriptions to all active asset_ids.

### Loop D Startup Sequence:
1. Fetch all active markets from Gamma API (paginated)
2. Extract all token IDs (YES + NO per market)
3. Subscribe to all via CLOB WebSocket with `custom_feature_enabled: true`
4. Start processing `last_trade_price` events for anomaly detection

### Loop D Runtime Maintenance:
- `new_market` event → auto-subscribe to new token IDs
- `market_resolved` event → unsubscribe resolved token IDs
- On disconnect → re-bootstrap from Gamma API, re-subscribe all

### Anomaly Detection → Wallet Attribution Flow:
1. CLOB detects anomaly on market X (volume spike, price anomaly)
2. Query Alchemy `eth_getLogs` for OrderFilled events on market X's contract + recent blocks (60 CU)
3. Extract maker/taker wallet addresses from event data
4. Run insider detection heuristics (binomial test, pre-event score)
5. If flagged → promote to Loop B watchlist + trigger Loop C deep analysis

### All Open Questions Now Resolved
- [x] CLOB WebSocket: per-asset subscription, no wildcard (managed subscription required)
- [x] Message volume: 2-50/sec, single asyncio process handles easily
- [x] Alchemy CU: 1.38M CU/month total, well under 30M free tier
- [x] Leaderboard API: data-api.polymarket.com/v1/leaderboard, public, returns proxyWallet
