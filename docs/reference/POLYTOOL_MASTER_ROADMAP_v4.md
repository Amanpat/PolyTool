# PolyTool — Master Roadmap
**Version:** 4.0 · **Date:** March 2026 · **Status:** Living Document

---

## Vision

Polymarket is populated by profitable bots whose strategies are unknown, proprietary, or require
resources unavailable to the average operator. PolyTool's mission is to close that gap through
three stages: **reverse-engineer** what the top wallets are doing, **simulate and validate** those
strategies until profitable, and **deploy a live bot** that continuously improves itself.

The end state is a self-funding, self-improving trading system: it discovers strategies
automatically, tests them in simulation, promotes the survivors to live capital, and archives
the failures with post-mortems so the same mistake is never repeated twice. The loop ingests
knowledge from three sources — reverse-engineered wallet behavior, external research and
academic material, and real-time news signals — and synthesizes all three into a continuously
improving strategy library. Over time, as the live bot generates performance data, that data
feeds back into the loop as a fourth input: ground truth from our own execution.

---

## North Star Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             POLYTOOL SYSTEM                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       n8n ORCHESTRATION LAYER                        │   │
│  │  Visual pipeline canvas · Scheduling · Workflow monitoring           │   │
│  │  Calls FastAPI (production) or CLI (dev/testing) interchangeably     │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │ HTTP calls to FastAPI                        │
│  ┌────────────────────────────▼─────────────────────────────────────────┐   │
│  │                      FASTAPI WRAPPER LAYER                           │   │
│  │  /api/candidate-scan · /api/wallet-scan · /api/alpha-distill         │   │
│  │  /api/llm-bundle · /api/simtrader/run · /api/rag-query               │   │
│  │  /api/research-scraper · /api/signals-ingest · /api/bot/status       │   │
│  │  Thin REST wrapper — no logic lives here                             │   │
│  └────────────────────────────┬─────────────────────────────────────────┘   │
│                               │                                              │
│  ┌────────────────────────────▼─────────────────────────────────────────┐   │
│  │                    PYTHON CORE LIBRARY                               │   │
│  │  All logic lives here. CLI wraps this for dev/testing.               │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐   │   │
│  │  │ AUTO         │  │ RESEARCH      │  │ KNOWLEDGE BRAIN        │   │   │
│  │  │ SCANNER      │  │ SCRAPER       │  │ (Hybrid RAG)           │   │   │
│  │  └──────────────┘  └───────────────┘  └────────────────────────┘   │   │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐   │   │
│  │  │ NEWS &       │  │ SIMTRADER     │  │ LIVE BOT               │   │   │
│  │  │ SIGNALS      │  │ ENGINE        │  │ EXECUTION              │   │   │
│  │  └──────────────┘  └───────────────┘  └────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │           POLYTOOL STUDIO — Unified Operator Dashboard               │   │
│  │  Next.js + Tremor + TradingView Lightweight Charts (localhost:8765)  │   │
│  │  Dashboard · SimTrader · Research · Bot Monitor · Signals · RAG      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### How the Layers Work Together

**Python Core** is the brain. Every business rule, data transformation, RAG operation,
SimTrader run, scraper evaluation, and LLM call lives here. It has no knowledge of n8n
or FastAPI.

**FastAPI Wrapper** is a thin REST skin over the Python core. Each endpoint calls one
CLI function and returns JSON. No logic lives here — it is purely a translation layer so
n8n can trigger Python operations over HTTP.

**n8n** is the control plane and visual pipeline. It schedules jobs, sequences multi-step
workflows, handles retries, and gives a real-time view of what the system is doing. In
production it calls FastAPI. In development you call the CLI directly.

**The CLI never goes away.** It remains the fastest way to test a single command, debug a
specific step, or run a one-off analysis. During development everything starts as a CLI
command. FastAPI endpoints are added when the feature is stable and ready for automation.

**PolyTool Studio** is the unified operator dashboard — a full React application that
surfaces every system component in one place. It does not duplicate data processing;
it presents it.

---

## The Self-Improving Loop

This is the flywheel the entire system is designed to create. Once all phases are
operational, it runs continuously without human intervention except at the explicitly
defined human gates:

```
DISCOVER (Auto Scanner, every 6h)
    ↓ New profitable wallets flagged
ANALYZE (Wallet Scan + LLM Report, automated)
    ↓ Dossier + hypothesis candidates
DISTILL (Alpha Distill, automated)
    ↓ Hypothesis registered in registry
VALIDATE (SimTrader L1 → L2 → L3, automated)
    ↓ All gates pass → [HUMAN GATE: approve for live capital]
EXECUTE (Live Bot, autonomous within risk limits)
    ↓ Real fills, real PnL
MEASURE (Weekly perf eval, automated)
    ↓ perf_ratio < 0.40 → auto-disable + post-mortem written to RAG
    ↓ perf_ratio ≥ 0.75 → performance record written to RAG
LEARN (Research RAG grows richer, new scans informed by history)
    ↓ Loop restarts with better signal
```

The Research Scraper and News/Signals pipeline run in parallel, feeding the RAG brain
continuously so that hypothesis generation and LLM analysis improve over time.

---

## Human-in-the-Loop Policy

Explicit definition of what the system does autonomously vs what requires human approval.
This is an architectural constraint, not a convention — the code must enforce it.

### Fully Autonomous (no human needed)
- Candidate wallet discovery and initial scoring
- Wallet scanning and dossier generation
- Alpha distillation and hypothesis candidate creation
- SimTrader Level 1 and Level 2 validation runs
- SimTrader Level 3 shadow run initiation
- Research scraper ingestion and RAG writes (after quality gate)
- News ingest, signal linking, reaction measurement
- Market selection scoring and capital plan updates
- Strategy parameter adjustments within pre-approved bounds
- Kill switch trigger on risk limit breach
- Performance records written to Research RAG
- Strategy AUTO_DISABLE when perf_ratio < 0.40 (with Discord notification)

### Human Confirmation Required (Discord button approval)
- **Promoting a strategy from validated to live capital** — the most important gate.
  The system sends a Discord message with [Approve] / [Reject] buttons. No capital
  moves until the operator clicks Approve. Response timeout: 48 hours, then re-alerts.
- **Capital stage increases** (Stage 1 → 2 → 3) — explicit human decision, never
  automatic. System surfaces the recommendation with supporting data.
- **Any strategy flagged LOW_CONFIDENCE by local Ollama** — routed to the Studio
  Flagged Review Queue, not auto-saved.
- **Strategy REVIEW state** (perf_ratio 0.40–0.75) — system halves allocation
  automatically, then Discord-notifies and waits for human direction.

### Human Only (never automated)
- Wallet private key operations
- Moving capital between wallets or funding the hot wallet
- Infrastructure configuration changes (AWS, RPC, secrets)
- Adding a strategy type that has never been validated in any form before
- Disabling a strategy (system can recommend, human confirms)

---

## n8n Pipeline Architecture

### What n8n Owns

n8n is responsible for the connective tissue of the system — scheduling, sequencing,
and observability of multi-step workflows. It does not process data; it directs traffic.

| Workflow | Trigger | What n8n Does |
|----------|---------|---------------|
| Candidate Discovery | Cron every 6h | Calls `/api/candidate-scan` → filters → queues new wallets |
| Wallet Scan Loop | New candidate in queue | Calls `/api/wallet-scan` → waits → triggers llm-bundle |
| LLM Report Generation | Scan complete | Calls Ollama OR flags for manual review → calls `/api/llm-save` |
| Alpha Distill | Batch scan complete | Calls `/api/alpha-distill` → writes candidates to hypothesis registry |
| SimTrader Validation | New hypothesis registered | Sequences L1 → L2 → L3 shadow run automatically |
| Research Scraper | Cron every 4h | Calls `/api/research-scraper` → evaluates content → writes to RAG |
| News Ingest | Cron every 5 min | Fetches RSS/social → calls `/api/signals-ingest` → links to markets |
| Bot Health Check | Cron every 1 min | Polls `/api/bot/status` → fires Discord alert on anomaly |
| Market Scanner | Cron every 2h | Calls `/api/market-scan` → updates capital allocation plan |
| Feedback Loop | Cron weekly | Calls `/api/strategy-review` → promotes/archives/disables strategies |
| Discord Approval Listener | Webhook from Discord | Receives button click → calls appropriate action endpoint |

