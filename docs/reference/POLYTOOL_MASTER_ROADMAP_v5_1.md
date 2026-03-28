# PolyTool — Master Roadmap
**Version:** 5.1 · **Date:** March 2026 · **Status:** Living Document

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

**Scope evolution:** PolyTool launches as a Polymarket-first system. After first sustained profit,
the architecture expands to a universal prediction market tool supporting Kalshi, Polymarket US
Exchange, and future platforms via a Platform Abstraction Layer. The pmxt library already
abstracts Polymarket + Kalshi behind one API, making this expansion low-cost when the time comes.

---

## Development Principles

These principles govern how features are built. They exist because past development
produced elaborate orchestration systems that never completed end-to-end.

1. **Simple Path First.** Before building an orchestrator, make the raw CLI commands work
   end-to-end manually. Orchestrators are convenience layers, not prerequisites.

2. **First Dollar Before Perfect System.** Any strategy that generates real profit — even $1 —
   is more valuable than an untested system with 500 passing tests. Ship revenue paths first,
   polish later.

3. **Triple Track Strategy.** Never depend on a single strategy for revenue. Three independent
   strategy tracks (market making, crypto pairs, sports directional) run in parallel. If one
   stalls, the others keep us alive.

4. **Front-Load Context, Not Chat.** Claude Code burns tokens re-discovering project
   conventions. Every convention, rule, and pattern belongs in `CLAUDE.md` and
   `CURRENT_STATE.md`, not in chat messages. A proper `CLAUDE.md` saves 30-40% of
   Claude Code token consumption.

5. **Checklist, Not Calendar.** Phases are ordered checklists, not week-based timelines.
   Complete items sequentially. Mark done. Move to next. No artificial deadlines, no
   guilt about pace — just forward progress.

6. **Visualize With What Exists.** Grafana is already built and reads from ClickHouse.
   Use it for all operational visibility until revenue justifies a custom dashboard.
   No new frontend code until post-profit.

---

## North Star Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             POLYTOOL SYSTEM                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
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
│  │  │  STRATEGY TRACKS                                             │   │   │
│  │  │  Track 1: A-S Market Maker (spread capture + rewards)        │   │   │
│  │  │  Track 2: Crypto Pair Bot (asymmetric accumulation)          │   │   │
│  │  │  Track 3: Sports Directional (ML probability model)          │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  AUTORESEARCH ENGINE (Phase 4+)                              │   │   │
│  │  │  strategy_research_program.md → agent loop → SimTrader       │   │   │
│  │  │  benchmark_v1 tape set → keep/revert → experiment ledger     │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      FASTAPI WRAPPER LAYER (Phase 3+)               │   │
│  │  Thin REST wrapper — no logic lives here. Not needed until Phase 3. │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              SCHEDULING (Phase 1: cron/APScheduler)                  │   │
│  │              (Phase 3+: n8n orchestration layer)                     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              VISUALIZATION (Phase 1: Grafana only)                   │   │
│  │              (Phase 7: PolyTool Studio Next.js rebuild)              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### How the Layers Work Together

**Python Core** is the brain. Every business rule, data transformation, RAG operation,
SimTrader run, scraper evaluation, LLM call, and autoresearch experiment lives here.

**FastAPI Wrapper** is a thin REST skin added in Phase 3 when automation needs HTTP endpoints.
Not needed for Phase 1 or 2.

**Scheduling** starts simple: cron jobs or APScheduler for Phase 1 automation (tape recording,
market scanning). Upgrades to n8n in Phase 3 when workflow complexity justifies it.

**The CLI never goes away.** It is the fastest way to test and debug. Everything starts
as a CLI command. Automation is layered on top of working CLI commands.

**Grafana** is the visualization layer from day one. It already exists, reads from ClickHouse,
and requires zero new code to add panels. The Studio rebuild happens in Phase 7 post-profit.

---

## Triple Track Strategy Pipeline

Three independent revenue paths running in parallel. Each can succeed or fail
independently. The bot only needs ONE to work to survive.

### Track 1 — Avellaneda-Stoikov Market Maker
**Markets:** Politics, sports, crypto (longer-duration event markets)
**Edge:** Spread capture + Polymarket liquidity rewards
**Capital needed:** $500+ for meaningful returns
**Validation:** Gate 2 parameter sweep → Gate 3 shadow → Stage 0 paper live
**Timeline to revenue:** Longest — requires tape library, calibration, shadow validation
**Why it matters:** Highest sustained revenue ceiling. $25K across 10 markets → $75-250/day.

### Track 2 — Crypto Asymmetric Pair Bot
**Markets:** 5-minute and 15-minute BTC/ETH/SOL up-or-down markets
**Edge:** Buy YES cheap when it dips + buy NO cheap when it dips = pair cost < $1.00 = guaranteed profit at settlement regardless of outcome. Maker orders earn 20bps rebate.
**Capital needed:** $50-200 is enough to start
**Validation:** Backtest on historical 5-min market data, then paper mode, then live
**Timeline to revenue:** Shortest — can be built and deployed in days
**Why it matters:** First dollar. Proves the system works. Funds compute.

The asymmetric pair strategy (sometimes called "gabagool strategy") is NOT latency
arbitrage. It does not race the oracle. It accumulates YES and NO positions at favorable
prices over time using limit orders (maker), ensuring total pair cost stays below $1.00.
No special infrastructure needed — Python is fine, home internet is fine.

Fee structure on 5-min/15-min crypto markets:
- Taker orders: small fee (dynamic, peaks near 50% odds)
- Maker orders: 20bps REBATE (you get paid to provide liquidity)
- Strategy uses maker orders exclusively → net positive fee impact

### Track 3 — Sports Directional Model
**Markets:** NBA, NFL, soccer, and other sports prediction markets
**Edge:** ML probability model trained on freely available historical data. When model
disagrees with Polymarket price by >5 points, signal fires.
**Capital needed:** $200+ for diversified sports positions
**Validation:** Paper predictions tracked against outcomes for 2+ weeks before capital
**Timeline to revenue:** Medium — model can be trained immediately on free data, but needs
track record before deploying capital
**Why it matters:** Jon-Becker data shows Sports markets have 2.23pp maker-taker gap —
wide spreads mean edge is available for anyone with a slightly better model than the
market consensus.

Free data sources:
- `nba_api` Python package — full NBA stats back to 1946
- `nfl_data_py` — play-by-play, rosters, schedules
- `sportsreference` Python package — multi-sport
- Kaggle datasets for historical outcomes

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
- **Crypto pair bot trade execution** — within configured risk limits

### Human Confirmation Required (Discord button approval)
- **Promoting a strategy from validated to live capital** — most important gate.
- **Capital stage increases** (Stage 1 → 2 → 3) — explicit human decision only.
- **Any strategy flagged LOW_CONFIDENCE by LLM evaluation**
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

## Team & Developer Workflow

### Team Structure

