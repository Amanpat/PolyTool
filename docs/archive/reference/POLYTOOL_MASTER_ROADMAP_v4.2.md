---
status: superseded
superseded_by: docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
superseded_date: 2026-04-21
---
**STATUS: SUPERSEDED by v5_1 as of 2026-04-21. Historical reference only.**

# PolyTool — Master Roadmap
**Version:** 4.2 · **Date:** March 2026 · **Status:** Living Document

---

## Vision

Polymarket is populated by profitable bots whose strategies are unknown, proprietary, or require
resources unavailable to the average operator. PolyTool's mission is to close that gap through
three stages: **reverse-engineer** what the top wallets are doing, **simulate and validate** those
strategies until profitable, and **deploy a live bot** that continuously improves itself.

The end state is a self-funding, self-improving trading system: it discovers strategies
automatically, tests them in simulation, promotes the survivors to live capital, and archives
the failures with post-mortems so the same mistake is never repeated twice. The loop ingests
knowledge from four sources — reverse-engineered wallet behavior, external research and academic
material, real-time news signals, and autonomous overnight experimentation — and synthesizes all
four into a continuously improving strategy library. Over time, as the live bot generates
performance data, that data feeds back into the loop as a fifth input: ground truth from our own
execution.

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
│  │  /api/autoresearch/run · /api/autoresearch/status                    │   │
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
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  AUTORESEARCH ENGINE (Phase 4+)                              │   │   │
│  │  │  strategy_research_program.md → agent loop → SimTrader       │   │   │
│  │  │  benchmark_v1 tape set → keep/revert → experiment ledger     │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
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
SimTrader run, scraper evaluation, LLM call, and autoresearch experiment lives here.

**FastAPI Wrapper** is a thin REST skin over the Python core. No logic lives here.

**n8n** is the control plane. Schedules jobs, sequences workflows, handles retries.
In production it calls FastAPI. In development you call the CLI directly.

**The CLI never goes away.** It is the fastest way to test and debug. Everything starts
as a CLI command. FastAPI endpoints are added when the feature is stable.

**PolyTool Studio** is the unified operator dashboard. It presents data, it does not
process it.

---

## The Self-Improving Loop

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
EXPERIMENT (Autoresearch overnight loop, automated)
    ↓ Agent proposes config/code changes → SimTrader benchmark → keep/revert
    ↓ Experiment ledger grows richer
LEARN (Research RAG + Experiment ledger, new scans informed by history)
    ↓ Loop restarts with better signal
```

The Research Scraper, News/Signals pipeline, and Autoresearch engine run in parallel,
feeding the system continuously. The four knowledge inputs are: wallet behavior, external
research, news signals, and autonomous experiments. The fifth input — live execution ground
truth — begins flowing at Stage 1.

---

## Human-in-the-Loop Policy

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
- **Autoresearch parameter-level changes** (Phase 4) — numerical tuning within bounds
  defined in `strategy_research_program.md`. No human needed per experiment.
  Discord green alert when a significant improvement is committed.

### Human Confirmation Required (Discord button approval)
- **Promoting a strategy from validated to live capital** — most important gate.
- **Capital stage increases** (Stage 1 → 2 → 3) — explicit human decision only.
- **Any strategy flagged LOW_CONFIDENCE by local Ollama**
- **Strategy REVIEW state** (perf_ratio 0.40–0.75) — halved allocation + awaits direction
- **Autoresearch structural code changes** (Phase 6) — agent can propose, human confirms
  before any code change touches the live strategy file. Discord approval required.

### Human Only (never automated)
- Wallet private key operations
- Moving capital between wallets or funding the hot wallet
- Infrastructure configuration changes (AWS, RPC, secrets)
- Adding a strategy type never previously validated
- Disabling a live strategy

---

## n8n Pipeline Architecture

| Workflow | Trigger | What n8n Does |
|----------|---------|---------------|
| Candidate Discovery | Cron every 6h | Calls `/api/candidate-scan` → filters → queues new wallets |
| Wallet Scan Loop | New candidate in queue | Calls `/api/wallet-scan` → waits → triggers llm-bundle |
| LLM Report Generation | Scan complete | Calls Ollama → evaluates → saves or flags |
| Alpha Distill | Batch scan complete | Calls `/api/alpha-distill` → registers hypotheses |
| SimTrader Validation | New hypothesis registered | Sequences L1 → L2 → L3 automatically |
| Research Scraper | Cron every 4h | Calls `/api/research-scraper` → evaluates → writes to RAG |
| News Ingest | Cron every 5 min | Fetches RSS → calls `/api/signals-ingest` → links markets |
| Bot Health Check | Cron every 1 min | Polls `/api/bot/status` → fires Discord alert on anomaly |
| Market Scanner | Cron every 2h | Calls `/api/market-scan` → updates capital allocation plan |
| Feedback Loop | Cron weekly | Calls `/api/strategy-review` → routes KEEP/REVIEW/DISABLE |
| Discord Approval Listener | Webhook from Discord | Receives button click → calls action endpoint |
| Wallet Watchlist Monitor | Cron every 15 min | Polls top-50 wallets → fires yellow alert on new position |
| Autoresearch Scheduler | Cron nightly at 22:00 | Calls `/api/autoresearch/run` → monitors → digest at 07:00 |

### n8n Hosting
- Phase 1–2: Runs locally.
- Phase 3+: Moves to AWS alongside the live bot.

---

## LLM Policy — Self-Funding Model

| Tier | Model | Cost | When Used |
|------|-------|------|-----------|
| Tier 1 | Ollama local (Llama-3-8B / Mistral) | Free | All automated hypothesis generation, scraper evaluation, autoresearch proposals |
| Tier 2 | Manual escalation (Claude / ChatGPT) | Free (operator tokens) | When local model flags low confidence |
| Tier 3 | Claude API auto-escalation | Paid API | Only enabled when `bot_profit_30d > api_cost_estimate` |

### Multi-LLM Specialist Routing (Phase 3)

Four specialist models loaded sequentially via Ollama (~6GB RAM per Llama-3-8B instance):

| Specialist | Task | Input | Output |
|------------|------|-------|--------|
| Model A — Wallet Analyst | Dossier → hypothesis | dossier.json bundle | hypothesis.json |
| Model B — Research Evaluator | Document → quality score | Raw document text | 0–100 score + summary |
| Model C — Signal Classifier | News + market → relevance | headline + market slug | confidence 0–1 |
| Model D — Post-mortem Writer | Failed strategy → report | strategy record + failure | post-mortem.md |

Model C may use Mistral 7B to avoid RAM contention during concurrent news + scan activity.
Research free cloud-hosted Ollama models via n8n before committing to local-only inference.

---

## Multi-Layer Data Stack

The key insight: hourly L2 anchor points from the pmxt archive transform reconstruction
from "build from nothing" to "fill 60-minute gaps between known states."

### The Five Free Layers

**Layer 1 — pmxt Archive (hourly L2 snapshots)**
`archive.pmxt.dev` — free hourly Parquet snapshots of full Polymarket AND Kalshi L2
orderbook and trade data. Join pmxt Discord for higher download speeds. This is your
structural anchor: known full book state at T=0, T+1h, T+2h, etc.

**Layer 2 — Jon-Becker Dataset (72.1M trades, 7.68M markets, 36GB)**
`github.com/Jon-Becker/prediction-market-analysis` — download from
`s3.jbecker.dev/data.tar.zst`. Fields: timestamp, price (1-99¢), size, taker_side
(YES/NO), resolution outcome, category. MIT license. Also seeds `external_knowledge`
RAG partition immediately as PEER_REVIEWED (see RAG section).

**Layer 3 — polymarket-apis PyPI (2-minute price history)**
Public, free, no API key. 30 mid-price observations per 60-minute window.
Used as the mid-price constraint in Silver tape reconstruction.

**Layer 4 — Subgraph / Goldsky (on-chain confirmation + wallet attribution)**
`warproxxx/poly_data` provides `orderFilled` events with maker/taker wallet addresses
directly from the Polygon smart contract. Essential for Louvain community detection.

**Layer 5 — Live Tape Recorder (non-negotiable, start now)**
Tick-level millisecond data. Only source of true microstructure. No reconstruction
approach replaces it. Record via `pmxt.watchOrderBook()`.

### Tape Library Tiers

| Tier | Source | Granularity | Use Case | Available |
|------|--------|-------------|----------|-----------|
| **Gold** | Live Tape Recorder | Tick-level, ms | Microstructure, A-S calibration, Gate 3 | Accumulates from now |
| **Silver** | pmxt + Jon-Becker + polymarket-apis reconstruction | ~2 min effective | Strategy PnL, Gate 2, autoresearch | Immediately after bulk import |
| **Bronze** | Jon-Becker raw trades only | Trade-level, no book | Category analysis, κ MLE | Immediately after download |

**Gate 2 runs on Silver tapes.** Gate 3 requires Gold. Gate 2 is unblocked immediately
after the one-time data import.

### Reconstruction Algorithm

```
FOR each market, FOR each 60-minute window between pmxt hourly snapshots:
  1. ANCHOR: Load L2 book state at window start (pmxt Parquet)
  2. FILL EVENTS: Load all trades in window (Jon-Becker dataset)
     → Each fill removes that size from the resting side of the book
  3. MID-PRICE TRACK: Load 2-min price history (polymarket-apis)
     → Constrains plausible midpoint at 30 intervals
  4. INTERPOLATE: Between fills, assume book persists unless mid-price moves
  5. OUTPUT: Tagged source='reconstructed', reconstruction_confidence='medium'
