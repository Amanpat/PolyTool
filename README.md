# PolyTool — Polymarket Research & Trading Bot

> **What this is:** A complete system for discovering profitable trading
> strategies on Polymarket, validating them in simulation, and deploying a
> live market-making bot. Roadmaps 0–5 are complete. The execution layer
> (Track A) is code-complete. Three gates need closing before live capital.

## Current Status (as of 2026-03-27)

> **Current Status (as of 2026-03-27):** Phase 1A (crypto pair bot) is
> code-complete and awaiting 24-hour paper soak. Phase 1B (market maker
> gate closure) is in active development — Gate 2 sweep tooling is complete,
> Gate 2 verdict pending. See `docs/CURRENT_STATE.md` for full details.

**For an end-to-end operator guide (research loop → RAG → SimTrader → Grafana), see [`docs/OPERATOR_QUICKSTART.md`](docs/OPERATOR_QUICKSTART.md).**

## Historical Quick Status (as of 2026-03-05)

Archive note: this snapshot is retained for milestone history only. Use the
current status block above for operator decisions.

| Component | Status | What it means |
|---|---|---|
| Research pipeline (R0–R5) | ✅ Complete | Data ingestion, PnL, segment analysis, CLV all working |
| SimTrader simulation | ✅ Complete | Record tapes, replay, sweeps, shadow mode all working |
| Market maker strategy (A-S) | ✅ Complete | Avellaneda-Stoikov model deployed |
| Market selection engine | ✅ Complete | `market-scan` CLI scores and ranks live markets |
| CLOB execution wiring | ✅ Complete | `wallet.py` + `--live` flag ready to use |
| Gate 4 (Dry-Run Live) | ✅ PASSED | Confirmed zero-submission dry-run works |
| Gate 1 (Replay) | 🔴 Open | Needs live Polymarket network — run `close_replay_gate.py` |
| Gate 2 (Sweep) | 🔴 Open | Needs live Polymarket network — run `close_sweep_gate.py` |
| Gate 3 (Shadow) | 🟡 90% | Shadow validation still open; complete the manual gate checklist + artifact |
| Stage 0 Paper Live | ⏳ Next | 72h zero-capital paper-live run after all 4 gates pass |
| Stage 1 Live ($500) | ⏳ Blocked | Needs all 4 gates + clean Stage 0 + VPS + Polygon RPC provisioned |

## Part 1 — First-Time Setup

### Step 1.1 — Prerequisites

You need these installed before anything else:

**Python 3.11+**
```bash
# Check your version — must be 3.11 or higher
python --version

# If not installed: https://www.python.org/downloads/
# Windows: download the installer, check "Add to PATH"
# Mac: brew install python@3.11
```

**Docker Desktop** (for ClickHouse database + Grafana dashboards)
```bash
# Download from: https://www.docker.com/products/docker-desktop/
# After install, make sure Docker Desktop is RUNNING before continuing

# Verify:
docker --version
docker compose version
```

**Git**
```bash
git --version
# If not installed: https://git-scm.com/downloads
```

---

### Step 1.2 — Clone the Repo
```bash
git clone https://github.com/Amanpat/PolyTool.git
cd PolyTool
git checkout simtrader
```

Why this branch: `simtrader` is the active development branch with the full
execution layer. Do not use `main` — it is behind.

---

### Step 1.3 — Install Python Dependencies
```bash
# Create a virtual environment (keeps your system Python clean)
python -m venv .venv

# Activate it:
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# You should see (.venv) in your terminal prompt now.
# Install everything:
pip install -e ".[dev]"

# This installs polytool itself plus all research, simulation, and execution
# dependencies. It will take 2-5 minutes the first time.
```

Verify the install worked:
```bash
python -m polytool --help
# Should print a list of commands. If it errors, your venv is not active.
```

---

### Step 1.4 — Install the CLOB Client (for live trading only)
```bash
pip install py-clob-client
# This is the official Polymarket Python SDK.
# Only needed when you're ready for live orders. Safe to install now.
```

---

### Step 1.5 — Copy Config File
```bash
# Windows:
copy polytool.example.yaml polytool.yaml

# Mac/Linux:
cp polytool.example.yaml polytool.yaml
```

Why: `polytool.yaml` is your local config. It is gitignored (your changes never
get committed). The example file has safe defaults. You can edit it later to
tune things like fee rates, entry price tiers, and segment config.

---

### Step 1.6 — Start the Database and Dashboards
```bash
docker compose up -d
```

What this starts:
- **ClickHouse** (port 8123): the analytics database where all trade data lives.
  Every scan, PnL computation, and segment analysis writes here.
- **Grafana** (port 3000): the dashboard UI. Open http://localhost:3000 in your
  browser. Default login: admin / admin.