### n8n Hosting
- **Phase 1–2:** Runs locally on the same machine as PolyTool.
- **Phase 3+ (live bots):** Moves to AWS alongside the live bot, co-located in the region
  closest to Polymarket's servers for lowest execution latency.

---

## LLM Policy — Self-Funding Model

The tool must earn before it spends. LLM API tokens are a cost, and no recurring cost
is acceptable until the bot is generating profit to cover it.

| Tier | Model | Cost | When Used |
|------|-------|------|-----------|
| Tier 1 | Ollama local (Llama-3-8B / Mistral) | Free | All automated hypothesis generation, research scraper evaluation. Always-on. |
| Tier 2 | Manual escalation (Claude / ChatGPT) | Free (operator tokens) | When local model flags low confidence. Dossier pre-formatted in Studio queue. Paste, get report, save via `llm-save`. |
| Tier 3 | Claude API auto-escalation | Paid API | Only enabled when `bot_profit_30d > api_cost_estimate`. Gated programmatically. Not built until bot is profitable. |

---

## RAG Architecture — Hybrid Partitioned Brain

One Chroma collection (`polytool_brain`) with five internal partition tags. One query
interface. No synchronization problems between separate systems. Each document carries
a `partition` metadata field and a `trust_tier` field. Queries can scope to one partition
or span all.

| Partition | Contains | Trust Tier | Who Writes |
|-----------|----------|-----------|-----------|
| `user_data` | Dossiers, scan artifacts, LLM reports, audit outputs | Low / Exploratory | Automated pipeline |
| `research` | Validated StrategySpecs, live performance records, failure post-mortems | High / Curated | Validation gate PASS + human confirmation only |
| `signals` | News items + measured market price reactions. Proven patterns only (≥10 events, >3% move) | Medium | Auto when pattern significance threshold met |
| `market_data` | All Polymarket markets, metadata, historical snapshots | Reference | Automated sync from Gamma + CLOB APIs |
| `external_knowledge` | Academic papers, quant research, forum strategy threads, book excerpts, blog posts evaluated by LLM scraper | Medium / Reference | Research Scraper pipeline, LLM quality gate required |

**Hard rules:**
- Nothing enters `research` without a `validation_gate_pass` artifact attached. Enforced
  at write time in code.
- Nothing enters `external_knowledge` without a scraper quality score above threshold.
  Low-scoring content stays in ClickHouse staging, never in the RAG.
- The `external_knowledge` partition informs hypothesis generation and LLM analysis
  but is never treated as ground truth — that role belongs to `research` only.

---

## UI Architecture — PolyTool Studio

### Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Framework | Next.js (React) | Component ecosystem, SSR, API routes |
| Dashboard components | Tremor | Purpose-built for metrics dashboards, Tailwind CSS, 35+ components |
| Charts | TradingView Lightweight Charts v5+ | MIT license, handles probability data (0–1) natively, real-time WebSocket updates, 447K weekly npm downloads |
| Embedded tools | Grafana + n8n via iframe | Both already have polished UIs — no reason to rebuild them |
| Backend | Existing FastAPI + Python core | No change to backend architecture |
| Real-time data | FastAPI WebSocket endpoints → Lightweight Charts `series.update()` | Sub-second updates |

### Why Not OpenBB

OpenBB Platform v4 is a data aggregation SDK (Python) paired with a proprietary closed-source
web UI (OpenBB Workspace). You cannot extract Workspace components into your own application —
it is all-or-nothing. The open-source layer (AGPLv3) requires source disclosure if modified
and served over a network. Its WebSocket support is experimental at the SDK level. It is
excellent for connecting to 100+ traditional financial data providers; it is the wrong
foundation for a custom prediction market operator console. The `jose-donato/openbb-polymarket`
project demonstrates that Polymarket data can flow into Workspace — but the UI layer is
locked. Build freely with Next.js instead.

### Probability Chart Specification

TradingView Lightweight Charts handles 0–1 probability data with zero modification:
- `SingleValueData` format `{time, value}` — no OHLCV required.
- `Baseline` series with `baseValue: { type: 'price', price: 0.5 }` automatically colors
  above-50¢ green and below-50¢ red — visually identical to Polymarket's own chart style.
- `priceFormat` formatter displays values as percentages (0.65 → "65%").
- Y-axis locked to [0, 1] via `setVisibleRange()` on `IPriceScaleApi`.
- Real-time updates: WebSocket from FastAPI → `series.update()`. Designed for thousands
  of bars with multiple updates per second.

### Studio Tab Map

Every tab has a one-sentence purpose, a defined data source, and a defined action set.
No tab does more than one thing.

| Tab | Purpose | Primary Data Source | Human Actions Available |
|-----|---------|---------------------|------------------------|
| **Dashboard** | Single-glance system health in under 10 seconds | `/api/bot/status`, ClickHouse | Arm/disarm kill switch |
| **SimTrader** | OnDemand backtesting, strategy comparison, tape library | SimTrader Engine | Run session, load tape, compare strategies |
| **Research** | Discovery pipeline — candidate queue, hypothesis registry, flagged reviews | `/api/candidate-scan`, hypothesis DB | Promote wallet, reject hypothesis, paste LLM report |
| **Bot Monitor** | Live bot real-time view — orders, fills, inventory, PnL | WebSocket `/api/bot/stream` | Kill switch, pause market |
| **Signals** | Live news feed, market links, reaction measurements | `/api/signals-ingest`, Signals RAG | Mark signal as relevant/noise |
| **Knowledge** | RAG query interface across all partitions | `/api/rag-query` | Query, scope by partition |
| **Scraper** | Research scraper feed — what was ingested, scored, accepted/rejected | `/api/research-scraper/log` | Manually submit URL for evaluation |
| **Grafana** | Grafana dashboards embedded via iframe | Grafana at its own port | Navigate within Grafana |
| **Pipelines** | n8n workflow canvas embedded via iframe | n8n at its own port | Navigate within n8n |
| **Settings** | System config, risk limits, Discord settings | Config files / `.env` | Edit limits, test Discord connection |

### Dashboard Tab — Data Points

The Dashboard tab shows everything needed to assess full system health at a glance:

- Live bot status indicator (RUNNING / STOPPED / ERROR) with uptime counter
- Daily PnL vs target (progress bar with color: green ≥100%, yellow 50–99%, red <50%)
- Open positions count and total notional exposure
- Kill switch status with arm/disarm button (requires confirmation modal)
- Active market count with breakdown by strategy
- Last candidate scan timestamp and count of new candidates
- Hypothesis registry summary: N hypotheses in testing, M validated, K archived
- Research scraper: last run time, items ingested today, `external_knowledge` partition size
- Signals partition: items added this week, last signal timestamp
- n8n workflow health widget: active workflows, last run times, any failed workflows

### SimTrader Tab — Full Specification

The SimTrader tab is the ThinkorSwim OnDemand equivalent for Polymarket. It has three
sub-views selectable by tabs within the tab:

**OnDemand Replay (manual)**
The operator selects a tape from the tape library, selects a strategy (from either the
pre-built strategy library or the hypothesis registry), and presses Play. The chart
animates the probability over time as the tape replays. Simulated orders appear on the
chart as markers. The right panel shows: running PnL, fill count, inventory, and a
real-time order book snapshot. Playback speed is adjustable (1×, 5×, 20×, max). The
operator can pause at any moment, inspect the book state, and resume. This is for
manual strategy intuition and debugging — not for automated validation.

