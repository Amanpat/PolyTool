# Development Research Index
**Purpose:** Living research notes, design decisions, and open questions for PolyTool development.
**Rule:** Claude reads and writes here. Repo docs (01-07) are read-only for Claude.

## Active Research Threads

- [[01-Wallet-Discovery-Pipeline]] — Four-loop architecture for continuous wallet scanning
- [[02-Metrics-Engine-MVF]] — 12-dimension Minimal Viable Fingerprint spec
- [[03-Insider-Detection]] — Information advantage detection system
- [[04-Loop-B-Live-Monitoring]] — WebSocket architecture for watchlist
- [[05-LLM-Chunking-Strategy]] — Hybrid metrics + exemplars approach

## Decision Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-04-09 | RIS Phase 2 conditionally closed; n8n pilot scoped to RIS ingestion only (ADR 0013) | Phase 2 shipped items verified, deferred items explicit |
| 2026-04-08 | Hybrid approach (metrics + exemplars) over map-reduce for LLM analysis | Research showed map-reduce loses subtle signals |
| 2026-04-08 | Four independent loops (A/B/C/D) over single scanning pipeline | Different timing needs per loop type |
| 2026-04-08 | Alchemy WebSocket as primary for Loop B live monitoring | Research confirmed <1-3s latency, free tier sufficient |
| 2026-04-08 | n8n for workflow orchestration, Grafana for data dashboards | Complementary roles, not competing |
| 2026-04-08 | Unified `polytool scan` command with --quick flag | Keep --flags for debug, full scan as default |

| 2026-04-09 | Two-feed architecture: CLOB WS (free, all trades) + Alchemy WS (filtered, wallet-specific) | Event volume research showed Alchemy all-events = 120M CU/mo, 4x over free tier |
| 2026-04-09 | Loop A uses Data API leaderboard endpoint for automated discovery | Public endpoint found: data-api.polymarket.com/v1/leaderboard |
| 2026-04-09 | Loop D is event-centric (CLOB detects WHAT, Alchemy identifies WHO) | Solves "scan wallet, deny it, miss their trade later" problem |

| 2026-04-09 | Loop D uses managed CLOB subscription (no wildcard mode exists) | Research confirmed per-asset subscription only |
| 2026-04-09 | Total Alchemy cost ~1.38M CU/month (4.6% of free tier) | All four loops run for $0/month |
| 2026-04-09 | CLOB `last_trade_price` has no wallet address — two-step detection confirmed | CLOB detects WHAT, Alchemy identifies WHO |

- [[06-Wallet-Discovery-Roadmap]] — Implementation roadmap v1.0 (7 phases, work packets defined)

| 2026-04-09 | Roadmap narrowed to v1 slice (Loop A + watchlist + scan consolidation + MVF only) | Architect review identified scope, LLM policy, and math issues |
| 2026-04-09 | Loop C hypotheses are exploratory only (user_data, not research partition) | Must earn promotion through existing gate system |
| 2026-04-09 | Watchlist promotion requires human review gate in v1 | LLM novelty flag is signal, not auto-trigger |
| 2026-04-09 | Insider scoring math needs correction (heterogeneous probability test) | Single binom_test with averaged p0 is mathematically wrong |


## Open Source Repo Integration (2026-04-10)

- [[07-Backtesting-Repo-Deep-Dive]] — evan-kolberg/prediction-market-backtesting (fee models, sports strategies, fill engine)
- [[08-Copy-Trader-Deep-Dive]] — realfishsam/Polymarket-Copy-Trader (LOW value, skip)
- [[09-Hermes-PMXT-Deep-Dive]] — 0xharryriddle/hermes-pmxt (LEARNINGS.md, arb matching, RIS signals)

| Date | Decision | Context |
|------|----------|---------|
| 2026-04-10 | SimTrader fee formula is WRONG (exponent 2 vs Polymarket exponent 1) | Verified via GLM-5 + Polymarket official docs |
| 2026-04-10 | Makers pay ZERO fees on Polymarket | Polymarket docs: "Makers are never charged fees" |
| 2026-04-10 | Maker rebates are pool-based daily redistribution, NOT per-fill credit | Polymarket Maker Rebates page — uses p(1-p) curve |
| 2026-04-10 | Kalshi formula: round_up(0.07 × C × P × (1-P)), no volume tiers | CFTC filing + Kalshi Help Center |
| 2026-04-10 | Defer pmxt SDK to Phase 3 (Node.js sidecar overhead) | Sidecar on port 3847 adds Docker complexity |
| 2026-04-10 | Use hybrid Jaccard + Levenshtein for cross-platform matching | Pure Jaccard has known failure modes at 40% threshold |