```

### Database Architecture — ClickHouse + DuckDB

Two databases, strict separation rule. This is a ONE-SENTENCE rule the architect follows:
**ClickHouse handles all live streaming writes. DuckDB handles all historical Parquet reads.**
They never share data, they never communicate. Both are `import`ed in the same Python files.

```python
# Live streaming data → ClickHouse
import clickhouse_driver
ch = clickhouse_driver.Client('localhost')
ch.execute('INSERT INTO live_fills VALUES', rows)

# Historical Parquet research → DuckDB (zero import step, reads files directly)
import duckdb
result = duckdb.query("""
    SELECT category, AVG(price) FROM '/data/raw/jon_becker/trades/*.parquet'
    WHERE timestamp > '2024-01-01' GROUP BY category
""").df()
```

| What | Database | Why |
|------|----------|-----|
| Live fills, tick data, VPIN, price series, WS events | ClickHouse | High-throughput concurrent writes, compression |
| pmxt Parquet, Jon-Becker trades (historical bulk) | DuckDB | Zero-import native Parquet reads, fast analytical SQL |
| Autoresearch experiment ledger | DuckDB | Research queries, no streaming writes needed |
| SimTrader sweep results | DuckDB | Join-heavy analytics, aggregations across many runs |
| Tape metadata (path, tier, market, date) | ClickHouse | Also serves live tape recording metadata |
| Resolution signatures | ClickHouse | Updated continuously as new markets resolve |
| Signal reactions (t+5/30/120) | ClickHouse | Time-series, streaming inserts |

DuckDB is zero-config: `pip install duckdb`. No server process. Reads Parquet directly from
`/data/raw/` without any ingestion step. This eliminates the entire ClickHouse bulk import
pipeline for historical data — just point DuckDB at the files and query.

### Paid Upgrade Path

`polymarketdata.co` — 1-minute L2 depth snapshots, full bid/ask depth, Python SDK.
Activate when bot is covering costs consistently. First infrastructure upgrade post-profit.

---

## Autoresearch Engine

The pattern pioneered by Karpathy's `autoresearch` repo applied to prediction market strategy
optimization. The core idea: give an AI agent a fixed evaluation metric and a bounded search
space, let it run overnight, wake up to 100+ experiments worth of progress.

### The Analogy

| autoresearch (Karpathy) | PolyTool equivalent |
|------------------------|---------------------|
| `train.py` (GPT training code) | Strategy config or strategy Python file |
| `program.md` (research constraints) | `strategy_research_program.md` |
| `val_bpb` (validation bits per byte) | Median net PnL across benchmark_v1 tape set |
| 5-minute fixed training budget | Fixed 50-tape benchmark sweep per experiment |
| Keep if improved, revert if not | Keep if median PnL improves ≥5% across 3 confirmation runs |
| 100 experiments overnight | 80–150 experiments overnight (hardware-dependent) |

### strategy_research_program.md

This is the most important file in the autoresearch system — Karpathy calls the equivalent
"the research org code." It is a Markdown document that:
- States the research goal (maximize median net PnL after fees on benchmark_v1)
- Lists what the agent is allowed to change (explicit allowlist, not denylist)
- Lists hard bounds for every numerical parameter
- Describes what good looks like vs what bad looks like
- Records accumulated lessons from past experiments (human-updated)

As experiment history grows, the operator updates `strategy_research_program.md` to capture
what's been learned — what directions improve PnL, what causes failure modes. The document
becomes a compressed history of everything the system has tried. This is the human's primary
contribution to the autoresearch loop.

### Benchmark Tape Set — Fixed + Versioned

**Critical design decision:** all autoresearch experiments must run against the same fixed
tape set to be comparable. Without this, experiment 1 on 50 volatile politics tapes and
experiment 2 on 50 stable sports tapes produce meaningless relative numbers.

- `config/benchmark_v1.tape_manifest` — a JSON file listing 50 tape paths by name
- Curated once: 10 high-volatility politics tapes, 15 sports tapes, 10 crypto tapes,
  10 near-resolution tapes, 5 new-market (<48h) tapes. Balance of categories.
- **Never changes** mid-experiment-series. When the benchmark needs updating, increment
  to `benchmark_v2.tape_manifest` and reset the experiment ledger for the new series.
- All autoresearch runs, Gate 2 sweeps, and strategy comparisons reference this manifest.
- Human decision to bump version. Driven by: significant market regime change, major tape
  quality improvement (e.g., 3 months of Gold tapes replacing Silver), or strategy overhaul.

### Parallel SimTrader — multiprocessing.Pool

Tape replays are embarrassingly parallel — no shared state, no communication between runs.

```python
from multiprocessing import Pool
import os

N_WORKERS = max(1, os.cpu_count() - 2)  # Leave 2 cores free for system

def run_tape(args):
    tape_path, strategy_config = args
    return SimTrader.replay(tape_path, strategy_config)

with Pool(N_WORKERS) as pool:
    results = pool.map(run_tape, [(t, cfg) for t in benchmark_tapes])

median_pnl = statistics.median(r.net_pnl for r in results)
```

**Hardware targets:**
- Development machine (i7-8700K, 6 cores): `Pool(10)` — 50 tapes in ~5 batches
- Friends' machines (higher core counts): auto-detected via `os.cpu_count()`
- 50 tapes × 3 confirmation runs at Pool(10): ~37 seconds per experiment
- 100 experiments overnight on dev machine: ~1 hour total

### Keep/Revert Logic — Three-Confirmation Multi-Run

A single 50-tape run has variance. A 5% PnL improvement might be noise.
Three confirmation runs is the minimum for statistical confidence:

```python
def should_keep(old_config, new_config, benchmark_tapes, n_confirmations=3):
    """Run new config 3 times. Keep only if it beats old config ≥2/3 times."""
    wins = 0
    for _ in range(n_confirmations):
        new_pnl = run_benchmark(new_config, benchmark_tapes)
        old_pnl = run_benchmark(old_config, benchmark_tapes)
        if new_pnl > old_pnl * 1.05:  # Require ≥5% improvement to count as win
            wins += 1
    return wins >= 2  # Majority wins: keep if 2-of-3 or better
```

The 5% threshold prevents micro-improvements from noise accumulating into garbage configs
over hundreds of experiments. Adjust based on observed variance after first 20 experiments.

### Experiment Ledger (DuckDB)

Every experiment writes a row to `autoresearch_experiments` in DuckDB:

```sql
CREATE TABLE autoresearch_experiments (
    experiment_id     INTEGER PRIMARY KEY,
    run_timestamp     TIMESTAMP,
    phase             TEXT,         -- 'parameter' or 'code'
    benchmark_version TEXT,         -- 'v1', 'v2', etc.
    config_before     JSON,
    config_after      JSON,
    change_description TEXT,
    confirmation_wins INTEGER,       -- 0-3
    median_pnl_before DOUBLE,
    median_pnl_after  DOUBLE,
    pct_improvement   DOUBLE,
    decision          TEXT,         -- 'KEEP' or 'REVERT'
    notes             TEXT
);
```

After 6 months this table is a research paper about your strategy. Every dead-end is
documented. Every improvement is traceable. Surface in Studio Autoresearch tab (Phase 7).

### Two Phases of Autoresearch

**Phase 4 — Parameter autoresearch (numerical tuning only)**
The agent proposes changes to `strategy_config.json` only. Allowlist of tuneable parameters
defined in `strategy_research_program.md`:
- γ (risk aversion): bounds [0.05, 5.0]
- κ (trade arrival multiplier per category): bounds [0.1, 10.0]
- Spread floor/ceiling per category: bounds [0.005, 0.15]
- Inventory skew factor: bounds [0.5, 3.0]
- Time-decay exponent in A-S formula: bounds [0.1, 2.0]

No Python files are touched. Human never reviews individual experiments (too many).
Discord green alert when an experiment commits an improvement ≥10%: "Autoresearch committed
improvement: +12.3% median PnL. Config delta: γ 0.8→0.6, κ sports 1.2→1.8."

**Phase 6 — Code-level autoresearch**
The agent proposes changes to the strategy Python file. Allowlist from
`strategy_research_program.md`:
- Signal computation logic (what inputs feed into the quote calculation)
- Reservation price formula modifications (within the logit A-S structure)
- Category-specific branching logic (different parameters per market category)
- New indicator combinations (e.g., add VPIN term to the spread calculation)

Hard denylist (agent cannot touch, enforced by code review gate):
- Kill switch logic
- EIP-712 signing code
- Order execution paths
- Risk manager pre-trade checks
- ClickHouse write logic

Code changes require Discord human confirmation before the modified file goes into
the live strategy rotation. The agent proposes + benchmarks; human approves the commit.

### Docker — One-Command Distributed Training

For running autoresearch experiments on friends' machines overnight:

```bash
# What a non-technical friend runs. That's it.
docker run --rm \
  -v /path/to/results:/results \
  -e EXPERIMENT_HOURS=8 \
  polytool-autoresearch:latest