**Strategy Comparison (automated)**
The operator selects 2–6 strategies and a shared tape set, then clicks Run. The system
instantiates N parallel SimTrader sessions against the same tapes. Each session runs
independently. Results appear in a side-by-side comparison panel: equity curves on the
same Lightweight Chart (one colored line per strategy), plus a metrics table showing
net PnL, Sharpe ratio, max drawdown, fill rate, and win rate per strategy. A winner
highlight card shows which strategy won and by what margin. This is distinct from the
existing parameter sweep, which tests parameter variations of one strategy — this tests
strategy vs strategy head-to-head.

**Tape Library**
A searchable, filterable table of all recorded tapes. Columns: market slug, category,
duration, date recorded, volatility classification (HIGH/LOW/NEAR_RESOLUTION), and
a preview thumbnail of the probability curve. Historical data sourced from:
1. Tapes recorded by the Tape Recorder from the live WS feed (starts accumulating now)
2. Kaggle Polymarket market datasets (covers thousands of markets back to 2021 — import
   once, available immediately for backtesting)
3. Gamma API historical snapshots (coarser but broad coverage, good for market selection
   testing)
Note: Kaggle data is snapshot-level, not tick-level. It is suitable for strategy-level
backtesting but not for microstructure-level spread optimization. Tick-level data only
comes from tapes recorded by the live Tape Recorder. Start recording now.

---

## Discord Notification System

### Architecture

Two-way communication via Discord. Outbound alerts use webhooks (no bot token required).
Inbound approval responses use a Discord Bot with slash commands and button components.
The two systems are separate: the webhook posts messages, the bot listens for button
clicks and maps them to FastAPI action endpoints.

### Alert Channels

| Channel | Audience | Alert Types |
|---------|----------|-------------|
| `#polytool-ops` | Operator only | Every fill, WS stall/reconnect, daily fill summary |
| `#polytool-alerts` | Operator + collaborators | Risk breaches, kill switch events, strategy disable, n8n failures |
| `#polytool-approvals` | Operator only | Hypothesis promotion requests, capital stage increase recommendations |
| `#polytool-digest` | Operator only | Daily PnL summary at midnight UTC, weekly performance report |

### Alert Tiers

**Red (requires immediate action or approval):**
- Risk limit breach (which limit, current value, threshold, action taken)
- Kill switch armed or disarmed (who triggered it, timestamp)
- Strategy AUTO_DISABLE: strategy ID, perf_ratio, one-line post-mortem, re-analysis triggered
- n8n workflow failure: workflow name, failed step, error message, retry count
- WebSocket disconnect unresolved after 3 retry attempts

**Yellow (awareness — no action required immediately):**
- New high-value candidate wallet discovered: handle, composite score, flags triggered
- Strategy enters REVIEW state (perf_ratio 0.40–0.75): strategy ID, current allocation halved
- Research scraper quality gate rejection spike (>20% rejection rate in one run)
- Signals RAG: a pattern just graduated from ClickHouse staging (worth reviewing)

**Green (informational):**
- WebSocket stall detected (yellow) and reconnect confirmed (green)
- New hypothesis registered and Level 1 validation started
- Level 3 shadow run completed, results available in Studio

**Approval Messages (button components):**

When a hypothesis passes all three validation gates, the Discord bot posts a message
to `#polytool-approvals` containing:
- Strategy ID and name
- Source wallets that generated it
- Level 1 PnL across tapes (% tapes positive, median PnL)
- Level 2 realistic-retail PnL
- Level 3 shadow run PnL vs prediction (deviation %)
- Recommended initial capital allocation
- **[✅ Approve for Live Capital]** button
- **[❌ Reject]** button
- **[🔍 View Full Report in Studio]** link

The bot listens for button clicks. On Approve, it calls `/api/strategy/promote` with the
strategy ID. On Reject, it calls `/api/strategy/archive` and asks for a rejection reason
via a follow-up text prompt. Response timeout: 48 hours. After timeout, re-alerts once.

Capital stage increase recommendations follow the same pattern with [Approve Scale] /
[Hold Current Stage] buttons.

---

## Current State — What Is Already Built ✅

### Research Pipeline (Complete)

| Component | What It Does |
|-----------|-------------|
| ClickHouse Schema + API Ingest | Stores all Polymarket trade, position, and market data locally |
| Grafana Dashboards | Visualises User Trades, Strategy Detectors, PnL, Arb Feasibility |
| `scan` CLI | One-shot ingestion + trust artifact emission per user |
| Strategy Detectors | Identifies HOLDING_STYLE, DCA_LADDERING, MARKET_SELECTION_BIAS, COMPLETE_SET_ARBISH |
| PnL Computation | FIFO realized + MTM. Fee model: 2% on gross profit |
| Resolution Enrichment | 4-stage chain. UNKNOWN_RESOLUTION < 5% |
| Segment Analysis | Breakdown by entry_price_tier, market_type, category |
| CLV Capture | Closing Line Value per position. Cache-first enrichment |
| `wallet-scan` CLI | Batch scan, composite scoring, leaderboard |
| `alpha-distill` CLI | Cross-user segment edge distillation into ranked hypothesis candidates |
| Hypothesis Registry | Register, status, experiment-init, experiment-run |
| Local RAG | Chroma vector + FTS5 lexical + RRF hybrid + cross-encoder rerank |
| LLM Bundle + Save | Evidence bundles, prompt templates, structured hypothesis.json |
| Export Dossier | memo.md + dossier.json + manifest.json per user |
| MCP Server | Claude Desktop integration |

### SimTrader (Complete)

| Component | What It Does |
|-----------|-------------|
| Tape Recorder | Records live Polymarket WS feed into deterministic replay files |
| L2 Book Reconstruction | Replays tape → exact orderbook state at any moment |
| Replay Runner + BrokerSim | Strategy receives book events, places simulated orders, fills with realistic queue model |
| Sweeps + Local Reports | Parameter grid sweeps, HTML report, batch leaderboard |
| Shadow Mode | Live WS → strategy decisions → simulated fills, no real orders |
| SimTrader Studio UI | FastAPI + vanilla HTML/JS at localhost:8765 (to be replaced in Phase 7) |
| OrderManager | Quote reconciliation, rate caps |
| MarketMakerV0 | Conservative two-sided quoting, inventory skew, binary market guards |
| Execution Primitives | KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner — dry-run default |

---

## Development Checklist

Each item below is a concrete deliverable. Items are ordered by dependency.
Check them off as they complete. Track A (execution) and Track B (research) run
in parallel starting from Phase 2.

---

### PHASE 0 — Foundation
> Complete. No items need revisiting unless a specific bug or regression is found.

- [x] ClickHouse schema and API ingest
- [x] Grafana dashboards
- [x] scan CLI and strategy detectors
- [x] PnL computation + fee model
- [x] Resolution enrichment (4-stage chain)
- [x] CLV capture (Closing Line Value)
- [x] Segment analysis
- [x] wallet-scan and batch-run
- [x] alpha-distill
- [x] Hypothesis Registry
- [x] Local RAG (Chroma + FTS5 + RRF + rerank)
- [x] LLM Bundle + Save + MCP Server
- [x] SimTrader full stack (Tapes through Shadow Mode)
- [x] SimTrader Studio UI (initial version — replaced in Phase 7)
- [x] Execution Primitives (dry-run)

---

### PHASE 1 — Track A: Live Bot
> Priority: NOW. Critical path to revenue.
> All items must be completed before any real capital is deployed.