Wait about 30 seconds after running this before proceeding. Verify they're up:
```bash
docker compose ps
# Both services should show "Up" or "running"
```

---

### Step 1.7 — Bootstrap Private Folders
```bash
# Windows:
powershell -ExecutionPolicy Bypass -File tools\bootstrap_kb.ps1

# Mac/Linux:
bash tools/bootstrap_kb.sh
```

Why: Creates the private `kb/` and `artifacts/` directories that hold your
research data. These are gitignored — your data never leaves your machine.

---

### Step 1.8 — Verify Everything Works
```bash
python -m pytest -q --tb=short
# Should show 1188+ tests passing, 0 failures.
# A few warnings are normal. Failures are not.
```

---

## Part 2 — Research Loop (Track B)

This is how you find profitable wallets, extract strategy patterns, and build a
hypothesis pipeline. Run this first — it feeds the execution bot with real signal.

### Step 2.1 — Create a wallet list

Create a file called `wallets.txt` in the repo root. Add Polymarket handles or
wallet addresses, one per line:
@TopTrader1
@AnotherGoodOne
0xabc123...

Where to find good wallets: Check Polymarket's leaderboard at
https://polymarket.com/leaderboard — copy the handles of top performers.
Start with 10–20. More is better but takes longer.

---

### Step 2.2 — Scan Wallets
```bash
python -m polytool wallet-scan --input wallets.txt --profile lite
```

What this does: Pulls each wallet's full trade history, computes PnL, CLV
(Closing Line Value — did they beat the closing odds?), and resolution outcomes.
Takes 2–5 minutes for 20 wallets.

Output: `artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>/`
- `leaderboard.json` — ranked by net PnL, best wallets first
- `leaderboard.md` — human-readable table of top 20
- `per_user_results.jsonl` — full detail per wallet

---

### Step 2.3 — Distill Edge Patterns
```bash
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>
```

Replace `YYYY-MM-DD/<run_id>` with the actual path from Step 2.2 output.

What this does: Finds patterns that appear across MULTIPLE profitable wallets —
not just one lucky trader. Outputs ranked hypothesis candidates sorted by
cross-wallet persistence (the strongest signal of real edge).

Output: `alpha_candidates.json` in the same run directory.

---

### Step 2.4 — Register a Hypothesis
```bash
python -m polytool hypothesis-register \
  --candidate-file artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>/alpha_candidates.json \
  --rank 1 \
  --registry artifacts/research/hypothesis_registry/registry.jsonl
```

What this does: Takes the #1 ranked candidate and formally registers it in your
hypothesis tracker. Prints a `hypothesis_id` like `hyp_a1b2c3d4`.

Why: Gives you a persistent ID to track this hypothesis through testing,
validation, and deployment. The registry is append-only — nothing is ever deleted.

---

### Step 2.5 — Create an Experiment
```bash
python -m polytool experiment-run \
  --id hyp_<your_id> \
  --registry artifacts/research/hypothesis_registry/registry.jsonl \
  --outdir artifacts/research/experiments/hyp_<your_id>
```

What this does: Creates a structured experiment directory with a JSON skeleton
that links the hypothesis to its source wallet evidence. This is your starting
point for validation work.

---

## Part 3 — Market Scanner

Before running the bot, you need to know WHICH markets to trade. The market
scanner scores all active Polymarket markets and ranks them by profitability
potential.
```bash
python -m polytool market-scan --min-volume 5000 --top 20
```

What this does: Fetches all active markets from Polymarket's API, filters out
ones with low volume, near-resolution price, or no reward program, then scores
each one on: reward APR, spread width, fill rate, competition level, and market
age. New markets (< 48h old) score highest — they have the widest spreads and
fewest competitors.

Output: Prints a ranked table + saves to `artifacts/market_selection/YYYY-MM-DD.json`

What to look for: Markets in the top 5 with:
- `mid_price` between 0.25 and 0.75 (not near resolution)
- `spread_score` > 1.5 (wide enough to be profitable after fees)
- `age_hours` < 48 (bonus points for new markets)

Note the `token_id` of your top pick — you'll need it for the bot commands below.

---

## Part 4 — SimTrader Validation (Gates 1–4)

Before ANY real money goes in, the strategy must pass 4 gates. This is not
optional. Gates prove the strategy works on real market data in simulation
before you risk capital. Stage 0 paper-live is separate and starts only after
all four gates are passed.

**Check current gate status first:**
```bash
python tools/gates/gate_status.py
```

Current status as of 2026-03-07:

1. Gate 1 is PASSED.
2. Gate 2 is not passed yet. The tooling path is implemented and working:
   `scan-gate2-candidates`, `prepare-gate2`, presweep eligibility checks,
   `watch-arb-candidates`, and `--watchlist-file` ingest.