```

The Docker image contains:
- All Python dependencies pre-installed
- The benchmark tape set (pre-loaded into the image for the current version)
- The current best config as starting point
- The `strategy_research_program.md` constraints
- Auto-detect `os.cpu_count()` for Pool sizing
- Writes results JSON to `/results/` on the host machine
- Operator reviews the output JSON in Studio the next morning

`Dockerfile` and a `build_training_image.sh` script are Phase 4 deliverables alongside
the autoresearch engine itself. The goal: non-technical operator runs one command and leaves
their machine running overnight. Results are importable into the experiment ledger with one
CLI command: `polytool autoresearch import-results ./results/experiment_batch_20260315.json`.

---

## Open-Source Repository Integration

Specific files and patterns to pull from reviewed open-source repos. The architect should
clone each referenced repo and extract precisely what is listed — not adopt the whole project.

### `lorine93s/polymarket-market-maker-bot`

**Pull:**
- `src/services/auto_redeem.py` — Automatic position redemption for settled markets.
  Detects resolved markets, redeems winning positions, handles gas optimization. We do not
  have this yet. Without auto-redemption, settled positions accumulate and capital is locked.
  Integrate into the live bot's post-resolution loop as a Phase 1 deliverable.
- `src/execution/order_executor.py` — Cancel/replace cycle logic. Production-tested
  pattern for updating stale quotes without leaving orphaned orders. Reference the
  cancellation sequencing before building our OrderManager's cancel/replace flow.
- `src/inventory/inventory_manager.py` — Balanced YES/NO exposure tracking with absolute
  skew limits. Reference implementation before writing our inventory skew logic.

**Skip:** `quote_engine.py` (we have better Logit A-S), `risk_manager.py` (we have ours),
`websocket_client.py` (pmxt.watchOrderBook() is the better choice).

**Note:** Author's `warproxxx/poly-maker` README explicitly states "not profitable today."
lorine93s's bot is more recent (2025-2026) but same caveat applies — use as reference,
not as a deployable strategy.

### `realfishsam/prediction-market-arbitrage-bot`

**Pull:**
- `src/matcher.js` — Fuzzy market matching algorithm between Polymarket and Kalshi.
  Handles the hard problem of matching "Will Trump win?" on Polymarket to "Presidential
  election 2024" on Kalshi when question wording differs. Port this logic to Python.
  This is exactly what our Kalshi resolution condition parser needs — matching market
  questions across platforms before any cross-platform position is opened.
- `src/arbitrage.js` — Expected profit calculation for cross-platform synthetic arb
  (buy YES on one platform, NO on another). Reference the EV formula and fee accounting
  before building our cross-platform arb detector in Phase 3.

**Skip:** Execution layer (TypeScript, not compatible), bot.js (single-market polling logic
we don't need). The dry-run mode pattern is already in our SimTrader.

### `realfishsam/Risk-Free-Prediction-Market-Trading-Bot`

**Pull:**
- `live_trading/arb_bot.py` — Binary complement arb scanner architecture (WebSocket
  scanning for sum_ask < $0.99 events). Complement arb is non-viable on current Polymarket
  (sum_ask floors above 1.001), but the scanning pattern and WebSocket monitoring loop
  is directly reusable for the Gnosis CTF atomic conversion arb detector (Phase 5).
  The scanner monitors the same condition we need: sum of YES prices deviating from $1.00.
- `analysis/fetch_spread_data.py` — Historical arbitrage frequency charting. Use as
  reference for building the Arb Feasibility Grafana dashboard panel.

### `dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot`

**Pull:**
- **SMI formula** (Smart Money Index: 0-100 bullish/bearish aggregate from whale
  positioning). Formula: `SMI = normalize(sum(whale_count_i × dollar_size_i × direction_i))`
  Integrate as a composite signal in our candidate scanner's watchlist scoring.
- **Conviction score formula**: `conviction = whale_count × dollar_size`. Simple but
  proven. Use as the primary ranking signal for the watchlist alert threshold — fire a
  yellow alert when conviction score exceeds threshold, not just when any whale moves.
- **7-phase liquid scanner pipeline**: Leaderboard → Markets → Global Trades → Market
  Trades → Ranking → Analysis → Score & Save. This maps almost exactly to our candidate
  scanner flow. Review their exact implementation before building our version — they have
  already debugged the API pagination, rate limiting, and deduplication logic.
- **OFI windows**: Order Flow Imbalance across 60min/4hr/24hr rolling windows. Their
  implementation is more granular than our current single-window OFI. Adopt multi-window
  OFI as the standard in our live bot's adverse selection detection (Phase 1 Stage 1).

**Skip:** Multi-LLM ensemble layer (we have a better architecture), the 9-tab dashboard
(we have Studio), the Grafana integration (already in our stack).

### `warproxxx/poly-maker`

**Pull:**
- `poly_merger` module — Production-tested NO→YES token conversion on Polygon. Handles
  the Gnosis CTF atomic merge: combines NO positions into YES + USDC. Reduces gas fees
  and unlocks capital from settled positions. Pull this entire module directly — it's
  built on open-source Polymarket code and the author has run it in production.

**Skip:** Parameter configs (explicitly "not profitable today" per author). The Google
Sheets config approach is replaced by our Settings tab. Their MM strategy is superseded
by our Logit A-S.

### `vgreg/MeatPy`

**Do NOT pull directly.** MeatPy is built for NASDAQ ITCH 5.0 binary protocol — not
compatible with Polymarket's CLOB format.

**Pull the architectural pattern only:**
- Parser → Market Processor → Recorders observer pattern. This is the correct architecture
  for our Silver tape reconstructor. The parser reads anchors (pmxt Parquet) + fill events
  (Jon-Becker), the market processor maintains book state, recorders output tape files.
  Each recorder can be independently attached/detached (e.g., a top-of-book recorder, an
  L2 snapshot recorder, a quality metrics recorder). Build our reconstructor with this
  separation — it makes testing individual components much easier.

### `Polymarket/real-time-data-client` (TypeScript, official)

**What it is:** Polymarket's official RTDS (Real-Time Data Socket) client. Provides
comments, crypto prices, and activity topic streams. **This is NOT the CLOB orderbook
feed** — it is a separate WebSocket service.

**Pull for signals pipeline (Phase 3):**
- RTDS provides real-time comment streams for Polymarket markets — comment sentiment
  is a leading indicator before the orderbook moves. Wire RTDS comments into the
  signals pipeline alongside RSS/Reddit.
- RTDS crypto prices (`btcusdt`, `ethusdt`, `solusdt`) provide Chainlink/Binance price
  feeds — useful for the 15-minute crypto market strategy (Phase 5) and for the News
  Governor high-risk calendar (price threshold triggers).
- The TypeScript client is a reference — implement equivalent Python subscription in
  our signals pipeline using `websockets` library with the same RTDS message format.

**Skip:** For CLOB L2 orderbook data, use `pmxt.watchOrderBook()` — that is the CLOB
WebSocket feed, a completely different connection.

### `agenttrader` (finnfujimura) — Pending README

**Status:** README not yet received. Placeholder for v4.2 addendum.
When the README is shared, this section will be completed with the same extraction
analysis as the repos above. Add to v4.3 or as a standalone addendum to v4.2.

---

## RAG Architecture — Hybrid Partitioned Brain

One Chroma collection (`polytool_brain`) with five internal partition tags.

| Partition | Contains | Trust Tier | Who Writes |
|-----------|----------|-----------|-----------|
| `user_data` | Dossiers, scan artifacts, LLM reports | Low / Exploratory | Automated pipeline |
| `research` | Validated StrategySpecs, live performance records, post-mortems | High / Curated | Gate pass + human confirmation |
| `signals` | Proven news patterns (≥10 events, >3% move) | Medium | Auto at threshold |
| `market_data` | All Polymarket AND Kalshi markets, snapshots | Reference | Automated sync |
| `external_knowledge` | Academic papers, research, forum threads | Medium / Reference | Scraper + quality gate |

**Hard rules:** Nothing enters `research` without `validation_gate_pass` artifact (enforced
in code). Nothing enters `external_knowledge` below quality threshold.

### external_knowledge Metadata Fields

Every document carries three lifecycle fields:
- `freshness_tier`: `CURRENT` (2024+) / `RECENT` (2021-2023) / `HISTORICAL` (pre-2021)
- `confidence_tier`: `PEER_REVIEWED` / `PRACTITIONER` / `COMMUNITY`
- `validation_status`: `UNTESTED` → `CONSISTENT_WITH_RESULTS` → `CONTRADICTED`

Updated automatically by Phase 6 feedback loop when strategies are promoted or archived.

### Jon-Becker Research Findings — Seed Immediately

Seed into `external_knowledge` with `confidence_tier: PEER_REVIEWED` on first import:

**Finding 1:** Makers earn +1.12%/trade, takers lose -1.12%, consistent across 80/99 price
levels across 72.1M trades. Empirical confirmation of the market making thesis.

**Finding 2 (Category allocation decision):** Finance: 0.17pp maker edge (near-efficient —
avoid). Sports: 2.23pp, Crypto: 2.69pp, Entertainment: 4.79pp. Prioritize Sports and Crypto.
Apply these as prior weights in the Market Selection Engine scoring.

**Finding 3 (Favorite-longshot bias quantification):** At 1-cent markets, YES takers lose
41% in expectation, NO buyers earn +23%. YES takers account for 41-47% of 1-10¢ volume.
Calibration dataset for the favorite-longshot bias exploitation strategy (Phase 5).

**Finding 4 (Regime risk):** Maker edge only emerged post-October 2024. Before that, takers
outperformed. Monitor for regime reversal — if volume drops significantly, the gap may
compress or reverse. Track in weekly feedback loop.

---

## AWS Architecture — Two-Server Design

**Stay local until profitable. Design for AWS from day one.**

**Server 1 — Research Server** (~$100-150/month): n8n, scanner, scraper, RAG, Ollama,
Grafana, Studio, ClickHouse, DuckDB. Migrate earlier (Phase 2-3) if profitable enough.

**Server 2 — Execution Server** (~$300-500/month): Live bot only. No other processes.
Dedicated cores. Closest region to Polymarket's CLOB (NY/NJ). Move at Stage 3.

**Cost coverage metric** always visible on Studio Dashboard: trailing 30-day revenue vs
estimated monthly infra cost. Color: green ≥2×, yellow 1-2×, red <1×.

---

## UI Architecture — PolyTool Studio

### Technology Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Framework | Next.js (React) | Component ecosystem, SSR, API routes |
| Components | Tremor | Purpose-built for metrics dashboards |
| Charts | TradingView Lightweight Charts v5+ | Handles 0-1 probability data natively |
| Embedded | Grafana + n8n via iframe | Both have polished UIs already |
| Real-time | FastAPI WebSocket → `series.update()` | Sub-second updates |

### Studio Tab Map

| Tab | Purpose | Primary Data Source | Actions |
|-----|---------|---------------------|---------|
| **Dashboard** | System health at a glance | `/api/bot/status`, ClickHouse | Arm/disarm kill switch |
| **SimTrader** | OnDemand backtesting, comparison, tape library | SimTrader Engine | Run, load tape, compare |
| **Research** | Discovery pipeline, watchlist, flagged reviews | `/api/candidate-scan` | Promote, reject, paste report |
| **Bot Monitor** | Live bot real-time | WebSocket `/api/bot/stream` | Kill switch, pause market |
| **Autoresearch** | Overnight experiment log, ledger, program.md editor | DuckDB experiment ledger | Edit program.md, import results, view history |
| **Signals** | Live news feed, market links, reactions | `/api/signals-ingest` | Mark signal relevant/noise |
| **Knowledge** | RAG query across all 5 partitions | `/api/rag-query` | Query, scope, filter by validation_status |
| **Scraper** | Research scraper log, scores, accepts/rejects | `/api/research-scraper/log` | Submit URL, manage overrides |
| **Grafana** | Grafana dashboards embedded | Grafana at its port | Navigate within Grafana |
| **Pipelines** | n8n canvas embedded | n8n at its port | Navigate within n8n |
| **Settings** | Risk limits, scraper config, governor settings | Config files | Edit limits, test Discord, manage category weights |

### Autoresearch Tab — New in v4.2

The Autoresearch tab surfaces the overnight experiment loop:
- **Experiment feed:** scrollable log of every experiment run. Each row: timestamp,
  change description, median PnL before/after, % improvement, KEEP/REVERT badge.
- **Trajectory chart:** Lightweight Charts line showing best-config median PnL over time
  (experiment number on X axis). Should trend upward with occasional flat periods.
- **program.md editor:** in-browser Markdown editor for `strategy_research_program.md`.
  Changes here are the operator's primary input to the research loop. Save button
  writes to disk and triggers a reload on the next autoresearch cycle.
- **Import results button:** ingests a `experiment_batch_*.json` from friends' distributed
  training runs into the local DuckDB ledger.
- **Benchmark manifest:** shows which tape set is currently active, allows bumping to
  the next version with a confirmation modal.

---

## Context Management for Architects

**Problem:** As the project grows, sharing full repo context with any LLM hits token limits.

**Solution:** Maintain `docs/CURRENT_STATE.md` as a tightly-written 2-3 page living document.
This is the primary handoff artifact. It contains:
- What is fully built and tested (component list, no explanations)
- What is partially built (component, what's done, what's missing)
- Current gate status (Gate 1/2/3/4 pass/fail)
- Active blockers
- Current data assets (what's in ClickHouse, what tapes exist, what's in the RAG)

At the start of any new session, paste `CURRENT_STATE.md` in the chat. Do not use GitHub
access for full repo context — token cost is prohibitive. The roadmap (this document) is the
strategic layer. `CURRENT_STATE.md` is the execution layer.

**Architect responsibility:** Update `CURRENT_STATE.md` after every meaningful work unit.
It should never be more than one work session out of date. The roadmap is updated when
architecture decisions change (approximately monthly). The state doc is updated when code
ships (approximately weekly).

---

## Current State — What Is Already Built ✅

### Research Pipeline (Complete)

| Component | What It Does |
|-----------|-------------|
| ClickHouse Schema + API Ingest | Stores Polymarket trade, position, market data |
| Grafana Dashboards | Visualises Trades, Strategy Detectors, PnL, Arb Feasibility |
| `scan` CLI | One-shot ingestion + trust artifact emission |
| Strategy Detectors | HOLDING_STYLE, DCA_LADDERING, MARKET_SELECTION_BIAS, COMPLETE_SET_ARBISH |
| PnL Computation | FIFO realized + MTM. Fee model: 2% on gross profit |
| Resolution Enrichment | 4-stage chain. UNKNOWN_RESOLUTION < 5% |
| CLV Capture | Closing Line Value per position |
| `wallet-scan` + `alpha-distill` | Batch scan, composite scoring, hypothesis distillation |
| Hypothesis Registry | Register, status, experiment-init, experiment-run |
| Local RAG | Chroma + FTS5 + RRF + cross-encoder rerank |
| LLM Bundle + Save + MCP | Evidence bundles, hypothesis.json, Claude Desktop integration |

### SimTrader (Complete)

| Component | What It Does |
|-----------|-------------|
| Tape Recorder | Records live Polymarket WS → deterministic replay files |
| L2 Book Reconstruction | Replays tape → exact orderbook state at any moment |
| Replay Runner + BrokerSim | Strategy → simulated orders → realistic fills |
| Sweeps + Local Reports | Parameter grid sweeps, HTML report, batch leaderboard |
| Shadow Mode | Live WS → strategy decisions → simulated fills, no real orders |
| SimTrader Studio UI | FastAPI + vanilla HTML/JS at localhost:8765 (replaced Phase 7) |
| OrderManager | Quote reconciliation, rate caps |
| MarketMakerV0 | Conservative two-sided quoting, inventory skew, binary guards |
| Execution Primitives | KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner |

---

## Development Checklist

---

### PHASE 0 — Foundation
> Complete.

- [x] ClickHouse schema and API ingest
- [x] Grafana dashboards
- [x] scan CLI and strategy detectors
- [x] PnL computation + fee model
- [x] Resolution enrichment (4-stage chain)
- [x] CLV capture
- [x] Segment analysis
- [x] wallet-scan and batch-run
- [x] alpha-distill
- [x] Hypothesis Registry
- [x] Local RAG (Chroma + FTS5 + RRF + rerank)
- [x] LLM Bundle + Save + MCP Server
- [x] SimTrader full stack (Tapes through Shadow Mode)
- [x] SimTrader Studio UI (initial — replaced Phase 7)
- [x] Execution Primitives (dry-run)

---

### PHASE 1 — Track A: Live Bot
> Priority: NOW. Critical path to revenue.

- [ ] **FIRST: Bulk data import — pmxt archive + Jon-Becker dataset**
      Execute the one-time historical data pull that seeds the tape library and unblocks Gate 2:
      (1) Join pmxt Discord (`discord.gg/Pyn252Pg95`) for higher download speeds. Download
      full Parquet archive from `archive.pmxt.dev` — `Polymarket/`, `Kalshi/`, `Opinion/`.
      DuckDB reads these files directly from `/data/raw/pmxt/` — no ClickHouse import needed.
      (2) Download Jon-Becker dataset: `s3.jbecker.dev/data.tar.zst` (36GB compressed).
      Extract to `/data/raw/jon_becker/`. DuckDB reads directly via `SELECT * FROM
      '/data/raw/jon_becker/trades/*.parquet'`. No ingestion step.
      (3) Pull 2-minute price history via `polymarket-apis` PyPI for active markets. Store in
      ClickHouse `price_2min` table (this one goes in ClickHouse — it's a live-updating series).
      Gate 2 is unblocked from this point: Silver-tier tapes are now generatable on demand.

- [ ] **DuckDB setup and integration**
      `pip install duckdb` — zero config, no server. Write the one-line rule into
      `docs/ARCHITECTURE.md`: "DuckDB = historical Parquet. ClickHouse = live streaming."
      Verify DuckDB can query pmxt Parquet and Jon-Becker Parquet files directly. Add
      `duckdb.query()` helper to Python core that encapsulates the connection lifecycle.

- [ ] **Auto-redeem — position redemption for settled markets**
      Pull `src/services/auto_redeem.py` from `lorine93s/polymarket-market-maker-bot`.
      Adapt to PolyTool's Python core: detect resolved markets with winning positions,
      auto-redeem on-chain via py-clob-client, log each redemption to ClickHouse.
      Without this, capital is locked in settled positions indefinitely. Run as a scheduled
      job every 30 minutes via n8n. Prerequisite to Stage 1 deployment.

- [ ] **Tape Recorder rewrite — pmxt.watchOrderBook()**
      Replace Tape Recorder's custom WS client with `pmxt.watchOrderBook(outcomeId)`.
      Output format stays identical. Note: py-clob-client remains the ONLY execution path.
      When Kalshi recording is added (Phase 3): `pmxt.Kalshi().watchOrderBook()` — zero
      new infrastructure.

- [ ] **Subgraph trade reconstructor (Silver tape generator)**
      CLI command that combines pmxt hourly anchor (DuckDB query) + Jon-Becker fills
      (DuckDB query) + polymarket-apis 2-min prices (ClickHouse query) using the
      parser→processor→recorder architecture from MeatPy (ported pattern, not direct use).
      Output: Silver-tier tape files in `/data/tapes/{platform}/{slug}/{date}.tape`.
      Tape metadata written to ClickHouse `tape_metadata` table. All tapes tagged
      `source='reconstructed', reconstruction_confidence='medium'`.

- [ ] **Benchmark tape set — benchmark_v1**
      Create `config/benchmark_v1.tape_manifest` — JSON list of 50 tape paths.
      Curation: 10 politics (high-volatility), 15 sports, 10 crypto, 10 near-resolution,
      5 new-market (<48h). Mix of Gold (if available) and Silver tapes.
      This manifest is referenced by Gate 2, all autoresearch runs, and strategy comparisons.
      Never change this file mid-experiment-series without bumping the version number.

- [ ] **Parallel SimTrader execution — multiprocessing.Pool**
      Refactor SimTrader sweep runner to use `multiprocessing.Pool(os.cpu_count() - 2)`.
      Each worker replays one tape independently. No shared state between processes.
      Target: 50 tapes replayed in ~5 seconds on dev machine (i7-8700K, Pool(10)).
      Verify results are deterministic: same tape + same config = same PnL every run.
      This is a prerequisite for autoresearch (Phase 4) and efficient Gate 2 sweeps.

- [ ] **News Governor — Risk Layer**
      **Approach A — Scheduled high-risk calendar:**
      Machine-readable JSON calendar of known high-impact events: Fed meetings, election
      days, debate nights, CPI/jobs releases, major sports championships. During configurable
      windows, auto-widen spreads by 2× or reduce position size by 50%. Not reactive to news
      — proactive. Store in `config/high_risk_calendar.json`, editable from Studio Settings.
      **Approach B — Multi-market cancellation detection:**
      If quote cancellations spike across ≥5 markets within 30 seconds, activate system-wide
      defensive posture (widen all spreads, halt new position opens). Fires in milliseconds.
      Both governors live before Stage 1 capital deployment.

- [ ] **MarketMakerV1 — Logit A-S upgrade**
      Transform mid-price to log-odds: `x = ln(p/(1-p))`. Compute reservation price and
      spread in that unbounded domain. Back-transform via sigmoid.
      - Reservation logit: `x_r = x_t - q·γ·σ_b²·(T-t)`
      - Spread in logit space: `δ = γ·σ_b²·(T-t) + (2/γ)·ln(1 + γ/κ)`
      - Physical bid: `p_b = sigmoid(x_r - δ/2)`, ask: `p_a = sigmoid(x_r + δ/2)`
      - κ calibrated via MLE on Jon-Becker 72M trades per category (DuckDB query)
      - NumPy vectorized — no Python loops in the hot path
      Must complete before Gate 2: incorrect spread math means sweep results cannot be trusted.

- [ ] **Pass Gate 2 — Parameter sweep (≥70% positive PnL)**
      Run MarketMakerV1 sweep across benchmark_v1 tape set using parallel SimTrader.
      Gate criterion: ≥70% of 50 tapes show positive net PnL after 2% fee model.
      Must also validate at realistic-retail latency (150ms, 70% fill rate, 5bps slippage).
      Top config from sweep becomes Stage 1 deployment config.

- [ ] **Multi-window OFI (from dylanpersonguy)**
      Adopt multi-window Order Flow Imbalance: 60min, 4hr, and 24hr rolling windows.
      Integrate as adverse selection signal in Stage 1 risk manager alongside VPIN.
      Reference dylanpersonguy's OFI implementation before building from scratch.

- [ ] **Begin Gate 3 — 30-day shadow run**
      3-5 live markets, best config from Gate 2, simulated fills only. After 30 days:
      shadow PnL within 25% of Gate 2 replay prediction = PASS.

- [ ] **FastAPI wrapper — first endpoints**
      `/api/candidate-scan`, `/api/wallet-scan`, `/api/llm-bundle`, `/api/llm-save`,
      `/api/simtrader/run`, `/api/market-scan`, `/api/bot/status`, `/api/bot/stream`,
      `/api/strategy/promote`, `/api/strategy/archive`. Thin wrappers only.

- [ ] **n8n local setup**
      Two first workflows: Market Scanner (2h cron) and Bot Health Check (1min cron).

- [ ] **Market Selection Engine**
      Scores all active Polymarket markets every 2 hours. Factors: reward APR, spread vs
      minimum profitable spread, 24h volume, competing MM count, age bonus (<48h = 80-200%
      APR). Category weights from Jon-Becker: Sports +bonus, Crypto +bonus, Finance -penalty.

- [ ] **Infrastructure setup (VPS + RPC + secrets)**
      NY/NJ datacenter. Dedicated Polygon RPC (Chainstack or Alchemy). All secrets in `.env`.

- [ ] **Grafana live-bot panels**
      Open orders count, fill rate per market, inventory skew, daily PnL, kill switch status,
      active market count.

- [ ] **Discord alert system — Phase 1 (outbound only)**
      `#polytool-ops`, `#polytool-alerts`, `#polytool-digest`. Webhook-based, no bot token.
      Green = info, yellow = warning, red = critical. Fire within 30 seconds of event.