- [ ] **MarketMakerV1 — Logit A-S upgrade**
      The current MarketMakerV0 applies the Avellaneda-Stoikov model in linear price space,
      which is mathematically incorrect for binary prediction markets where prices are bounded
      to [0,1]. The fix: transform the mid-price to log-odds space via `x = ln(p/(1-p))`,
      compute the reservation price and optimal spread entirely in that unbounded domain, then
      convert quotes back to probability space via the sigmoid function. This produces a
      critical structural advantage: the sigmoid's derivative causes spreads to naturally
      compress near the boundaries (0.05, 0.95) and expand maximally near 0.50 — exactly
      where gamma risk is highest and adverse selection is most dangerous.

      Key implementation details:
      - Inventory parameter `q` = `YES_inventory - NO_inventory` (net delta, not gross)
      - Reservation log-odds: `x_r = x_t - q·γ·σ_b²·(T-t)`
      - Optimal spread in logit space: `δ = γ·σ_b²·(T-t) + (2/γ)·ln(1 + γ/κ)`
      - Physical bid: `p_b = sigmoid(x_r - δ/2)`, ask: `p_a = sigmoid(x_r + δ/2)`
      - `σ_b` calibrated from realized variance of logit-transformed mid-prices over rolling window
      - `κ` calibrated via MLE over trade arrival distributions (SciPy `minimize`)
      - NumPy vectorized for all transforms — no Python loops in the hot path
      - Must be complete before Gate 2 sweep — incorrect spread math means sweep results
        cannot be trusted

- [ ] **Record 15+ diverse market tapes**
      Using `simtrader quickrun`, record WebSocket tapes across at least three market
      categories: high-volatility politics markets, low-volatility sports markets, and
      markets less than 48 hours old. These tapes are the test dataset for Gate 2. Without
      diverse tapes, the parameter sweep cannot demonstrate that the strategy works across
      market conditions. Begin recording immediately — tapes can only be built forward in time.
      Also initiate a one-time Kaggle dataset import during this phase to populate the tape
      library with historical market data for immediate use in the SimTrader.

- [ ] **Pass Gate 2 — Parameter sweep (≥70% positive PnL)**
      Run the MarketMakerV1 parameter grid sweep across all recorded tapes. Gate criterion:
      at least 70% of tapes show positive net PnL after the 2% fee model. The sweep produces
      a ranked config leaderboard — the top config becomes the live deployment config for
      Stage 1. Configs that pass Gate 2 must also be validated at realistic-retail latency
      (150ms, 70% fill rate, 5bps slippage) before being eligible for deployment.

- [ ] **Begin Gate 3 — 30-day shadow run**
      Start a shadow run on 3–5 live markets using the best config from Gate 2. Shadow mode
      streams real Polymarket order book data through the strategy and simulates fills without
      placing any real orders. After 30 days, compare simulated PnL to Gate 2 replay
      prediction. Gate criterion: shadow PnL within 25% of replay prediction. Gate 3 runs
      in parallel with infrastructure setup below.

- [ ] **FastAPI wrapper — first endpoints**
      Add REST endpoints for all operations n8n needs to call:
      `/api/candidate-scan`, `/api/wallet-scan`, `/api/llm-bundle`, `/api/llm-save`,
      `/api/simtrader/run`, `/api/market-scan`, `/api/bot/status`, `/api/bot/stream`
      (WebSocket for real-time bot data), `/api/strategy/promote`, `/api/strategy/archive`.
      Each endpoint is a thin wrapper around the existing CLI function — no new logic here.

- [ ] **n8n local setup**
      Install and configure n8n locally. Build the first two workflows:
      (1) Market Scanner — every 2 hours, calls `/api/market-scan`, outputs capital plan.
      (2) Bot Health Check — every 1 minute, polls `/api/bot/status`, fires Discord alert
      on anomaly. This establishes the n8n-to-FastAPI connection and validates the
      integration before more complex workflows are built.

- [ ] **Market Selection Engine**
      A scoring system that runs every 2 hours and ranks all active Polymarket markets by
      profitability for market making. Scoring factors: estimated reward APR from the Gamma
      API rewards program, current spread vs minimum profitable spread, 24-hour volume as
      fill-frequency proxy, number of active competing market makers, and a bonus for markets
      less than 48 hours old (these earn 80–200% APR in rewards). Pre-filters remove
      near-resolution markets, low-volume markets, and markets without an active reward
      program. Output is a ranked JSON file and capital allocation plan consumed by the bot
      and displayed in the Studio Dashboard tab.

- [ ] **Infrastructure setup (VPS + RPC + secrets)**
      Provision a VPS in a NY/NJ datacenter for lowest latency to Polymarket's CLOB servers.
      Set up a dedicated Polygon RPC node (Chainstack or Alchemy) — public nodes throttle
      and drop WebSocket connections under live trading conditions. Configure all secrets in
      `.env` (PK, CLOB_API_KEY, CLOB_API_SECRET, CLOB_API_PASSPHRASE, DISCORD_WEBHOOK_URL,
      DISCORD_MENTION_IDS, DISCORD_BOT_TOKEN). Never in code, never in git.

- [ ] **Grafana live-bot panels**
      Add new Grafana panels for live bot monitoring: open orders count, fill rate per market,
      inventory skew over time, daily PnL (realized vs target), kill switch status, and active
      market count. These panels are embedded later in Studio's Grafana tab. Without them,
      the operator is flying blind during Stage 1.

- [ ] **Discord alert system — Phase 1 (outbound only)**
      Implement outbound Discord alerts via webhook. No bot token required for this phase —
      just `requests.post()` to the webhook URL. Alert channels: `#polytool-ops` (operator
      fills and WS events), `#polytool-alerts` (shared risk/infrastructure alerts),
      `#polytool-digest` (midnight daily summary). All alerts use Discord embeds with color
      coding: green = info, yellow = warning, red = critical. Alerts must fire within 30
      seconds of the event. This is the foundation; the two-way approval system is added
      in Phase 2.

      Operator-only alerts (`#polytool-ops`):
      - Every fill: token, side, price, size, market slug, cumulative daily PnL
      - WebSocket stall/disconnect (yellow) and reconnect confirmed (green)

      Shared alerts (`#polytool-alerts`, @mention both operator and collaborator):
      - Risk limit breach: which limit, current value, threshold, action taken
      - Kill switch armed or disarmed: timestamp, trigger source
      - Daily PnL summary at midnight UTC: realized PnL, fill count, active markets, rewards estimate
      - n8n workflow failure: workflow name, failed step, error message, retry count
      - Weekly performance report: per-strategy PnL vs prediction, capital changes

- [ ] **Stage 0 — Paper Live (72-hour dry-run)**
      Run the full execution stack in dry-run mode for 72 consecutive hours on the top-ranked
      markets from the Market Selection Engine. Verify zero errors, positive PnL estimate,
      kill switch functioning, WebSocket reconnection working, and Discord alerts firing.
      This is the final dress rehearsal before real capital.

- [ ] **Stage 1 — $500 live deployment**
      Deploy $500 USDC to a dedicated hot wallet. Enable `--live` flag. Risk limits: $500
      max position per market, $200 max single order, $100 daily loss cap, $400 inventory
      skew limit. Target 3–5 markets from Tier 1 (new markets) and Tier 2 (reward markets).
      Operate for 7 days. Success criterion: positive realized PnL plus rewards after 7 days
      with no risk manager violations.

      **Adverse selection protection layer (built into Stage 1 risk manager):**
      Two real-time signals monitored continuously alongside standard OFI:
      (1) VPIN — segment trade data into fixed-volume buckets, measure directional imbalance
      per bucket. Normalize volume anomalies by market open interest, not rolling daily
      average. When VPIN exceeds threshold, widen spreads or cancel resting orders immediately.
      (2) Competing market maker cancellation mimicry — if resting liquidity on one side
      evaporates within milliseconds, do not remain as sole liquidity provider. Mimic the
      defensive posture instantly. This is an inverted but equally reliable toxicity signal.

- [ ] **Stage 2 — $5,000 scale**
      After Stage 1 success criterion met. Expand to 8–10 markets. Increase risk limits
      proportionally. Two weeks operating period. Success criterion: consistent daily positive
      PnL and all risk controls proven under real fill conditions.

---

### PHASE 2 — Track B: Automated Discovery Engine + Research Scraper
> Runs in parallel with Phase 1 from Week 3 onward.
> Two goals: (1) system finds profitable wallets automatically; (2) research scraper
> begins building the external_knowledge RAG partition immediately so it has months
> of indexed material before it is needed by hypothesis generation.