3. Gate 3 remains blocked behind Gate 2.
4. Gate 4 is PASSED.

The recent live watcher run produced no trigger and no new tapes, and the
recent acquisition cycle produced only ineligible tapes. The blocker is
strategy opportunity / edge scarcity, not SimTrader plumbing.

The step-by-step gate notes below are reference. The current next step is a
bounded live dislocation trial for `binary_complement_arb`:

```bash
python -m polytool watch-arb-candidates \
  --watchlist-file artifacts/watchlists/report_watchlist.json \
  --poll-interval 30 \
  --duration 300
```

If you do not have a watchlist file yet, use `--markets slug1,slug2,slug3`.
After the watch window, scan the tapes:

```bash
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all
python -m polytool prepare-gate2 --tapes-dir artifacts/simtrader/tapes
```

Only if an eligible tape appears should you rerun Gate 2:

```bash
python tools/gates/close_sweep_gate.py
```

After Gate 2 passes, complete Gate 3 with
`tools/gates/shadow_gate_checklist.md`. Do not proceed to Part 5 until
`python tools/gates/gate_status.py` shows all four gates as PASSED.

---

### Gate 1 — Replay Determinism (needs internet connection)
```bash
python tools/gates/close_replay_gate.py
```

What this does: Records a short tape of live market data, then replays it twice
with the market maker strategy. Checks that both replays produce identical output
— this proves the strategy is deterministic (no random behavior, reproducible results).

Pass criterion: Both replay summaries match exactly.
Time: ~5 minutes.

---

### Gate 2 — Scenario Sweep (needs internet connection)
```bash
python tools/gates/close_sweep_gate.py
```

What this does: Runs the strategy across a grid of realistic conditions: normal
latency, high latency, partial fills, missed fills, stale book data. Tests that
the strategy stays profitable even when things go wrong.

Pass criterion: ≥ 70% of scenarios show positive net PnL after 2% fees.
Time: ~10 minutes.

---

### Gate 3 — Shadow Mode (needs internet + admin shell for reconnect test)

This is the full shadow validation gate. It is not a multi-week shadow period.
The historical "30-day shadow validation" wording is replaced by Gate 3 shadow
validation, Gate 4 dry-run live, and the separate 72 hour Stage 0 paper-live
run.

This gate has two parts:

**Part A — Run shadow mode (normal terminal, needs internet):**
```bash
# First, find a good market to shadow:
python -m polytool market-scan --top 5

# Then start shadow mode (replace <slug> with the top market slug):
python -m polytool simtrader shadow \
  --market <slug> \
  --strategy market_maker_v0 \
  --duration 300
```

What this does: Connects to the live Polymarket WebSocket, runs the strategy
in real-time, simulates fills — but places ZERO real orders. You see exactly
what the bot would have done. Runs for 5 minutes (300 seconds).

**Part B — Reconnect test (ELEVATED / ADMINISTRATOR terminal required):**

Open a NEW terminal as Administrator (Windows: right-click Terminal → Run as
Administrator). Then:
```powershell
netsh advfirewall firewall add rule name="block_poly" dir=out action=block remoteip=188.0.0.0/8
Start-Sleep -Seconds 10
netsh advfirewall firewall delete rule name="block_poly"
```

What this does: Temporarily blocks the Polymarket connection for 10 seconds,
then restores it. The bot should detect the disconnect, cancel all open (simulated)
orders, wait, then reconnect cleanly. This proves the bot handles network
interruptions safely — critical before going live.

**After both parts complete, write the gate artifact manually:**
```bash
# Create the directory:
mkdir -p artifacts/gates/shadow_gate

# Create the file artifacts/gates/shadow_gate/gate_passed.json with this content:
{
  "gate": "shadow",
  "passed": true,
  "market_slug": "<the slug you used>",
  "duration_seconds": 300,
  "reconnect_tested": true,
  "timestamp": "<current datetime in ISO format e.g. 2026-03-06T10:00:00Z>"
}
```

---

### Gate 4 — Dry-Run Live ✅ (Already Passed)

This gate is already passed. No action needed. Artifact is at:
`artifacts/gates/dry_run_gate/gate_passed.json`

---

### Verify All Gates
```bash
python tools/gates/gate_status.py
# Expected output when ready:
# Gate 1 - Replay Determinism    [PASSED]
# Gate 2 - Scenario Sweep        [PASSED]
# Gate 3 - Shadow Mode           [PASSED]
# Gate 4 - Dry-Run Live          [PASSED]
# Exit code: 0
```

Do NOT proceed to Part 5 until you see all 4 as PASSED.

---

## Part 5 — Stage 0: Paper Live (72 Hours, Zero Capital)