- [ ] **Stage 0 — Paper Live (72-hour dry-run)**
      Full stack in dry-run mode. Verify: zero errors, positive PnL estimate, kill switch
      working, WS reconnection working, Discord alerts firing.

- [ ] **Stage 1 — $500 live deployment**
      $500 USDC to hot wallet. Risk limits: $500 max position, $200 max order, $100 daily
      loss cap, $400 inventory skew limit. Target 3-5 markets. 7 days. Success: positive
      realized PnL + rewards + zero risk manager violations.
      Adverse selection: VPIN + multi-window OFI + cancellation mimicry signal all active.

- [ ] **Stage 2 — $5,000 scale**
      After Stage 1 criterion met. 8-10 markets. 2 weeks. Proportional risk limits.

---

### PHASE 2 — Track B: Discovery Engine + Research Scraper
> Runs in parallel with Phase 1 from Week 3 onward.

- [ ] **Candidate Scanner CLI (`candidate-scan`)**
      9 signals: new-account large position (hard-flag), unusual concentration, consistent
      early entry, high CLV, COMPLETE_SET_ARBISH, win-rate outlier, Louvain community
      detection (python-louvain), Jaccard similarity (>0.7 across ≥5 shared markets),
      temporal coordination (<100ms variance across 10+ wallets).
      Reference `dylanpersonguy` 7-phase scanner pipeline and conviction score formula
      (whale_count × dollar_size) before building. Do not rebuild debugged logic.

