---
tags: [session-note]
date: 2026-04-09
status: complete
topics: [wallet-discovery, metrics-engine, insider-detection, loop-architecture, clob-websocket, alchemy, n8n, obsidian]
---
# Wallet Discovery Pipeline — Complete Design Session

## Session Context
Continuation from previous chat "Building out RAG systems for research and development." Aman's goal: design the continuous wallet scanning system that feeds the RIS knowledge base with strategy hypotheses discovered from profitable Polymarket wallets.

## What Aman Brought In (Brain Dump Summary)

Three interconnected systems envisioned:
1. **Wallet Discovery Pipeline** — find profitable users, scan them, generate hypotheses into their strategies
2. **SimTrader Closed-Loop Testing** — test hypotheses against historical data, generate new strategies from RAG, iterate
3. **External Strategy Discovery** — find methods from GitHub, forums, papers, news; learn and implement automatically

Key desires expressed:
- System should use "research grade math" for metrics
- LLM analysis of large dossiers needs chunking solution (dossiers can be thousands of lines)
- Wants n8n as the UI for pipeline visibility (see which users are being scanned, what step each is in)
- Wants live monitoring of wallets, not delayed polling
- 6-hour scan interval felt too slow — could miss trades and edges
- Insider trading detection as a separate concern
- System should eventually generate its own strategies and test them autonomously
- Obsidian vault should persist all research and decisions across chat sessions

## Discussion Arc

### Phase 1: Chunking Problem
- Aman pushed back on pure map-reduce (feared losing subtle signals)
- Research prompt sent to GLM-5 Turbo on 7 approaches
- **Result:** Hybrid approach chosen (programmatic metrics + selective raw exemplars + single LLM call)
- Map-reduce rejected; multi-agent mesh rejected; structured preprocessing alone insufficient
- Key insight: LLM should do pattern recognition, Python should do statistics

### Phase 2: Architecture Design
- Proposed four independent loops (A/B/C/D) instead of single pipeline
- Aman pushed back on:
  - 6h discovery interval → agreed, different loops need different timing
  - Polling for watchlist → agreed, live WebSocket monitoring needed
  - Loop C being dependent on watchlist → clarified Loop C is a triggered worker, not a detector
- Aman identified gap: "what if we scan a wallet, deny it, then it trades later?" → led to Loop D (event-centric anomaly detection)
- Loop D reframed from wallet-centric to event-centric: watch for anomalous PATTERNS, not pre-judge wallets

### Phase 3: Metrics Engine Research
- Research prompt on strategy fingerprinting metrics → 12-dimension MVF specified
- Research prompt on insider trading detection → phased approach (binomial test first)
- Mapped MVF against existing scan output: 5 of 12 already computed, 4 trivial adds, 3 need new data
- Cancel-to-Fill Ratio blocked for historical scans (off-chain data only)

### Phase 4: Data Source Research
- Research on live monitoring options → Alchemy WebSocket recommended for Loop B
- Research on Polymarket leaderboard API → found public endpoint at data-api.polymarket.com
- Research on OrderFilled event volume → 150k-300k/day average, 3-4.5M peak
- **Critical finding:** Alchemy all-events subscription would cost 120M CU/month (4x over free tier)
- **Solution:** Two-feed architecture — CLOB WebSocket (free, all trades) + Alchemy (filtered, wallet-specific)

