---
tags: [research, roadmap, draft, awaiting-promotion]
date: 2026-04-22
status: draft
target_path: PolyTool/05-Roadmap/00-MASTER.md
---

# Roadmap v6.0 — Master Draft (Awaiting Promotion to Zone A)

> **This is a draft for Aman's review.** Once approved, Claude Code installs the content below (everything under the "BEGIN MASTER" marker) at `PolyTool/05-Roadmap/00-MASTER.md`. See the decision record [[Decision - Roadmap v6.0 Slim Master Restructure]] for context and installation steps.

> **Editing rules while it's here:** Aman edits freely in-place. Claude Project may edit in response to Aman's feedback. When ready, hand this draft to Claude Code as a work packet.

---

## BEGIN MASTER — Content below this line is the proposed `00-MASTER.md`

---
type: master-roadmap
version: 6.0
status: active
tags: [roadmap, master]
created: 2026-04-22
last_reviewed: 2026-04-22
---

# PolyTool — Master Roadmap

**Version 6.0** · Navigation entry point for all roadmap questions. Strategic spine only — implementation detail lives in phase files and system docs linked throughout.

---

## Vision

PolyTool is a self-funding, self-improving trading system for prediction markets. Three stages: **reverse-engineer** what the top wallets actually do, **simulate and validate** those strategies until profitable, and **deploy a live bot** that continuously improves itself. Polymarket first; universal platform support (Kalshi, Polymarket US Exchange) added after first sustained profit.

The system learns from five knowledge inputs: reverse-engineered wallet behavior, external research, news signals, autonomous overnight experimentation, and — once live — ground truth from its own execution.

---

## Current State (2026-04-22)

| Area | Status |
|------|--------|
| Active development phase | 1A (crypto directional) and 1B (market maker) in parallel |
| Phase 1A blocker | WebSocket CLOB migration work packet drafted, not yet executed |
| Phase 1B blocker | Gate 2 at 7/50 (14%) — `benchmark_v2` escalation past deadline, awaiting strategy decision |
| Phase 1C status | Identified as next active target (zero infrastructure dependencies) |
| RIS (Research Intelligence System) | Implemented, near-operational — see [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]] |
| Wallet Intelligence (four-loop) | v1 scope narrowed to Loop A + watchlist + unified scan + MVF only — see [[06-Wallet-Discovery-Roadmap]] |
| Fee model | v5.1 formula confirmed wrong 2026-04-10. Rewrite packet in `12-Ideas/Work-Packet - Fee Model Maker-Taker + Kalshi.md` |
| Capital stage | Stage 0 (paper / pre-capital). No live deployment yet. |

---

## Triple Track Strategy Pipeline

Three independent revenue paths running in parallel. The system only needs one to succeed.

| Track | Strategy | Capital | Time to Revenue | Detail |
|-------|----------|---------|-----------------|--------|
| **1A — Crypto Directional** | Asymmetric directional with partial hedge on 5m/15m BTC/ETH/SOL markets. Maker rebates via limit orders. (Not the original snapshot pair accumulation thesis — that was invalidated by on-chain wallet analysis.) | $50–200 to start | Shortest | [[Phase-1A-Crypto-Pair-Bot]] |
| **1B — Market Maker** | Avellaneda-Stoikov two-sided quoting on longer-duration event markets. Spread capture + Polymarket liquidity rewards. | $500+ for meaningful returns | Longest — requires tape library, calibration, shadow validation | [[Phase-1B-Market-Maker-Gates]] |
| **1C — Sports Directional** | Logistic regression on freely available NBA data, fuzzy market matching, paper predictions tracked for ≥2 weeks before capital. | $200+ for diversified positions | Medium | [[Phase-1C-Sports-Model]] |

*Phase 1A wikilink will resolve to `Phase-1A-Crypto-Directional` after Claude Code renames the file during install (see decision record work packet item 3).*

---

## Phase Order

Phases are a checklist, not a calendar. Complete sequentially. 1A/1B/1C run in parallel.