Before real money, run the bot in "paper live" mode for 72 hours. It connects
to real markets, makes real decisions, but submits ZERO orders. You see exactly
what it would have traded. This is Stage 0, not Gate 3.
```bash
# Step 1: Get the best market to trade right now
python -m polytool market-scan --top 5
# Copy the token_id of the #1 ranked market

# Step 2: Run the bot in dry-run (default — no orders ever submitted)
python -m polytool simtrader live \
  --strategy market_maker_v0 \
  --asset-id <TOKEN_ID_FROM_MARKET_SCAN>
```

What to monitor: Open Grafana at http://localhost:3000 — check the SimTrader
panels. Look for:
- Fill rate > 0 (simulated fills happening)
- No risk manager rejections accumulating
- Kill switch NOT triggered
- Strategy showing positive simulated PnL

Run this for 72 hours. If it runs cleanly with no errors and positive simulated
PnL, you are ready for Stage 1.

Emergency stop at any time:
```bash
python -m polytool simtrader kill
# Or: echo 1 > artifacts/kill_switch.txt
```

---

## Part 6 — Infrastructure for Live Trading

These are required BEFORE putting real money in. Do NOT skip.

### 6.1 — VPS (Virtual Private Server)

Why: The bot needs to run 24/7 close to Polymarket's servers for low latency.
Your home internet connection is not reliable enough for live trading.