- [ ] **n8n — Candidate Discovery Workflow**
      Cron every 6h → `/api/candidate-scan` → queues new candidates.

- [ ] **n8n — Wallet Scan + LLM Report Workflow**
      Per candidate: `/api/wallet-scan` → `/api/llm-bundle` → Ollama → save or flag.

- [ ] **Local Ollama integration**
      Llama-3-8B or Mistral. Returns structured hypothesis.json. Confidence heuristic gates
      low-quality outputs to flagged review queue.

- [ ] **n8n — Alpha Distill Workflow**
      Post-batch: `/api/alpha-distill` → threshold (pattern in ≥5 wallets) → register
      hypotheses → trigger L1 validation.

- [ ] **Wallet Watchlist — Real-Time Alert Following**
      Top 20-50 wallets monitored every 15 min via n8n. New position in unseen market →
      Discord yellow alert immediately: wallet handle, market slug, position size, entry price.
      Conviction score (whale_count × dollar_size) determines alert priority tier.
      Config in `config/watchlist.json`, editable from Studio Research tab.

- [ ] **Market Obituary System — Stage 1 (trade-level)**
      Using DuckDB queries on Jon-Becker + pmxt archive data (both immediately available):
      Compute resolution signature features for all resolved markets:
      - Volume spike ratio: final 2h volume vs 24h rolling average
      - Price trajectory monotonicity: fraction of 5-min intervals moving toward resolution
      - Trade size progression: whether avg trade size increases in final 2h
      - Spread collapse: bid-ask narrows sharply before resolution
      - Maker withdrawal: maker quotes disappear from one side
      Write to ClickHouse `resolution_signatures`. Feeds Stage 1 risk manager quote-pull
      triggers. Stage 2 (tick-level, Phase 5) replaces once Gold tapes accumulate.