| Phase | Focus | Status | File |
|-------|-------|--------|------|
| 0 | Accounts, wallet architecture, CLAUDE.md | In progress | [[Phase-0-Accounts-Setup]] |
| 1A | Track 2 — Crypto Directional | Active | [[Phase-1A-Crypto-Pair-Bot]] |
| 1B | Track 1 — Market Maker → Gate closure → Stage 1 | Active (Gate 2 blocked) | [[Phase-1B-Market-Maker-Gates]] |
| 1C | Track 3 — Sports Directional Model | Next active target | [[Phase-1C-Sports-Model]] |
| 2 | Discovery Engine + Research Scraper (incorporates RIS + Wallet Intelligence v1) | Partially shipped | [[Phase-2-Discovery-Engine]] |
| 3 | Hybrid RAG + Kalshi + n8n | Scoped, not started | [[Phase-3-Hybrid-RAG-Kalshi-n8n]] |
| 4 | Autoresearch parameter loop | Scoped, not started | [[Phase-4-Autoresearch]] |
| 5 | Advanced strategies (resolution arb, favorite-longshot, combinatorial) | Scoped | [[Phase-5-Advanced-Strategies]] |
| 6 | Closed-loop feedback + code-level autoresearch | Scoped | [[Phase-6-Closed-Loop]] |
| 7 | Unified UI (Studio rebuild — post-profit only) | Deferred | [[Phase-7-Unified-UI]] |
| 8 | Scale + universal platform abstraction | Deferred | [[Phase-8-Scale-Platform]] |

---

## Cross-Cutting Systems

Systems that span multiple phases. Each has its own detailed doc.

| System | Role | Detail |
|--------|------|--------|
| **Research Intelligence System (RIS)** | Four-layer knowledge accumulation: ingestion → evaluation gate → knowledge store → synthesis. Makes research queryable before code is written. | [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]] |
| **Wallet Intelligence Pipeline** | Four loops — A (leaderboard discovery), B (live watchlist), C (deep analysis), D (anomaly detection). v1 scope narrowed. | [[01-Wallet-Discovery-Pipeline]], [[06-Wallet-Discovery-Roadmap]] |
| **Market Selection Engine** | Seven-factor composite scoring across all active markets every 2 hours. Routes capital by edge, not volume. | `PolyTool/02-Modules/` (to be written) |
| **Fee Model** | Per-category maker/taker fee structure. v5.1 formula was wrong; rewrite in progress. | `Claude Desktop/12-Ideas/Work-Packet - Fee Model Maker-Taker + Kalshi.md` |
| **Data Stack (ClickHouse + DuckDB)** | One rule: ClickHouse for live streaming writes, DuckDB for historical Parquet reads. They never share data. | [[01-Architecture]] |
| **Tape Library (Gold / Silver / Bronze)** | Gold = live-recorded tick. Silver = reconstructed from pmxt + Jon-Becker. Bronze = trade-level only. | [[01-Architecture]] |

---

## Core Principles

1. **Simple path first.** Raw CLI end-to-end before orchestrators. Orchestrators are convenience, not prerequisites.
2. **First dollar beats perfect system.** Any strategy generating real profit — even $1 — outranks an untested system with 500 passing tests.
3. **Triple track.** Never depend on a single strategy for revenue.
4. **Front-load context, not chat.** Conventions live in `CLAUDE.md`, `CURRENT_STATE.md`, and phase files — not chat messages.
5. **Checklist, not calendar.** No artificial deadlines.
6. **Visualize with what exists.** Grafana until revenue justifies a custom UI.
7. **Guess nothing.** Research before building. The pair accumulation pivot (weeks of work invalidated by 30 minutes of wallet analysis) is the canonical motivation.
8. **Live data must be truly live.** Polled/delayed data has already killed one bot. Execution-layer feeds use WebSocket.

---

## Human-in-the-Loop Policy

**Fully autonomous:** discovery scans, wallet scoring, L1/L2 validation, RAG writes after quality gate, parameter-level autoresearch, Track 1A execution within risk limits, kill-switch trigger on risk breach.

**Human confirmation required (Discord button):** promoting any strategy to live capital, capital stage increases, code-level autoresearch commits, REVIEW-state strategies, any LOW_CONFIDENCE flag.

**Human only:** wallet private-key operations, capital movement, infrastructure config, disabling a live strategy, adding a never-validated strategy type.

---

## Capital Progression

| Stage | Capital | Success Criterion | Next |
|-------|---------|-------------------|------|
| 0 — Paper Live | $0 | 72h dry-run, zero errors, positive PnL estimate, kill switch tested | → 1 |
| 1 — Micro | $50–500 | Positive realized PnL, no risk violations | → 2 |
| 2 — Small | $5,000 | Consistent daily positive PnL | → 3 |
| 3 — Scale-1 | $25,000 | $75–250/day, 10+ markets, first Alpha strategy live | Continue |
| 4 — Scale-2 | $100,000 | $300–800/day, multi-bot, 3+ validated strategies | Professional LP |