| Role | Person | Tools | Responsibility |
|------|--------|-------|---------------|
| Director / Decision-Maker | Aman (Augusta, GA) | This Claude Project | Strategy, prioritization, manual operations |
| Architect | ChatGPT (GPT-4o, $20/mo) | ChatGPT Pro | Specs, prompts, CLAUDE.md files |
| Primary Executor | Claude Code (Pro plan) | Terminal + repo | Multi-file coding, testing, complex features |
| Secondary Executor | Codex | GitHub | Batch tasks, parallel work packets |
| Quick Edits | Cursor (free tier) | IDE | Single-file edits, autocomplete |
| Dev Partner | Canadian team member | Their machine | Code execution, testing, bot hosting |

### Workflow Rules

1. **ChatGPT writes CLAUDE.md-compatible output.** Instead of freeform specs, ChatGPT
   produces structured prompts that include scope guards, don't-do lists, and file paths.
   These are directly consumable by Claude Code without additional context chat.

2. **CLAUDE.md is the highest-ROI file in the repo.** Keep it current. Every convention,
   database rule, file structure pattern, and known gotcha belongs there. Claude Code reads
   it automatically at session start — a good CLAUDE.md eliminates 30-40% of wasted tokens.

3. **CURRENT_STATE.md is updated after every meaningful work unit.** Never more than one
   session out of date. This is what gets pasted into new LLM sessions.

4. **One work packet per session.** Scoping discipline prevents context bloat. Each Claude
   Code or Codex session has one clear objective with explicit completion criteria.

5. **Dev logs are mandatory.** Every code session produces a dev log at
   `docs/dev_logs/YYYY-MM-DD_<description>.md`. This is non-negotiable — it's how we
   track what happened when things go wrong.

### Post-Profit Upgrade Path

When bot generates consistent profit:
- **Claude Max $100/mo** — 5x Pro usage, Opus 4.6 for Claude Code, agent teams
  for parallel workstreams. Single biggest productivity upgrade.
- **Dedicated API keys** for automated LLM calls (Tier 3 auto-escalation)

---

## LLM Policy — Self-Funding Model

| Tier | Model | Cost | When Used |
|------|-------|------|-----------|
| Tier 1 | Free cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash) | Free | All automated hypothesis generation, scraper evaluation, signal classification |
| Tier 1b | Ollama local (Qwen3-30B or Llama-3-8B) | Free | Fallback when cloud APIs are down or rate-limited |
| Tier 2 | Manual escalation (Claude / ChatGPT) | Free (operator tokens) | When Tier 1 flags low confidence |
| Tier 3 | Claude API auto-escalation | Paid API | Only enabled when `bot_profit_30d > api_cost_estimate` |

### Why Free Cloud Over Local-Only

Llama-3-8B running locally on 32GB RAM alongside Docker + ClickHouse + DuckDB leaves
insufficient headroom for quality inference. DeepSeek V3 via free API provides dramatically
better reasoning at zero cost. Gemini 2.5 Flash via Google AI Studio gives 1,500 free
requests/day — more than enough for signal classification.

Local Ollama remains as a fallback for when cloud APIs are rate-limited or unavailable.
The system should gracefully degrade: try Tier 1 cloud → fall back to Tier 1b local →
flag for Tier 2 manual if both fail.

### Multi-LLM Specialist Routing (Phase 3)

Four specialist tasks routed to the best free model for each:

| Specialist | Task | Recommended Model |
|------------|------|-------------------|
| Wallet Analyst | Dossier → hypothesis | DeepSeek V3 (best reasoning) |
| Research Evaluator | Document → quality score | Gemini Flash (fast, free quota) |
| Signal Classifier | News + market → relevance | Gemini Flash |
| Post-mortem Writer | Failed strategy → report | DeepSeek R1 (structured output) |

---

## Multi-Layer Data Stack

The key insight: hourly L2 anchor points from the pmxt archive transform reconstruction
from "build from nothing" to "fill 60-minute gaps between known states."

### The Five Free Layers

**Layer 1 — pmxt Archive (hourly L2 snapshots)**
`archive.pmxt.dev` — free hourly Parquet snapshots of full Polymarket AND Kalshi L2
orderbook and trade data. This is your structural anchor.

**Layer 2 — Jon-Becker Dataset (72.1M trades, 7.68M markets, 36GB)**
`github.com/Jon-Becker/prediction-market-analysis` — MIT license. Also seeds
`external_knowledge` RAG partition immediately as PEER_REVIEWED.

**Layer 3 — polymarket-apis PyPI (2-minute price history)**
Public, free, no API key. 30 mid-price observations per 60-minute window.

**Layer 4 — Subgraph / Goldsky (on-chain confirmation + wallet attribution)**
`warproxxx/poly_data` provides `orderFilled` events with maker/taker wallet addresses.

**Layer 5 — Live Tape Recorder (non-negotiable, start now)**
Tick-level millisecond data. Only source of true microstructure.

### Tape Library Tiers

| Tier | Source | Granularity | Use Case | Available |
|------|--------|-------------|----------|-----------|
| **Gold** | Live Tape Recorder | Tick-level, ms | Microstructure, A-S calibration, Gate 3 | Accumulates from now |
| **Silver** | pmxt + Jon-Becker + polymarket-apis reconstruction | ~2 min effective | Strategy PnL, Gate 2, autoresearch | After bulk import |
| **Bronze** | Jon-Becker raw trades only | Trade-level, no book | Category analysis, κ MLE | After download |

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

This is not perfect — cancellations without subsequent fills are invisible — but the
confidence level is high enough for strategy-level PnL testing. Tag every reconstructed
tape with `reconstruction_confidence` so the validation pipeline knows which results to
weight more cautiously.

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
- Development machine (i7-8700K, 6 cores, 32GB RAM): `Pool(10)` — 50 tapes in ~5 batches
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

## RAG Architecture — Hybrid Partitioned Brain

One Chroma collection (`polytool_brain`) with four internal partition tags.
Built incrementally: `user_data` exists now, `external_knowledge` seeded in Phase 1,
`research` added in Phase 2 when validated strategies exist, `signals` added in Phase 3
when the news pipeline produces measured reaction data. The `market_data` partition from
v5.0 has been eliminated — Gamma API + ClickHouse + DuckDB already serve this role
without duplication.

| Partition | Contains | Trust Tier | Who Writes | When Built |
|-----------|----------|-----------|-----------|------------|
| `user_data` | Dossiers, scan artifacts, LLM reports | Low / Exploratory | Automated pipeline | Exists now |
| `external_knowledge` | Academic papers, Jon-Becker findings, research, forum threads | Medium / Reference | Scraper + quality gate | Phase 1 (seed), Phase 2 (scraper) |
| `research` | Validated StrategySpecs, performance records, post-mortems | High / Curated | Gate pass + human confirmation | Phase 2 (after first validated strategy) |
| `signals` | Proven news patterns (≥10 events, >3% move) | Medium | Auto at threshold | Phase 3 (after news pipeline built) |

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

## $POLY Airdrop Strategy

Polymarket has signaled a $POLY token launch. Airdrops typically reward early, active
platform users. This creates a secondary revenue stream from on-chain activity.