- [ ] **Candidate Scanner CLI (`candidate-scan`)**
      A CLI command that queries Polymarket's public APIs and the Polymarket Subgraph to
      surface wallets worth investigating. Applies nine candidate signals:
      1. New account with large position (insider signal — hard-flagged regardless of score)
      2. Unusual market concentration
      3. Consistent early entry
      4. High CLV across many positions
      5. COMPLETE_SET_ARBISH detector flag
      6. Statistical win-rate outlier
      7. Louvain community detection (Asset Transfer Graph on Polygon — maps treasury wallet
         distributing gas to execution addresses before major events. Library: `python-louvain`
         or `networkx` + `community`)
      8. Jaccard similarity clustering (intersection-over-union of markets traded across
         wallet pairs. Threshold: Jaccard > 0.7 across ≥5 shared markets = coordinated cluster)
      9. Temporal coordination detection (time-to-execution intervals between gas receipt
         and first trade. Sub-100ms variance across 10+ wallets = single algorithmic engine)

- [ ] **n8n — Candidate Discovery Workflow**
      n8n cron every 6 hours → calls `/api/candidate-scan` → compares against already-scanned
      wallets → queues new candidates. Operator can pause the queue or manually promote a
      wallet to priority scan from the Studio Research tab.

- [ ] **n8n — Wallet Scan + LLM Report Workflow**
      For each new candidate in the queue: calls `/api/wallet-scan` → waits → calls
      `/api/llm-bundle` → sends to local Ollama model → evaluates confidence score →
      if high confidence: calls `/api/llm-save` automatically → if low confidence: writes
      to flagged review queue visible in Studio Research tab.

- [ ] **Local Ollama integration**
      Integrate Ollama (Llama-3-8B or Mistral) as the local LLM for automated hypothesis
      generation. The model receives the formatted dossier bundle and returns a structured
      hypothesis.json. A confidence scoring heuristic evaluates output quality — vague or
      internally inconsistent hypotheses are flagged, not saved. Free, private, always-on.

- [ ] **n8n — Alpha Distill Workflow**
      After every wallet-scan batch: calls `/api/alpha-distill` → filters candidates meeting
      cross-wallet persistence threshold (pattern in ≥5 wallets with positive CLV) →
      automatically registers qualifying candidates as new hypotheses → triggers SimTrader
      Level 1 validation.

- [ ] **Discord bot — two-way approval system**
      Upgrade the alert system from outbound-only webhooks to a Discord Bot with button
      components. The bot listens on a webhook for button click events. When a hypothesis
      passes all validation gates, the bot posts to `#polytool-approvals` with strategy
      summary and [✅ Approve for Live Capital] / [❌ Reject] buttons. Button click maps
      to a FastAPI action endpoint. Rejection triggers a text follow-up asking for reason.
      48-hour response timeout with re-alert. This is the primary human-in-the-loop
      interface — the operator approves strategy promotions from Discord without opening
      Studio.

- [ ] **LLM-Assisted Research Scraper**
      A new pipeline that continuously ingests external knowledge into the `external_knowledge`
      RAG partition. The scraper runs every 4 hours via n8n and operates in two stages:

      **Stage A — Fetch:** Collect raw content from target sources:
      - ArXiv (market microstructure, prediction markets, ML finance — query via API)
      - Reddit: r/algotrading, r/Polymarket, r/quant (via Reddit API / PRAW)
      - Polymarket documentation and changelog (feedparser)
      - GitHub READMEs of relevant open-source bots (curated list in config)
      - Medium / Substack posts (RSS feeds from curated authors)
      - Manually submitted URLs via the Studio Scraper tab

      Do NOT auto-scrape: full commercial textbooks (legal exposure), Twitter/X
      (ToS violation and API cost), any paywalled content. For books and academic
      PDFs the operator manually uploads them via Studio — the scraper evaluates and
      indexes them but does not fetch them autonomously.

      **Stage B — LLM Evaluation:** Each fetched document is passed through Ollama with
      a structured evaluation prompt. The model scores the document on four dimensions
      (0–10 each): relevance to prediction market trading, presence of actionable math
      or mechanism, source credibility, and novelty against what is already indexed.
      Documents scoring below a configurable threshold (default: 28/40 total) are
      discarded and logged. Documents above threshold are chunked, embedded, and written
      to the `external_knowledge` partition with metadata: source URL, date, topic tags,
      quality score, and a 2-sentence LLM summary.

      **Quality control:** The Studio Scraper tab shows a daily log of everything evaluated:
      source, title, score breakdown, and accept/reject outcome. The operator can manually
      override a rejection or flag a source domain to always-accept or always-reject.
      Start with high-quality structured sources (ArXiv, Polymarket docs, GitHub READMEs)
      and open up messier sources (Reddit, forums) only after the quality gate is validated
      to be working.

      Building this in Phase 2 (not later) means the `external_knowledge` partition has
      months of indexed material before it is needed intensively by hypothesis generation
      in Phases 3–5.

- [ ] **n8n — Research Scraper Workflow**
      n8n cron every 4 hours → calls `/api/research-scraper` → logs accept/reject outcomes
      → Discord yellow alert if rejection rate > 20% in one run (possible source quality
      degradation). Separate daily digest of items ingested, visible in Studio Scraper tab.

---

### PHASE 3 — Hybrid RAG Brain
> Replaces the current local RAG with the five-partition unified knowledge layer.
> Existing `kb/` data is migrated in during this phase.

- [ ] **Unified Chroma collection (`polytool_brain`)**
      Migrate all existing `kb/` content into a single Chroma collection with five partition
      tags (`user_data`, `research`, `signals`, `market_data`, `external_knowledge`). Write
      policy enforcement added at ingest time — `research` partition gate is programmatic,
      not a convention. Existing RAG queries continue to work via the same CLI commands,
      now pointing at the unified collection.

- [ ] **Market Data partition + Polymarket full store**
      Automated sync of all active Polymarket markets, metadata, historical price snapshots,
      and resolution outcomes into the `market_data` partition. Sources: Gamma API (market
      discovery, rewards config), CLOB API (live orderbook snapshots), ClickHouse (add RAG
      indexing to existing store). This partition is the reference layer for backtesting,
      market selection scoring, and pattern matching.

- [ ] **Signals ingest pipeline — repurpose existing project**
      The senior developer's news ingest project (Discord, Reddit, Twitter/X) collects from
      those sources already. Repurposing work:
      (1) Audit the storage layer — if ChromaDB, plug directly into `signals` partition;
      if Postgres or flat files, add a translation adapter.
      (2) Replace the stock ticker market resolver with a Gamma API market lookup.
      (3) Add RSS feeds not currently in the stack (AP, Reuters, BBC, ESPN, Bloomberg) via feedparser.
      Do not rebuild what exists — review the code first and map what carries over.

- [ ] **Market linker (signals → Polymarket markets)**
      For each ingested signal, extract named entities and match to relevant active Polymarket
      markets via Gamma API `/markets?keyword=<entity>`. Ambiguous matches use a local LLM
      disambiguation step: "does this news affect this market? confidence 0–1." Confidence
      score stored with the signal-market link in ClickHouse. Locate the exact insertion
      point in the existing codebase (where entities are currently resolved to assets) and
      replace the ticker resolver with the Gamma API call.

- [ ] **Reaction measurement (price change tracking)**
      For every linked signal, a scheduled job records the Polymarket market price at
      t+5min, t+30min, and t+2hr after the signal timestamp. Calculates `price_change_5min`,
      `price_change_30min`, and `max_move_30min`. This transforms a news feed into a
      trading signal database. Without measuring actual reactions, no signal type can be
      proven effective.

- [ ] **Signals partition write (proven patterns only)**
      A pattern graduates from ClickHouse staging to the Signals RAG partition only when the
      same signal type + market category shows `market_moved_pct > 3%` in 10 or more
      historical events. Below that threshold the data stays in ClickHouse for accumulation.
      This keeps the Signals partition high-signal — no noise.