- [ ] **Discord bot — two-way approval system**
      Discord Bot with button components. `#polytool-approvals`: [Approve]/[Reject] on
      hypothesis promotion. 48-hour timeout, re-alerts once. Maps to FastAPI endpoints.

- [ ] **LLM-Assisted Research Scraper**
      Stage A (fetch): ArXiv, Reddit PRAW, GitHub READMEs, Medium/Substack RSS,
      manual URLs via Studio. Do NOT auto-scrape: commercial textbooks, Twitter/X,
      paywalled content.
      Stage B (evaluate): Ollama scores 0-100 (4 dimensions × 25). Default threshold: 55/100.
      Tune in first two weeks of manual review. Accepted docs: metadata includes
      `freshness_tier`, `confidence_tier`, `validation_status: UNTESTED`.

- [ ] **n8n — Research Scraper Workflow**
      Cron every 4h → `/api/research-scraper` → log → Discord yellow alert if rejection
      rate >20% in one run.

---

### PHASE 3 — Hybrid RAG Brain + Kalshi Integration
> Replaces current local RAG. Kalshi integrated via pmxt.

- [ ] **Unified Chroma collection (`polytool_brain`)**
      Migrate all `kb/` content. Five partition tags. `research` partition gate enforced
      in code at write time.

- [ ] **Market Data partition + Polymarket full store**
      Gamma API + CLOB API + pmxt archive → `market_data` partition.

- [ ] **Kalshi integration (pmxt-enabled)**
      (1) Kalshi market sync → `market_data` partition via `pmxt.Kalshi().fetchMarkets()`.
      (2) Kalshi L2 recording: `pmxt.Kalshi().watchOrderBook()` → same tape format.
      (3) Cross-platform calibration: Kalshi price for same event as external signal.
      (4) Cross-platform arb detector: >3¢ spread adjusted for fees → Signals partition
          at ≥5 historical profitable occurrences.
      (5) Resolution condition parser — port fuzzy matcher from `realfishsam/matcher.js`.
          Block cross-platform positions when question text diverges. March 2025 precedent
          (government shutdown — platforms resolved opposite sides) is the canonical failure.
      Regulatory note: Kalshi is CFTC-regulated (US-legal). Polymarket restricts US access.

- [ ] **Signals ingest pipeline — repurpose existing project**
      Audit existing storage layer → adapt to `signals` partition → replace ticker resolver
      with Gamma API lookup → add RSS feeds (AP, Reuters, BBC, ESPN, Bloomberg).

- [ ] **RTDS comment stream (from Polymarket/real-time-data-client)**
      Implement Python WebSocket client for Polymarket RTDS comments topic. Pipe comment
      sentiment into signals pipeline as a leading indicator. Reference TypeScript client
      for message format. RTDS crypto prices → feed into 15-min crypto market signal (Phase 5)
      and News Governor calendar triggers.

- [ ] **Market linker (signals → Polymarket + Kalshi)**
      Entity extraction → Gamma API market lookup (both platforms) → Ollama disambiguation
      for ambiguous matches → confidence score in ClickHouse.

- [ ] **Reaction measurement (price change tracking)**
      Price at t+5min, t+30min, t+2hr post-signal. `price_change_5min`, `price_change_30min`,
      `max_move_30min` in ClickHouse `signal_reactions` table.

- [ ] **Signals partition write (proven patterns only)**
      Pattern graduates ClickHouse → Signals RAG only when same signal type + category
      shows >3% move in ≥10 historical events.

- [ ] **n8n — News Ingest Workflow**
      Cron every 5min → RSS + RTDS → `/api/signals-ingest` → market linker → ClickHouse.
      Separate cron: check graduation threshold for staging patterns.

- [ ] **Multi-LLM Specialist Routing**
      Four specialist Ollama models (A/B/C/D). Sequential loading. Model C may use Mistral
      7B for latency. Research free cloud-hosted models via n8n before finalizing local-only.

- [ ] **Domain Specialization Layer**
      Category-specific CLV breakdown per wallet. Category-specific signal pipelines for
      highest-alpha niches. Jon-Becker category gap table seeded into `external_knowledge`
      as PEER_REVIEWED prior.

---

### PHASE 4 — SimTrader Validation Automation + Autoresearch
> Two goals: (1) automate hypothesis validation; (2) launch parameter-level autoresearch.

- [ ] **strategy-codify (StrategySpec → runnable code)**
      StrategySpec JSON → runnable SimTrader strategy class. Market-making and copy-wallet
      strategies: complete output. Arb and information-advantage: skeleton with hooks.

- [ ] **Historical tape library import (multi-source)**
      Normalize all available sources into standard tape format with source tier tags:
      (1) Silver tapes from Phase 1 reconstructor (pmxt + Jon-Becker + polymarket-apis)
      (2) Bronze tapes from Jon-Becker raw (trade-level, no book state)
      (3) Gold tapes from live Tape Recorder (accumulating from Phase 1)
      (4) Kaggle legacy imports if pre-existing (tagged `source='kaggle'`)

- [ ] **Auto Level 1 validation (multi-tape replay)**
      New hypothesis registered → run against 20+ diverse tapes using parallel Pool.
      Gate: ≥70% tapes positive PnL after fees. Failed: auto-generate post-mortem stub →
      write to `research` partition → prevents re-testing same dead-end.

- [ ] **Auto Level 2 validation (scenario sweep)**
      If L1 passes: four latency profiles (0ms/100% fills, 150ms/70%/5bps, 500ms/40%,
      1000ms/20%). Gate: profitable at realistic-retail. Low-latency-only strategies noted.

- [ ] **Auto Level 3 — 30-day shadow run trigger**
      If L2 passes: automated 30-day shadow run. Gate: shadow PnL within 25% of L1 replay
      prediction. Higher deviation = replay model not capturing live conditions.

- [ ] **Research partition write on gate pass + Discord approval**
      All gates pass → StrategySpec + validation report + shadow record → `research` partition
      → Discord `#polytool-approvals` with [Approve]/[Reject] buttons.

- [ ] **Simulated Adversary in BrokerSim**
      Competing MM module that detects when our quotes are consistently best on one side
      and free-rides our liquidity. Behavior: if our YES bid is best for ≥60 seconds,
      adversary posts a 1-tick better bid and cancels immediately after our fill.
      Surfaces second-order effects before they cost real money at Stage 3 scale.
      Spec and build now so BrokerSim architecture doesn't need rebuilding later.

- [ ] **n8n — Validation Pipeline Workflow**
      Sequences L1 → L2 → L3 with waits and gate checks. Visual: current hypothesis,
      which level, pass/fail status, estimated completion time for L3.

- [ ] **AUTORESEARCH — Parameter Loop (Phase 4 primary deliverable)**
      Implement the autoresearch engine for numerical parameter tuning.

      **Files:**
      - `autoresearch/engine.py` — main agent loop
      - `autoresearch/proposer.py` — LLM-based config modification proposals
      - `autoresearch/evaluator.py` — 3-confirmation benchmark runner using parallel Pool
      - `autoresearch/ledger.py` — DuckDB experiment ledger writer
      - `config/strategy_research_program.md` — constraint document (human-authored)
      - `config/benchmark_v1.tape_manifest` — fixed tape set

      **Loop (runs overnight, triggered by n8n at 22:00):**
      ```
      1. Load current best config + strategy_research_program.md
      2. LLM (Ollama) proposes a config change within stated bounds
      3. Run 3-confirmation benchmark (parallel Pool against benchmark_v1)
      4. If 2/3 confirmations beat old config by ≥5%: KEEP, update current best
      5. Else: REVERT, note the failure in ledger
      6. Write experiment row to DuckDB autoresearch_experiments table
      7. Repeat until EXPERIMENT_HOURS budget exhausted
      ```

      **Discord integration:** Green alert when improvement ≥10% is committed.
      Message format: "Autoresearch committed: +{pct}% median PnL. Delta: {config_diff}"

      **Studio Autoresearch tab:** Shows experiment feed, trajectory chart, program.md
      editor, benchmark manifest, and import button for distributed results.

- [ ] **Docker training image — one-command distributed compute**
      Build `polytool-autoresearch:latest` Docker image:
      - All Python dependencies pre-installed
      - benchmark_v1 tape set embedded (or mountable volume)
      - Current best config as starting point
      - `strategy_research_program.md` constraints included
      - Auto-detects `os.cpu_count()` for Pool sizing
      - Writes `experiment_batch_{date}.json` to `/results/` on host
      - `EXPERIMENT_HOURS` env var controls duration (default: 8)

      For non-technical friends: one command, leave overnight:
      ```bash
      docker run --rm -v ./results:/results -e EXPERIMENT_HOURS=8 \
        polytool-autoresearch:latest
      ```

      Import results next morning:
      ```bash
      polytool autoresearch import-results ./results/experiment_batch_20260315.json
      ```

      `Dockerfile` and `build_training_image.sh` are concrete deliverables alongside the
      engine. The image must work on machines with only Docker installed — no Python, no
      repo clone required. This is the technical spec for the "one-command" requirement.

---

### PHASE 5 — Advanced Strategies
> Activate after Phase 3 RAG Brain has produced validated StrategySpecs.