### Rules (overlay on all trading activity)
- Maintain consistent daily trading volume from day one of account setup
- Diversify activity across multiple market categories (not just crypto)
- Track cumulative on-chain transaction count as a KPI alongside PnL
- Even during paper-live testing, execute real small-size ($1-5) trades for airdrop farming
- Monitor Polymarket Discord/Twitter for airdrop announcements
- When announced, temporarily increase activity volume

### Capital Implication
Even a breakeven or slightly negative trading bot becomes net-positive if the airdrop
is valuable. This changes the risk calculus for early Stage 1 deployment — don't wait
for perfect strategy validation to start generating on-chain activity.

---

## AWS Architecture — Two-Server Design

**Stay local until profitable. Design for AWS from day one.**

**Phase 1:** Bot runs on Canadian dev partner's machine (Canada — no Polymarket geo-restriction).
Aman's machine (Augusta, GA) is the development environment.

**Post-profit Server 1 — Research Server** (~$100-150/month): Scanner, scraper, RAG,
LLM inference, Grafana, ClickHouse, DuckDB, scheduling.

**Post-profit Server 2 — Execution Server** (~$300-500/month): Live bot only. No other
processes. Dedicated cores. Closest region to Polymarket CLOB.

**Cost coverage metric** always visible in Grafana: trailing 30-day revenue vs estimated
monthly infra cost. Green ≥2×, yellow 1-2×, red <1×.

---

## n8n Pipeline Architecture (Phase 3+)

n8n is deferred to Phase 3. Until then, APScheduler or cron handles scheduling.
When n8n is deployed, these are the target workflows:

| Workflow | Trigger | What n8n Does |
|----------|---------|---------------|
| Candidate Discovery | Cron every 6h | Calls `/api/candidate-scan` → filters → queues new wallets |
| Wallet Scan Loop | New candidate in queue | Calls `/api/wallet-scan` → waits → triggers llm-bundle |
| LLM Report Generation | Scan complete | Calls Tier 1 LLM → evaluates → saves or flags |
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
- Phase 3: Runs locally.
- Phase 8+: Moves to AWS alongside the live bot.

---

## UI Architecture — PolyTool Studio (Phase 7)

Phase 1 uses Grafana only. Phase 7 rebuilds the UI as a full React application.

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

### Autoresearch Tab Detail

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

## Context Management

### CLAUDE.md — The Most Important File in the Repo

The current `CLAUDE.md` is 65 lines and describes PolyTool as "a monorepo for Polymarket
reverse-engineering tools." This is critically underweight. Claude Code reads this file
automatically at session start — a comprehensive `CLAUDE.md` eliminates 30-40% of wasted
token consumption by front-loading project conventions.

**CLAUDE.md must contain:**
- Project overview (what it actually is, not what it was 3 months ago)
- Repository structure with all current directories
- The ClickHouse/DuckDB one-sentence rule
- Gate system explanation (what each gate tests, current status)
- Strategy track descriptions (market maker, crypto pairs, sports directional)
- Tape tier definitions (Gold/Silver/Bronze)
- Testing conventions (test file naming, what to test)
- Known Windows gotchas (encoding, Docker/WSL, path separators)
- CLI command reference (grouped by category)
- File naming conventions for dev logs, specs, artifacts
- Don't-do list (no Kafka, no modifying specs, etc.)

**Updating CLAUDE.md is a Phase 0 deliverable.** It should be rebuilt before any new
feature work begins.

### CURRENT_STATE.md

Tightly-written 2-3 page living document. Updated after every meaningful work unit.
Contains: what's built, what's partially built, current gate status, active blockers,
current data assets. Paste at start of every new LLM session.

### Artifacts Directory Standard

All runtime artifacts live under `artifacts/` (gitignored). Standard layout:

```
artifacts/
  tapes/                    # ALL tapes, unified by tier
    gold/                   # Live-recorded from harvester/shadow
    silver/                 # Reconstructed from pmxt + Jon-Becker
    bronze/                 # Jon-Becker raw trade tapes
    crypto/                 # Crypto pair bot recordings
    shadow/                 # Shadow run tape recordings
  gates/                    # Gate validation artifacts
    gate2_sweep/            # MM parameter sweep results
    gate3_shadow/           # Shadow validation
    manifests/              # Tape manifests
  simtrader/                # SimTrader execution outputs
    runs/                   # Replay runs
    sweeps/                 # Parameter sweeps
    ondemand_sessions/      # On-demand sessions
  dossiers/users/           # Per-user wallet dossiers
  research/batch_runs/      # Research batch analysis
  benchmark/                # Benchmark closure pipeline
  market_selection/         # Market scan JSON outputs
  watchlists/               # Ranked watchlist files
  debug/                    # One-off diagnostics (safe to clean periodically)
```

All tapes live under `artifacts/tapes/` organized by tier. Never create tape directories
elsewhere. Every new tool that writes artifacts must follow this layout.

### External Data Paths

Jon-Becker dataset (36GB, 72.1M trades) and pmxt archive (hourly L2 Parquet) live in a
configured external folder outside the repo. DuckDB reads Parquet files directly from the
configured path — no import step, no copying into the repo. Document the path in
`CLAUDE.md` so every coding session knows where to find them.