- [ ] **n8n — News Ingest Workflow**
      n8n cron every 5 minutes → fetches RSS feeds → calls `/api/signals-ingest` → market
      linker runs → stores in ClickHouse. Separate cron every 5 minutes checks for signals
      that now have enough reaction history to qualify for Signals partition graduation.
      Full pipeline visible in n8n canvas with per-source success/failure counts.

---

### PHASE 4 — SimTrader Validation Automation
> Automates the hypothesis → validated StrategySpec progression.
> Removes manual CLI steps from the validation pipeline.

- [ ] **strategy-codify (StrategySpec → runnable code)**
      Takes a StrategySpec JSON from alpha-distill and produces a runnable SimTrader strategy
      class. For market-making and copy-wallet strategies the output is complete and
      immediately runnable. For arb and information-advantage strategies it produces a skeleton
      class with clearly marked implementation hooks. Eliminates manual translation of
      hypothesis into code before testing.

- [ ] **Kaggle dataset import + tape normalization**
      One-time import of the Kaggle Polymarket market datasets into the tape library.
      Kaggle data is snapshot-level (not tick-level) — normalize it into the same replay
      format used by live-recorded tapes, but tag it as `source: kaggle` so users know it
      lacks tick-level microstructure. This gives the SimTrader a library of thousands of
      historical markets immediately, without waiting for the Tape Recorder to build up
      a library over months. Tick-level strategies still require live-recorded tapes;
      strategy-level PnL testing can use Kaggle data today.

- [ ] **Auto Level 1 validation (multi-tape replay)**
      When a new hypothesis is registered and a StrategySpec is codified, automatically run
      it against 20+ diverse tapes from the tape library (mix of live-recorded and Kaggle
      data). Compute net PnL after fees for each tape and check the gate criterion (≥70%
      positive). Failed strategies get a post-mortem stub automatically generated and
      written to the `research` partition — prevents re-testing the same dead-end.

- [ ] **Auto Level 2 validation (scenario sweep)**
      If Level 1 passes, automatically run the scenario sweep with four latency profiles:
      base case (0ms, 100% fills), realistic retail (150ms, 70% fills, 5bps slippage),
      degraded (500ms, 40% fills), and worst case (1000ms, 20% fills). Gate criterion:
      profitability at realistic-retail. Strategies profitable only at base case are flagged
      as requiring low-latency infrastructure before deployment — not discarded, noted.

- [ ] **Auto Level 3 — 30-day shadow run trigger**
      If Level 2 passes, automatically start a 30-day shadow run on live markets. At day 30,
      compare shadow PnL to Level 1 replay prediction. Gate criterion: within 25% deviation.
      Higher deviation means the replay model is not accurately capturing live market
      conditions — strategy needs revision.

- [ ] **Research partition write on gate pass + Discord approval**
      When all three levels pass, the StrategySpec, validation report, and shadow performance
      record are written to the `research` partition. The Discord bot immediately posts the
      approval request to `#polytool-approvals` with full metrics and [Approve] / [Reject]
      buttons. No capital moves until the operator clicks Approve.

- [ ] **n8n — Validation Pipeline Workflow**
      n8n sequences the three validation levels with appropriate waits and gate checks.
      Visual pipeline shows current hypothesis, which level it is at, pass/fail status, and
      estimated completion time for Level 3. Operator can pause, inspect artifacts, or
      manually fail a hypothesis from the n8n canvas or Studio Research tab.

---

### PHASE 5 — Advanced Strategies
> Activate after Phase 3 (RAG Brain) has produced validated StrategySpecs.
> Each strategy below is a separate deliverable, independently deployable.

- [ ] **Resolution Timing Arb (with oracle attack EV adjustment)**
      Monitors the UMA Optimistic Oracle v3 on Polygon for `AssertionMade` events on the
      `UmaCtfAdapter` contract at `0x157Ce2d672854c848c9b79C49a8Cc6cc89176a49`. When UMA
      proposes YES=1.0 but the market still trades at 0.85–0.92, the difference is
      theoretically risk-free profit during the 2-hour liveness window. The existing
      `OnChainCTFProvider` already reads Polygon RPC state — a data advantage over Gamma API
      which lags by minutes.

      EV formula must now discount for oracle manipulation risk (March 2025 precedent —
      5M UMA tokens / 25% voting power forced a false $7M resolution):
      `EV = P(true_event)·P(honest_vote) + P(false_event)·P(attack) − entry − gas − opportunity_cost`

      Monitor UMA voting power concentration on-chain before taking positions. Avoid heavy
      exposure into DVM escalation (48–72hr Ethereum mainnet vote, capital fully illiquid)
      on controversial high-value markets where attack incentive exceeds bond cost. The 750
      USDC bond is trivial relative to a $7M market. If `AssertionDisputed` fires, evaluate
      hold vs exit based on real-time UMA token concentration.

- [ ] **Combinatorial / Correlation Arb**
      Monitors pairs of logically related markets (e.g., candidate X wins primary + candidate
      X wins general). When implied joint probability diverges from historical correlation,
      enter a position in the underpriced direction. Correlation divergences persist for
      minutes — executable at retail latency without co-location. Covariance between binary
      events i and j: `Cov(i,j) = P(i∩j) − P(i)·P(j)`. For logically linked markets where
      i is a prerequisite for j, joint probability simplifies deterministically.

- [ ] **Information Advantage (news-driven directional)**
      When a news event has a clear, high-confidence directional impact on a specific market
      and the market price has not yet moved, enter a directional position. Signal only fires
      if: local LLM confidence > 0.75, market has not yet moved more than 1%, and the signal
      type + category has a proven pattern in the Signals RAG partition (≥10 historical
      events with >3% moves). This gate prevents trading on noise. The `external_knowledge`
      partition supplements the LLM's domain knowledge for classification.

- [ ] **15-Minute Crypto Markets (flash crash mean reversion)**
      Polymarket posts BTC/ETH/SOL up/down markets resolved by Chainlink at 15-minute
      intervals. If the price drops more than a threshold percentage in the first 5 minutes
      of the bar, historical data shows >70% probability of mean reversion before bar close.
      Resolution is fully deterministic via Chainlink oracle. Note: Polymarket introduced
      dynamic taker fees (up to ~3%) on these markets to curb latency arb — verify current
      fee structure before deploying capital here.

- [ ] **Gnosis CTF atomic conversion arb (multi-outcome markets)**
      In categorical multi-outcome markets (e.g., 5-candidate election), the Gnosis CTF
      allows atomic conversion: buy NO shares across a subset of outcomes and convert to YES
      shares for all remaining outcomes plus extract USDC collateral, in a single atomic
      transaction. When the sum of all YES probabilities drops below $0.98 or rises above
      $1.02, this conversion is mathematically risk-free profit. Monitor implied sum
      continuously. When threshold is breached, halt standard quoting and execute the
      conversion arb. This arb is enforced by smart contract math — it cannot be front-run
      once initiated atomically on-chain.

- [ ] **Favorite-longshot bias exploitation**
      Prediction markets exhibit a persistent structural anomaly: retail participants
      systematically overprice low-probability tail events (1–5¢ YES contracts) in pursuit
      of lottery-style payoffs, while underpricing high-probability outcomes. The edge:
      systematically provide liquidity as the seller on extreme tail events, capturing the
      overpricing premium. Apply fractional Kelly sizing (quarter-Kelly to half-Kelly) to
      bound losses from the occasional true tail event resolution. Best applied in sports
      and entertainment markets where behavioral bias is most pronounced.

---

### PHASE 6 — Closed-Loop Feedback
> The system improves itself continuously without human intervention.

- [ ] **Weekly strategy performance evaluation**
      Every 7 days, compute `perf_ratio = live_pnl_7d / predicted_pnl_from_validation`.
      Three outcomes:
      - KEEP (ratio ≥ 0.75): write performance record to `research` partition, Discord green
      - REVIEW (ratio 0.40–0.75): reduce capital allocation 50%, Discord yellow alert awaiting
        human direction, strategy continues at reduced size
      - AUTO_DISABLE (ratio < 0.40): remove from live bot, write post-mortem to `research`
        partition, trigger re-run of `alpha-distill` on source wallets — they may have adapted,
        Discord red alert