- [ ] **Resolution Timing Arb (oracle attack EV adjustment)**
      Monitor UMA Optimistic Oracle v3 at `0x157Ce2d672854c848c9b79C49a8Cc6cc89176a49`.
      EV = P(true_event)·P(honest_vote) + P(false_event)·P(attack) − entry − gas − opportunity_cost.
      Monitor UMA voting power concentration before positions. Avoid DVM escalation on
      high-value controversial markets (March 2025 precedent: 5M UMA tokens forced a
      false $7M resolution).

- [ ] **Combinatorial / Correlation Arb**
      Logically related market pairs. When implied joint probability diverges from historical
      correlation: `Cov(i,j) = P(i∩j) − P(i)·P(j)`. Executable at retail latency.

- [ ] **Information Advantage (news-driven directional)**
      Signal fires only if: LLM confidence >0.75, market <1% move, signal type + category
      has ≥10 proven historical events with >3% moves in Signals RAG.

- [ ] **15-Minute Crypto Markets (flash crash mean reversion)**
      BTC/ETH/SOL up/down markets. >threshold drop in first 5 min → >70% probability of
      mean reversion before bar close. Verify current dynamic taker fee structure first.

- [ ] **Gnosis CTF atomic conversion arb**
      Scanner architecture ported from `realfishsam/Risk-Free-Prediction-Market-Trading-Bot`.
      Monitors: sum of YES prices < $0.98 or > $1.02 → atomic conversion arb.
      Cannot be front-run once initiated on-chain. Binary complement arb is NOT viable
      (sum_ask floors above 1.001) — this is the CTF atomic conversion variant only.

- [ ] **Favorite-longshot bias exploitation**
      Provide liquidity as seller on extreme tail events (1-5¢ YES contracts). Quarter-Kelly
      to half-Kelly sizing. Sports and Entertainment markets prioritized (Jon-Becker:
      Sports 2.23pp gap, Entertainment 4.79pp). Calibration: at 1-cent markets YES takers
      lose 41% in expectation, NO buyers earn +23% — these are the position sizing anchors.

- [ ] **Market Obituary System — Stage 2 (tick-level upgrade)**
      Once Gold tapes exist from markets that subsequently resolved: replace Stage 1
      trade-level features with tick-level features (L2 book asymmetry, precise spread
      collapse timing, Poisson arrival rate acceleration vs κ baseline). Gold tapes required.

---

### PHASE 6 — Closed-Loop Feedback + Code-Level Autoresearch

- [ ] **Weekly strategy performance evaluation**
      perf_ratio = live_pnl_7d / predicted_pnl_from_validation.
      KEEP (≥0.75): performance record → research partition, Discord green.
      REVIEW (0.40-0.75): 50% allocation cut, Discord yellow, await human direction.
      AUTO_DISABLE (<0.40): remove from live, post-mortem → research, re-analysis triggered.

- [ ] **Live execution data feeds back into the loop**
      Every resolved position → ClickHouse: strategy ID, market, entry/exit price, PnL,
      fill latency, VPIN at entry, spread at entry. `alpha-distill` consumes this table.
      Bot becomes its own teacher.

- [ ] **Performance records in Research RAG**
      Weekly write for each active strategy. 6-month track record of what worked and when.

- [ ] **Source wallet re-analysis trigger**
      When strategy AUTO_DISABLED: re-run candidate-scan + wallet-scan on source wallets.
      Alpha may persist in a changed form.

- [ ] **external_knowledge validation_status updates**
      KEEP → cited docs: `CONSISTENT_WITH_RESULTS`.
      AUTO_DISABLE → cited docs: `CONTRADICTED`.
      Accumulates empirical credibility over time.

- [ ] **Strategy Graveyard Analytics**
      Monthly aggregation of `research` partition failures. Clusters of ≥3 failures sharing
      a characteristic → "graveyard summary" document in `external_knowledge` tagged
      `category: failure_pattern`. Prevents repeated category-level mistakes.

- [ ] **News Governor — Approach D (RAG-informed thresholds)**
      Signals RAG patterns directly inform governor sensitivity: if signal type X has caused
      >5% moves in ≥10 historical events for category Y, governor pre-widens spreads when
      X is detected — before the market moves. Combines Approach A (calendar), B (multi-market
      cancellation), and learned RAG patterns into one unified risk layer.

- [ ] **n8n — Feedback Loop Workflow**
      Weekly cron → `/api/strategy-review` → routes KEEP/REVIEW/AUTO_DISABLE →
      updates external_knowledge validation_status → updates capital allocation plan →
      triggers re-analysis if needed → Discord weekly digest.

- [ ] **AUTORESEARCH — Code-Level Loop (Phase 6)**
      Upgrade autoresearch from numerical parameter tuning to Python code modification.
      The agent proposes changes to the strategy Python file within the hardened allowlist
      defined in `strategy_research_program.md`:

      **Allowlist (agent may propose):**
      - Signal computation logic (new inputs into the quote calculation)
      - Reservation price formula modifications (within logit A-S structure)
      - Category-specific branching logic
      - New indicator combinations (e.g., add VPIN term to spread)

      **Hard denylist (enforced, agent cannot touch):**
      - Kill switch logic
      - EIP-712 signing code
      - Order execution paths
      - Risk manager pre-trade checks
      - ClickHouse write logic

      **Approval flow for code changes:**
      Agent benchmarks proposed code change → if 2/3 confirmations pass →
      Discord `#polytool-approvals` posts: code diff + before/after PnL + [Approve]/[Reject].
      Human reviews the diff and approves. Only then does the modified file enter rotation.
      No code change goes live without human review — this is the Phase 6 human gate.

      **Docker image updated for code-level experiments:**
      `polytool-autoresearch-code:latest` — same as parameter image but mounts the
      strategy file for modification. Requires human approval before any result propagates
      to the production strategy.

---

### PHASE 7 — Unified UI (PolyTool Studio Rebuild)
> Replace vanilla HTML/JS Studio with full React application.
> Stack: Next.js + Tremor + TradingView Lightweight Charts v5+

- [ ] **Project scaffold and design system**
      `/studio-v2`. Dark theme. Sidebar navigation with all tab names + one-sentence tooltips.

- [ ] **Dashboard tab**
      Tremor KPI cards. All metrics from `/api/bot/status` every 10 seconds. Required:
      bot status + uptime, daily PnL vs target, **cost coverage ratio** (trailing 30d
      revenue vs estimated monthly infra cost, green ≥2×, yellow 1-2×, red <1×),
      open positions, kill switch with CONFIRM modal, active markets, candidate scan last
      run, hypothesis registry summary, scraper stats, signals stats, n8n workflow health.

- [ ] **Bot Monitor tab**
      WebSocket `/api/bot/stream`. Open orders per market, probability chart (Baseline
      series), fill log (last 50), inventory skew gauge, daily PnL bar, risk limit gauges
      (green → yellow → red as limits approach).

- [ ] **SimTrader tab**
      Three sub-tabs: OnDemand (tape selector shows source tier badge Gold/Silver/Bronze,
      playback controls, probability chart, running PnL panel), Strategy Comparison
      (overlapping equity curves + metrics table + winner card), Tape Library (searchable
      table with tier badges, probability thumbnails, bulk-select for comparison).

- [ ] **Research tab**
      Candidate queue, wallet watchlist panel (top-50 with last seen position + last alert),
      hypothesis registry (validation trace on row expand), Flagged Review Queue (dossier
      cards + LLM report paste area + llm-save button).

- [ ] **Autoresearch tab** *(new in v4.2)*
      Experiment feed (timestamp, change description, PnL before/after, % improvement,
      KEEP/REVERT badge), trajectory chart (best-config median PnL over experiment count),
      `strategy_research_program.md` in-browser Markdown editor (Save writes to disk),
      Import results button (ingests `experiment_batch_*.json` from distributed runs),
      benchmark manifest card (active version + bump-version button with confirmation modal).

- [ ] **Signals tab**
      News feed newest-first. Cards: headline, source, timestamp, linked markets with prices,
      LLM confidence, t+5/30/120 reactions. Proven Signals RAG matches get colored border.
      News Governor status: whether high-risk calendar mode or multi-market cancellation
      defensive posture is currently active.

- [ ] **Knowledge (RAG) tab**
      Query across all 5 partitions. Results: source, partition, trust tier badge, date,
      relevance, 2-sentence summary. `external_knowledge` results show freshness_tier,
      confidence_tier, and validation_status badges.

- [ ] **Scraper tab**
      Daily log: source URL, title, 0-100 score breakdown (relevance/actionability/
      credibility/novelty each 0-25), accept/reject. Rejection rate chart. URL submission
      form. Domain override controls. Stats: total indexed, rejected, partition size,
      validation_status breakdown.

- [ ] **Grafana embed + Pipelines + Settings tabs**
      Same as v4.1. Settings adds: autoresearch config section (experiment hours, Pool size,
      benchmark version, code-level toggle), category scoring weights from Jon-Becker data,
      News Governor calendar editor.

- [ ] **Retire old Studio**
      Once v2 stable, retire vanilla HTML/JS Studio at localhost:8765. Both run in parallel
      during transition. New Studio takes over the port when old one is confirmed redundant.

---

### PHASE 8 — Scale Architecture
> Activate after 3+ validated strategies running and feedback loop operational.