Recommended: QuantVPS (https://quantvps.com) or Vultr (https://vultr.com)
- Choose a New York or New Jersey datacenter (closest to Polymarket infrastructure)
- 2 CPU / 4GB RAM is sufficient to start
- Cost: ~$30–100/month
- OS: Ubuntu 22.04

After provisioning, deploy the bot there:
```bash
# On your VPS, clone the repo and repeat Steps 1.2–1.8
# Then set your environment variables (see Step 6.3)
```

### 6.2 — Dedicated Polygon RPC Node

Why: The bot reads from the Polygon blockchain to track market resolutions.
Free/public RPC nodes throttle under load and drop connections — unacceptable
for live trading.

Recommended: Chainstack (https://chainstack.com) or Alchemy (https://alchemy.com)
- Create a Polygon mainnet node
- Copy the WSS endpoint URL
- Cost: ~$50–100/month
- Set in your `.env`: `POLYGON_RPC_URL=wss://your-node-url`

### 6.3 — Set Up Credentials

Create a `.env` file in the repo root (it is gitignored — never committed):
```bash
# .env — NEVER commit this file
PK=your_trading_wallet_private_key_no_0x_prefix

# Generate API credentials once (run this command, copy the output into .env):
# python -c "from packages.polymarket.simtrader.execution.wallet import build_client, derive_and_print_creds; derive_and_print_creds(build_client())"
CLOB_API_KEY=paste_output_here
CLOB_API_SECRET=paste_output_here
CLOB_API_PASSPHRASE=paste_output_here

POLYGON_RPC_URL=wss://your-chainstack-or-alchemy-endpoint
```

**SECURITY RULES — NON-NEGOTIABLE:**
- Use a SEPARATE wallet for trading. Never use your main/cold wallet.
- Fund it with ONLY the current stage capital ($500 for Stage 1).
- Never put your private key in any file that might be committed.
- Run `git status` before every commit to check nothing sensitive is staged.

---

## Part 7 — Stage 1: Live Trading ($500 USDC)

Only run this after: all 4 gates PASSED + 72h Stage 0 clean + VPS provisioned
+ Polygon RPC set + `.env` configured + USDC in trading wallet.
```bash
# Load your credentials first:
# Windows: set -a; source .env (or load manually)
# Mac/Linux: export $(cat .env | xargs)

# Run the live bot:
python -m polytool simtrader live \
  --live \
  --strategy market_maker_v0 \
  --asset-id <TOKEN_ID_FROM_MARKET_SCAN> \
  --max-position-usd 500 \
  --daily-loss-cap-usd 100 \
  --max-order-usd 200 \
  --inventory-skew-limit-usd 400
```

What happens:
1. Bot checks all 4 gate artifacts exist — exits if any missing
2. Loads your CLOB credentials from environment
3. Prints a WARNING banner with your risk settings
4. Asks you to type `CONFIRM` to proceed
5. Starts placing real limit orders on Polymarket

**Risk settings explained:**
- `--max-position-usd 500`: Never hold more than $500 of one market
- `--daily-loss-cap-usd 100`: Auto-halt if you lose $100 in one day
- `--max-order-usd 200`: Single order size capped at $200
- `--inventory-skew-limit-usd 400`: Halt if long/short imbalance exceeds $400

**Emergency stop:**
```bash
# From any terminal (works immediately even while bot is running):
python -m polytool simtrader kill

# Or from another terminal:
echo 1 > artifacts/kill_switch.txt
```

**Daily monitoring (5 minutes):**
1. Open Grafana: http://localhost:3000 (or your VPS IP:3000)
2. Check: fill rate, realized PnL, open orders, inventory drift
3. Check: no Telegram alerts fired (see below for Telegram setup)
4. Run market scan to rotate into better markets if needed:
```bash
   python -m polytool market-scan --top 5
```

**Stage 1 success criterion:** Positive realized PnL + rewards after 7 days,
no risk manager violations. If met, scale to Stage 2 ($5,000).

---

## Part 8 — Telegram Alerts (Optional but Recommended)

Get real-time alerts when fills happen, risk limits are approached, or the
kill switch triggers.
```bash
# 1. Create a Telegram bot: message @BotFather on Telegram, send /newbot
# 2. Copy the bot token it gives you
# 3. Add to .env:
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id  # send any message to your bot, then check:
# https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates

# 4. Test alerts work:
python -m polytool simtrader live --test-alerts
```

---

## Part 9 — Alpha Factory (Track B, Run in Parallel)

While the market maker is running, the Alpha Factory discovers better strategies
from profitable wallets. These get validated and deployed on top of the existing
bot infrastructure.
```bash
# 1. Keep your wallets.txt updated with new top performers (weekly)
python -m polytool wallet-scan --input wallets.txt --profile full

# 2. Distill cross-wallet patterns
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>

# 3. Review alpha_candidates.json — look for candidates with:
#    - multi_user_persistence > 0 (appeared in multiple wallets)
#    - fee_adjusted_edge > 0.02 (positive after 2% fee model)
#    - next_test field tells you exactly how to validate it

# 4. Register and track your best hypothesis:
python -m polytool hypothesis-register \
  --candidate-file <path>/alpha_candidates.json \
  --rank 1 \
  --registry artifacts/research/hypothesis_registry/registry.jsonl
```

---

## Common Problems & Fixes

**"python -m polytool" says command not found**
→ Your virtual environment is not active. Run `.venv\Scripts\activate` (Windows)
  or `source .venv/bin/activate` (Mac/Linux) first.

**Docker services not starting**
→ Make sure Docker Desktop is running (look for the whale icon in your system tray).
  Then: `docker compose down && docker compose up -d`

**"PK" environment variable not set**
→ You haven't loaded your `.env` file. Load it before running live commands.

**Gate status shows MISSING after running close_replay_gate.py**
→ You need an active internet connection to Polymarket. Check:
  `curl https://gamma-api.polymarket.com/markets?limit=1`
  If this fails, your network is blocking the connection.

**Kill switch triggered unexpectedly**
→ Check if `artifacts/kill_switch.txt` exists: `cat artifacts/kill_switch.txt`
  To disarm: `python -m polytool simtrader disarm` or delete the file.

**ClickHouse connection refused**
→ Docker is not running. Start Docker Desktop, then `docker compose up -d`

---

## Quick Reference — All Commands
```bash
# Research
python -m polytool wallet-scan --input wallets.txt --profile lite
python -m polytool alpha-distill --wallet-scan-run <path>
python -m polytool market-scan --top 20

# Hypothesis tracking
python -m polytool hypothesis-register --candidate-file <path> --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl
python -m polytool hypothesis-status --id hyp_<id> --status testing --reason "starting validation"
python -m polytool experiment-run --id hyp_<id> --registry artifacts/research/hypothesis_registry/registry.jsonl --outdir artifacts/research/experiments/hyp_<id>

# SimTrader gates
python tools/gates/gate_status.py
python tools/gates/close_replay_gate.py
python tools/gates/close_sweep_gate.py

# SimTrader modes
python -m polytool simtrader shadow --market <slug> --strategy market_maker_v0 --duration 300
python -m polytool simtrader live --strategy market_maker_v0 --asset-id <id>           # dry-run (safe)
python -m polytool simtrader live --live --strategy market_maker_v0 --asset-id <id>    # REAL ORDERS

# Safety
python -m polytool simtrader kill     # arm kill switch — halts all new orders immediately

# Data & RAG
python -m polytool scan --user "@handle"
python -m polytool rag-refresh                                                              # one-command rebuild (alias for rag-index --rebuild)
python -m polytool rag-index                                                                # incremental / advanced rebuild
python -m polytool rag-query --hybrid --rerank --query "what strategies did this wallet use"
```

---

## Where to Go From Here

After Stage 1 is profitable and stable:
- **Scale to Stage 2 ($5,000):** Add 5 more markets from `market-scan`
- **Deploy discovered strategies:** Run `alpha-distill` on 100 wallets, validate top candidates through SimTrader gates, add to the live bot
- **Read the full Construction Manual:** `docs/PolyTool_Master_Construction_Manual.pdf` — contains the complete A-S model math, arb strategy specs, Kelly sizing, and multi-bot architecture for $100K+ scale

---

## Security Reminders

- Never commit `.env`, `polytool.yaml`, `kb/`, or `artifacts/` — all are gitignored
- Use a dedicated trading wallet funded with ONLY the current stage capital
- The kill switch file (`artifacts/kill_switch.txt`) halts all orders immediately if it exists
- Daily loss cap auto-halts the bot — this is a feature, not a bug
- If anything looks wrong: `python -m polytool simtrader kill` first, investigate second

[Continue to full documentation hub →](docs/README.md)

---

# PolyTool

PolyTool is a local-first toolbox for analyzing Polymarket users. You run scans against a target handle, and PolyTool writes trust artifacts and reports to local disk for repeatable, offline review. The code and docs are public; private analysis outputs stay under gitignored `artifacts/` and `kb/`.

## What PolyTool Is

PolyTool combines a local API, ClickHouse, and CLI commands to turn a user handle into structured research artifacts. It can ingest positions/trades, compute PnL and CLV, enrich resolution data, generate hypothesis candidates, and aggregate cross-user hypotheses. The primary entrypoint is:

```bash
python -m polytool <command> [options]
```

## SimTrader (replay-first + shadow simulated trading)

SimTrader is a realism-first simulated trader for Polymarket:
- Record Market Channel WS tapes and replay deterministically
- Run strategies with audited artifacts, sweeps, and batch leaderboards
- Shadow mode runs strategies on live WS data with simulated fills (no real orders)
- Local HTML reports for runs/sweeps/batches: `python -m polytool simtrader report ...`

Start here: `docs/README_SIMTRADER.md`

Quick example:

```powershell
python -m polytool simtrader quickrun --duration 300 --strategy-preset sane
python -m polytool simtrader browse --open
```

---

## SimTrader Studio (UI) — User Guide

SimTrader Studio is a browser dashboard for SimTrader: sessions, tapes, reports, and interactive OnDemand replays in a single-page workspace grid.

### Launch

Local dev:

```bash
pip install polytool[studio]
python -m polytool simtrader studio --open
# Opens http://localhost:8765
```

Docker (binds all interfaces):

```bash
docker compose up --build polytool
# Opens http://localhost:8765
```

Inside a Docker container omit `--open` (no local browser to open).

### Tabs at a glance

| Tab | What it does |
|-----|--------------|
| Dashboard | Command launcher + recent session summary |
| Sessions | List of all running and completed sessions with status |
| Cockpit | Workspace grid: attach sessions, OnDemand replays, or static artifacts to panels |
| Workspaces | Manage saved workspace layouts and panel arrangement |
| Tapes | Browse recorded WS tapes |
| Reports | Browse and open HTML run/sweep/batch reports |
| OnDemand | Create and control interactive tape replay sessions |
| Settings | Export/import workspace layout JSON; clear saved workspaces |

### Start here: three workflows

**Workflow A — Live practice (Shadow to Viewer to Rewind):**

1. Go to Dashboard, click **Shadow** (fill in market slug + duration) to start a live simulation session.
2. Switch to the Sessions tab — the new session appears. Click it to open the Simulation Viewer (equity curve, orders, fills, Reasons tab).
3. When the shadow run ends, go to the OnDemand tab, select the tape that was recorded, and replay it interactively to scrub/seek with different strategy configs.

**Workflow B — OnDemand prop trading (replay and iterate):**

1. Go to the OnDemand tab; select a tape from the list.
2. Click **Start** to create a replay session. Use seek/scrub controls to advance through events.
3. Adjust strategy config (inline JSON or preset) and restart from any position.
4. Artifacts (`run_manifest.json`, `summary.json`, `ledger.jsonl`) are written to `artifacts/simtrader/` on finish.

**Workflow C — Visual bot playback (interpret a simulation run):**

1. Go to Cockpit, open a workspace, and attach it to an existing Session or Artifact.
2. The workspace shows the equity curve chart, orders table, fills table, and the Reasons tab.
3. The Reasons tab lists rejection counters — `no_bbo`, `edge_below_threshold`, `fee_kills_edge`, etc. — explaining why a no-trade run produced no fills.

### Troubleshooting

- **"0 trades" is normal** — check the Reasons tab for the dominant rejection counter (e.g. `edge_below_threshold` means the strategy threshold is stricter than the market spread).
- **No tapes available** — run a shadow session first: Dashboard → Shadow; tapes are written to `artifacts/simtrader/tapes/` by default.
- **WS stall** — the shadow run exits early. Pick a more active market or increase `--max-ws-stalls-seconds` in the shadow config form.
- **Studio won't start** — ensure `pip install polytool[studio]` was run. Port conflicts: pass `--port 9000` or another free port.

### Further reading

| Resource | Purpose |
|----------|---------|
| [docs/README_SIMTRADER.md](docs/README_SIMTRADER.md) | Full CLI operator guide: quickrun, shadow, sweeps, batch, artifact layout |
| [docs/features/FEATURE-simtrader-studio.md](docs/features/FEATURE-simtrader-studio.md) | Studio architecture, API endpoints, workspace types, monitor cards |
| [docs/TODO_SIMTRADER_STUDIO.md](docs/TODO_SIMTRADER_STUDIO.md) | Planned features: Live button, Rewind button, auto-attach, playback speed |

---

## Quickstart

### 1. Prerequisites

- Python 3.10+
- Docker Desktop (or Docker Engine + Compose)
- `git`

### 2. Install

```bash
git clone <your-repo-url>
cd PolyTool
python -m venv .venv
. .venv/Scripts/Activate.ps1
python -m pip install -U pip
python -m pip install -e .
```

### 3. Start local services

```bash
docker compose up -d
docker compose ps
```

Expected local endpoints:

- API docs: `http://localhost:8000/docs`
- ClickHouse HTTP: `http://localhost:8123`
- Grafana: `http://localhost:3000`

### 4. Configure API base URL (optional but recommended on Windows)

Set `.env` in repo root:

```env
API_BASE_URL=http://127.0.0.1:8000
```

You can also pass `--api-base-url` directly to commands.

### 5. Target a user

1. Find the Polymarket handle (for example `@DrPufferfish`).
2. Run a scan with no stage flags:

```bash
python -m polytool scan --user "@DrPufferfish"
```

3. Open the latest run root:

```text
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/
```

4. Open these first:
- `coverage_reconciliation_report.md` (or `.json`)
- `segment_analysis.json`
- `hypothesis_candidates.json`
- `audit_coverage_report.md`

## One-Command Full Scan (Default)

If you pass no stage flags, `scan` runs the full research pipeline by default.

```bash
python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000"
```

Default full scan emits a run manifest plus trust artifacts, including coverage reports, segment analysis, hypothesis candidates, CLV preflight, CLV warm-cache summary, and audit coverage.

## Common Recipes

### Fast/lite scan

```bash
python -m polytool scan --user "@DrPufferfish" --lite
```

`--lite` runs a minimal pipeline: positions + pnl + resolution enrichment + CLV compute.

### Debug export diagnostics

```bash
python -m polytool scan --user "@DrPufferfish" --full --debug-export
```

`--debug-export` prints export/hydration diagnostics to help debug sparse coverage.

### Aggregate-only batch from existing run roots

```bash
python -m polytool batch-run \
  --aggregate-only \
  --run-roots artifacts/research/batch_runs/2026-02-20/<batch_id>/
```

## Command Reference

### `scan`

```bash
python -m polytool scan --user "@handle" [options]
```

Defaulting rules:
- No stage flags: full pipeline auto-enabled.
- Any stage flag present: only explicitly selected stages are used (no auto-enable).
- `--full`: force full pipeline even if stage flags are present.
- `--lite`: force minimal fast pipeline.

Convenience flags:
- `--full`
- `--lite`

Stage flags:
- `--ingest-markets`: ingest active market metadata.
- `--ingest-activity`: ingest user activity.
- `--ingest-positions`: ingest positions snapshot.
- `--compute-pnl`: compute PnL.
- `--compute-opportunities`: compute opportunity candidates.
- `--snapshot-books`: snapshot orderbook metrics.
- `--enrich-resolutions`: enrich resolution data.
- `--warm-clv-cache`: warm CLV snapshot cache.
- `--compute-clv`: compute per-position CLV fields.

Other common flags:
- `--debug-export`
- `--audit-sample N`
- `--audit-seed INT`
- `--resolution-max-candidates N`
- `--resolution-batch-size N`
- `--resolution-max-concurrency N`
- `--clv-offline`
- `--clv-window-minutes MINUTES`
- `--config polytool.yaml`
- `--api-base-url URL`

### `batch-run`

```bash
python -m polytool batch-run --users users.txt [options]
```

Purpose: run scans for multiple users and build deterministic leaderboard artifacts.

Common flags:
- `--users PATH`
- `--workers N`
- `--continue-on-error` / `--no-continue-on-error`
- `--aggregate-only --run-roots PATH`
- Scan pass-through flags: `--api-base-url`, `--full`, `--lite`, `--ingest-positions`, `--compute-pnl`, `--enrich-resolutions`, `--debug-export`, `--warm-clv-cache`, `--compute-clv`

### `audit-coverage`

```bash
python -m polytool audit-coverage --user "@handle" [options]
```

Offline audit from scan artifacts. Key flags: `--sample N`, `--seed SEED`, `--run-id`, `--format {md,json}`.

### `export-dossier`

```bash
python -m polytool export-dossier --user "@handle" [options]
```

Export an LLM research packet dossier. Key flags: `--days`, `--max-trades`, `--artifacts-dir`.

### `export-clickhouse`

```bash
python -m polytool export-clickhouse --user "@handle" [options]
```

Export user datasets from ClickHouse. Key flags: `--out`, `--trades-limit`, `--orderbook-limit`, `--arb-limit`, `--no-arb`.

### `examine`

```bash
python -m polytool examine --user "@handle" [options]
```

Orchestrates examination workflow. Key flags: `--days`, `--max-trades`, `--skip-scan`, `--no-enrich-resolutions`, resolution knobs, `--dry-run`.

### `llm-bundle`

```bash
python -m polytool llm-bundle --user "@handle" [options]
python -m polytool llm-bundle --user "@handle" --run-root artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id> [options]
```

Build evidence bundle from the latest run root under `artifacts/dossiers/users/<normalized_user>/` plus optional RAG excerpts.
Manifest lookup prefers `run_manifest.json` and falls back to legacy `manifest.json`.
Use `--run-root` to bypass automatic latest-run lookup.
Key flags: `--run-root`, `--dossier-path`, `--questions-file`, `--no-devlog`.

### `llm-save`

```bash
python -m polytool llm-save --user "@handle" --model "<model>" [options]
```

Save LLM output to private KB. Key flags: `--run-id`, `--date`, `--report-path`, `--prompt-path`, `--input`, `--rag-query-path`, `--tags`, `--no-devlog`.

### `rag-index`

```bash
python -m polytool rag-index [options]
```

Build/rebuild local RAG index. Key flags: `--roots`, `--rebuild`, `--reconcile`, `--chunk-size`, `--overlap`, `--model`, `--device`.

### `rag-query`

```bash
python -m polytool rag-query --question "..." [options]
```

Query local RAG index. Key flags: `--user`, `--doc-type`, `--private-only/--public-only`, `--hybrid`, `--lexical-only`, `--rerank`.

### `rag-eval`

```bash
python -m polytool rag-eval --suite docs/eval/sample_queries.jsonl [options]
```

Offline retrieval evaluation harness.

### `cache-source`

```bash
python -m polytool cache-source --url "https://..." [options]
```

Fetch/cache trusted web sources for indexing. Key flags: `--ttl-days`, `--force`, `--output-dir`, `--config`, `--skip-robots`.

### `agent-run`

```bash
python -m polytool agent-run --agent codex --packet P5 --slug run-name [options]
```

Write one-file-per-run agent logs to `kb/devlog/`.

### `mcp`

```bash
python -m polytool mcp [--log-level INFO]
```

Start MCP server for local integration.

### Deprecated alias

- `python -m polytool opus-bundle ...` is deprecated and routes to `llm-bundle`.

## Outputs And Trust Artifacts

Run root:

```text
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/
```

| Artifact | Meaning |
|---|---|
| `run_manifest.json` | Provenance: command, argv, config snapshot, output paths |
| `dossier.json` | Exported user dossier payload |
| `coverage_reconciliation_report.json` | Machine-readable trust/coverage report |
| `coverage_reconciliation_report.md` | Human-readable trust/coverage summary |
| `segment_analysis.json` | Segment metrics and breakdowns |
| `hypothesis_candidates.json` | Ranked hypothesis candidate segments |
| `audit_coverage_report.md` | Offline trust sanity report |
| `clv_preflight.json` | CLV preflight checks and missingness reasons |
| `clv_warm_cache_summary.json` | CLV cache warm summary |
| `notional_weight_debug.json` | Notional-weight normalization diagnostics |
| `resolution_parity_debug.json` | Resolution consistency diagnostics |

## Troubleshooting

### `localhost` vs `127.0.0.1` on Windows

If `localhost` resolves to IPv6 and connections fail, use:

```bash
python -m polytool scan --user "@handle" --api-base-url "http://127.0.0.1:8000"
```

### Missing outputs or sparse coverage

1. Re-run with `--debug-export`.
2. Confirm handle -> wallet resolution in `http://localhost:8000/docs` (`/api/resolve`).
3. Check latest run root has `dossier.json` and `run_manifest.json`.
4. Re-run with `--full` to force all major stages.

### CLV gaps

- `clv_preflight.json` explains why CLV is missing.
- Use `--warm-clv-cache` to prefetch snapshot data.
- If network access is restricted, use `--clv-offline` and expect lower coverage.

---

For CLI-level details, run `python -m polytool <command> --help`.

## Validation Pipeline (Canonical)

Use this validation sequence as the operator source of truth:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical note: older planning language may refer to a "30-day shadow
validation." That wording is obsolete. The replacement is Gate 3 shadow
validation, Gate 4 dry-run live, and then a separate 72 hour Stage 0
paper-live run before Stage 1 capital is allowed.