- [ ] **Live execution data feeds back into the loop**
      As the live bot accumulates fills, this creates a fourth input stream into the discovery
      loop: ground truth from our own execution. Every resolved position writes a record to
      ClickHouse: strategy ID, market, entry price, exit price, PnL, fill latency, VPIN at
      entry, and spread at entry. This data is the highest-quality signal in the system —
      it came from real capital on real markets. The alpha-distill command is updated to
      also consume this table, surfacing patterns in what our own bot does vs does not do
      profitably. Over time, the bot becomes its own best teacher.

- [ ] **Performance records in Research RAG**
      Every week, write a performance record for each active strategy to the `research`
      partition. After 6 months this partition contains a complete track record: which
      strategies worked, when they stopped working, why, and what replaced them. This is
      the primary long-term competitive advantage of the system.

- [ ] **Source wallet re-analysis trigger**
      When a strategy is auto-disabled, re-run `candidate-scan` and `wallet-scan` on the
      source wallets that generated it. Profitable wallets adapt over time. Re-analysis
      may surface a new pattern in the same wallet — the alpha is still there, just changed
      form. This closes the discovery loop automatically.

- [ ] **n8n — Feedback Loop Workflow**
      n8n cron weekly → calls `/api/strategy-review` for each active strategy → routes to
      KEEP/REVIEW/AUTO_DISABLE → updates capital allocation plan → triggers re-analysis if
      needed → posts Discord weekly performance digest. Full audit trail in n8n canvas.

---

### PHASE 7 — Unified UI (PolyTool Studio Rebuild)
> Replace the existing vanilla HTML/JS SimTrader Studio with a full React application.
> The existing Studio is a prototype. This phase builds the operator tool it should have
> been from the start.
>
> Stack: Next.js + Tremor + TradingView Lightweight Charts v5+
> Grafana and n8n embedded as iframes — not rebuilt.

- [ ] **Project scaffold and design system**
      Initialize a Next.js project inside the PolyTool repo under `/studio-v2`. Install
      Tremor for dashboard components and TradingView Lightweight Charts for probability
      visualization. Configure Tailwind CSS. Establish the sidebar navigation layout with
      all tab names from the Studio Tab Map above, each with a one-sentence tooltip
      description visible on hover. Every tab must be clearly labeled and self-explanatory —
      no unexplained file names, no mystery tabs. Dark theme to match the aesthetic of
      Grafana and n8n which will be embedded alongside.

- [ ] **Dashboard tab**
      Implement the system health overview using Tremor KPI cards, progress bars, and status
      badges. All data sourced from polling `/api/bot/status` every 10 seconds. Metric cards:
      bot status, daily PnL vs target (color-coded), open positions, kill switch status,
      active markets, candidate scan last run, hypothesis registry summary, scraper stats,
      signals stats. Kill switch card includes arm/disarm button with a confirmation modal
      that requires typing "CONFIRM" before activation. n8n workflow health widget shows
      which workflows are active and their last run times.

- [ ] **Bot Monitor tab**
      Real-time view of the live bot using a WebSocket connection to `/api/bot/stream`.
      Left panel: open orders table per market (side, size, price, age). Center panel:
      probability chart using Lightweight Charts Baseline series showing mid-price movement
      for the currently selected market in real time. Right panel: fill log (last 50 fills),
      inventory skew gauge, and daily PnL attribution bar chart. Risk limit gauges at the
      bottom show how close to each limit the bot currently sits, color-coded green → yellow
      → red as limits approach. Kill switch button present but requires the same confirmation
      modal as the Dashboard tab.

- [ ] **SimTrader tab**
      Three sub-tabs: OnDemand, Strategy Comparison, and Tape Library.

      OnDemand: strategy selector dropdown (all validated strategies + all hypothesis registry
      entries), tape selector from the library, playback controls (play/pause/speed), a
      Lightweight Charts probability chart animating the replay, and a right-panel showing
      running PnL, fills, and inventory. Operator can pause at any frame and inspect the
      simulated order book state.

      Strategy Comparison: select 2–6 strategies and a shared tape set, click Run, watch N
      parallel sessions execute. Results display as overlapping equity curves on one
      Lightweight Chart (one color per strategy) plus a sortable metrics table (net PnL,
      Sharpe, max drawdown, fill rate, win rate). A winner summary card highlights the
      top-performing strategy and its margin of victory.

      Tape Library: searchable table of all tapes — live-recorded and Kaggle-imported.
      Columns: market slug, category, duration, date, volatility classification, data source.
      Each row includes a small Lightweight Charts thumbnail of the probability curve.
      Bulk-select tapes for use in Strategy Comparison runs.

- [ ] **Research tab**
      Left panel: candidate scan queue — wallets discovered, score, flags, scan status
      (queued / scanning / complete / failed). Operator can manually promote a wallet to
      priority, skip a wallet, or manually trigger a scan. Center panel: hypothesis registry
      table — hypothesis ID, source wallets, current validation level, pass/fail status,
      predicted PnL. Clicking a row expands it to show the full validation trace. Right
      panel: Flagged Review Queue — wallets where Ollama flagged low confidence. Each card
      shows the pre-formatted dossier, confidence score, and a text area to paste a manual
      LLM report. Save button calls `llm-save`. Quick link to n8n canvas for the underlying
      workflow.

- [ ] **Signals tab**
      Live feed of ingested news signals, newest first. Each card shows: headline,
      source, timestamp, linked Polymarket markets (with their current prices), LLM
      confidence score for the market link, and reaction measurements as they arrive
      (t+5min, t+30min, t+2hr price changes). Cards for signals that match proven Signals
      RAG patterns are highlighted with a colored border. The operator can see in real time
      which news is being detected, whether the market linker is working, and which signal
      types are producing market moves.

- [ ] **Knowledge (RAG) tab**
      A query interface for the full RAG brain. Text search box, partition scope selector
      (all / user_data / research / signals / market_data / external_knowledge), and result
      cards showing: source, partition, trust tier badge, date, relevance score, and a
      2-sentence summary. Lets the operator query the knowledge brain from the UI without
      using the CLI. Supports queries like "what do we know about wallets concentrating on
      political markets near resolution?" or "what does external_knowledge say about
      favorite-longshot bias?"

- [ ] **Scraper tab**
      Daily log of everything the research scraper evaluated: source URL, title, score
      breakdown (relevance, actionability, credibility, novelty), and accept/reject outcome.
      Rejection rate chart over time (Lightweight Charts area series). A URL submission
      form for the operator to manually submit a URL for immediate evaluation. Domain
      override controls: always-accept and always-reject lists. Stats card: total items
      indexed, total rejected, `external_knowledge` partition size, last run time.

- [ ] **Grafana embed tab**
      Grafana dashboards embedded via iframe. A tab selector within the tab lets the
      operator switch between the existing dashboards (User Trades, Strategy Detectors,
      PnL, Arb Feasibility) and the new live-bot panels added in Phase 1. Grafana continues
      to run independently — Studio just frames it.

- [ ] **Pipelines tab**
      n8n workflow canvas embedded via iframe. The operator can see, pause, or inspect any
      workflow without leaving Studio. A status summary widget above the iframe shows
      which workflows are currently active and their last run/failure states.

- [ ] **Settings tab**
      System configuration without editing files manually. Sections: Risk Limits (editable
      fields for each limit with a Save button that writes to config), Discord Settings (test
      alert button, channel assignment, mention IDs), Market Selection (scoring weight sliders,
      pre-filter thresholds), Research Scraper (quality score threshold, source enable/disable
      toggles), and LLM Policy (which tier is active, Ollama model selection).

- [ ] **Retire old Studio**
      Once the new Studio is stable and all functionality is replicated, retire the vanilla
      HTML/JS Studio at localhost:8765. Both can run simultaneously during transition.
      The new Studio takes over the port when the old one is confirmed redundant.