Default paths (configurable):
- Jon-Becker: `D:/polymarket_data/jon_becker/` (or equivalent on partner's machine)
- pmxt archive: `D:/polymarket_data/pmxt_archive/`

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
| Hypothesis Registry | Register, status, experiment-init, experiment-run, validate, diff, summary |
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
| OrderManager | Quote reconciliation, rate caps |
| MarketMakerV0 | Conservative two-sided quoting, inventory skew, binary guards |
| Execution Primitives | KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner |

### Benchmark Pipeline (Built, Not Yet Completed End-to-End)

| Component | Status |
|-----------|--------|
| Silver Tape Reconstructor | Operational v1, DuckDB integration pending |
| Benchmark Manifest Curator | Built, blocked on tape shortages |
| Gap-Fill Planner | Built, 9,249 markets discovered, targets manifest written |
| Gap-Fill Execution | Built, dry-run confirmed, real generation not yet run |
| New-Market Capture | Built, requires live Gamma API connectivity |
| Benchmark Closure Orchestrator | Built, not yet completed end-to-end |

---

## Development Checklist

---

### PHASE 0 — Accounts, Setup & CLAUDE.md
> **Priority: IMMEDIATE. Cannot trade without accounts. Cannot develop efficiently
> without proper CLAUDE.md.**

- [x] **Rebuild CLAUDE.md**
      Rewrite from 65 lines to comprehensive project context file. Include all items
      listed in the Context Management section above. This is the single highest-ROI
      task for development velocity. Do this before any code work.

- [ ] **Polymarket account setup**
      Create Polymarket account. Complete KYC if required. Set up a browser wallet
      or use WalletConnect. Fund with minimum USDC for testing ($50-100).
      Note: Access from US may require VPN or running the bot from Canadian
      partner's machine. Test access before committing capital.

- [ ] **Kalshi account setup (backup)**
      Create Kalshi account (CFTC-regulated, US-legal). Complete KYC. Fund with
      minimum for testing. This is the jurisdiction-safe backup path.

- [ ] **USDC funding path**
      Establish the fiat → USDC → Polymarket pipeline:
      (1) Fiat to Coinbase/Kraken (or preferred exchange)
      (2) Buy USDC
      (3) Withdraw USDC to Polygon network
      (4) Deposit to Polymarket
      Document the exact steps, fees at each stage, and time required.

- [ ] **Wallet architecture setup**
      Create two wallets:
      (1) Cold wallet — capital storage. Never on VPS. Never in `.env`.
      (2) Hot wallet — trading only. Funded with current stage capital only.
      Derive API key via py-clob-client. Document the process.

- [ ] **Canadian dev partner environment setup**
      Write step-by-step setup guide for partner:
      (1) Clone repo, install Python deps, verify `python -m polytool --help`
      (2) Install Docker, run `docker compose up -d`, verify ClickHouse + Grafana
      (3) Test Polymarket WS connectivity
      (4) Verify bot can run in dry-run mode
      This machine will host the live bot — it must be reliable.

- [x] **Write `docs/OPERATOR_SETUP_GUIDE.md`**
      Comprehensive guide covering: account setup, wallet architecture, fund flow
      (fiat → exchange → USDC → Polygon → Polymarket → trading → withdrawal),
      capital allocation rules (50% reinvest, 30% tax reserve, 20% compute),
      tax tracking (every trade logged with timestamps and cost basis),
      minimum balances (gas reserve, withdrawal buffer, tax reserve),
      infrastructure setup (VPS, RPC, SSH).

- [ ] **Windows development gotchas document**
      Add to CLAUDE.md or separate doc: PowerShell stdout encoding (`cp1252`
      incompatible with Unicode arrows/symbols), Docker Desktop WSL2 sandbox
      permissions (Codex sandbox account ≠ real Windows user), path separator
      issues, `.env` file encoding. Every known Windows-specific bug and its fix.

- [ ] **Document external data paths in CLAUDE.md**
      Jon-Becker (36GB) and pmxt archive live outside the repo. Add their paths
      to CLAUDE.md so every dev agent session knows where to find them. DuckDB
      reads Parquet directly — no import step needed. Also document the
      `artifacts/` directory standard layout from the Context Management section.

---

### PHASE 1A — Track 2: Crypto Pair Bot (Fastest Path to First Dollar)
> **Priority: HIGH. This is the quickest revenue path. Build standalone, no
> SimTrader dependency.**

- [x] **Binance/Coinbase WebSocket price feed** *(shipped 2026-03-26)*
      `BinanceFeed`, `CoinbaseFeed`, and `AutoReferenceFeed` (primary + fallback)
      in `packages/polymarket/crypto_pairs/reference_feed.py`. CLI flag:
      `--reference-feed-provider binance|coinbase|auto`. 55 offline tests.
      Coinbase fallback resolves Binance HTTP 451 geo-restriction blocker.

- [ ] **Polymarket 5-min/15-min market discovery**
      Auto-discover active crypto up-or-down markets via Gamma API. Track
      market slugs, token IDs, start/end times, and current prices.

- [ ] **Asymmetric pair accumulation engine**
      Core logic: monitor both YES and NO orderbooks. When YES price drops below
      threshold (e.g., $0.48 when model says fair value is $0.52), place a
      maker limit buy. Same for NO. Track cumulative pair cost. When pair
      cost < $1.00 - minimum_profit_threshold, both sides are held to settlement.
      Guaranteed profit = $1.00 - pair_cost per pair.

- [ ] **Risk controls for crypto pair bot**
      Max capital per 5-min window. Max daily loss cap. Max open pairs.
      Kill switch (file-based, same as market maker). Position tracking
      persisted to ClickHouse.

- [ ] **Grafana dashboard — crypto pair bot**
      Panels: active pairs, pair cost distribution, realized profit per
      settlement, cumulative PnL, daily trade count (for airdrop tracking).

- [ ] **Paper mode testing**
      Run against live markets with simulated fills for 24-48 hours.
      Verify: pair completion rate, average pair cost, estimated profit
      per pair, fill rate on maker orders.

- [ ] **Live deployment — crypto pair bot**
      Deploy on Canadian partner's machine. $50-100 initial capital.
      Monitor via Grafana for first 24 hours. Scale if profitable.

---

### PHASE 1B — Track 1: Market Maker (Gate Closure → Live)
> **Priority: HIGH. Runs in parallel with Phase 1A. This is the long-term
> revenue engine.**

- [ ] **Complete Silver tape generation end-to-end**
      The benchmark pipeline tooling is built but has never completed a full run.
      **Simple path first:** Instead of running the full closure orchestrator,
      manually run each step in sequence and verify output before moving on:
      (1) `fetch-price-2min` for priority-1 tokens — verify rows in ClickHouse
      (2) `batch-reconstruct-silver` for one market — verify tape file created
      (3) If one works, run the batch for all 39 priority-1 targets
      (4) `benchmark-manifest` — verify manifest created with 50 tapes
      Only after this works manually should the orchestrator be used.

- [ ] **Pass Gate 2 — Parameter sweep (≥70% positive PnL)**
      Run MarketMakerV0 (or V1 if Logit A-S is ready) sweep across benchmark_v1.
      Gate: ≥70% of 50 tapes positive net PnL after fee model.
      Must also validate at realistic-retail latency (150ms, 70% fill rate).

- [x] **MarketMakerV1 — Logit A-S upgrade**
      Transform mid-price to log-odds: `x = ln(p/(1-p))`. Compute reservation
      price and spread in unbounded domain. Back-transform via sigmoid.
      κ calibrated via MLE on Jon-Becker 72M trades per category (DuckDB query).
      NumPy vectorized — no Python loops in hot path.

- [ ] **Begin Gate 3 — Shadow run**
      3-5 live markets, best config from Gate 2, simulated fills only.
      Shadow PnL within 25% of Gate 2 replay prediction = PASS.

- [ ] **Stage 0 — Paper Live (72-hour dry-run)**
      Full stack in dry-run mode. Zero errors, positive PnL estimate,
      kill switch working, WS reconnection working.

- [ ] **Stage 1 — $500 live deployment**
      Deploy on Canadian partner's machine. Risk limits enforced.
      Target 3-5 markets. 7 days. Success: positive realized PnL + rewards.

- [ ] **Bulk data import (if not already done)**
      pmxt archive + Jon-Becker dataset downloaded and accessible via DuckDB.
      DuckDB reads Parquet directly — no ClickHouse import needed.

- [ ] **DuckDB setup and integration**
      `pip install duckdb`. Verify queries against pmxt and Jon-Becker Parquet.

- [ ] **Tape Recorder rewrite — pmxt.watchOrderBook()**
      Replace custom WS client with pmxt. Output format stays identical.

- [ ] **Auto-redeem — position redemption for settled markets**
      Pull from `lorine93s/polymarket-market-maker-bot`. Without this, capital
      is locked in settled positions indefinitely.

- [ ] **Multi-window OFI**
      60min, 4hr, 24hr rolling windows from dylanpersonguy's implementation.

- [ ] **News Governor — Risk Layer**
      Scheduled high-risk calendar (Fed meetings, elections, major sports finals).
      Auto-widen spreads during configurable windows.

- [ ] **Parallel SimTrader — multiprocessing.Pool**
      Prerequisite for autoresearch and efficient sweeps.

- [x] **Benchmark tape set — benchmark_v1**
      50 tape manifest. Mix of Gold and Silver. Fixed for experiment series.

- [x] **Market Selection Engine**
      Scores all active markets every 2 hours using a seven-factor composite formula.
      Routes capital to the highest-edge opportunities regardless of raw volume.

      **Seven scoring factors (Phase 1 static weights):**

      | Factor | Weight | Source | What It Measures |
      |--------|--------|--------|-----------------|
      | Category edge | 0.20 | Jon-Becker 72.1M trades | Maker-taker gap by market category |
      | Spread opportunity | 0.20 | Live CLOB orderbook | Wider spread = more per-fill profit |
      | Volume | 0.15 | Gamma API (log-scaled) | Fill rate / how often resting orders execute |
      | Competition density | 0.15 | CLOB orderbook levels | Fewer competing MMs = bigger share of edge + rewards |
      | Reward APR | 0.15 | Q-score share estimate | Polymarket liquidity rewards (often 50-80% of total income) |
      | Adverse selection | 0.10 | Category priors | Risk of informed traders picking off resting orders |
      | Time to resolution | 0.05 | Gamma API end date | Inverted U — peaks at ~14 days |

      **Category edge priors (empirical, from Jon-Becker):**
      Entertainment/World Events/Media: 1.0 (4.79-7.32pp gap)
      Crypto: 0.70 (2.69pp) · Weather: 0.65 (2.57pp) · Sports: 0.55 (2.23pp)
      Politics: 0.25 (1.02pp) · Finance: 0.05 (0.17pp — near-efficient)

      **Gate filters (hard constraints, must all pass):**
      volume_24h > $500, spread > 0.5¢, days_to_resolution > 1, orderbook enabled.

      **Additional scoring modifiers:**
      - Longshot bonus: +0.15 max for markets priced beyond 15¢/85¢ (favorite-longshot bias)
      - NegRisk penalty: ×0.85 for multi-outcome markets (Phase 1 infrastructure limitation)

      **Composite:** `score = Σ(w_i × factor_i) + longshot_bonus × negrisk_penalty`

      **Phase 4+ learning path:** Static weights → EWA updates from live PnL correlation
      → Thompson Sampling multi-armed bandit for explore/exploit allocation. All weights
      and priors in `config.py` are tunable by autoresearch.

      **CLI:** `python -m polytool market-scan --top 20` outputs ranked market table.
      JSON output to `artifacts/market_selection/YYYY-MM-DD.json` for downstream consumption
      by harvester and live bot.

- [ ] **Universal Market Discovery (NegRisk + Events + Sports)**
      Three bugs in the original market discovery pipeline blocked access to front-page
      markets. All fixed in v5.1:

      **(1) Volume sorting:** `fetch_markets_page` now passes `order=volume24hr` and
      `ascending=false` to the Gamma API. Previously returned markets in arbitrary order,
      causing high-volume markets to be buried under novelty markets.

      **(2) Positional token assignment:** `_identify_yes_index` no longer rejects markets
      with non-YES/NO outcome names (e.g. "Pistons"/"Timberwolves"). A tier-3 positional
      fallback assigns token index 0 as primary. Sports matchup markets, named NegRisk
      outcomes, and any future market type are now valid candidates.

      **(3) Events-based discovery:** New `fetch_top_events` method hits `/events` endpoint,
      decomposes multi-outcome events (e.g. "Presidential Election 2028" with 128 outcomes)
      into individual tradeable markets. Each outcome has its own YES/NO token pair and is
      a valid market-making target.

      **Architectural principle:** The scanner is market-type agnostic. Any tradeable token
      pair on the platform is a valid candidate. Category classification is metadata, not a
      filter gate. This ensures the system works for all current and future Polymarket
      market types without code changes.

- [ ] **Seed Jon-Becker findings into RAG `external_knowledge`**
      One-time operation: seed the four key empirical findings from the 72.1M trade analysis
      as `external_knowledge` entries with `confidence_tier: PEER_REVIEWED`:
      (1) Maker +1.12% / taker -1.12% consistent across 80/99 price levels
      (2) Category allocation: Entertainment 4.79pp, Sports 2.23pp, Finance 0.17pp
      (3) Favorite-longshot: YES at 1¢ = -41% EV, NO at 1¢ = +23% EV
      (4) Regime shift: maker edge only emerged post-October 2024
      Also seed the Avellaneda-Stoikov (2008) and Kelly (1956) paper summaries.

- [ ] **Grafana live-bot panels**
      Open orders, fill rate, inventory skew, daily PnL, kill switch status.

- [x] **Discord alert system — Phase 1 (outbound only)**
      Webhook-based. Green/yellow/red. Fire within 30 seconds of event.

---

### PHASE 1C — Track 3: Sports Directional Model (Foundation)
> **Runs in parallel with 1A/1B from the start. No capital needed initially —
> just model training and paper prediction tracking.**

- [ ] **Historical sports data ingestion**
      Download NBA data via `nba_api`, NFL via `nfl_data_py`.
      Store in DuckDB for research queries.

- [ ] **Probability model v1 — NBA**
      Train a simple model (logistic regression or gradient boosted trees) on
      historical game outcomes. Features: team records, home/away, recent form,
      rest days, injuries (if available). Output: win probability per team.

- [ ] **Polymarket price comparison**
      For each upcoming NBA game, fetch current Polymarket prices.
      Compare model probability to market probability. Log disagreements
      (model says 65%, market says 55% = 10-point signal).

- [ ] **Paper prediction tracker**
      Log every model prediction + Polymarket price + actual outcome to
      ClickHouse. After 2+ weeks, compute: model accuracy, calibration,
      profit if we had traded every signal above threshold.

- [ ] **Grafana sports model dashboard**
      Panels: model vs market scatter plot, cumulative paper PnL,
      calibration curve, signal frequency by sport.

- [ ] **Live deployment (after paper validation)**
      When paper track record shows consistent edge over 2+ weeks:
      deploy with $200 capital, Kelly-fraction sizing.

---

### PHASE 2 — Discovery Engine + Research Scraper
> Runs in parallel after Phase 1 strategies are generating revenue or in shadow.

- [ ] **Candidate Scanner CLI (`candidate-scan`)**
      9 signals: new-account large position (hard-flag), unusual concentration, consistent
      early entry, high CLV, COMPLETE_SET_ARBISH, win-rate outlier, Louvain community
      detection (python-louvain), Jaccard similarity (>0.7 across ≥5 shared markets),
      temporal coordination (<100ms variance across 10+ wallets).
      Reference `dylanpersonguy` 7-phase scanner pipeline and conviction score formula
      (whale_count × dollar_size) before building. Do not rebuild debugged logic.

- [ ] **Scheduling — APScheduler or cron**
      Simple Python scheduling for: market scanning (every 2h), tape recording
      (continuous), health checks (every 1min), candidate discovery (every 6h).
      No n8n yet — just scheduled Python functions.

- [ ] **Local LLM integration (Tier 1 cloud + Tier 1b Ollama fallback)**
      DeepSeek V3 API for hypothesis generation. Gemini Flash for evaluation.
      Ollama (Qwen3-30B or Llama-3-8B) as fallback. Returns structured hypothesis.json.
      Confidence heuristic gates low-quality outputs to flagged review queue.

- [ ] **Wallet Watchlist — Real-Time Alert Following**
      Top 20-50 wallets monitored every 15 min. New position in unseen market →
      Discord yellow alert immediately: wallet handle, market slug, position size, entry price.
      Conviction score (whale_count × dollar_size) determines alert priority tier.
      Config in `config/watchlist.json`, editable from Studio Research tab.

- [ ] **Market Obituary System — Stage 1 (trade-level)**
      Using DuckDB queries on Jon-Becker + pmxt archive data:
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
      Stage B (evaluate): Tier 1 LLM scores 0-100 (4 dimensions × 25). Default threshold: 55/100.
      Tune in first two weeks of manual review. Accepted docs: metadata includes
      `freshness_tier`, `confidence_tier`, `validation_status: UNTESTED`.

- [ ] **Domain Specialization Layer**
      Category-specific CLV breakdown per wallet. Category-specific signal pipelines for
      highest-alpha niches. Jon-Becker category gap table seeded into `external_knowledge`
      as PEER_REVIEWED prior.

---

### PHASE 3 — Hybrid RAG Brain + Kalshi + n8n
> Upgrade infrastructure after revenue is flowing.

- [ ] **Unified Chroma collection (`polytool_brain`)**
      Migrate all existing `kb/` content into a single Chroma collection with four partition
      tags (`user_data`, `external_knowledge`, `research`, `signals`). Write policy
      enforcement added at ingest time — `research` partition gate is programmatic, not a
      convention. Existing RAG queries continue to work via the same CLI commands, now
      pointing at the unified collection. The `market_data` partition from v5.0 is eliminated
      — Gamma API (live), ClickHouse (streaming), and DuckDB (historical) already serve this
      role. Adding a RAG layer on top would duplicate data without unique capability.

      **Incremental build:**
      - `user_data` — already exists and works. Migrate as-is.
      - `external_knowledge` — seeded in Phase 1 with Jon-Becker findings. Phase 2 adds
        the LLM-assisted scraper for continuous ingestion of papers, Reddit, GitHub.
      - `research` — activated when first strategy passes Gate 3 and runs live.
        Write gate enforces `validation_gate_pass` artifact requirement.
      - `signals` — activated when news pipeline (RSS + social) is producing measured
        market reactions. Pattern graduates to RAG only at ≥10 events with >3% move.

- [ ] **Kalshi integration (pmxt-enabled)**
      With pmxt abstracting the exchange interface, Kalshi integration is not a separate
      adapter project. Deliverables:
      (1) Kalshi market sync → `market_data` partition via `pmxt.Kalshi().fetchMarkets()`.
      (2) Kalshi L2 recording: `pmxt.Kalshi().watchOrderBook()` → same tape format.
      (3) Cross-platform calibration: Kalshi price for same event as external signal.
      (4) Cross-platform arb detector: >3¢ spread adjusted for fees → Signals partition
          at ≥5 historical profitable occurrences.
      (5) Resolution condition parser — port fuzzy matcher from `realfishsam/matcher.js`.
          Block cross-platform positions when question text diverges. March 2025 precedent
          (government shutdown — platforms resolved opposite sides) is the canonical failure.
      Regulatory note: Kalshi is CFTC-regulated (US-legal). Polymarket restricts US access.

- [ ] **Signals ingest pipeline**
      Audit existing storage layer → adapt to `signals` partition → replace ticker resolver
      with Gamma API lookup → add RSS feeds (AP, Reuters, BBC, ESPN, Bloomberg).

- [ ] **RTDS comment stream (from Polymarket/real-time-data-client)**
      Implement Python WebSocket client for Polymarket RTDS comments topic. Pipe comment
      sentiment into signals pipeline as a leading indicator. Reference TypeScript client
      for message format. RTDS crypto prices → feed into crypto pair bot and News Governor
      calendar triggers.

- [ ] **Market linker (signals → Polymarket + Kalshi)**
      Entity extraction → Gamma API market lookup (both platforms) → LLM disambiguation
      for ambiguous matches → confidence score in ClickHouse.

- [ ] **Reaction measurement (price change tracking)**
      Price at t+5min, t+30min, t+2hr post-signal. `price_change_5min`, `price_change_30min`,
      `max_move_30min` in ClickHouse `signal_reactions` table.

- [ ] **Signals partition write (proven patterns only)**
      Pattern graduates ClickHouse → Signals RAG only when same signal type + category
      shows >3% move in ≥10 historical events.

- [ ] **n8n local setup**
      Now that workflows are complex enough to justify visual orchestration,
      replace APScheduler with n8n. Migrate all scheduled jobs. First workflows:
      Market Scanner (2h cron) and Bot Health Check (1min cron).

- [ ] **FastAPI wrapper — first endpoints**
      `/api/candidate-scan`, `/api/wallet-scan`, `/api/llm-bundle`, `/api/llm-save`,
      `/api/simtrader/run`, `/api/market-scan`, `/api/bot/status`, `/api/bot/stream`,
      `/api/strategy/promote`, `/api/strategy/archive`. Thin wrappers only.

- [ ] **Multi-LLM Specialist Routing**
      Four specialist tasks routed to the best free model for each. Sequential loading
      if using Ollama. Research free cloud-hosted models via n8n before committing
      to local-only inference.

---

### PHASE 4 — Autoresearch + SimTrader Validation Automation
> Two goals: (1) automate hypothesis validation; (2) launch parameter-level autoresearch.

- [ ] **strategy-codify (StrategySpec → runnable code)**
      StrategySpec JSON → runnable SimTrader strategy class. Market-making and copy-wallet
      strategies: complete output. Arb and information-advantage: skeleton with hooks.

- [ ] **Historical tape library import (multi-source)**
      Normalize all available sources into standard tape format with source tier tags:
      (1) Silver tapes from Phase 1 reconstructor (pmxt + Jon-Becker + polymarket-apis)
      (2) Bronze tapes from Jon-Becker raw (trade-level, no book state)
      (3) Gold tapes from live Tape Recorder (accumulating from Phase 1)

- [ ] **Auto Level 1 validation (multi-tape replay)**
      New hypothesis registered → run against 20+ diverse tapes using parallel Pool.
      Gate: ≥70% tapes positive PnL after fees. Failed: auto-generate post-mortem stub →
      write to `research` partition → prevents re-testing same dead-end.

- [ ] **Auto Level 2 validation (scenario sweep)**
      If L1 passes: four latency profiles (0ms/100% fills, 150ms/70%/5bps, 500ms/40%,
      1000ms/20%). Gate: profitable at realistic-retail. Low-latency-only strategies noted.

- [ ] **Auto Level 3 — shadow run trigger**
      If L2 passes: automated shadow run on live markets. Gate: shadow PnL within 25%
      of L1 replay prediction. Higher deviation = replay model not capturing live conditions.

- [ ] **Research partition write on gate pass + Discord approval**
      All gates pass → StrategySpec + validation report + shadow record → `research` partition
      → Discord `#polytool-approvals` with [Approve]/[Reject] buttons.

- [ ] **Simulated Adversary in BrokerSim**
      Competing MM module that detects when our quotes are consistently best on one side
      and free-rides our liquidity. Behavior: if our YES bid is best for ≥60 seconds,
      adversary posts a 1-tick better bid and cancels immediately after our fill.
      Surfaces second-order effects before they cost real money at Stage 3 scale.

- [ ] **AUTORESEARCH — Parameter Loop (Phase 4 primary deliverable)**
      Implement the autoresearch engine for numerical parameter tuning.

      **Files:**
      - `autoresearch/engine.py` — main agent loop
      - `autoresearch/proposer.py` — LLM-based config modification proposals
      - `autoresearch/evaluator.py` — 3-confirmation benchmark runner using parallel Pool
      - `autoresearch/ledger.py` — DuckDB experiment ledger writer
      - `config/strategy_research_program.md` — constraint document (human-authored)
      - `config/benchmark_v1.tape_manifest` — fixed tape set

      **Loop (runs overnight, triggered by scheduler at 22:00):**
      ```
      1. Load current best config + strategy_research_program.md
      2. LLM (Tier 1) proposes a config change within stated bounds
      3. Run 3-confirmation benchmark (parallel Pool against benchmark_v1)
      4. If 2/3 confirmations beat old config by ≥5%: KEEP, update current best
      5. Else: REVERT, note the failure in ledger
      6. Write experiment row to DuckDB autoresearch_experiments table
      7. Repeat until EXPERIMENT_HOURS budget exhausted
      ```

      **Discord integration:** Green alert when improvement ≥10% is committed.
      Message format: "Autoresearch committed: +{pct}% median PnL. Delta: {config_diff}"

- [ ] **Docker training image — one-command distributed compute**
      Build `polytool-autoresearch:latest` Docker image. For non-technical friends:
      one command, leave overnight. Results importable via CLI.
      `Dockerfile` and `build_training_image.sh` are concrete deliverables.

---

### PHASE 5 — Advanced Strategies
> Activate after validated strategies are running.

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

- [ ] **Favorite-Longshot Bias Exploitation**
      Jon-Becker calibrated: YES overpriced at extremes. NO buyers at 1¢ markets earn +23%.
      Position sizing: Kelly criterion with Ledoit-Wolf covariance estimation, quarter-Kelly
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

- [ ] **AUTORESEARCH — Code-Level Loop (Phase 6)**
      Upgrade autoresearch from numerical parameter tuning to Python code modification.

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
      strategy file for modification.

- [ ] **Feedback Loop scheduling**
      Weekly cron → strategy review → routes KEEP/REVIEW/AUTO_DISABLE →
      updates external_knowledge validation_status → updates capital allocation plan →
      triggers re-analysis if needed → Discord weekly digest.

---

### PHASE 7 — Unified UI (PolyTool Studio Rebuild)
> Replace Grafana-only workflow with full React application.
> Stack: Next.js + Tremor + TradingView Lightweight Charts v5+
> Only after sustained profit justifies the investment.

- [ ] **Project scaffold and design system**
      `/studio-v2`. Dark theme. Sidebar navigation with all tab names + one-sentence tooltips.

- [ ] **Dashboard tab**
      Tremor KPI cards. All metrics from `/api/bot/status` every 10 seconds. Required:
      bot status + uptime, daily PnL vs target, **cost coverage ratio** (trailing 30d
      revenue vs estimated monthly infra cost, green ≥2×, yellow 1-2×, red <1×),
      open positions, kill switch with CONFIRM modal, active markets, candidate scan last
      run, hypothesis registry summary, scraper stats, signals stats.

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
      hypothesis registry (validation trace on row expand), Flagged Review Queue.

- [ ] **Autoresearch tab**
      Experiment feed, trajectory chart, program.md editor, import button, benchmark manifest.

- [ ] **Signals tab**
      News feed newest-first. Cards: headline, source, timestamp, linked markets with prices,
      LLM confidence, t+5/30/120 reactions. Proven Signals RAG matches get colored border.

- [ ] **Knowledge (RAG) tab**
      Query across all 4 partitions. Results: source, partition, trust tier badge, date,
      relevance, 2-sentence summary. `external_knowledge` results show freshness_tier,
      confidence_tier, and validation_status badges.

- [ ] **Scraper tab**
      Daily log: source URL, title, 0-100 score breakdown, accept/reject. URL submission
      form. Domain override controls. Stats: total indexed, rejected, partition size.

- [ ] **Grafana embed + Pipelines + Settings tabs**
      Settings adds: autoresearch config section, category scoring weights from Jon-Becker
      data, News Governor calendar editor.

- [ ] **Retire old Studio**
      Once v2 stable, retire vanilla HTML/JS Studio at localhost:8765.

---

### PHASE 8 — Scale + Universal Platform
> Activate after 3+ validated strategies and consistent profit.

- [ ] **Platform Abstraction Layer**
      `PlatformAdapter` interface:
      ```
      PlatformAdapter
        ├── PolymarketAdapter (py-clob-client)     ← built first
        ├── KalshiAdapter (pmxt.Kalshi)              ← Phase 3
        ├── PolymarketUSAdapter (exchange API)       ← when US exchange launches
        └── FutureAdapter                             ← extensible
      ```
      Rename project scope to universal prediction market tool.

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

### Crypto Pair Bot Risk Limits (separate from market maker)

| Check | Default | What It Prevents |
|-------|---------|-----------------|
| Max capital per 5-min window | $20 USDC | Overexposure to single settlement |
| Max total open pairs | 10 | Capital lock-up |
| Max daily loss | $25 USDC | Runaway losses |
| Max incomplete pair age | 3 windows | Stale one-sided exposure |

### Kill Switch Hierarchy (five layers)

1. File kill switch — `touch artifacts/simtrader/KILL`
2. Daily loss cap — RiskManager blocks all new orders
3. WS disconnect — `emergency_stop()` → cancel all → backoff
4. Inventory limit — strategy returns `cancel_all`
5. Discord command — `/stop` → `arm_kill_switch()`

### Wallet Security

- Primary capital: cold storage. Never on VPS. Never in `.env`.
- Trading hot wallet: separate wallet, only current stage capital.
- API key: derived via py-clob-client. Trading key ≠ funded address.
- USDC allowance: limited to 2× current stage capital.

### Jurisdiction Strategy

Polymarket restricts US access. Kalshi is CFTC-regulated and US-legal.
**Primary plan:** Bot runs on Canadian dev partner's machine (no restriction).
**Backup plan:** Kalshi adapter via pmxt (Phase 3, but can be accelerated if needed).
**Long-term plan:** Polymarket US Exchange (CFTC-regulated, launching 2026) — 0.01% fees.
Verify jurisdiction requirements before deploying capital on any platform.

---

## Capital Progression

| Stage | Capital | Duration | Success Criterion | Next |
|-------|---------|----------|------------------|------|
| 0: Paper Live | $0 | 72h minimum | Zero errors, positive PnL estimate, kill switch tested | → Stage 1 |
| 1: Micro | $50-500 USDC | Until criterion met | Positive realized PnL. No risk violations. Crypto pair bot can start at $50. | → Stage 2 |
| 2: Small | $5,000 USDC | Until criterion met | Consistent daily positive PnL. All controls proven. | → Stage 3 |
| 3: Scale-1 | $25,000 USDC | Ongoing | $75-250/day. 10+ markets. First Alpha strategy live. | Continue |
| 4: Scale-2 | $100,000 USDC | Ongoing | $300-800/day. Multi-bot. 3+ validated strategies. | Professional LP |

### Capital Allocation Formula (post-profit)

For every dollar of realized profit:
- **50% reinvested** into trading capital (compounds the bot's earning power)
- **30% tax reserve** (prediction market gains are taxable as ordinary income)
- **20% compute/infrastructure** (API costs, VPS, data subscriptions)

These percentages are configurable. Review monthly. Adjust based on actual tax
obligations and infrastructure needs.

### $POLY Airdrop Overlay

All stages include real on-chain activity for potential airdrop qualification.
Even during paper-live testing (Stage 0), execute minimum-size real trades ($1-5)
across diverse market categories to generate on-chain history.

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
  feeds — useful for the crypto pair bot (Phase 1A) and for the News
  Governor high-risk calendar (price threshold triggers).
- The TypeScript client is a reference — implement equivalent Python subscription in
  our signals pipeline using `websockets` library with the same RTDS message format.

**Skip:** For CLOB L2 orderbook data, use `pmxt.watchOrderBook()` — that is the CLOB
WebSocket feed, a completely different connection.

### `gabagool` / CoinsBench analysis

**Pull for Track 2 (Crypto Pair Bot):**
- Asymmetric pair accumulation logic — buy YES cheap when it dips, buy NO cheap when
  it dips, ensure total pair cost < $1.00, guaranteed profit at settlement.
- Pair cost tracking across multiple 5-min/15-min windows.
- Settlement profit calculation and position management.
- Reference the CoinsBench deep-dive analysis for exact entry thresholds and timing.

### `agenttrader` (finnfujimura) — Pending README

**Status:** README not yet received. Placeholder for v5.0 addendum.
When the README is shared, this section will be completed with the same extraction
analysis as the repos above.

---

## Reference Documents

### Internal

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | **Claude Code project context. Updated before every feature cycle.** |
| `docs/CURRENT_STATE.md` | **Primary handoff doc. Paste at start of every LLM session.** |
| `docs/ARCHITECTURE.md` | Component map, data flow, one-line database rule |
| `docs/PLAN_OF_RECORD.md` | Mission, constraints, backtesting kill conditions |
| `docs/OPERATOR_SETUP_GUIDE.md` | Account setup, fund flow, tax tracking, wallet architecture |
| `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md` | Full SimTrader architecture |
| `docs/specs/SPEC-0011-live-execution-layer.md` | Track A execution layer |
| `docs/OPERATOR_QUICKSTART.md` | Step-by-step from zero to shadow |
| `docs/STRATEGY_PLAYBOOK.md` | Outcome taxonomy and EV framework |
| `config/strategy_research_program.md` | Autoresearch constraints |
| `config/benchmark_v1.tape_manifest` | Fixed benchmark tape set |

### Academic Papers

| Reference | Paper |
|-----------|-------|
| Market Making | Avellaneda & Stoikov (2008). QF, 8(3), 217-224 |
| Inventory | Guéant, Lehalle & Fernandez-Tapia (2013). Math. Financial Econ., 7(4) |
| Position Sizing | Kelly, J.L. (1956). Bell System Technical Journal, 35(4) |
| Binary Markets | "Toward Black Scholes for Prediction Markets." arXiv:2510.15205 |
| Adverse Selection | "Optimal Signal Extraction from Order Flow." arXiv:2512.18648v2 |
| PM Microstructure | Becker, J. (2026). 72.1M trades. jbecker.dev |
| PM Efficiency | Reichenbach & Walther (2025). SSRN:5910522 |
| PM Microstructure 2 | Palumbo, N. (2025). "A Microstructure Perspective on Prediction Markets." SSRN:6325658 |
| DePM Survey | "SoK: Market Microstructure for Decentralized Prediction Markets." arXiv:2510.15612 |
| NegRisk Arbitrage | "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets." IMDEA/AFT 2025 |
| Adversarial MM | "Robust Market Making via Adversarial Reinforcement Learning." IJCAI 2020 |
| Autoresearch | Karpathy, A. (2026). github.com/karpathy/autoresearch |

### Key External Tools

| Tool | Role | Phase |
|------|------|-------|
| pmxt (`github.com/pmxt-dev/pmxt`) | Unified PM data API | 1 |
| pmxt Archive (`archive.pmxt.dev`) | Free hourly Parquet L2 snapshots | 1 |
| Jon-Becker Dataset | 72.1M trades, 36GB | 1 |
| polymarket-apis (PyPI) | 2-min price history | 1 |
| DuckDB | Historical Parquet analytics | 1 |
| py-clob-client | CLOB execution (ONLY order path) | 1 |
| lorine93s/poly-market-maker-bot | auto_redeem, cancel/replace, inventory | 1 |
| dylanpersonguy/Trading-Bot | SMI, conviction, OFI, scanner pipeline | 1-2 |
| warproxxx/poly-maker | poly_merger module | 1 |
| realfishsam/arbitrage-bot | Fuzzy matcher, EV formula | 3 |
| Polymarket/real-time-data-client | RTDS comment + crypto stream | 3 |
| polymarketdata.co | 1-min L2 depth (paid, post-profit) | post-profit |
| karpathy/autoresearch | Overnight experiment pattern | 4 |
| Ollama | Local LLM fallback | 2 |
| TradingView Lightweight Charts | Studio probability charts | 7 |
| Tremor | Dashboard UI components | 7 |
| Next.js | Studio frontend framework | 7 |

---

*End of PolyTool Master Roadmap — version 5.1 — March 2026*
*Living document. Update when architecture decisions are made or phases complete.*
*Supersedes v5.0. v5.1 changes: expanded Market Selection Engine (seven-factor composite),*
*Universal Market Discovery (NegRisk + events + sports), RAG reduced from 5→4 partitions*
*(market_data eliminated), artifacts directory standard added, new academic references.*