### Phase 5: Final Technical Resolution
- Research on CLOB WebSocket subscription model → NO wildcard mode, must subscribe per-asset_id
- Loop D needs managed subscription (bootstrap from Gamma API, maintain via dynamic subscribe)
- Python asyncio handles 2-50 msg/sec easily (we're 100x below capacity limits)
- Alchemy CU budget confirmed: 1.38M CU/month total (4.6% of free tier)
- Total cost for all four loops: **$0/month**

### Deferred Topics
- **SimTrader integration** — Aman explicitly deferred: "We can work on the simtrader after our n8n system is in a working stage along with candidate scan"
- **External strategy discovery** — acknowledged as RIS scraper extension, not specced in detail
- **Grafana dashboard cleanup** — acknowledged as needed, separate task
- **n8n template research** — parallel exploration, not blocking
- **Obsidian vault organization** — separate chat opened for this

## Key Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Hybrid LLM approach (metrics + exemplars) | Map-reduce loses subtle signals; mesh too expensive |
| 2 | Four independent loops (A/B/C/D) | Different timing needs, separation of concerns |
| 3 | Two-feed architecture (CLOB + Alchemy) | CLOB free for all trades; Alchemy filtered for wallet attribution |
| 4 | Loop D event-centric, not wallet-centric | Solves "scan and deny, miss trade later" problem |
| 5 | Loop D managed CLOB subscription | No wildcard mode; must maintain asset_id set |
| 6 | Leaderboard API for Loop A discovery | Public, no auth, returns wallet addresses |
| 7 | Unified `polytool scan` with --quick flag | Consolidate existing CLI commands for autonomous operation |
| 8 | n8n for workflow orchestration (separate from RIS workflows) | Pipeline visibility as UI |
| 9 | Grafana for data/results dashboards | Complementary to n8n, not competing |
| 10 | SimTrader closed-loop deferred | Build discovery pipeline first, SimTrader after |

## Research Prompts Executed (5 total)

1. LLM chunking approaches for large financial datasets → [[11-Prompt-Archive/2026-04-08 GLM5 - LLM Chunking]]
2. Strategy fingerprinting metrics for prediction markets → [[08-Research/02-Metrics-Engine-MVF]]
3. Insider trading detection in prediction markets → [[08-Research/03-Insider-Detection]]
4. Live wallet monitoring data sources (Alchemy, Goldsky, Subgraph) → [[11-Prompt-Archive/2026-04-09 GLM5 - Polymarket Event Volume]]
5. Polymarket leaderboard API → [[11-Prompt-Archive/2026-04-09 GLM5 - Polymarket Leaderboard API]]
6. CLOB WebSocket subscription model + Alchemy CU costs → [[11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU]]

## Gaps / Unknowns Identified During Review

1. **Maker/taker data in existing ClickHouse schema** — MVF metric #1 (Maker/Taker Ratio) needs maker/taker flags per trade. Do our existing ClickHouse tables store this from the scan pipeline? If not, we need to add it. The `OrderFilled` event has this data, but does our `scan` command capture and store it?

2. **Current `candidate-scan` command capabilities** — It's implemented but unclear exactly what it does. Is it a leaderboard scraper? On-chain analysis? What signals does it use? Understanding its current state determines how much we extend vs rebuild for Loop A.

3. **Watchlist storage and management** — When Loop A or Loop D promotes a wallet to the watchlist, where is it stored? Config file? ClickHouse table? How does Loop B's Alchemy subscription pick up new addresses dynamically (the Alchemy docs support adding topics to an existing subscription, but we need to design the management layer)?

4. **Loop D anomaly detector thresholds** — "Volume spike" and "price anomaly" are conceptual. Specific algorithms and thresholds need to be defined. What constitutes a "volume spike" — 3x the rolling 1-hour average? 10x? This can be calibrated empirically but needs initial values.

5. **LLM hypothesis prompt template** — We know the structure (metrics + exemplars + detectors → "propose 1-3 hypotheses") but the actual prompt hasn't been written. This is a work item, not a blocker.

6. **n8n workflow design for wallet discovery loops** — We have the RIS n8n workflow design from the previous chat. The wallet discovery pipeline needs its OWN set of n8n workflows (separate project folder in n8n). Not yet designed.

7. **Docker services for Loop B and Loop D** — These are long-running processes (WebSocket consumers). They need their own Docker service definitions in docker-compose.yml. Standard pattern per project conventions.

8. **Reconnection and missed-event handling** — CLOB WebSocket has no replay on disconnect. Loop D needs a strategy for gaps: REST backfill via `GET /trades` for missed periods, or accept small data gaps as tolerable.

## What's Ready for Roadmap

- Four-loop architecture: fully designed and researched
- Metrics engine (12-dim MVF): fully specified, ready for implementation
- Insider detection Phase 1: fully specified, ready for implementation
- LLM chunking approach: decided, ready for prompt engineering
- Data sources: all resolved (leaderboard API, CLOB WebSocket, Alchemy WebSocket, eth_getLogs)
- Cost model: confirmed $0/month on free tiers
- Build order: agreed (discovery pipeline first, SimTrader integration later)

## Cross-References
- [[08-Research/01-Wallet-Discovery-Pipeline]]
- [[08-Research/02-Metrics-Engine-MVF]]
- [[08-Research/03-Insider-Detection]]
- [[08-Research/04-Loop-B-Live-Monitoring]]
- [[08-Research/05-LLM-Chunking-Strategy]]
- [[09-Decisions/Decision - Two-Feed Architecture]]
- [[09-Decisions/Decision - Loop A Leaderboard API]]
- [[09-Decisions/Decision - Loop D Managed CLOB Subscription]]