- [ ] **Multi-bot capital manager**
      Three specialized bots: Market Maker (70% capital, 20-50 markets), Alpha Bot (20%,
      discovered strategies), Resolution Arb Bot (10%, UMA oracle). Portfolio-level risk
      limits enforced by the Capital Manager regardless of individual bot state.

- [ ] **Multivariate Kelly position sizing**
      `f* = Σ⁻¹ · μ`. `Cov(i,j) = P(i∩j) − P(i)·P(j)`. Ledoit-Wolf shrinkage on Σ.
      Quarter-Kelly to half-Kelly global scaling.
      Implementation: `sklearn.covariance.LedoitWolf`, `numpy.linalg.inv`.

- [ ] **Adverse selection detection at scale**
      (1) OFI >80% one-sided in 5 minutes: widen spreads.
      (2) Single order >5× our size: temporary widening.
      (3) Rapid mid-price move after fill: adjust γ upward for that market type.

- [ ] **AWS deployment**
      Two-server architecture. Live bot to NY/NJ region. Research server migrates earlier.
      Dedicated Polygon RPC. CloudWatch or equivalent infrastructure monitoring.

- [ ] **Sub-millisecond execution hardening**
      CPU thread pinning via `os.sched_setaffinity()`. Pre-compute EIP-712 invariant
      components at startup. Replace `eth_account` with `coincurve` C++ bindings.
      Combined: ~50ms → sub-5ms order submission latency.

- [ ] **Tier 3 LLM auto-escalation (funded by bot profit)**
      Enable Claude API auto-calls for flagged high-value wallets when
      `bot_profit_30d > api_cost_estimate`. Programmatic gate — checks profitability
      before spending tokens.

---

## Risk Framework

### Pre-Trade Checks (always enforced)

| Check | Stage 1 Default | What It Prevents |
|-------|----------------|-----------------|
| Max position per market | $500 USDC | Single market concentration |
| Max total notional | 80% of USDC balance | No liquidity buffer |
| Max single order size | $200 USDC | Misconfigured order |
| Daily loss cap | $100 USDC | Broken strategy today |
| Inventory skew limit | $400 USDC abs(long-short) | Compounding directional exposure |

### Kill Switch Hierarchy (five layers)

1. File kill switch — `touch artifacts/simtrader/KILL` — checked before every order
2. Daily loss cap — RiskManager blocks all new orders when `daily_pnl < -cap`
3. WS disconnect — `ConnectionClosed` → `emergency_stop()` → cancel all → backoff
4. Inventory limit — strategy returns `cancel_all` when `abs(inventory_usdc) > max`
5. Discord command — `/stop` in #polytool → Discord bot triggers `arm_kill_switch()`

### Wallet Security

- Primary capital: cold storage hardware wallet. Never on VPS. Never in `.env`.
- Trading hot wallet: separate wallet, only current stage capital.
- API key: derived via py-clob-client. Trading key ≠ funded address.
- USDC allowance: one-time approval limited to 2× current stage capital.

### Regulatory Note

Polymarket restricts access from certain jurisdictions including the United States.
Kalshi is CFTC-regulated and legal for US residents. Verify jurisdiction before deploying
capital. PolyTool does not constitute legal or financial advice.

---

## Capital Progression

| Stage | Capital | Duration | Success Criterion | Next |
|-------|---------|----------|------------------|------|
| 0: Paper Live | $0 | 72h | Zero errors, positive PnL estimate, kill switch + reconnect tested | → Stage 1 |
| 1: Micro | $500 USDC | 7 days | Positive realized PnL + rewards. No risk violations | → Stage 2 |
| 2: Small | $5,000 USDC | 2 weeks | Consistent daily positive PnL. All controls proven | → Stage 3 |
| 3: Scale-1 | $25,000 USDC | Ongoing | $75-250/day. 10+ markets. First Alpha strategy live | Continue |
| 4: Scale-2 | $100,000 USDC | Ongoing | $300-800/day. Multi-bot. 3+ validated strategies | Professional LP |

---

## Reference Documents

### Internal

| Document | Purpose |
|----------|---------|
| `docs/CURRENT_STATE.md` | **Primary handoff doc. Paste at start of every LLM session.** Kept ≤3 pages. |
| `docs/ARCHITECTURE.md` | Component map, data flow, one-line database rule |
| `docs/PLAN_OF_RECORD.md` | Mission, constraints, backtesting kill conditions |
| `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md` | Full SimTrader architecture |
| `docs/specs/SPEC-0011-live-execution-layer.md` | Track A execution layer |
| `docs/OPERATOR_QUICKSTART.md` | Step-by-step from zero to shadow |
| `docs/STRATEGY_PLAYBOOK.md` | Outcome taxonomy and EV framework |
| `config/strategy_research_program.md` | Autoresearch constraints. Human-updated. |
| `config/benchmark_v1.tape_manifest` | Fixed benchmark tape set for all experiments |

### Academic Papers

| Reference | Paper |
|-----------|-------|
| Market Making | Avellaneda & Stoikov (2008). "High-frequency trading in a limit order book." QF, 8(3), 217-224 |
| Inventory | Guéant, Lehalle & Fernandez-Tapia (2013). "Dealing with the inventory risk." Math. Financial Econ., 7(4) |
| Position Sizing | Kelly, J.L. (1956). "A New Interpretation of Information Rate." Bell System Technical Journal, 35(4) |
| Binary Markets | "Toward Black Scholes for Prediction Markets." arXiv:2510.15205 |
| Adverse Selection | "Optimal Signal Extraction from Order Flow." arXiv:2512.18648v2 |
| **PM Microstructure** | **Becker, J. (2026). "The Microstructure of Wealth Transfer in Prediction Markets." jbecker.dev. 72.1M trades. Makers +1.12%/trade. Category gaps: Finance 0.17pp, Sports 2.23pp, Crypto 2.69pp, Entertainment 4.79pp.** |
| PM Efficiency | Reichenbach & Walther (2025). "Exploring Decentralized Prediction Markets." SSRN:5910522 |
| Autoresearch | Karpathy, A. (2026). "autoresearch." github.com/karpathy/autoresearch. Autonomous overnight strategy experimentation pattern. |

### Key External Tools

| Tool | Role | License | Phase |
|------|------|---------|-------|
| pmxt (`github.com/pmxt-dev/pmxt`) | Unified PM data API — L2, OHLCV, WebSocket (Polymarket + Kalshi) | MIT | 1 |
| pmxt Archive (`archive.pmxt.dev`) | Free hourly Parquet L2 snapshots. Primary historical data source. | Free | 1 |
| Jon-Becker Dataset | 72.1M trades, 7.68M markets, Poly + Kalshi through Nov 2025. 36GB. | MIT | 1 |
| polymarket-apis (PyPI) | 2-min price history, public, no auth. Silver tape reconstruction. | Open | 1 |
| warproxxx/poly_data | Goldsky orderFilled events + wallet attribution from Polygon. | Open | 1 |
| DuckDB | Historical Parquet analytics. Zero-config, zero-import. | MIT | 1 |
| **lorine93s/poly-market-maker-bot** | **Pull: auto_redeem.py, order_executor.py cancel/replace, inventory_manager.py** | MIT | 1 |
| **realfishsam/prediction-market-arbitrage-bot** | **Pull: matcher.js fuzzy market matcher (port to Python), arbitrage.js EV formula** | MIT | 3 |
| **realfishsam/Risk-Free-Prediction-Market-Trading-Bot** | **Pull: arb scanner architecture for Gnosis CTF atomic conversion arb (Phase 5)** | MIT | 5 |
| **dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot** | **Pull: SMI formula, conviction score, 7-phase scanner pipeline, multi-window OFI** | MIT | 1-2 |
| **warproxxx/poly-maker** | **Pull: poly_merger module (NO→YES atomic conversion, gas optimization)** | Open | 1 |
| Polymarket/real-time-data-client | RTDS TypeScript client — reference for comment + crypto price stream (signals pipeline) | MIT | 3 |
| polymarketdata.co | 1-min L2 depth. Paid. Upgrade when profitable. | Commercial | post-profit |
| py-clob-client | CLOB execution. ONLY order execution path — never route orders through pmxt. | Open | 1 |
| karpathy/autoresearch | Autoresearch pattern reference. Overnight autonomous strategy experimentation. | MIT | 4 |
| MeatPy (vgreg) | Pattern reference only: parser→processor→recorder for Silver tape reconstruction. | BSD-3 | 1 |
| NautilusTrader | Reference for execution architecture. Polymarket adapter. Cython hot-path patterns. | LGPL | ref |
| TradingView Lightweight Charts | Probability charts in Studio | Apache 2.0 | 7 |
| Tremor | Dashboard UI components | MIT | 7 |
| Next.js | Studio frontend framework | MIT | 7 |
| python-louvain | Wallet clustering community detection | BSD | 2 |
| Ollama | Local LLM for Tier 1/2 specialist inference | MIT | 2 |

---

*End of PolyTool Master Roadmap — version 4.2 — March 2026*
*Living document. Update when architecture decisions are made or phases complete.*
*Supersedes v4.1. Reference v4.1 only for historical context.*
*Pending addendum: agenttrader (finnfujimura) analysis — share README to complete.*