**Profit allocation:** 50% reinvest · 30% tax reserve · 20% compute/infrastructure.

**$POLY airdrop overlay:** real on-chain activity from Stage 0 onward, even at $1–5 trade sizes, across diverse categories.

---

## Risk Framework Overview

- **Pre-trade checks always enforced** — max position, max notional, daily loss cap, inventory skew, max single order size. Per-track limits in each phase file.
- **Five-layer kill switch hierarchy** — file flag, daily loss cap, WS disconnect, inventory limit, Discord command. Any one halts trading.
- **Wallet security** — cold wallet for capital storage (never on VPS, never in env), separate hot wallet funded only with current stage capital, USDC allowance capped at 2× stage capital.
- **Jurisdiction** — Polymarket restricts US access. Primary deployment: partner's Canadian machine. Backup: Kalshi (CFTC-regulated, US-legal). Long-term: Polymarket US Exchange when available.

Detail: [[01-Architecture]] and each phase file.

---

## Key External References

Academic: Avellaneda & Stoikov (2008), Guéant/Lehalle/Fernandez-Tapia (2013), Kelly (1956), Becker (2026) — 72.1M trade dataset, arXiv:2510.15205 (A-S for prediction markets), Karpathy autoresearch (2026).

Tools: pmxt, pmxt archive, Jon-Becker dataset, polymarket-apis, DuckDB, ClickHouse, Chroma, BGE-M3, py-clob-client, Ollama, TradingView Lightweight Charts, Tremor, Next.js.

Open-source integration notes: [[07-Backtesting-Repo-Deep-Dive]], [[09-Hermes-PMXT-Deep-Dive]].

---

## What Changed From v5.1

- Phase 1A strategy corrected from snapshot pair accumulation to directional-with-hedge (on-chain wallet analysis invalidated the original thesis).
- Research Intelligence System (RIS) added as a cross-cutting system (absent in v5.1).
- Wallet Intelligence four-loop pipeline added as a cross-cutting system (absent in v5.1).
- Fee model flagged as under rewrite (v5.1 formula was mathematically wrong).
- Gate 2 status reflected (7/50 pass, benchmark_v2 decision pending).
- Removed from master: CLI command listings, open-source repo extraction notes, tab-by-tab Studio tab map, full n8n workflow table, full risk framework tables, Phase 7/8 implementation detail, team/workflow operational details. All of these now live in their appropriate phase files or system docs.
- RAG partition count reduced from 5 to 4 (`market_data` eliminated; Gamma + ClickHouse + DuckDB already serve this role).
- v5.1 itself archived at `PolyTool/05-Roadmap/_archive/v5.1.md`. Still readable; no longer authoritative.

---

## Maintenance

- **Master changes only when strategic direction changes** (new track, phase reorder, principle update).
- **Phase files update whenever implementation reality changes.** Not reflected here.
- **`last_reviewed` date in frontmatter** — if >90 days old, assume drift and audit.

---

## END MASTER — Everything above this line is the proposed content for `00-MASTER.md`

---

## Review Notes (remove before installing)

Things Aman should specifically check:

1. **Current state table** — are the blockers accurate? Is Phase 1C really the next active target?
2. **Cross-cutting systems table** — Market Selection Engine doesn't yet have a `02-Modules/` doc. Should Claude Code be tasked to create a stub? Same question for the fee model — should it graduate out of `12-Ideas/` into `02-Modules/` once the rewrite lands?
3. **"What changed from v5.1"** — is anything missing? Any pivot or system addition I missed?
4. **Principles list** — added #7 (Guess Nothing) and #8 (Live Data) since they're explicit in your working principles but weren't in v5.1's principles section. Keep both?
5. **Cross-track ordering** — v5.1 had 1A/1B/1C running in parallel from Phase 1. Kept that. Confirm.
6. **Zone A → Zone B wikilink policy (install-blocker).** Several master links point into Zone B (`08-Research/`, `09-Decisions/`). Decision record work packet item 4 presents two options: (a) create Zone A mirror stubs for each cross-cutting system, or (b) document the exception in `Vault-System-Guide.md`. Pick one before install — Claude Code will not improvise.
7. **Phase 1A filename rename** — the existing file is `Phase-1A-Crypto-Pair-Bot.md` but the track has pivoted to directional. Work packet item 3 renames it to `Phase-1A-Crypto-Directional.md` and updates all cross-references. Confirm this is desired before install (the rename touches dev logs and CLAUDE.md references).