---

### PHASE 8 — Scale Architecture
> Activate after 3+ validated strategies running and feedback loop operational.

- [ ] **Multi-bot capital manager**
      A central Capital Manager process overseeing three specialised bots:
      - Market Maker Bot: 70% of capital, 20–50 markets simultaneously
      - Alpha Bot: 20% of capital, discovered strategies from Research RAG
      - Resolution Arb Bot: 10% of capital, UMA oracle monitoring
      The Capital Manager enforces portfolio-level risk limits that cap total exposure
      regardless of what individual bots are doing.

- [ ] **Multivariate Kelly position sizing**
      Replace fixed position sizes with the multivariate Kelly formulation for correlated
      binary positions. Naive single-asset Kelly applied independently to linked markets
      dangerously amplifies portfolio volatility. Correct formulation: maximize expected
      log utility via `f* = Σ⁻¹ · μ` where `Σ` is the covariance matrix of binary outcomes
      and `μ` is the vector of expected edges. Covariance between binary events i and j:
      `Cov(i,j) = P(i∩j) − P(i)·P(j)`, derived from joint probabilities — not historical
      returns. Apply Ledoit-Wolf shrinkage to `Σ` before inversion to prevent extreme
      leverage during estimation errors. Use quarter-Kelly to half-Kelly global scaling.
      Implementation: `sklearn.covariance.LedoitWolf`, `numpy.linalg.inv`.

- [ ] **Adverse selection detection at scale**
      Three detection signals at scale beyond Stage 1:
      (1) Order Flow Imbalance: if 80%+ of fills in 5 minutes are one-sided, widen spreads.
      (2) Large order eating deep into book: single order > 5× our size, widen spreads temporarily.
      (3) Rapid mid-price movement after our fill: we were adversely selected — track in
      ClickHouse and adjust gamma parameter `γ` upward for that market type. Price impact
      in prediction markets scales with the Jacobian of the logit transform: adverse selection
      is exponentially more dangerous near 0.50 where the sigmoid derivative peaks.

- [ ] **AWS deployment**
      Move live bots to AWS region closest to Polymarket CLOB servers. Move n8n alongside.
      Provision dedicated Polygon RPC. Establish monitoring and alerting at infrastructure
      level (CloudWatch or equivalent) in addition to application-level Discord alerts.
      Studio remains accessible to the operator remotely via HTTPS.

- [ ] **Sub-millisecond execution hardening**
      Three optimizations for production:
      (1) CPU thread pinning — bind WebSocket ingest, strategy computation, and order
      execution to isolated dedicated cores via `os.sched_setaffinity()`.
      (2) Pre-compute invariant EIP-712 signature hash components at startup, storing
      domain separator and type hash bytes so only variable order fields require hashing
      per submission.
      (3) Replace `eth_account` Python crypto with C++ bindings for elliptic curve signing
      (via `coincurve` or equivalent). Combined: order submission latency from ~50ms to
      sub-5ms — critical for adverse selection evasion during high-volatility events.

- [ ] **Tier 3 LLM auto-escalation (funded by bot profit)**
      Enable automatic Claude API calls for flagged high-value wallets once
      `bot_profit_30d > api_cost_estimate` is consistently true. Gate is programmatic —
      the system checks profitability before spending tokens. Eliminates the last manual
      step in the discovery pipeline for priority wallets.

---

## Risk Framework

### Pre-Trade Checks (always enforced, all stages)

| Check | Stage 1 Default | What It Prevents |
|-------|----------------|-----------------|
| Max position per market | $500 USDC | Single market concentrates too much capital |
| Max total notional | 80% of USDC balance | Bot locks all capital, no liquidity buffer |
| Max single order size | $200 USDC | Misconfigured order enters at enormous size |
| Daily loss cap | $100 USDC | Strategy broken for today — limits maximum bleed |
| Inventory skew limit | $400 USDC abs(long–short) | Market moving against inventory — stops compounding |

### Kill Switch Hierarchy (five layers, checked in order)

1. **File kill switch** — `touch artifacts/simtrader/KILL` — checked before every order
2. **Daily loss cap** — RiskManager blocks all new orders when `daily_pnl < −cap`
3. **WS disconnect** — event loop detects `ConnectionClosed` → `emergency_stop()` → cancel all → exponential backoff
4. **Inventory limit** — strategy returns `cancel_all` action when `abs(inventory_usdc) > max`
5. **Discord command** — operator sends `/stop` in #polytool → Discord bot triggers `arm_kill_switch()` remotely

### Wallet Security

- Primary capital: cold storage hardware wallet. Never on VPS. Never in `.env`.
- Trading hot wallet: separate wallet funded with only the current stage capital.
- API key: derived once from private key via `py-clob-client`. Trading key ≠ funded address.
- USDC allowance: one-time approval limited to 2× current stage capital.

### Regulatory Note

Polymarket restricts access from certain jurisdictions including the United States.
Verify operating jurisdiction before deploying any live capital. PolyTool does not
constitute legal or financial advice. All trading is the sole responsibility of the operator.

---

## Capital Progression

| Stage | Capital | Duration | Success Criterion | Next Action |
|-------|---------|----------|------------------|------------|
| 0: Paper Live | $0 (dry-run) | 72 hours | Zero errors, positive PnL estimate, kill switch + reconnect tested | → Stage 1 |
| 1: Micro | $500 USDC | 7 days | Positive realized PnL + rewards. No risk manager violations | → Stage 2 |
| 2: Small | $5,000 USDC | 2 weeks | Consistent daily positive PnL. All risk controls proven | → Stage 3 |
| 3: Scale-1 | $25,000 USDC | Ongoing | $75–250/day target. 10+ markets. First Alpha strategy live | Continue |
| 4: Scale-2 | $100,000 USDC | Ongoing | $300–800/day. Multi-bot. 3+ validated strategies | Professional LP |

---

## Reference Documents

### Internal

| Document | Purpose |
|----------|---------|
| `docs/CURRENT_STATE.md` | What exists and works today |
| `docs/ARCHITECTURE.md` | Component map and data flow |
| `docs/PLAN_OF_RECORD.md` | Mission, constraints, backtesting kill conditions |
| `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md` | Full SimTrader architecture |
| `docs/specs/SPEC-0011-live-execution-layer.md` | Track A execution layer |
| `docs/OPERATOR_QUICKSTART.md` | Step-by-step from zero to shadow |
| `docs/STRATEGY_PLAYBOOK.md` | Outcome taxonomy and EV framework |

### Academic Papers

| Reference | Paper |
|-----------|-------|
| Market Making | Avellaneda & Stoikov (2008). "High-frequency trading in a limit order book." QF, 8(3), 217–224 |
| Inventory | Guéant, Lehalle & Fernandez-Tapia (2013). "Dealing with the inventory risk." Math. Financial Econ., 7(4) |
| Position Sizing | Kelly, J.L. (1956). "A New Interpretation of Information Rate." Bell System Technical Journal, 35(4) |
| Binary Markets | "Toward Black Scholes for Prediction Markets." arXiv:2510.15205 |
| Adverse Selection | "Optimal Signal Extraction from Order Flow." arXiv:2512.18648v2 |

### Key External Tools

| Tool | Role | License |
|------|------|---------|
| TradingView Lightweight Charts | Probability charts in Studio | Apache 2.0 |
| Tremor | Dashboard UI components | MIT |
| Next.js | Studio frontend framework | MIT |
| NautilusTrader | Reference for execution architecture, Polymarket adapter | LGPL |
| Kaggle Polymarket datasets | Historical market data for tape library | Public |
| python-louvain | Wallet clustering community detection | BSD |
| Ollama | Local LLM for Tier 1 inference | MIT |

---

*End of PolyTool Master Roadmap — version 4.0 — March 2026*
*Living document. Update when architecture decisions are made or phases complete.*
*Supersedes v3.0. Reference v3.0 only for historical context.*
